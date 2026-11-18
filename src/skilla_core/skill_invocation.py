from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from pydantic import Field, model_validator

from .models import FrozenModel
from .skill_runtime import SkillRecord, SkillStatus

SKILL_INVOCATION_CONTEXT_KEY = "verified_skill_invocation"


class SkillInvocationError(RuntimeError):
    pass


class SkillInputValue(FrozenModel):
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def reject_control_characters(self) -> SkillInputValue:
        if any(unicodedata.category(character).startswith("C") for character in self.value):
            raise ValueError("skill input contains a control character")
        return self


class SkillInvocationCommand(FrozenModel):
    skill_id: UUID
    skill_version: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2_000)
    inputs: tuple[SkillInputValue, ...] = Field(max_length=20)


class SkillInputCollector(Protocol):
    def __call__(self, skill: SkillRecord) -> Mapping[str, str] | None: ...


def bind_skill_invocation(
    skill: SkillRecord,
    values: Mapping[str, str],
) -> SkillInvocationCommand:
    """Bind exact, user-supplied dynamic values to one verified skill invocation."""

    if skill.status is not SkillStatus.VERIFIED:
        raise SkillInvocationError("skill invocation requires a verified skill")
    expected = tuple(skill.dynamic_inputs)
    if set(values) != set(expected) or len(values) != len(expected):
        raise SkillInvocationError("skill invocation inputs do not match the skill")
    inputs = tuple(
        SkillInputValue(name=name, value=_normalized_value(values[name]))
        for name in expected
    )
    trigger = skill.triggers[0].strip()
    suffix = " | ".join(f"{item.name}: {item.value}" for item in inputs)
    text = trigger if not suffix else f"{trigger} | {suffix}"
    if len(text) > 2_000:
        raise SkillInvocationError("skill invocation command is too long")
    return SkillInvocationCommand(
        skill_id=skill.skill_id,
        skill_version=skill.version,
        text=text,
        inputs=inputs,
    )


def skill_invocation_trusted_context(
    command: SkillInvocationCommand,
) -> dict[str, object]:
    """Bind one internal invocation to the exact reviewed skill version."""

    return {
        SKILL_INVOCATION_CONTEXT_KEY: {
            "skill_id": str(command.skill_id),
            "skill_version": command.skill_version,
        }
    }


def collect_tk_skill_inputs(skill: SkillRecord) -> Mapping[str, str] | None:
    """Ask only for declared dynamic inputs; cancellation leaves the suggestion pending."""

    if not skill.dynamic_inputs:
        return {}
    try:
        from tkinter import simpledialog
    except ImportError as error:
        raise SkillInvocationError("tkinter skill input dialog is unavailable") from error
    values: dict[str, str] = {}
    for name in skill.dynamic_inputs:
        value = simpledialog.askstring(
            "SKILLA 실행 입력",
            f"{skill.title}\n\n{name}",
        )
        if value is None:
            return None
        values[name] = value
    return values


def _normalized_value(value: str) -> str:
    if not isinstance(value, str):
        raise SkillInvocationError("skill input must be text")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise SkillInvocationError("skill input contains a control character")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 200:
        raise SkillInvocationError("skill input length is invalid")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise SkillInvocationError("skill input contains a control character")
    return normalized
