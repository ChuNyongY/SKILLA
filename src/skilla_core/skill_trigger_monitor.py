from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from threading import Event, Lock, Thread
from uuid import UUID

from pydantic import Field

from .context_events import ContextEventError, EventDrivenContextManager
from .models import FrozenModel
from .skill_runtime import SkillRecord
from .skill_triggers import (
    SkillTriggerError,
    SkillTriggerSuggestion,
    SkillTriggerSuggestionEngine,
)


class SkillTriggerMonitorState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class SkillTriggerMonitorStatus(FrozenModel):
    state: SkillTriggerMonitorState
    reason: str = Field(pattern=r"^[A-Z0-9_]{2,64}$")


class SkillTriggerSuggestionStore:
    """Keep at most one user-visible suggestion and resolve it exactly once."""

    def __init__(self, engine: SkillTriggerSuggestionEngine) -> None:
        self._engine = engine
        self._lock = Lock()
        self._pending: SkillTriggerSuggestion | None = None

    def publish(self, suggestion: SkillTriggerSuggestion) -> bool:
        with self._lock:
            if self._pending is not None:
                return False
            self._pending = suggestion
            return True

    def snapshot(self) -> SkillTriggerSuggestion | None:
        with self._lock:
            return self._pending.model_copy() if self._pending is not None else None

    def dismiss(self, suggestion_id: UUID) -> bool:
        with self._lock:
            if self._pending is None or self._pending.suggestion_id != suggestion_id:
                return False
            self._pending = None
            return True

    def claim(self, suggestion_id: UUID) -> SkillRecord:
        with self._lock:
            pending = self._pending
            if pending is None or pending.suggestion_id != suggestion_id:
                raise SkillTriggerError("skill trigger suggestion is unavailable")
            skill = self._engine.resolve(pending)
            self._pending = None
            return skill

    def resolve(self, suggestion_id: UUID) -> SkillRecord:
        with self._lock:
            pending = self._pending
            if pending is None or pending.suggestion_id != suggestion_id:
                raise SkillTriggerError("skill trigger suggestion is unavailable")
            return self._engine.resolve(pending)


ContextManagerFactory = Callable[[], EventDrivenContextManager]


class SkillTriggerMonitor:
    """Observe verified foreground transitions and publish suggestions only."""

    def __init__(
        self,
        manager_factory: ContextManagerFactory,
        engine: SkillTriggerSuggestionEngine,
        suggestions: SkillTriggerSuggestionStore,
        *,
        thread_factory: Callable[..., Thread] = Thread,
    ) -> None:
        self._manager_factory = manager_factory
        self._engine = engine
        self._suggestions = suggestions
        self._thread_factory = thread_factory
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._manager: EventDrivenContextManager | None = None
        self._status = SkillTriggerMonitorStatus(
            state=SkillTriggerMonitorState.CREATED,
            reason="MONITOR_CREATED",
        )

    def status_snapshot(self) -> SkillTriggerMonitorStatus:
        with self._lock:
            return self._status.model_copy()

    def start(self) -> SkillTriggerMonitorStatus:
        with self._lock:
            if self._status.state is not SkillTriggerMonitorState.CREATED:
                raise RuntimeError("skill trigger monitor may only start once")
            self._stop.clear()
            try:
                thread = self._thread_factory(
                    target=self._run,
                    name="skilla-skill-trigger-monitor",
                    daemon=False,
                )
                self._thread = thread
                self._status = SkillTriggerMonitorStatus(
                    state=SkillTriggerMonitorState.RUNNING,
                    reason="MONITOR_STARTED",
                )
                thread.start()
            except Exception:
                self._thread = None
                self._status = SkillTriggerMonitorStatus(
                    state=SkillTriggerMonitorState.FAILED,
                    reason="MONITOR_START_FAILED",
                )
            return self._status.model_copy()

    def stop(self, *, timeout_seconds: float = 2.0) -> SkillTriggerMonitorStatus:
        if isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 5:
            raise ValueError("timeout_seconds must be within 0..5")
        with self._lock:
            state = self._status.state
            if state in {SkillTriggerMonitorState.STOPPED, SkillTriggerMonitorState.FAILED}:
                return self._status.model_copy()
            if state is SkillTriggerMonitorState.CREATED:
                self._status = SkillTriggerMonitorStatus(
                    state=SkillTriggerMonitorState.STOPPED,
                    reason="MONITOR_STOPPED",
                )
                return self._status.model_copy()
            self._stop.set()
            manager = self._manager
            thread = self._thread
        close_failed = False
        if manager is not None:
            try:
                manager.close(timeout_seconds=timeout_seconds)
            except ContextEventError:
                close_failed = True
        if thread is not None:
            thread.join(timeout=timeout_seconds)
            if thread.is_alive():
                close_failed = True
        with self._lock:
            self._status = SkillTriggerMonitorStatus(
                state=(
                    SkillTriggerMonitorState.FAILED
                    if close_failed
                    else SkillTriggerMonitorState.STOPPED
                ),
                reason=("MONITOR_STOP_FAILED" if close_failed else "MONITOR_STOPPED"),
            )
            return self._status.model_copy()

    def _run(self) -> None:
        try:
            manager = self._manager_factory()
            with self._lock:
                self._manager = manager
            while not self._stop.is_set():
                update = manager.next_update(timeout_seconds=0.2)
                if update is None:
                    continue
                app_id = (
                    update.snapshot.app_id
                    if update.snapshot.identity_verified
                    else None
                )
                suggestion = self._engine.observe(app_id)
                if suggestion is not None:
                    self._suggestions.publish(suggestion)
        except Exception:
            if not self._stop.is_set():
                with self._lock:
                    self._status = SkillTriggerMonitorStatus(
                        state=SkillTriggerMonitorState.FAILED,
                        reason="MONITOR_CONTEXT_FAILED",
                    )
        finally:
            with self._lock:
                current_manager = self._manager
                self._manager = None
            if current_manager is not None:
                try:
                    current_manager.close(timeout_seconds=2.0)
                except ContextEventError:
                    if not self._stop.is_set():
                        with self._lock:
                            self._status = SkillTriggerMonitorStatus(
                                state=SkillTriggerMonitorState.FAILED,
                                reason="MONITOR_CONTEXT_FAILED",
                            )
