from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from pydantic import Field, StrictBool, model_validator

from .models import FrozenModel
from .skill_runtime import LocalSkillCatalog, SkillRecord, SkillRuntimeError, SkillStatus
from .sqlite_state import (
    SqliteStateError,
    connect_sqlite_state,
    enable_sqlite_wal,
    validate_existing_sqlite,
)
from .windows_acl import WindowsUserOnlyAcl

_APP_ID = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")


class SkillTriggerError(RuntimeError):
    pass


class SkillTriggerRule(FrozenModel):
    rule_id: UUID
    app_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,63}$")
    skill_id: UUID
    skill_version: int = Field(ge=1)
    enabled: StrictBool
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def timestamps_are_utc(self) -> SkillTriggerRule:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("trigger timestamps must be timezone-aware")
        return self


class SkillTriggerSuggestion(FrozenModel):
    suggestion_id: UUID
    rule_id: UUID
    app_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,63}$")
    skill_id: UUID
    skill_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)


class LocalSkillTriggerRepository:
    """Persist exact app-to-skill bindings; rules can only suggest work."""

    def __init__(
        self,
        path: Path,
        *,
        registered_app_ids: Iterable[str],
        skill_catalog: LocalSkillCatalog,
        max_rows: int = 1_000,
        max_bytes: int = 1_048_576,
        acl: WindowsUserOnlyAcl | None = None,
    ) -> None:
        app_ids = frozenset(registered_app_ids)
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.parent.is_dir()
            or not app_ids
            or any(_APP_ID.fullmatch(item) is None for item in app_ids)
            or type(max_rows) is not int
            or not 1 <= max_rows <= 10_000
            or type(max_bytes) is not int
            or max_bytes < 16_384
        ):
            raise ValueError("invalid skill trigger repository configuration")
        if path.exists() and (not path.is_file() or path.stat().st_size > max_bytes):
            raise ValueError("invalid skill trigger database")
        self._path = path
        self._app_ids = app_ids
        self._skills = skill_catalog
        self._max_rows = max_rows
        self._max_bytes = max_bytes
        self._acl = acl if acl is not None else (
            WindowsUserOnlyAcl() if os.name == "nt" else None
        )
        try:
            validate_existing_sqlite(path, max_bytes=max_bytes)
            self._initialize()
        except (OSError, sqlite3.Error, SqliteStateError) as error:
            raise SkillTriggerError("skill trigger database is unavailable") from error

    @property
    def registered_app_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._app_ids))

    def bind(
        self,
        app_id: str,
        skill_id: UUID,
        *,
        now: datetime | None = None,
    ) -> SkillTriggerRule:
        if app_id not in self._app_ids:
            raise SkillTriggerError("trigger app is not registered")
        skill = self._verified_skill(skill_id)
        instant = _utc(now)
        with closing(self._connect()) as database, database:
            if database.execute(
                "SELECT 1 FROM trigger_rules WHERE app_id=?", (app_id,)
            ).fetchone() is not None:
                raise SkillTriggerError("trigger app already has a rule")
            count = int(database.execute("SELECT COUNT(*) FROM trigger_rules").fetchone()[0])
            if count >= self._max_rows:
                raise SkillTriggerError("skill trigger repository is full")
            rule = SkillTriggerRule(
                rule_id=uuid4(),
                app_id=app_id,
                skill_id=skill.skill_id,
                skill_version=skill.version,
                enabled=True,
                created_at=instant,
                updated_at=instant,
            )
            database.execute(
                "INSERT INTO trigger_rules VALUES (?,?,?,?,?,?,?)",
                (
                    str(rule.rule_id),
                    rule.app_id,
                    str(rule.skill_id),
                    rule.skill_version,
                    1,
                    rule.created_at.isoformat(),
                    rule.updated_at.isoformat(),
                ),
            )
        self._check_size()
        return rule

    def set_enabled(
        self,
        rule_id: UUID,
        enabled: bool,
        *,
        now: datetime | None = None,
    ) -> SkillTriggerRule:
        if type(enabled) is not bool:
            raise ValueError("enabled must be boolean")
        instant = _utc(now)
        with closing(self._connect()) as database, database:
            cursor = database.execute(
                "UPDATE trigger_rules SET enabled=?, updated_at=? WHERE rule_id=?",
                (1 if enabled else 0, instant.isoformat(), str(rule_id)),
            )
        if cursor.rowcount != 1:
            raise SkillTriggerError("skill trigger rule not found")
        return self.require(rule_id)

    def delete(self, rule_id: UUID) -> bool:
        with closing(self._connect()) as database, database:
            cursor = database.execute(
                "DELETE FROM trigger_rules WHERE rule_id=?", (str(rule_id),)
            )
        return cursor.rowcount == 1

    def require(self, rule_id: UUID) -> SkillTriggerRule:
        with closing(self._connect()) as database:
            row = database.execute(
                "SELECT * FROM trigger_rules WHERE rule_id=?", (str(rule_id),)
            ).fetchone()
        if row is None:
            raise SkillTriggerError("skill trigger rule not found")
        return _rule(row)

    def match(self, app_id: str) -> SkillTriggerRule | None:
        if app_id not in self._app_ids:
            return None
        with closing(self._connect()) as database:
            row = database.execute(
                "SELECT * FROM trigger_rules WHERE app_id=? AND enabled=1", (app_id,)
            ).fetchone()
        return None if row is None else _rule(row)

    def list(self, *, limit: int = 100) -> tuple[SkillTriggerRule, ...]:
        if type(limit) is not int or not 1 <= limit <= 1_000:
            raise ValueError("trigger list limit must be within 1..1000")
        with closing(self._connect()) as database:
            rows = database.execute(
                "SELECT * FROM trigger_rules ORDER BY updated_at DESC, app_id LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(_rule(row) for row in rows)

    def resolve_current_skill(self, rule: SkillTriggerRule) -> SkillRecord:
        stored = self.require(rule.rule_id)
        if stored != rule or not stored.enabled:
            raise SkillTriggerError("skill trigger binding changed")
        skill = self._verified_skill(stored.skill_id)
        if skill.version != stored.skill_version:
            raise SkillTriggerError("skill trigger version is stale")
        return skill

    def _verified_skill(self, skill_id: UUID) -> SkillRecord:
        try:
            skill = self._skills.require(skill_id)
        except SkillRuntimeError as error:
            raise SkillTriggerError("trigger skill is unavailable") from error
        if skill.status is not SkillStatus.VERIFIED:
            raise SkillTriggerError("trigger skill is not verified")
        return skill

    def _initialize(self) -> None:
        with closing(self._connect()) as database, database:
            enable_sqlite_wal(database)
            database.executescript(
                """
                PRAGMA user_version=1;
                CREATE TABLE IF NOT EXISTS trigger_rules(
                    rule_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL UNIQUE,
                    skill_id TEXT NOT NULL,
                    skill_version INTEGER NOT NULL CHECK(skill_version >= 1),
                    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
        if self._acl is not None:
            self._acl.harden(self._path)
        self._check_size()

    def _connect(self) -> sqlite3.Connection:
        database = connect_sqlite_state(self._path, timeout_seconds=2.0)
        database.row_factory = sqlite3.Row
        return database

    def _check_size(self) -> None:
        if self._path.stat().st_size > self._max_bytes:
            raise SkillTriggerError("skill trigger database exceeded its size limit")


class SkillTriggerSuggestionEngine:
    """Emit one suggestion on a verified app transition; never execute a skill."""

    def __init__(
        self,
        repository: LocalSkillTriggerRepository,
    ) -> None:
        self._repository = repository
        self._lock = Lock()
        self._last_app_id: str | None = None

    def observe(self, verified_app_id: str | None) -> SkillTriggerSuggestion | None:
        if verified_app_id is not None and _APP_ID.fullmatch(verified_app_id) is None:
            raise ValueError("invalid verified app ID")
        with self._lock:
            if verified_app_id == self._last_app_id:
                return None
            self._last_app_id = verified_app_id
        if verified_app_id is None:
            return None
        rule = self._repository.match(verified_app_id)
        if rule is None:
            return None
        try:
            skill = self._repository.resolve_current_skill(rule)
        except SkillTriggerError:
            return None
        return SkillTriggerSuggestion(
            suggestion_id=uuid4(),
            rule_id=rule.rule_id,
            app_id=rule.app_id,
            skill_id=skill.skill_id,
            skill_version=skill.version,
            title=skill.title,
        )

    def resolve(self, suggestion: SkillTriggerSuggestion) -> SkillRecord:
        rule = self._repository.require(suggestion.rule_id)
        if (
            not rule.enabled
            or suggestion.app_id != rule.app_id
            or suggestion.skill_id != rule.skill_id
            or suggestion.skill_version != rule.skill_version
        ):
            raise SkillTriggerError("skill trigger suggestion is no longer valid")
        skill = self._repository.resolve_current_skill(rule)
        if skill.title != suggestion.title:
            raise SkillTriggerError("skill trigger suggestion title changed")
        return skill


def _rule(row: sqlite3.Row) -> SkillTriggerRule:
    return SkillTriggerRule(
        rule_id=UUID(row["rule_id"]),
        app_id=row["app_id"],
        skill_id=UUID(row["skill_id"]),
        skill_version=row["skill_version"],
        enabled=bool(row["enabled"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _utc(value: datetime | None) -> datetime:
    instant = value or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("trigger time must be timezone-aware")
    return instant.astimezone(UTC)
