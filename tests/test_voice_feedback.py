import threading
from uuid import uuid4

import pytest

from skilla_core import ActionStatus, CancellationToken, TaskOutcome
from skilla_core.local_responses import LocalResponseRouter
from skilla_core.voice_feedback import (
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


def test_presenter_exposes_speaking_state_only_during_sink_playback() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingSink(FakeSpeechSink):
        def speak(self, text: str, **kwargs: object) -> None:
            entered.set()
            assert release.wait(timeout=1)
            super().speak(text, **kwargs)  # type: ignore[arg-type]

    sink = BlockingSink()
    presenter = VoiceFeedbackPresenter(sink)
    worker = threading.Thread(target=lambda: presenter.present(FeedbackCode.PLAN_READY))

    worker.start()
    assert entered.wait(timeout=1)
    assert presenter.is_speaking
    release.set()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert not presenter.is_speaking


def test_self_introduction_uses_only_product_owned_fixed_speech() -> None:
    sink = FakeSpeechSink()
    response = LocalResponseRouter().resolve("자기소개해줘")
    assert response is not None

    code = VoiceFeedbackPresenter(sink).present_local_response(response)

    assert code is FeedbackCode.SELF_INTRODUCTION
    assert sink.calls == [
        (
            "저는 스킬라예요. 반복 작업을 스킬로 저장하고 검색해 다시 실행하는 "
            "로컬 인공지능 에이전트예요. 음성과 텍스트 명령을 받을 수 있고, "
            "중요한 작업은 승인과 결과 확인 절차를 거쳐 실행해요.",
            None,
        )
    ]


@pytest.mark.parametrize(
    ("utterance", "expected_code", "expected_text"),
    (
        (
            "안녕하세요",
            FeedbackCode.GREETING,
            "안녕하세요. 스킬라예요. 필요한 작업을 말씀해 주세요.",
        ),
        (
            "뭐 할 수 있어?",
            FeedbackCode.CAPABILITY_OVERVIEW,
            "저는 음성과 텍스트로 윈도우 작업을 받고, 반복 작업을 스킬로 저장해 다시 실행해요. "
            "중요한 작업은 승인받고, 실행 결과도 직접 확인해요.",
        ),
        (
            "고마워",
            FeedbackCode.THANKS,
            "도움이 되어 기뻐요. 다음 작업도 말씀해 주세요.",
        ),
        (
            "다음에 보자",
            FeedbackCode.GOODBYE,
            "네, 다음에 필요할 때 다시 불러 주세요.",
        ),
    ),
)
def test_bounded_conversation_uses_product_owned_fixed_speech(
    utterance: str,
    expected_code: FeedbackCode,
    expected_text: str,
) -> None:
    sink = FakeSpeechSink()
    response = LocalResponseRouter().resolve(utterance)
    assert response is not None

    code = VoiceFeedbackPresenter(sink).present_local_response(response)

    assert code is expected_code
    assert sink.calls == [(expected_text, None)]


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
