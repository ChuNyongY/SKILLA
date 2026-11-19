from __future__ import annotations

from enum import StrEnum
from threading import Event
from typing import Protocol

from .cancellation import CancellationToken
from .local_responses import LocalResponse, LocalResponseCode
from .models import ActionStatus
from .runtime_models import TaskOutcome


class FeedbackCode(StrEnum):
    PLAN_READY = "PLAN_READY"
    TASK_SUCCEEDED = "TASK_SUCCEEDED"
    TASK_ABORTED = "TASK_ABORTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    SKILL_REGISTER_REVIEW = "SKILL_REGISTER_REVIEW"
    SKILL_REUSE_REVIEW = "SKILL_REUSE_REVIEW"
    SELF_INTRODUCTION = "SELF_INTRODUCTION"
    GREETING = "GREETING"
    CAPABILITY_OVERVIEW = "CAPABILITY_OVERVIEW"
    THANKS = "THANKS"
    GOODBYE = "GOODBYE"


_FIXED_KOREAN_MESSAGES: dict[FeedbackCode, str] = {
    FeedbackCode.PLAN_READY: "작업 순서를 정했어요.",
    FeedbackCode.TASK_SUCCEEDED: "작업을 마쳤고, 결과도 확인했어요.",
    FeedbackCode.TASK_ABORTED: "안전을 위해 여기서 멈췄어요.",
    FeedbackCode.APPROVAL_REQUIRED: "계속하려면 화면에서 승인해 주세요.",
    FeedbackCode.CANCELLED: "작업을 취소했어요.",
    FeedbackCode.FAILED: "작업을 마치지 못했어요.",
    FeedbackCode.SKILL_REGISTER_REVIEW: (
        "새 스킬의 작업 순서와 안전 조건을 화면에서 확인해 주세요. 등록하고 실행할까요?"
    ),
    FeedbackCode.SKILL_REUSE_REVIEW: "저장된 스킬을 찾았어요. 화면에서 확인한 작업을 실행할까요?",
    FeedbackCode.SELF_INTRODUCTION: (
        "저는 스킬라예요. 반복 작업을 스킬로 저장하고 검색해 다시 실행하는 "
        "로컬 인공지능 에이전트예요. 음성과 텍스트 명령을 받을 수 있고, "
        "중요한 작업은 승인과 결과 확인 절차를 거쳐 실행해요."
    ),
    FeedbackCode.GREETING: "안녕하세요. 스킬라예요. 필요한 작업을 말씀해 주세요.",
    FeedbackCode.CAPABILITY_OVERVIEW: (
        "저는 음성과 텍스트로 윈도우 작업을 받고, 반복 작업을 스킬로 저장해 다시 실행해요. "
        "중요한 작업은 승인받고, 실행 결과도 직접 확인해요."
    ),
    FeedbackCode.THANKS: "도움이 되어 기뻐요. 다음 작업도 말씀해 주세요.",
    FeedbackCode.GOODBYE: "네, 다음에 필요할 때 다시 불러 주세요.",
}

_LOCAL_RESPONSE_FEEDBACK = {
    LocalResponseCode.SELF_INTRODUCTION: FeedbackCode.SELF_INTRODUCTION,
    LocalResponseCode.GREETING: FeedbackCode.GREETING,
    LocalResponseCode.CAPABILITY_OVERVIEW: FeedbackCode.CAPABILITY_OVERVIEW,
    LocalResponseCode.THANKS: FeedbackCode.THANKS,
    LocalResponseCode.GOODBYE: FeedbackCode.GOODBYE,
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
        self._speaking = Event()

    @property
    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def present(
        self,
        code: FeedbackCode,
        *,
        cancellation: CancellationToken | None = None,
    ) -> None:
        self._speaking.set()
        try:
            self._sink.speak(_FIXED_KOREAN_MESSAGES[code], cancellation=cancellation)
        finally:
            self._speaking.clear()

    def present_outcome(
        self,
        outcome: TaskOutcome,
        *,
        cancellation: CancellationToken | None = None,
    ) -> FeedbackCode:
        code = feedback_code_for_outcome(outcome)
        self.present(code, cancellation=cancellation)
        return code

    def present_local_response(
        self,
        response: LocalResponse,
        *,
        cancellation: CancellationToken | None = None,
    ) -> FeedbackCode:
        try:
            code = _LOCAL_RESPONSE_FEEDBACK[response.code]
        except KeyError as error:
            raise ValueError("unsupported local response") from error
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
