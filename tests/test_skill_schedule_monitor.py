from __future__ import annotations

import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from skilla_core.skill_schedule_monitor import (
    SkillScheduleMonitor,
    SkillScheduleMonitorState,
    SkillScheduleSuggestionStore,
)
from skilla_core.skill_schedules import ScheduledSkillSuggestion, SkillScheduleError


def suggestion() -> ScheduledSkillSuggestion:
    return ScheduledSkillSuggestion(
        suggestion_id=uuid4(),
        rule_id=uuid4(),
        skill_id=uuid4(),
        skill_version=1,
        title="아침 작업 준비",
        due_key="2026-11-16T08:30+0000",
    )


class Engine:
    def __init__(self, items: tuple[ScheduledSkillSuggestion, ...]) -> None:
        self.items = items
        self.calls = 0
        self.resolved = SimpleNamespace(triggers=("아침 작업 준비",))

    def observe(self, _now: datetime) -> tuple[ScheduledSkillSuggestion, ...]:
        self.calls += 1
        return self.items if self.calls == 1 else ()

    def resolve(self, item: ScheduledSkillSuggestion) -> object:
        assert item in self.items
        return self.resolved


def test_schedule_store_is_fifo_and_claims_exact_head() -> None:
    first = suggestion()
    second = suggestion().model_copy(update={"suggestion_id": uuid4()})
    engine = Engine((first, second))
    store = SkillScheduleSuggestionStore(engine)  # type: ignore[arg-type]

    assert store.publish(first)
    assert store.publish(second)
    assert store.snapshot() == first
    assert store.resolve(first.suggestion_id) is engine.resolved
    assert store.snapshot() == first
    with pytest.raises(SkillScheduleError, match="unavailable"):
        store.claim(second.suggestion_id)
    assert store.claim(first.suggestion_id) is engine.resolved
    assert store.snapshot() == second
    assert store.dismiss(second.suggestion_id)
    assert store.snapshot() is None


def test_schedule_store_is_bounded() -> None:
    item = suggestion()
    store = SkillScheduleSuggestionStore(Engine((item,)), capacity=1)  # type: ignore[arg-type]

    assert store.publish(item)
    assert not store.publish(item.model_copy(update={"suggestion_id": uuid4()}))
    with pytest.raises(ValueError, match="capacity"):
        SkillScheduleSuggestionStore(Engine(()), capacity=0)  # type: ignore[arg-type]


def test_schedule_monitor_publishes_due_suggestion_without_execution() -> None:
    item = suggestion()
    engine = Engine((item,))
    store = SkillScheduleSuggestionStore(engine)  # type: ignore[arg-type]
    monitor = SkillScheduleMonitor(
        engine,  # type: ignore[arg-type]
        store,
        clock=lambda: datetime(2026, 11, 16, 8, 30, tzinfo=UTC),
        poll_interval_seconds=0.1,
    )

    assert monitor.start().state is SkillScheduleMonitorState.RUNNING
    for _ in range(100):
        if store.snapshot() is not None:
            break
        threading.Event().wait(0.01)
    assert store.snapshot() == item
    assert monitor.stop().state is SkillScheduleMonitorState.STOPPED


def test_schedule_monitor_fails_closed_with_redacted_reason() -> None:
    class FailingEngine(Engine):
        def observe(self, _now: datetime) -> tuple[ScheduledSkillSuggestion, ...]:
            raise RuntimeError("private scheduled task details")

    engine = FailingEngine(())
    store = SkillScheduleSuggestionStore(engine)  # type: ignore[arg-type]
    monitor = SkillScheduleMonitor(
        engine,  # type: ignore[arg-type]
        store,
        poll_interval_seconds=0.1,
    )
    monitor.start()
    for _ in range(100):
        if monitor.status_snapshot().state is SkillScheduleMonitorState.FAILED:
            break
        threading.Event().wait(0.01)

    status = monitor.status_snapshot()
    assert status.state is SkillScheduleMonitorState.FAILED
    assert status.reason == "SCHEDULE_MONITOR_FAILED"
    assert "private" not in status.model_dump_json()
    assert store.snapshot() is None
