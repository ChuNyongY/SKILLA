from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from skilla_core.registry import default_registry
from skilla_core.skill_runtime import LocalSkillCatalog, SkillRuntimeError
from skilla_core.skill_schedules import (
    LocalSkillScheduleRepository,
    SkillScheduleError,
)
from skilla_core.skill_trace_store import LocalSkillTraceStore, SkillTraceStoreError
from skilla_core.skill_triggers import LocalSkillTriggerRepository, SkillTriggerError
from skilla_core.sqlite_state import (
    SqliteStateError,
    connect_sqlite_state,
    enable_sqlite_wal,
    validate_existing_sqlite,
)


def test_sqlite_state_uses_wal_full_sync_and_passes_integrity_check(
    tmp_path: Path,
) -> None:
    path = (tmp_path / "state.sqlite3").resolve()

    with connect_sqlite_state(path) as database:
        enable_sqlite_wal(database)
        database.execute("CREATE TABLE sample(value TEXT NOT NULL)")
        database.execute("INSERT INTO sample VALUES ('ok')")
        assert database.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert database.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert database.execute("PRAGMA busy_timeout").fetchone()[0] == 5_000

    validate_existing_sqlite(path)
    with sqlite3.connect(path) as database:
        assert database.execute("SELECT value FROM sample").fetchone()[0] == "ok"


def test_sqlite_state_rejects_corruption_and_size_overflow(tmp_path: Path) -> None:
    corrupt = (tmp_path / "corrupt.sqlite3").resolve()
    corrupt.write_bytes(b"not-a-sqlite-database")

    with pytest.raises(SqliteStateError, match="integrity"):
        validate_existing_sqlite(corrupt)
    with pytest.raises(SqliteStateError, match="size limit"):
        validate_existing_sqlite(corrupt, max_bytes=4)


def test_skill_catalog_rejects_corrupt_database_with_stable_error(tmp_path: Path) -> None:
    path = (tmp_path / "skills.sqlite3").resolve()
    path.write_bytes(b"broken")

    with pytest.raises(SkillRuntimeError, match="database is unavailable"):
        LocalSkillCatalog(path, default_registry())


def test_skill_trace_store_rejects_corrupt_database_with_stable_error(
    tmp_path: Path,
) -> None:
    path = (tmp_path / "skill-traces.sqlite3").resolve()
    path.write_bytes(b"broken")

    with pytest.raises(SkillTraceStoreError, match="database is unavailable"):
        LocalSkillTraceStore(path)


def test_trigger_and_schedule_repositories_reject_corrupt_databases(
    tmp_path: Path,
) -> None:
    catalog = LocalSkillCatalog(
        (tmp_path / "skills.sqlite3").resolve(),
        default_registry(),
    )
    trigger_path = (tmp_path / "skill-triggers.sqlite3").resolve()
    schedule_path = (tmp_path / "skill-schedules.sqlite3").resolve()
    trigger_path.write_bytes(b"broken")
    schedule_path.write_bytes(b"broken")

    with pytest.raises(SkillTriggerError, match="database is unavailable"):
        LocalSkillTriggerRepository(
            trigger_path,
            registered_app_ids=("notepad",),
            skill_catalog=catalog,
            acl=None,
        )
    with pytest.raises(SkillScheduleError, match="database is unavailable"):
        LocalSkillScheduleRepository(
            schedule_path,
            skill_catalog=catalog,
            acl=None,
        )
