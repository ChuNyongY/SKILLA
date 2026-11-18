from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from threading import Event, Lock, Thread
from uuid import UUID

from pydantic import Field

from .models import FrozenModel
from .skill_runtime import SkillRecord
from .skill_schedules import (
    ScheduledSkillSuggestion,
    SkillScheduleError,
    SkillScheduleSuggestionEngine,
)


class SkillScheduleMonitorState(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class SkillScheduleMonitorStatus(FrozenModel):
    state: SkillScheduleMonitorState
    reason: str = Field(pattern=r"^[A-Z0-9_]{2,64}$")


class SkillScheduleSuggestionStore:
    """Hold a bounded FIFO of due suggestions until the user responds."""

    def __init__(
        self,
        engine: SkillScheduleSuggestionEngine,
        *,
        capacity: int = 20,
    ) -> None:
        if type(capacity) is not int or not 1 <= capacity <= 100:
            raise ValueError("schedule suggestion capacity must be within 1..100")
        self._engine = engine
        self._capacity = capacity
        self._lock = Lock()
        self._pending: deque[ScheduledSkillSuggestion] = deque()

    def publish(self, suggestion: ScheduledSkillSuggestion) -> bool:
        with self._lock:
            if len(self._pending) >= self._capacity:
                return False
            self._pending.append(suggestion)
            return True

    def snapshot(self) -> ScheduledSkillSuggestion | None:
        with self._lock:
            return self._pending[0].model_copy() if self._pending else None

    def dismiss(self, suggestion_id: UUID) -> bool:
        with self._lock:
            if not self._pending or self._pending[0].suggestion_id != suggestion_id:
                return False
            self._pending.popleft()
            return True

    def claim(self, suggestion_id: UUID) -> SkillRecord:
        with self._lock:
            if not self._pending or self._pending[0].suggestion_id != suggestion_id:
                raise SkillScheduleError("scheduled skill suggestion is unavailable")
            suggestion = self._pending[0]
            skill = self._engine.resolve(suggestion)
            self._pending.popleft()
            return skill

    def resolve(self, suggestion_id: UUID) -> SkillRecord:
        with self._lock:
            if not self._pending or self._pending[0].suggestion_id != suggestion_id:
                raise SkillScheduleError("scheduled skill suggestion is unavailable")
            return self._engine.resolve(self._pending[0])


class SkillScheduleMonitor:
    """Poll local time and publish due-skill suggestions without executing work."""

    def __init__(
        self,
        engine: SkillScheduleSuggestionEngine,
        suggestions: SkillScheduleSuggestionStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now().astimezone(),
        poll_interval_seconds: float = 15.0,
        thread_factory: Callable[..., Thread] = Thread,
    ) -> None:
        if (
            isinstance(poll_interval_seconds, bool)
            or not 0.1 <= poll_interval_seconds <= 60
        ):
            raise ValueError("schedule poll interval must be within 0.1..60")
        self._engine = engine
        self._suggestions = suggestions
        self._clock = clock
        self._interval = float(poll_interval_seconds)
        self._thread_factory = thread_factory
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._status = SkillScheduleMonitorStatus(
            state=SkillScheduleMonitorState.CREATED,
            reason="SCHEDULE_MONITOR_CREATED",
        )

    def status_snapshot(self) -> SkillScheduleMonitorStatus:
        with self._lock:
            return self._status.model_copy()

    def start(self) -> SkillScheduleMonitorStatus:
        with self._lock:
            if self._status.state is not SkillScheduleMonitorState.CREATED:
                raise RuntimeError("skill schedule monitor may only start once")
            self._stop.clear()
            try:
                thread = self._thread_factory(
                    target=self._run,
                    name="skilla-skill-schedule-monitor",
                    daemon=False,
                )
                self._thread = thread
                self._status = SkillScheduleMonitorStatus(
                    state=SkillScheduleMonitorState.RUNNING,
                    reason="SCHEDULE_MONITOR_STARTED",
                )
                thread.start()
            except Exception:
                self._thread = None
                self._status = SkillScheduleMonitorStatus(
                    state=SkillScheduleMonitorState.FAILED,
                    reason="SCHEDULE_MONITOR_START_FAILED",
                )
            return self._status.model_copy()

    def stop(self, *, timeout_seconds: float = 2.0) -> SkillScheduleMonitorStatus:
        if isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 5:
            raise ValueError("timeout_seconds must be within 0..5")
        with self._lock:
            if self._status.state in {
                SkillScheduleMonitorState.STOPPED,
                SkillScheduleMonitorState.FAILED,
            }:
                return self._status.model_copy()
            if self._status.state is SkillScheduleMonitorState.CREATED:
                self._status = SkillScheduleMonitorStatus(
                    state=SkillScheduleMonitorState.STOPPED,
                    reason="SCHEDULE_MONITOR_STOPPED",
                )
                return self._status.model_copy()
            self._stop.set()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_seconds)
        with self._lock:
            failed = thread is not None and thread.is_alive()
            self._status = SkillScheduleMonitorStatus(
                state=(
                    SkillScheduleMonitorState.FAILED
                    if failed
                    else SkillScheduleMonitorState.STOPPED
                ),
                reason=(
                    "SCHEDULE_MONITOR_STOP_FAILED"
                    if failed
                    else "SCHEDULE_MONITOR_STOPPED"
                ),
            )
            return self._status.model_copy()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                now = self._clock()
                for suggestion in self._engine.observe(now):
                    self._suggestions.publish(suggestion)
                self._stop.wait(self._interval)
        except Exception:
            if not self._stop.is_set():
                with self._lock:
                    self._status = SkillScheduleMonitorStatus(
                        state=SkillScheduleMonitorState.FAILED,
                        reason="SCHEDULE_MONITOR_FAILED",
                    )
