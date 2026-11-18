from __future__ import annotations

import unicodedata
from enum import StrEnum

from pydantic import Field

from .models import FrozenModel


class LocalResponseCode(StrEnum):
    SELF_INTRODUCTION = "SELF_INTRODUCTION"


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


class LocalResponseRouter:
    """Resolve a narrow allowlist of conversational requests without a model call."""

    def resolve(self, text: str) -> LocalResponse | None:
        normalized = _normalize_utterance(text)
        if normalized in _SELF_INTRODUCTION_UTTERANCES:
            return _SELF_INTRODUCTION.model_copy(deep=True)
        if normalized.startswith("스킬라"):
            without_wake_name = normalized.removeprefix("스킬라")
            if without_wake_name in _SELF_INTRODUCTION_UTTERANCES:
                return _SELF_INTRODUCTION.model_copy(deep=True)
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
