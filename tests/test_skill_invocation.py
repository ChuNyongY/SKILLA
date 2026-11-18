from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from skilla_core.skill_invocation import (
    SkillInvocationError,
    bind_skill_invocation,
    skill_invocation_trusted_context,
)
from skilla_core.skill_runtime import SkillRecord, SkillStatus


def skill(*, dynamic_inputs: tuple[str, ...]) -> SkillRecord:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    return SkillRecord(
        skill_id=uuid4(),
        key="coursework-sort",
        version=4,
        status=SkillStatus.VERIFIED,
        title="과제 자료 정리",
        description="과제 파일을 과목별 폴더로 정리합니다.",
        triggers=("과제 자료 정리", "이번 주 자료 정리"),
        procedure=("파일 확인", "폴더 이동", "결과 확인"),
        dynamic_inputs=dynamic_inputs,
        decision_rules=("과목을 확정할 수 없으면 분리",),
        verification_rules=("이동 전후 파일 수 일치",),
        allowed_capabilities=("file.list", "file.move"),
        created_at=now,
        updated_at=now,
    )


def test_exact_dynamic_inputs_are_bound_in_declared_order() -> None:
    record = skill(dynamic_inputs=("현재 폴더", "이번 주 파일"))

    command = bind_skill_invocation(
        record,
        {"이번 주 파일": "  report.pdf  ", "현재 폴더": " Downloads "},
    )

    assert command.skill_id == record.skill_id
    assert command.skill_version == 4
    assert tuple(item.name for item in command.inputs) == record.dynamic_inputs
    assert command.text == (
        "과제 자료 정리 | 현재 폴더: Downloads | 이번 주 파일: report.pdf"
    )
    assert skill_invocation_trusted_context(command) == {
        "verified_skill_invocation": {
            "skill_id": str(record.skill_id),
            "skill_version": 4,
        }
    }


def test_input_free_skill_accepts_only_empty_values() -> None:
    record = skill(dynamic_inputs=())

    assert bind_skill_invocation(record, {}).text == "과제 자료 정리"
    with pytest.raises(SkillInvocationError, match="do not match"):
        bind_skill_invocation(record, {"임의 값": "금지"})


def test_missing_extra_or_empty_dynamic_input_is_rejected() -> None:
    record = skill(dynamic_inputs=("현재 폴더", "이번 주 파일"))

    with pytest.raises(SkillInvocationError, match="do not match"):
        bind_skill_invocation(record, {"현재 폴더": "Downloads"})
    with pytest.raises(SkillInvocationError, match="do not match"):
        bind_skill_invocation(
            record,
            {"현재 폴더": "Downloads", "이번 주 파일": "a.pdf", "추가": "금지"},
        )
    with pytest.raises(SkillInvocationError, match="length"):
        bind_skill_invocation(
            record,
            {"현재 폴더": "Downloads", "이번 주 파일": "   "},
        )


def test_control_characters_and_unverified_skill_are_rejected() -> None:
    record = skill(dynamic_inputs=("현재 폴더",))
    with pytest.raises(SkillInvocationError, match="control"):
        bind_skill_invocation(record, {"현재 폴더": "Down\x00loads"})
    with pytest.raises(SkillInvocationError, match="control"):
        bind_skill_invocation(record, {"현재 폴더": "Downloads\nsecret"})

    retired = record.model_copy(update={"status": SkillStatus.RETIRED})
    with pytest.raises(SkillInvocationError, match="verified"):
        bind_skill_invocation(retired, {"현재 폴더": "Downloads"})
