from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from .cancellation import CancellationToken
from .models import ActionStatus
from .runtime_models import TaskOutcome


class FeedbackCode(StrEnum):
    PLAN_READY = "PLAN_READY"
    TASK_SUCCEEDED = "TASK_SUCCEEDED"
    TASK_ABORTED = "TASK_ABORTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


_FIXED_KOREAN_MESSAGES: dict[FeedbackCode, str] = {
    FeedbackCode.PLAN_READY: "작업 순서를 정했어요.",
    FeedbackCode.TASK_SUCCEEDED: "작업을 마쳤고, 결과도 확인했어요.",
    FeedbackCode.TASK_ABORTED: "안전을 위해 여기서 멈췄어요.",
    FeedbackCode.APPROVAL_REQUIRED: "계속하려면 화면에서 승인해 주세요.",
    FeedbackCode.CANCELLED: "작업을 취소했어요.",
    FeedbackCode.FAILED: "작업을 마치지 못했어요.",
}

_SAFETY_ABORT_REASONS = frozenset(
    {
        "INVALID_APPROVAL",
        "REPLAN_REUSED_ACTION_ID",
    }
)


class SpeechSink(Protocol):
    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None: ...


class VoiceFeedbackPresenter:
    """Speak fixed local phrases, never user, model, or error text."""

    def __init__(self, sink: SpeechSink) -> None:
        self._sink = sink

    def present(
        self,
        code: FeedbackCode,
        *,
        cancellation: CancellationToken | None = None,
    ) -> None:
        self._sink.speak(_FIXED_KOREAN_MESSAGES[code], cancellation=cancellation)

    def present_outcome(
        self,
        outcome: TaskOutcome,
        *,
        cancellation: CancellationToken | None = None,
    ) -> FeedbackCode:
        code = feedback_code_for_outcome(outcome)
        self.present(code, cancellation=cancellation)
        return code


def feedback_code_for_outcome(outcome: TaskOutcome) -> FeedbackCode:
    if outcome.status is ActionStatus.SUCCEEDED:
        return FeedbackCode.TASK_SUCCEEDED
    reason = outcome.reason.upper()
    if (
        reason in {"GLOBAL_STOP", "LOCAL_STOP"}
        or reason.startswith("CANCEL")
        or reason.endswith("_CANCELLED")
        or reason.startswith("STOP_REQUESTED")
    ):
        return FeedbackCode.CANCELLED
    if "APPROVAL_REQUIRED" in reason or reason == "STRONG_AUTH_REQUIRED":
        return FeedbackCode.APPROVAL_REQUIRED
    if reason.startswith("POLICY_DENIED:") or reason in _SAFETY_ABORT_REASONS:
        return FeedbackCode.TASK_ABORTED
    return FeedbackCode.FAILED
