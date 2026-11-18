from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest

from skilla_core.sqlite_state import (
    connect_sqlite_state,
    enable_sqlite_wal,
    validate_existing_sqlite,
)
from skilla_core.state_backup import (
    STATE_DATABASE_NAMES,
    create_state_backup,
    verify_state_backup,
)

_CRASH_WRITER = r"""
import sqlite3
import sys
import time
from pathlib import Path

database_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
database = sqlite3.connect(database_path, timeout=5.0)
database.execute("PRAGMA synchronous=FULL")
mode = database.execute("PRAGMA journal_mode").fetchone()
if mode is None or str(mode[0]).casefold() != "wal":
    raise RuntimeError("WAL mode is unavailable")
database.execute("INSERT INTO crash_probe(value) VALUES ('committed')")
database.commit()
database.execute("BEGIN IMMEDIATE")
database.execute("INSERT INTO crash_probe(value) VALUES ('uncommitted')")
ready_path.write_text("dirty transaction ready", encoding="utf-8")
while True:
    time.sleep(1.0)
"""


def _initialize_database(path: Path) -> None:
    with closing(connect_sqlite_state(path)) as database:
        enable_sqlite_wal(database)
        database.execute("CREATE TABLE crash_probe(value TEXT NOT NULL)")
        database.commit()


def _kill_during_dirty_transaction(path: Path, ready: Path) -> None:
    process = subprocess.Popen(
        (sys.executable, "-c", _CRASH_WRITER, str(path), str(ready)),
        cwd=Path.cwd(),
    )
    try:
        deadline = time.monotonic() + 10.0
        while not ready.is_file():
            if process.poll() is not None:
                raise AssertionError("crash writer exited before reaching the dirty state")
            if time.monotonic() >= deadline:
                raise AssertionError("crash writer did not reach the dirty state")
            time.sleep(0.02)
        process.kill()
        process.wait(timeout=5.0)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)


def _values(path: Path) -> tuple[str, ...]:
    validate_existing_sqlite(path)
    with closing(connect_sqlite_state(path)) as database:
        quick_check = database.execute("PRAGMA quick_check(1)").fetchone()
        journal_mode = database.execute("PRAGMA journal_mode").fetchone()
        values = tuple(
            str(row[0])
            for row in database.execute(
                "SELECT value FROM crash_probe ORDER BY rowid"
            ).fetchall()
        )
    assert quick_check == ("ok",)
    assert journal_mode is not None and str(journal_mode[0]).casefold() == "wal"
    return values


@pytest.mark.parametrize("database_name", STATE_DATABASE_NAMES)
def test_committed_wal_survives_forced_process_termination(
    tmp_path: Path,
    database_name: str,
) -> None:
    database = tmp_path / database_name
    _initialize_database(database)
    _kill_during_dirty_transaction(database, tmp_path / f"{database_name}.ready")

    assert (tmp_path / f"{database_name}-wal").is_file()
    assert _values(database) == ("committed",)


def test_backup_recovers_all_four_databases_after_forced_termination(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    for name in STATE_DATABASE_NAMES:
        database = state / name
        _initialize_database(database)
        _kill_during_dirty_transaction(database, tmp_path / f"{name}.ready")

    backup = tmp_path / "backup"
    report = create_state_backup(state.resolve(), backup.resolve())
    manifest = verify_state_backup(backup.resolve())

    assert report.database_count == 4
    assert tuple(entry.name for entry in manifest.entries) == STATE_DATABASE_NAMES
    for name in STATE_DATABASE_NAMES:
        assert _values(state / name) == ("committed",)
        validate_existing_sqlite(backup / name)
        with closing(sqlite3.connect(backup / name)) as database:
            assert database.execute("PRAGMA quick_check(1)").fetchone() == ("ok",)
            assert database.execute("SELECT value FROM crash_probe").fetchall() == [
                ("committed",)
            ]
