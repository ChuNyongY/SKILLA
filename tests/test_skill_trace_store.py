import sqlite3
from pathlib import Path

import pytest

from javis_core import Action, ActionStatus, Plan, TaskOutcome
from javis_core.skill_trace_store import LocalSkillTraceStore, SkillTraceStoreError


def test_trace_store_redacts_common_identifiers_and_queues_for_review(tmp_path: Path) -> None:
    store = LocalSkillTraceStore((tmp_path / "traces.sqlite3").resolve())
    plan = Plan(
        goal="C:\\private\\secret.pdf를 https://example.com/a 에서 user@example.com에게 정리",
        steps=(
            Action(
                capability_id="file.move",
                purpose="move",
                arguments={"secret": "raw"},
            ),
        ),
    )
    store.observe(
        plan,
        TaskOutcome(
            task_id=plan.task_id,
            status=ActionStatus.SUCCEEDED,
            completed_actions=1,
            reason="ALL_ACTIONS_VERIFIED",
        ),
    )
    pending = store.pending()
    assert len(pending) == 1
    serialized = pending[0].trace.model_dump_json()
    assert "private" not in serialized
    assert "example.com" not in serialized
    assert "user@" not in serialized
    assert "raw" not in serialized
    store.mark_consumed(pending[0].trace.trace_id)
    assert store.pending() == ()
    with pytest.raises(SkillTraceStoreError):
        store.mark_consumed(pending[0].trace.trace_id)


def test_trace_discard_is_recoverable_and_existing_schema_is_migrated(tmp_path: Path) -> None:
    path = (tmp_path / "traces.sqlite3").resolve()
    with sqlite3.connect(path) as db:
        db.execute(
            """
            CREATE TABLE skill_traces(
              trace_id TEXT PRIMARY KEY, trace_json TEXT NOT NULL,
              recorded_at TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)
            """
        )
    store = LocalSkillTraceStore(path)
    plan = Plan(goal="자료 정리", steps=(Action(capability_id="file.move", purpose="move"),))
    store.observe(
        plan,
        TaskOutcome(
            task_id=plan.task_id,
            status=ActionStatus.SUCCEEDED,
            completed_actions=1,
            reason="ALL_ACTIONS_VERIFIED",
        ),
    )
    trace_id = store.pending()[0].trace.trace_id
    store.discard(trace_id)
    assert store.pending() == ()
    store.restore(trace_id)
    assert store.require_pending(trace_id).trace.trace_id == trace_id
