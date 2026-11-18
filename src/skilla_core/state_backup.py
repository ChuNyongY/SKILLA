from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
from collections.abc import Callable
from contextlib import closing, suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import Field, model_validator

from .file_lock import FileLockTimeout, InterprocessFileLock
from .models import FrozenModel
from .sqlite_state import SqliteStateError, validate_existing_sqlite

STATE_DATABASE_NAMES = (
    "skills.sqlite3",
    "skill-traces.sqlite3",
    "skill-triggers.sqlite3",
    "skill-schedules.sqlite3",
)
RESTORE_CONFIRMATION = "RESTORE_SKILLA_STATE"
_MANIFEST_NAME = "state-backup-manifest.json"
_MAX_MANIFEST_BYTES = 65_536


class StateBackupError(RuntimeError):
    pass


class StateBackupEntry(FrozenModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}\.sqlite3$")
    size_bytes: int = Field(ge=1, le=1_073_741_824)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StateBackupManifest(FrozenModel):
    schema_version: str = Field(pattern=r"^1\.0$")
    created_at: datetime
    entries: tuple[StateBackupEntry, ...] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def exact_database_set(self) -> StateBackupManifest:
        if self.created_at.tzinfo is None:
            raise ValueError("backup timestamp must be timezone-aware")
        if tuple(item.name for item in self.entries) != STATE_DATABASE_NAMES:
            raise ValueError("backup database set is invalid")
        return self


class StateBackupReport(FrozenModel):
    backup_directory: Path
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_count: int = Field(ge=4, le=4)


class StateRestoreReport(FrozenModel):
    state_directory: Path
    rollback_directory: Path
    restored_databases: tuple[str, ...] = Field(min_length=4, max_length=4)


def create_state_backup(
    state_directory: Path,
    destination: Path,
    *,
    now: datetime | None = None,
    hardener: Callable[[Path], None] | None = None,
) -> StateBackupReport:
    source_root = _existing_directory(state_directory, "state directory")
    destination = _new_directory_path(destination, "backup destination")
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        temporary.mkdir()
        entries: list[StateBackupEntry] = []
        for name in STATE_DATABASE_NAMES:
            source = source_root / name
            try:
                validate_existing_sqlite(source)
            except SqliteStateError as error:
                raise StateBackupError(f"state database is unavailable: {name}") from error
            target = temporary / name
            _snapshot_database(source, target)
            if hardener is not None:
                hardener(target)
            entries.append(
                StateBackupEntry(
                    name=name,
                    size_bytes=target.stat().st_size,
                    sha256=_sha256(target),
                )
            )
        instant = now or datetime.now(UTC)
        if instant.tzinfo is None:
            raise ValueError("backup time must be timezone-aware")
        manifest = StateBackupManifest(
            schema_version="1.0",
            created_at=instant.astimezone(UTC),
            entries=tuple(entries),
        )
        manifest_path = temporary / _MANIFEST_NAME
        _write_new_file(manifest_path, manifest.model_dump_json(indent=2).encode("utf-8"))
        if hardener is not None:
            hardener(manifest_path)
        temporary.replace(destination)
        verified = verify_state_backup(destination)
        del verified
        return StateBackupReport(
            backup_directory=destination,
            manifest_sha256=_sha256(destination / _MANIFEST_NAME),
            database_count=len(entries),
        )
    except Exception:
        with suppress(OSError):
            shutil.rmtree(temporary)
        raise


def verify_state_backup(backup_directory: Path) -> StateBackupManifest:
    root = _existing_directory(backup_directory, "backup directory")
    manifest_path = root / _MANIFEST_NAME
    _regular_file(manifest_path, "backup manifest")
    if manifest_path.stat().st_size > _MAX_MANIFEST_BYTES:
        raise StateBackupError("backup manifest exceeded its size limit")
    try:
        manifest = StateBackupManifest.model_validate_json(manifest_path.read_bytes())
    except (OSError, ValueError) as error:
        raise StateBackupError("backup manifest is invalid") from error
    allowed = {_MANIFEST_NAME, *STATE_DATABASE_NAMES}
    try:
        observed = {item.name for item in root.iterdir()}
    except OSError as error:
        raise StateBackupError("backup directory is unavailable") from error
    if observed != allowed:
        raise StateBackupError("backup directory contents are invalid")
    for entry in manifest.entries:
        path = root / entry.name
        _regular_file(path, "backup database")
        if path.stat().st_size != entry.size_bytes or _sha256(path) != entry.sha256:
            raise StateBackupError("backup database identity mismatch")
        try:
            validate_existing_sqlite(path)
        except SqliteStateError as error:
            raise StateBackupError("backup database integrity check failed") from error
    return manifest


def restore_state_backup(
    backup_directory: Path,
    state_directory: Path,
    *,
    confirmation: str,
    now: datetime | None = None,
    hardener: Callable[[Path], None] | None = None,
    replace: Callable[[Path, Path], None] = os.replace,
) -> StateRestoreReport:
    if confirmation != RESTORE_CONFIRMATION:
        raise StateBackupError("explicit restore confirmation is required")
    manifest = verify_state_backup(backup_directory)
    backup_root = backup_directory.resolve(strict=True)
    state_root = _existing_directory(state_directory, "state directory")
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("restore time must be timezone-aware")
    rollback_root = state_root / "restore-rollbacks"
    if rollback_root.is_symlink():
        raise StateBackupError("restore rollback root is invalid")
    rollback_root.mkdir(exist_ok=True)
    rollback = rollback_root / (
        instant.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid4().hex[:8]}"
    )
    rollback.mkdir()
    staged: dict[str, Path] = {}
    original_names: set[str] = set()
    replaced: list[str] = []
    lock = state_root / ".state-restore.lock"
    try:
        with InterprocessFileLock(lock, timeout_seconds=5.0, hardener=hardener):
            for entry in manifest.entries:
                current = state_root / entry.name
                if current.exists() or current.is_symlink():
                    _regular_file(current, "current state database")
                    try:
                        validate_existing_sqlite(current)
                    except SqliteStateError as error:
                        raise StateBackupError("current state database is invalid") from error
                    rollback_file = rollback / entry.name
                    _snapshot_database(current, rollback_file)
                    original_names.add(entry.name)
                    if hardener is not None:
                        hardener(rollback_file)
                staged_file = state_root / f".{entry.name}.{uuid4().hex}.restore.tmp"
                _snapshot_database(backup_root / entry.name, staged_file)
                if hardener is not None:
                    hardener(staged_file)
                staged[entry.name] = staged_file
            for entry in manifest.entries:
                replace(staged[entry.name], state_root / entry.name)
                replaced.append(entry.name)
            if hardener is not None:
                for name in replaced:
                    hardener(state_root / name)
    except (FileLockTimeout, OSError, sqlite3.Error, StateBackupError) as error:
        _rollback_restore(
            state_root,
            rollback,
            original_names=original_names,
            replaced=replaced,
        )
        raise StateBackupError("state restore failed; previous files were retained") from error
    finally:
        for path in staged.values():
            with suppress(OSError):
                path.unlink(missing_ok=True)
    return StateRestoreReport(
        state_directory=state_root,
        rollback_directory=rollback,
        restored_databases=STATE_DATABASE_NAMES,
    )


def _rollback_restore(
    state_root: Path,
    rollback: Path,
    *,
    original_names: set[str],
    replaced: list[str],
) -> None:
    for name in reversed(replaced):
        target = state_root / name
        if name in original_names:
            rollback_file = rollback / name
            temporary = state_root / f".{name}.{uuid4().hex}.rollback.tmp"
            try:
                _snapshot_database(rollback_file, temporary)
                os.replace(temporary, target)
            finally:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)
        else:
            with suppress(OSError):
                target.unlink(missing_ok=True)


def _snapshot_database(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise StateBackupError("snapshot destination already exists")
    try:
        uri = f"{source.resolve(strict=True).as_uri()}?mode=ro"
        with (
            closing(sqlite3.connect(uri, uri=True, timeout=5.0)) as source_database,
            closing(sqlite3.connect(destination, timeout=5.0)) as target_database,
        ):
            source_database.backup(target_database)
            target_database.commit()
            journal_mode = target_database.execute(
                "PRAGMA journal_mode=DELETE"
            ).fetchone()
            if journal_mode is None or str(journal_mode[0]).casefold() != "delete":
                raise StateBackupError("SQLite snapshot journal cleanup failed")
        validate_existing_sqlite(destination)
        with destination.open("r+b") as stream:
            os.fsync(stream.fileno())
    except (OSError, sqlite3.Error, SqliteStateError, StateBackupError) as error:
        with suppress(OSError):
            destination.unlink(missing_ok=True)
        raise StateBackupError("SQLite snapshot failed") from error


def _existing_directory(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise StateBackupError(f"{label} is invalid")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise StateBackupError(f"{label} is unavailable") from error
    if not resolved.is_dir() or resolved.is_symlink():
        raise StateBackupError(f"{label} is invalid")
    return resolved


def _new_directory_path(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.exists() or path.is_symlink():
        raise StateBackupError(f"{label} is invalid")
    parent = _existing_directory(path.parent, f"{label} parent")
    return parent / path.name


def _regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise StateBackupError(f"{label} is invalid")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise StateBackupError("backup file is unavailable") from error
    return digest.hexdigest()


def _write_new_file(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb", buffering=0) as stream:
            stream.write(payload)
            os.fsync(stream.fileno())
    except OSError as error:
        raise StateBackupError("backup manifest write failed") from error
