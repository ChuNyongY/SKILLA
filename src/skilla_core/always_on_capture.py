from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from threading import Lock
from typing import Protocol

from pydantic import Field

from .agent_session import FrameSource
from .always_on_runtime import (
    AlwaysOnAgentRuntime,
    AlwaysOnState,
    RuntimeEvent,
    RuntimeEventType,
)
from .cancellation import CancellationToken
from .intent import LocalStopDetector
from .models import FrozenModel
from .voice import AudioFrame, VoiceCaptureResult


class CapturePipeline(Protocol):
    def feed(self, frame: AudioFrame) -> VoiceCaptureResult | None: ...

    def cancel(self) -> None: ...


class CapturePumpStatus(StrEnum):
    STOPPED = "STOPPED"
    FRAME_LIMIT_REACHED = "FRAME_LIMIT_REACHED"
    INPUT_EXHAUSTED = "INPUT_EXHAUSTED"
    RUNTIME_CLOSED = "RUNTIME_CLOSED"
    FAILED = "FAILED"


class CapturePumpResult(FrozenModel):
    status: CapturePumpStatus
    reason: str = Field(
        min_length=2,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    frame_count: int = Field(ge=0)
    capture_count: int = Field(ge=0)
    tasks_started: int = Field(ge=0)
    stops_accepted: int = Field(ge=0)
    busy_ignored: int = Field(ge=0)
    duplicate_ignored: int = Field(default=0, ge=0)
    last_event: RuntimeEvent | None = None


class AlwaysOnCapturePump:
    """Continuously feed microphone frames while task planning/execution runs."""

    def __init__(
        self,
        *,
        frame_source: FrameSource,
        voice_pipeline: CapturePipeline,
        runtime: AlwaysOnAgentRuntime,
        duplicate_cooldown_frames: int = 250,
        feedback_active_provider: Callable[[], bool] | None = None,
        feedback_cooldown_frames: int = 8,
    ) -> None:
        if not 1 <= duplicate_cooldown_frames <= 10_000:
            raise ValueError("duplicate cooldown must be within 1..10000 frames")
        if not 0 <= feedback_cooldown_frames <= 1_000:
            raise ValueError("feedback cooldown must be within 0..1000 frames")
        self._frame_source = frame_source
        self._voice_pipeline = voice_pipeline
        self._runtime = runtime
        self._duplicate_cooldown_frames = duplicate_cooldown_frames
        self._feedback_active = feedback_active_provider or (lambda: False)
        self._feedback_cooldown_frames = feedback_cooldown_frames
        self._stop_detector = LocalStopDetector()
        self._lock = Lock()
        self._lifecycle: CancellationToken | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._lifecycle is not None

    def request_stop(self) -> bool:
        with self._lock:
            lifecycle = self._lifecycle
            if lifecycle is None:
                return False
            lifecycle.cancel("CAPTURE_PUMP_STOP")
            return True

    def run(self, *, max_frames: int = 1_080_000) -> CapturePumpResult:
        if type(max_frames) is not int or not 1 <= max_frames <= 1_080_000:
            raise ValueError("max_frames must be an integer from 1 through 1080000")
        lifecycle = CancellationToken()
        with self._lock:
            if self._lifecycle is not None:
                raise RuntimeError("capture pump is already running")
            self._lifecycle = lifecycle

        frames = 0
        captures = 0
        started = 0
        stopped = 0
        ignored = 0
        duplicate_ignored = 0
        last_transcript: str | None = None
        last_transcript_frame = -self._duplicate_cooldown_frames
        last_event: RuntimeEvent | None = None
        iterator: object | None = None
        status = CapturePumpStatus.INPUT_EXHAUSTED
        reason = "AUDIO_INPUT_EXHAUSTED"
        failed_reason: str | None = None
        feedback_was_active = False
        feedback_cooldown = 0
        try:
            iterator = iter(
                self._frame_source.frames(lifecycle, max_frames=max_frames)
            )
            for frame in iterator:
                frames += 1
                feedback_active = self._feedback_active()
                if feedback_active:
                    if not feedback_was_active:
                        self._voice_pipeline.cancel()
                    feedback_was_active = True
                    feedback_cooldown = self._feedback_cooldown_frames
                    continue
                if feedback_was_active:
                    feedback_was_active = False
                if feedback_cooldown > 0:
                    feedback_cooldown -= 1
                    continue
                review_active = getattr(self._runtime, "state", None) is AlwaysOnState.REVIEWING
                set_review_active = getattr(self._voice_pipeline, "set_review_active", None)
                if callable(set_review_active):
                    set_review_active(review_active)
                capture = self._voice_pipeline.feed(frame)
                if capture is not None:
                    captures += 1
                    normalized = _normalized_transcript(capture.transcript)
                    if (
                        normalized is not None
                        and not review_active
                        and not self._stop_detector.matches(normalized)
                        and normalized == last_transcript
                        and frames - last_transcript_frame
                        <= self._duplicate_cooldown_frames
                    ):
                        duplicate_ignored += 1
                        continue
                    try:
                        last_event = self._runtime.submit_capture(capture)
                    except Exception:
                        failed_reason = "RUNTIME_SUBMISSION_FAILED"
                        break
                    if normalized is not None:
                        last_transcript = normalized
                        last_transcript_frame = frames
                    started += last_event.event_type is RuntimeEventType.TASK_STARTED
                    stopped += last_event.event_type is RuntimeEventType.STOP_ACCEPTED
                    ignored += last_event.event_type is RuntimeEventType.BUSY_IGNORED
                    if last_event.event_type is RuntimeEventType.CLOSED:
                        status = CapturePumpStatus.RUNTIME_CLOSED
                        reason = "RUNTIME_CLOSED"
                        break
                if frames >= max_frames:
                    status = CapturePumpStatus.FRAME_LIMIT_REACHED
                    reason = "CAPTURE_FRAME_LIMIT_REACHED"
                    break
            if lifecycle.is_cancelled:
                status = CapturePumpStatus.STOPPED
                reason = "CAPTURE_PUMP_STOPPED"
        except Exception:
            failed_reason = "AUDIO_CAPTURE_FAILED"
        finally:
            cleanup_failed = self._cleanup(iterator)
            with self._lock:
                if self._lifecycle is lifecycle:
                    self._lifecycle = None

        if cleanup_failed:
            failed_reason = "AUDIO_CAPTURE_CLEANUP_FAILED"
        if failed_reason is not None:
            status = CapturePumpStatus.FAILED
            reason = failed_reason
        return CapturePumpResult(
            status=status,
            reason=reason,
            frame_count=frames,
            capture_count=captures,
            tasks_started=started,
            stops_accepted=stopped,
            busy_ignored=ignored,
            duplicate_ignored=duplicate_ignored,
            last_event=last_event,
        )

    def _cleanup(self, iterator: object | None) -> bool:
        failed = False
        close = getattr(iterator, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                failed = True
        try:
            self._voice_pipeline.cancel()
        except Exception:
            failed = True
        return failed


def _normalized_transcript(transcript: str | None) -> str | None:
    if transcript is None:
        return None
    normalized = " ".join(transcript.casefold().split())
    return normalized or None
