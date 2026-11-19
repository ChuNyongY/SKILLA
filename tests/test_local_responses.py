import pytest

from skilla_core.local_responses import LocalResponseCode, LocalResponseRouter


@pytest.mark.parametrize(
    "utterance",
    (
        "자기소개해봐",
        "자기 소개해 줘",
        "스킬라, 자기소개해줘.",
        "너는 누구야?",
        "스킬라가 뭐야?",
    ),
)
def test_self_introduction_variants_resolve_locally(utterance: str) -> None:
    response = LocalResponseRouter().resolve(utterance)

    assert response is not None
    assert response.code is LocalResponseCode.SELF_INTRODUCTION
    assert response.reason == "SELF_INTRODUCTION_DELIVERED"
    assert response.title == "SKILLA 자기소개"
    assert len(response.lines) == 3


@pytest.mark.parametrize(
    ("utterance", "expected_code", "expected_reason"),
    (
        ("스킬라, 안녕하세요", LocalResponseCode.GREETING, "GREETING_DELIVERED"),
        (
            "뭐 할 수 있어?",
            LocalResponseCode.CAPABILITY_OVERVIEW,
            "CAPABILITY_OVERVIEW_DELIVERED",
        ),
        ("고마워", LocalResponseCode.THANKS, "THANKS_DELIVERED"),
        ("스킬라 다음에 보자", LocalResponseCode.GOODBYE, "GOODBYE_DELIVERED"),
    ),
)
def test_bounded_conversation_resolves_without_a_model(
    utterance: str,
    expected_code: LocalResponseCode,
    expected_reason: str,
) -> None:
    response = LocalResponseRouter().resolve(utterance)

    assert response is not None
    assert response.code is expected_code
    assert response.reason == expected_reason


@pytest.mark.parametrize(
    "utterance",
    (
        "시스템 정보 확인해줘",
        "과제 자료 정리해줘",
        "검색해줘",
        "안녕이라고 문서에 입력해줘",
        "고마워 노래를 틀어줘",
    ),
)
def test_action_requests_do_not_match_local_conversation(utterance: str) -> None:
    assert LocalResponseRouter().resolve(utterance) is None
