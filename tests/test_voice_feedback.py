from uuid import uuid4

import pytest

from javis_core import ActionStatus, CancellationToken, TaskOutcome
from javis_core.voice_feedback import (
    FeedbackCode,
    VoiceFeedbackPresenter,
    feedback_code_for_outcome,
)


class FakeSpeechSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, CancellationToken | None]] = []

    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None:
        assert rate == 0
        assert volume == 100
        self.calls.append((text, cancellation))


@pytest.mark.parametrize(
    ("status", "reason", "expected"),
    [
        (ActionStatus.SUCCEEDED, "ALL_ACTIONS_VERIFIED", FeedbackCode.TASK_SUCCEEDED),
        (ActionStatus.ABORTED, "GLOBAL_STOP", FeedbackCode.CANCELLED),
        (ActionStatus.ABORTED, "CANCELLED_BY_USER", FeedbackCode.CANCELLED),
        (ActionStatus.ABORTED, "PLANNING_CANCELLED", FeedbackCode.CANCELLED),
        (ActionStatus.ABORTED, "STOP_REQUESTED_AFTER_INPUT", FeedbackCode.CANCELLED),
        (ActionStatus.ABORTED, "RED_APPROVAL_REQUIRED", FeedbackCode.APPROVAL_REQUIRED),
        (ActionStatus.ABORTED, "STRONG_AUTH_REQUIRED", FeedbackCode.APPROVAL_REQUIRED),
        (
            ActionStatus.ABORTED,
            "POLICY_DENIED:PROMPT_INJECTION_SUSPECTED",
            FeedbackCode.TASK_ABORTED,
        ),
        (ActionStatus.ABORTED, "INVALID_APPROVAL", FeedbackCode.TASK_ABORTED),
        (ActionStatus.ABORTED, "PRIVATE_FAILURE_DETAIL", FeedbackCode.FAILED),
        (ActionStatus.FAILED, "EXECUTION_FAILED", FeedbackCode.FAILED),
    ],
)
def test_outcome_maps_to_bounded_feedback(
    status: ActionStatus, reason: str, expected: FeedbackCode
) -> None:
    outcome = TaskOutcome(
        task_id=uuid4(), status=status, completed_actions=0, reason=reason
    )
    assert feedback_code_for_outcome(outcome) is expected


def test_presenter_speaks_only_fixed_phrase_and_forwards_stop_token() -> None:
    sink = FakeSpeechSink()
    token = CancellationToken()
    outcome = TaskOutcome(
        task_id=uuid4(),
        status=ActionStatus.ABORTED,
        completed_actions=0,
        reason="PRIVATE_MODEL_FAILURE",
    )

    code = VoiceFeedbackPresenter(sink).present_outcome(outcome, cancellation=token)

    assert code is FeedbackCode.FAILED
    assert sink.calls == [("작업을 마치지 못했어요.", token)]
    assert "PRIVATE_MODEL_FAILURE" not in sink.calls[0][0]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (FeedbackCode.PLAN_READY, "작업 순서를 정했어요."),
        (FeedbackCode.TASK_SUCCEEDED, "작업을 마쳤고, 결과도 확인했어요."),
        (FeedbackCode.TASK_ABORTED, "안전을 위해 여기서 멈췄어요."),
        (FeedbackCode.APPROVAL_REQUIRED, "계속하려면 화면에서 승인해 주세요."),
        (FeedbackCode.CANCELLED, "작업을 취소했어요."),
        (FeedbackCode.FAILED, "작업을 마치지 못했어요."),
    ],
)
def test_every_feedback_phrase_is_fixed_short_spoken_korean(
    code: FeedbackCode,
    expected: str,
) -> None:
    sink = FakeSpeechSink()

    VoiceFeedbackPresenter(sink).present(code)

    assert sink.calls == [(expected, None)]
    assert len(expected) <= 40
    assert expected == expected.strip()
    assert not any(character in expected for character in "\0\r\n\t")
