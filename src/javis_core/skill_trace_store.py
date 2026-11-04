from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from .models import FrozenModel, Plan
from .runtime_models import TaskOutcome
from .skill_authoring import SkillExecutionTrace
from .skill_trace import build_skill_execution_trace


class SkillTraceStoreError(RuntimeError):
    pass


class PendingSkillTrace(FrozenModel):
    trace: SkillExecutionTrace
    recorded_at: datetime
    consumed: bool = False
    discarded: bool = False


class LocalSkillTraceStore:
    """Local queue of privacy-minimized evidence awaiting explicit review."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir():
            raise ValueError("skill trace path must be absolute in an existing directory")
        self._path = path
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_traces(
                  trace_id TEXT PRIMARY KEY, trace_json TEXT NOT NULL,
                  recorded_at TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0,
                  discarded INTEGER NOT NULL DEFAULT 0)
                """
            )
            _ensure_column(
                db, "skill_traces", "discarded", "INTEGER NOT NULL DEFAULT 0"
            )

    def observe(self, plan: Plan, outcome: TaskOutcome) -> None:
        trace = build_skill_execution_trace(
            plan, outcome, goal_summary=_minimize_goal(plan.goal)
        )
        recorded_at = datetime.now(UTC)
        with closing(self._connect()) as db, db:
            db.execute(
                """
                INSERT INTO skill_traces(
                  trace_id, trace_json, recorded_at, consumed, discarded)
                VALUES (?,?,?,0,0)
                """,
                (str(trace.trace_id), trace.model_dump_json(), recorded_at.isoformat()),
            )

    def pending(self, *, limit: int = 20) -> tuple[PendingSkillTrace, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("trace limit must be within 1..100")
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT trace_json, recorded_at, consumed, discarded FROM skill_traces
                WHERE consumed=0 AND discarded=0
                ORDER BY recorded_at, trace_id LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(
            PendingSkillTrace(
                trace=SkillExecutionTrace.model_validate_json(row["trace_json"]),
                recorded_at=datetime.fromisoformat(row["recorded_at"]),
                consumed=bool(row["consumed"]),
                discarded=bool(row["discarded"]),
            )
            for row in rows
        )

    def mark_consumed(self, trace_id: UUID) -> None:
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "UPDATE skill_traces SET consumed=1 WHERE trace_id=? AND consumed=0",
                (str(trace_id),),
            )
            if cursor.rowcount != 1:
                raise SkillTraceStoreError("pending skill trace not found")

    def require_pending(self, trace_id: UUID) -> PendingSkillTrace:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT trace_json, recorded_at, consumed, discarded FROM skill_traces
                WHERE trace_id=? AND consumed=0 AND discarded=0
                """,
                (str(trace_id),),
            ).fetchone()
        if row is None:
            raise SkillTraceStoreError("pending skill trace not found")
        return PendingSkillTrace(
            trace=SkillExecutionTrace.model_validate_json(row["trace_json"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            consumed=False,
            discarded=False,
        )

    def discard(self, trace_id: UUID) -> None:
        self._set_discarded(trace_id, discarded=True)

    def restore(self, trace_id: UUID) -> None:
        self._set_discarded(trace_id, discarded=False)

    def _set_discarded(self, trace_id: UUID, *, discarded: bool) -> None:
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                """
                UPDATE skill_traces SET discarded=?
                WHERE trace_id=? AND consumed=0 AND discarded=?
                """,
                (int(discarded), str(trace_id), int(not discarded)),
            )
            if cursor.rowcount != 1:
                raise SkillTraceStoreError("eligible skill trace not found")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection


_WINDOWS_PATH = re.compile(r"(?i)(?:[a-z]:\\|\\\\)[^\s\"'<>|]+")
_URL = re.compile(r"(?i)https?://[^\s\"'<>]+")
_EMAIL = re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}")


def _minimize_goal(goal: str) -> str:
    value = _WINDOWS_PATH.sub("<경로>", goal)
    value = _URL.sub("<URL>", value)
    value = _EMAIL.sub("<이메일>", value)
    return value[:400]


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    existing = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
