from __future__ import annotations

import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from skilla_core.foreground_context import ForegroundSnapshot
from skilla_core.skill_trigger_monitor import (
    SkillTriggerMonitor,
    SkillTriggerMonitorState,
    SkillTriggerSuggestionStore,
)
from skilla_core.skill_triggers import SkillTriggerError, SkillTriggerSuggestion


def suggestion() -> SkillTriggerSuggestion:
    return SkillTriggerSuggestion(
        suggestion_id=uuid4(),
        rule_id=uuid4(),
        app_id="chrome",
        skill_id=uuid4(),
        skill_version=2,
        title="최근 음악 재생",
    )


class Engine:
    def __init__(self, item: SkillTriggerSuggestion) -> None:
        self.item = item
        self.observed: list[str | None] = []
        self.resolved = object()

    def observe(self, app_id: str | None) -> SkillTriggerSuggestion | None:
        self.observed.append(app_id)
        return self.item if app_id is not None and len(self.observed) == 1 else None

    def resolve(self, item: SkillTriggerSuggestion) -> object:
        assert item == self.item
        return self.resolved


def test_suggestion_store_is_single_pending_and_exactly_claimed() -> None:
    item = suggestion()
    engine = Engine(item)
    store = SkillTriggerSuggestionStore(engine)  # type: ignore[arg-type]

    assert store.publish(item)
    assert not store.publish(item.model_copy(update={"suggestion_id": uuid4()}))
    assert store.snapshot() == item
    assert store.resolve(item.suggestion_id) is engine.resolved
    assert store.snapshot() == item
    with pytest.raises(SkillTriggerError, match="unavailable"):
        store.claim(uuid4())
    assert store.claim(item.suggestion_id) is engine.resolved
    assert store.snapshot() is None


def test_suggestion_store_dismisses_without_resolving_or_executing() -> None:
    item = suggestion()
    engine = Engine(item)
    store = SkillTriggerSuggestionStore(engine)  # type: ignore[arg-type]
    store.publish(item)

    assert not store.dismiss(uuid4())
    assert store.dismiss(item.suggestion_id)
    assert store.snapshot() is None
    assert engine.observed == []


class Manager:
    def __init__(self, updates: list[object], *, fail: bool = False) -> None:
        self.updates = updates
        self.fail = fail
        self.closed = threading.Event()

    def next_update(self, *, timeout_seconds: float) -> object | None:
        assert timeout_seconds == 0.2
        if self.fail:
            raise RuntimeError("private window title")
        if self.updates:
            return self.updates.pop(0)
        self.closed.wait(0.01)
        return None

    def close(self, *, timeout_seconds: float = 2.0) -> None:
        self.closed.set()


def update(app_id: str | None, *, verified: bool) -> object:
    return SimpleNamespace(
        snapshot=ForegroundSnapshot(
            hwnd=10,
            pid=20,
            app_id=app_id,
            identity_verified=verified,
            captured_at=datetime.now(UTC),
        )
    )


def test_monitor_publishes_verified_app_suggestion_and_never_executes() -> None:
    item = suggestion()
    engine = Engine(item)
    store = SkillTriggerSuggestionStore(engine)  # type: ignore[arg-type]
    manager = Manager([update("chrome", verified=True)])
    monitor = SkillTriggerMonitor(
        lambda: manager,  # type: ignore[arg-type,return-value]
        engine,  # type: ignore[arg-type]
        store,
    )

    assert monitor.start().state is SkillTriggerMonitorState.RUNNING
    for _ in range(100):
        if store.snapshot() is not None:
            break
        threading.Event().wait(0.01)
    assert store.snapshot() == item
    assert engine.observed == ["chrome"]
    assert monitor.stop().state is SkillTriggerMonitorState.STOPPED


def test_monitor_ignores_unverified_identity() -> None:
    item = suggestion()
    engine = Engine(item)
    store = SkillTriggerSuggestionStore(engine)  # type: ignore[arg-type]
    manager = Manager([update(None, verified=False)])
    monitor = SkillTriggerMonitor(
        lambda: manager,  # type: ignore[arg-type,return-value]
        engine,  # type: ignore[arg-type]
        store,
    )

    monitor.start()
    for _ in range(100):
        if engine.observed:
            break
        threading.Event().wait(0.01)
    assert engine.observed == [None]
    assert store.snapshot() is None
    monitor.stop()


def test_monitor_fails_closed_with_redacted_reason() -> None:
    item = suggestion()
    engine = Engine(item)
    store = SkillTriggerSuggestionStore(engine)  # type: ignore[arg-type]
    monitor = SkillTriggerMonitor(
        lambda: Manager([], fail=True),  # type: ignore[arg-type,return-value]
        engine,  # type: ignore[arg-type]
        store,
    )

    monitor.start()
    for _ in range(100):
        if monitor.status_snapshot().state is SkillTriggerMonitorState.FAILED:
            break
        threading.Event().wait(0.01)
    status = monitor.status_snapshot()
    assert status.state is SkillTriggerMonitorState.FAILED
    assert status.reason == "MONITOR_CONTEXT_FAILED"
    assert "private" not in status.model_dump_json()
    assert store.snapshot() is None
