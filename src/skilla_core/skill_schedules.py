from __future__ import annotations

import json
import math
import os
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime
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


class SkillScheduleError(RuntimeError):
    pass


class SkillScheduleRule(FrozenModel):
    rule_id: UUID
    skill_id: UUID
    skill_version: int = Field(ge=1)
    local_minute: int = Field(ge=0, le=1_439)
    weekdays: tuple[int, ...] = Field(min_length=1, max_length=7)
    enabled: StrictBool
    last_suggested_key: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[+-]\d{4}$",
    )
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_rule(self) -> SkillScheduleRule:
        if (
            tuple(sorted(set(self.weekdays))) != self.weekdays
            or any(day < 0 or day > 6 for day in self.weekdays)
            or self.created_at.tzinfo is None
            or self.updated_at.tzinfo is None
        ):
            raise ValueError("invalid skill schedule rule")
        return self


class ScheduledSkillSuggestion(FrozenModel):
    suggestion_id: UUID
    rule_id: UUID
    skill_id: UUID
    skill_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=120)
    due_key: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[+-]\d{4}$")


class LocalSkillScheduleRepository:
    """Persist local-time skill schedules that can only create user suggestions."""

    def __init__(
        self,
        path: Path,
        *,
        skill_catalog: LocalSkillCatalog,
        max_rows: int = 1_000,
        max_bytes: int = 1_048_576,
        acl: WindowsUserOnlyAcl | None = None,
    ) -> None:
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.parent.is_dir()
            or type(max_rows) is not int
            or not 1 <= max_rows <= 10_000
            or type(max_bytes) is not int
            or max_bytes < 16_384
        ):
            raise ValueError("invalid skill schedule repository configuration")
        if path.exists() and (not path.is_file() or path.stat().st_size > max_bytes):
            raise ValueError("invalid skill schedule database")
        self._path = path
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
            raise SkillScheduleError("skill schedule database is unavailable") from error

    def create(
        self,
        skill_id: UUID,
        *,
        hour: int,
        minute: int,
        weekdays: Iterable[int],
        now: datetime,
    ) -> SkillScheduleRule:
        if (
            type(hour) is not int
            or type(minute) is not int
            or not 0 <= hour <= 23
            or not 0 <= minute <= 59
        ):
            raise ValueError("invalid schedule time")
        selected_days = _weekdays(weekdays)
        instant = _aware(now)
        skill = self._verified_skill(skill_id)
        with closing(self._connect()) as database, database:
            count = int(database.execute("SELECT COUNT(*) FROM schedule_rules").fetchone()[0])
            if count >= self._max_rows:
                raise SkillScheduleError("skill schedule repository is full")
            rule = SkillScheduleRule(
                rule_id=uuid4(),
                skill_id=skill.skill_id,
                skill_version=skill.version,
                local_minute=hour * 60 + minute,
                weekdays=selected_days,
                enabled=True,
                created_at=instant,
                updated_at=instant,
            )
            database.execute(
                "INSERT INTO schedule_rules VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(rule.rule_id),
                    str(rule.skill_id),
                    rule.skill_version,
                    rule.local_minute,
                    json.dumps(rule.weekdays),
                    1,
                    None,
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
        now: datetime,
    ) -> SkillScheduleRule:
        if type(enabled) is not bool:
            raise ValueError("enabled must be boolean")
        instant = _aware(now)
        with closing(self._connect()) as database, database:
            cursor = database.execute(
                "UPDATE schedule_rules SET enabled=?, updated_at=? WHERE rule_id=?",
                (1 if enabled else 0, instant.isoformat(), str(rule_id)),
            )
        if cursor.rowcount != 1:
            raise SkillScheduleError("skill schedule rule not found")
        return self.require(rule_id)

    def delete(self, rule_id: UUID) -> bool:
        with closing(self._connect()) as database, database:
            cursor = database.execute(
                "DELETE FROM schedule_rules WHERE rule_id=?", (str(rule_id),)
            )
        return cursor.rowcount == 1

    def require(self, rule_id: UUID) -> SkillScheduleRule:
        with closing(self._connect()) as database:
            row = database.execute(
                "SELECT * FROM schedule_rules WHERE rule_id=?", (str(rule_id),)
            ).fetchone()
        if row is None:
            raise SkillScheduleError("skill schedule rule not found")
        return _rule(row)

    def list(self, *, limit: int = 100) -> tuple[SkillScheduleRule, ...]:
        if type(limit) is not int or not 1 <= limit <= 1_000:
            raise ValueError("schedule list limit must be within 1..1000")
        with closing(self._connect()) as database:
            rows = database.execute(
                "SELECT * FROM schedule_rules ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(_rule(row) for row in rows)

    def due(self, now: datetime) -> tuple[tuple[SkillScheduleRule, str], ...]:
        instant = _aware(now)
        minute = instant.hour * 60 + instant.minute
        due_key = instant.strftime("%Y-%m-%dT%H:%M%z")
        with closing(self._connect()) as database:
            rows = database.execute(
                "SELECT * FROM schedule_rules WHERE enabled=1 AND local_minute=?",
                (minute,),
            ).fetchall()
        rules = tuple(_rule(row) for row in rows)
        return tuple(
            (rule, due_key)
            for rule in rules
            if instant.weekday() in rule.weekdays and rule.last_suggested_key != due_key
        )

    def mark_suggested(
        self,
        rule: SkillScheduleRule,
        due_key: str,
        *,
        now: datetime,
    ) -> bool:
        instant = _aware(now)
        with closing(self._connect()) as database, database:
            cursor = database.execute(
                """
                UPDATE schedule_rules
                SET last_suggested_key=?, updated_at=?
                WHERE rule_id=? AND enabled=1 AND skill_id=? AND skill_version=?
                  AND (last_suggested_key IS NULL OR last_suggested_key<>?)
                """,
                (
                    due_key,
                    instant.isoformat(),
                    str(rule.rule_id),
                    str(rule.skill_id),
                    rule.skill_version,
                    due_key,
                ),
            )
        return cursor.rowcount == 1

    def resolve_current_skill(self, rule: SkillScheduleRule) -> SkillRecord:
        stored = self.require(rule.rule_id)
        if stored != rule or not stored.enabled:
            raise SkillScheduleError("skill schedule binding changed")
        skill = self._verified_skill(stored.skill_id)
        if skill.version != stored.skill_version:
            raise SkillScheduleError("skill schedule version is stale")
        return skill

    def _verified_skill(self, skill_id: UUID) -> SkillRecord:
        try:
            skill = self._skills.require(skill_id)
        except SkillRuntimeError as error:
            raise SkillScheduleError("scheduled skill is unavailable") from error
        if skill.status is not SkillStatus.VERIFIED:
            raise SkillScheduleError("scheduled skill is not verified")
        return skill

    def _initialize(self) -> None:
        with closing(self._connect()) as database, database:
            enable_sqlite_wal(database)
            database.executescript(
                """
                PRAGMA user_version=1;
                CREATE TABLE IF NOT EXISTS schedule_rules(
                    rule_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    skill_version INTEGER NOT NULL CHECK(skill_version >= 1),
                    local_minute INTEGER NOT NULL CHECK(local_minute BETWEEN 0 AND 1439),
                    weekdays_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
                    last_suggested_key TEXT,
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
            raise SkillScheduleError("skill schedule database exceeded its size limit")


class SkillScheduleSuggestionEngine:
    """Create bounded due-time suggestions; never execute a skill."""

    def __init__(self, repository: LocalSkillScheduleRepository) -> None:
        self._repository = repository
        self._lock = Lock()

    def observe(self, now: datetime) -> tuple[ScheduledSkillSuggestion, ...]:
        suggestions: list[ScheduledSkillSuggestion] = []
        with self._lock:
            for rule, due_key in self._repository.due(now):
                try:
                    skill = self._repository.resolve_current_skill(rule)
                except SkillScheduleError:
                    continue
                if not self._repository.mark_suggested(rule, due_key, now=now):
                    continue
                suggestions.append(
                    ScheduledSkillSuggestion(
                        suggestion_id=uuid4(),
                        rule_id=rule.rule_id,
                        skill_id=skill.skill_id,
                        skill_version=skill.version,
                        title=skill.title,
                        due_key=due_key,
                    )
                )
        return tuple(suggestions)

    def resolve(self, suggestion: ScheduledSkillSuggestion) -> SkillRecord:
        rule = self._repository.require(suggestion.rule_id)
        if (
            not rule.enabled
            or suggestion.skill_id != rule.skill_id
            or suggestion.skill_version != rule.skill_version
            or suggestion.due_key != rule.last_suggested_key
        ):
            raise SkillScheduleError("scheduled skill suggestion is no longer valid")
        skill = self._repository.resolve_current_skill(rule)
        if skill.title != suggestion.title:
            raise SkillScheduleError("scheduled skill suggestion title changed")
        return skill


def _rule(row: sqlite3.Row) -> SkillScheduleRule:
    weekdays = _weekdays(json.loads(row["weekdays_json"]))
    return SkillScheduleRule(
        rule_id=UUID(row["rule_id"]),
        skill_id=UUID(row["skill_id"]),
        skill_version=row["skill_version"],
        local_minute=row["local_minute"],
        weekdays=weekdays,
        enabled=bool(row["enabled"]),
        last_suggested_key=row["last_suggested_key"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _weekdays(values: Iterable[int]) -> tuple[int, ...]:
    try:
        days = tuple(sorted(set(values)))
    except TypeError as error:
        raise ValueError("invalid schedule weekdays") from error
    if not days or any(type(day) is not int or not 0 <= day <= 6 for day in days):
        raise ValueError("invalid schedule weekdays")
    return days


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("schedule time must be timezone-aware")
    offset = value.utcoffset()
    if offset is None or not math.isfinite(offset.total_seconds()):
        raise ValueError("schedule time must have a finite UTC offset")
    return value
