from __future__ import annotations

import sqlite3
from contextlib import closing, suppress
from pathlib import Path
from time import sleep


class SqliteStateError(RuntimeError):
    pass


def validate_existing_sqlite(
    path: Path,
    *,
    timeout_seconds: float = 2.0,
    max_bytes: int | None = None,
) -> None:
    """Fail closed before a repository writes to an existing SQLite database."""

    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or not path.is_file():
        raise SqliteStateError("SQLite state path is not a regular file")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise SqliteStateError("SQLite state file is unavailable") from error
    if max_bytes is not None and size > max_bytes:
        raise SqliteStateError("SQLite state file exceeded its size limit")
    row: tuple[object, ...] | None = None
    for attempt in range(3):
        try:
            uri = f"{path.resolve(strict=True).as_uri()}?mode=ro"
            with closing(
                sqlite3.connect(uri, uri=True, timeout=timeout_seconds)
            ) as database:
                database.execute(
                    f"PRAGMA busy_timeout={int(timeout_seconds * 1_000)}"
                )
                row = database.execute("PRAGMA quick_check(1)").fetchone()
            break
        except sqlite3.OperationalError as error:
            code = getattr(error, "sqlite_errorcode", -1) & 0xFF
            retryable = code in {
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
                sqlite3.SQLITE_IOERR,
            }
            if not retryable or attempt == 2:
                raise SqliteStateError(
                    "SQLite state integrity check failed"
                ) from error
            sleep(0.05 * (attempt + 1))
        except (OSError, sqlite3.Error) as error:
            raise SqliteStateError("SQLite state integrity check failed") from error
    if row is None or len(row) != 1 or str(row[0]).casefold() != "ok":
        raise SqliteStateError("SQLite state integrity check failed")


def connect_sqlite_state(
    path: Path,
    *,
    timeout_seconds: float = 5.0,
) -> sqlite3.Connection:
    """Open a bounded state connection with durable, fail-closed defaults."""

    database: sqlite3.Connection | None = None
    try:
        database = sqlite3.connect(path, timeout=timeout_seconds)
        database.execute(f"PRAGMA busy_timeout={int(timeout_seconds * 1_000)}")
        database.execute("PRAGMA foreign_keys=ON")
        database.execute("PRAGMA synchronous=FULL")
    except sqlite3.Error as error:
        if database is not None:
            with suppress(sqlite3.Error):
                database.close()
        raise SqliteStateError("SQLite state connection failed") from error
    if database is None:  # defensive narrowing; sqlite3.connect either returns or raises
        raise SqliteStateError("SQLite state connection failed")
    return database


def enable_sqlite_wal(database: sqlite3.Connection) -> None:
    """Persist WAL journaling so committed writes survive abrupt process loss."""

    try:
        row = database.execute("PRAGMA journal_mode=WAL").fetchone()
    except sqlite3.Error as error:
        raise SqliteStateError("SQLite WAL initialization failed") from error
    if row is None or str(row[0]).casefold() != "wal":
        raise SqliteStateError("SQLite WAL initialization failed")
