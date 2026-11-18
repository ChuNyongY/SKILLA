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
    "utterance",
    ("시스템 정보 확인해줘", "과제 자료 정리해줘", "검색해줘"),
)
def test_action_requests_do_not_match_local_conversation(utterance: str) -> None:
    assert LocalResponseRouter().resolve(utterance) is None
