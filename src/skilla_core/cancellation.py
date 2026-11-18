from __future__ import annotations

from threading import Event, Lock


class CancellationToken:
    """Thread-safe, one-way local stop signal independent of the planner."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._reason = "GLOBAL_STOP"

    def cancel(self, reason: str = "GLOBAL_STOP") -> None:
        if not reason:
            raise ValueError("cancellation reason must not be empty")
        with self._lock:
            if self._event.is_set():
                return
            self._reason = reason
            self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    def wait(self, timeout_seconds: float) -> bool:
        """Wait for cancellation without exposing the mutable event."""
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 0 <= timeout_seconds <= 120.0
        ):
            raise ValueError("cancellation wait must be within 0..120 seconds")
        return self._event.wait(float(timeout_seconds))

