from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from skilla_core.cli import main
from skilla_core.sqlite_state import connect_sqlite_state, enable_sqlite_wal
from skilla_core.state_backup import (
    RESTORE_CONFIRMATION,
    STATE_DATABASE_NAMES,
    StateBackupError,
    create_state_backup,
    restore_state_backup,
    verify_state_backup,
)


def _state(root: Path, value: str) -> Path:
    root.mkdir()
    for name in STATE_DATABASE_NAMES:
        with closing(connect_sqlite_state(root / name)) as database:
            enable_sqlite_wal(database)
            database.execute("CREATE TABLE marker(value TEXT NOT NULL)")
            database.execute("INSERT INTO marker VALUES (?)", (f"{value}:{name}",))
            database.commit()
    return root.resolve()


def _values(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for name in STATE_DATABASE_NAMES:
        with closing(sqlite3.connect(root / name)) as database:
            values[name] = str(database.execute("SELECT value FROM marker").fetchone()[0])
    return values


def _set_values(root: Path, value: str) -> None:
    for name in STATE_DATABASE_NAMES:
        with closing(sqlite3.connect(root / name)) as database:
            database.execute("UPDATE marker SET value=?", (f"{value}:{name}",))
            database.commit()


def test_backup_verify_restore_and_rollback_copy(tmp_path: Path) -> None:
    state = _state(tmp_path / "state", "backup")
    backup = (tmp_path / "backup").resolve()

    report = create_state_backup(
        state,
        backup,
        now=datetime(2026, 11, 17, 12, 0, tzinfo=UTC),
    )
    manifest = verify_state_backup(backup)
    _set_values(state, "live")
    restored = restore_state_backup(
        backup,
        state,
        confirmation=RESTORE_CONFIRMATION,
        now=datetime(2026, 11, 17, 12, 5, tzinfo=UTC),
    )

    assert report.database_count == 4
    assert len(report.manifest_sha256) == 64
    assert tuple(item.name for item in manifest.entries) == STATE_DATABASE_NAMES
    assert _values(state) == {
        name: f"backup:{name}" for name in STATE_DATABASE_NAMES
    }
    assert _values(restored.rollback_directory) == {
        name: f"live:{name}" for name in STATE_DATABASE_NAMES
    }
    assert restored.restored_databases == STATE_DATABASE_NAMES


def test_backup_tampering_and_extra_files_are_rejected(tmp_path: Path) -> None:
    state = _state(tmp_path / "state", "backup")
    backup = (tmp_path / "backup").resolve()
    create_state_backup(state, backup)

    with (backup / STATE_DATABASE_NAMES[0]).open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(StateBackupError, match="identity mismatch"):
        verify_state_backup(backup)

    (backup / STATE_DATABASE_NAMES[0]).unlink()
    (backup / "unexpected.txt").write_text("x", encoding="utf-8")
    with pytest.raises(StateBackupError, match="contents"):
        verify_state_backup(backup)


def test_restore_requires_exact_confirmation_without_touching_state(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path / "state", "live")
    source = _state(tmp_path / "source", "backup")
    backup = (tmp_path / "backup").resolve()
    create_state_backup(source, backup)
    before = _values(state)

    with pytest.raises(StateBackupError, match="confirmation"):
        restore_state_backup(backup, state, confirmation="yes")

    assert _values(state) == before
    assert not (state / "restore-rollbacks").exists()


def test_partial_restore_failure_rolls_back_every_replaced_database(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path / "state", "live")
    source = _state(tmp_path / "source", "backup")
    backup = (tmp_path / "backup").resolve()
    create_state_backup(source, backup)
    before = _values(state)
    calls = 0

    def fail_third_replace(source_path: Path, destination_path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("injected replace failure")
        os.replace(source_path, destination_path)

    with pytest.raises(StateBackupError, match="previous files were retained"):
        restore_state_backup(
            backup,
            state,
            confirmation=RESTORE_CONFIRMATION,
            replace=fail_third_replace,
        )

    assert _values(state) == before
    assert not tuple(state.glob("*.restore.tmp"))


def test_cli_backup_verify_and_restore_temp_state(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    state = _state(project / "state", "backup")
    backup = (tmp_path / "backup").resolve()

    assert main(("backup-product-state", str(project), str(backup))) == 0
    assert '"database_count": 4' in capsys.readouterr().out
    assert main(("verify-product-state-backup", str(backup))) == 0
    assert '"status": "VERIFIED"' in capsys.readouterr().out

    _set_values(state, "live")
    assert (
        main(
            (
                "restore-product-state-backup",
                str(project),
                str(backup),
                "--confirm",
                RESTORE_CONFIRMATION,
            )
        )
        == 0
    )
    assert '"restored_databases"' in capsys.readouterr().out
    assert _values(state) == {
        name: f"backup:{name}" for name in STATE_DATABASE_NAMES
    }
