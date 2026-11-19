from __future__ import annotations

import unicodedata
from enum import StrEnum

from pydantic import Field

from .models import FrozenModel


class LocalResponseCode(StrEnum):
    SELF_INTRODUCTION = "SELF_INTRODUCTION"
    GREETING = "GREETING"
    CAPABILITY_OVERVIEW = "CAPABILITY_OVERVIEW"
    THANKS = "THANKS"
    GOODBYE = "GOODBYE"


class LocalResponse(FrozenModel):
    """A product-owned response that never contains model or user supplied text."""

    code: LocalResponseCode
    reason: str = Field(
        min_length=2,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    title: str = Field(min_length=1, max_length=80)
    lines: tuple[str, ...] = Field(min_length=1, max_length=8)


_SELF_INTRODUCTION = LocalResponse(
    code=LocalResponseCode.SELF_INTRODUCTION,
    reason="SELF_INTRODUCTION_DELIVERED",
    title="SKILLA 자기소개",
    lines=(
        "반복 작업을 스킬로 저장하고 다시 사용하는 로컬 인공지능 에이전트입니다.",
        "음성과 텍스트 명령을 받아 저장된 스킬을 검색하고 실행합니다.",
        "중요한 작업은 사용자 승인 후 실행하며 실제 결과를 다시 확인합니다.",
    ),
)

_SELF_INTRODUCTION_UTTERANCES = frozenset(
    {
        "자기소개",
        "자기소개해봐",
        "자기소개해줘",
        "자기소개해주세요",
        "너는누구야",
        "넌누구야",
        "스킬라가뭐야",
        "스킬라는뭐야",
        "스킬라소개해줘",
        "스킬라를소개해줘",
    }
)

_GREETING = LocalResponse(
    code=LocalResponseCode.GREETING,
    reason="GREETING_DELIVERED",
    title="SKILLA 인사",
    lines=(
        "안녕하세요. 필요한 작업을 말씀해 주세요.",
        "반복 작업은 스킬로 저장해 다음 요청에서 다시 사용할 수 있습니다.",
    ),
)

_CAPABILITY_OVERVIEW = LocalResponse(
    code=LocalResponseCode.CAPABILITY_OVERVIEW,
    reason="CAPABILITY_OVERVIEW_DELIVERED",
    title="SKILLA가 할 수 있는 일",
    lines=(
        "음성과 텍스트로 Windows 작업을 요청할 수 있습니다.",
        "성공한 반복 작업은 스킬로 저장·검색·재사용할 수 있습니다.",
        "파일·프로그램·소리·브라우저 작업은 등록된 기능 범위에서 실행합니다.",
        "실행 전 필요한 승인을 받고 실행 후 실제 상태를 다시 확인합니다.",
    ),
)

_THANKS = LocalResponse(
    code=LocalResponseCode.THANKS,
    reason="THANKS_DELIVERED",
    title="SKILLA 응답",
    lines=("도움이 되어 기뻐요. 다음 작업도 말씀해 주세요.",),
)

_GOODBYE = LocalResponse(
    code=LocalResponseCode.GOODBYE,
    reason="GOODBYE_DELIVERED",
    title="SKILLA 인사",
    lines=("네, 다음에 필요할 때 다시 불러 주세요.",),
)

_LOCAL_RESPONSE_UTTERANCES: tuple[
    tuple[LocalResponse, frozenset[str]], ...
] = (
    (
        _SELF_INTRODUCTION,
        _SELF_INTRODUCTION_UTTERANCES,
    ),
    (
        _GREETING,
        frozenset({"안녕", "안녕하세요", "반가워", "반가워요", "좋은아침", "좋은아침이야"}),
    ),
    (
        _CAPABILITY_OVERVIEW,
        frozenset(
            {
                "뭐할수있어",
                "무엇을할수있어",
                "어떤기능이있어",
                "할수있는게뭐야",
                "기능알려줘",
                "기능을알려줘",
            }
        ),
    ),
    (
        _THANKS,
        frozenset({"고마워", "고맙다", "고마워요", "감사합니다", "수고했어", "잘했어"}),
    ),
    (
        _GOODBYE,
        frozenset({"잘가", "또보자", "다음에보자", "잘자", "다음에봐"}),
    ),
)


class LocalResponseRouter:
    """Resolve a narrow allowlist of conversational requests without a model call."""

    def resolve(self, text: str) -> LocalResponse | None:
        normalized = _normalize_utterance(text)
        candidates = (normalized, normalized.removeprefix("스킬라"))
        for response, utterances in _LOCAL_RESPONSE_UTTERANCES:
            if any(candidate in utterances for candidate in candidates):
                return response.model_copy(deep=True)
        return None


def _normalize_utterance(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return "".join(
        character.casefold()
        for character in unicodedata.normalize("NFKC", text)
        if not character.isspace()
        and not unicodedata.category(character).startswith(("P", "S"))
    )
