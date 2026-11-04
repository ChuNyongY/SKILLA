from uuid import uuid4

import pytest

from javis_core import Action, ActionStatus, Plan, TaskOutcome
from javis_core.skill_runtime import SkillOutcome
from javis_core.skill_trace import SkillTraceError, build_skill_execution_trace


def plan() -> Plan:
    return Plan(
        goal="민감할 수 있는 실제 요청",
        steps=(
            Action(capability_id="file.list", purpose="목록 확인", arguments={"path": "secret"}),
            Action(capability_id="file.move", purpose="이동", arguments={"source": "secret"}),
        ),
    )


def test_successful_outcome_becomes_verified_trace_without_raw_arguments() -> None:
    task = plan()
    trace = build_skill_execution_trace(
        task,
        TaskOutcome(
            task_id=task.task_id,
            status=ActionStatus.SUCCEEDED,
            completed_actions=2,
            reason="ALL_ACTIONS_VERIFIED",
        ),
        goal_summary="주간 자료 정리",
    )
    assert trace.outcome is SkillOutcome.SUCCEEDED
    assert all(step.independently_verified for step in trace.steps)
    serialized = trace.model_dump_json()
    assert "secret" not in serialized
    assert "민감할 수 있는 실제 요청" not in serialized


def test_aborted_outcome_keeps_only_completed_and_attempted_steps() -> None:
    task = plan()
    trace = build_skill_execution_trace(
        task,
        TaskOutcome(
            task_id=task.task_id,
            status=ActionStatus.ABORTED,
            completed_actions=1,
            reason="TARGET_NOT_FOUND",
        ),
        goal_summary="주간 자료 정리",
    )
    assert tuple(step.outcome for step in trace.steps) == (
        SkillOutcome.SUCCEEDED,
        SkillOutcome.ABORTED,
    )
    assert trace.steps[0].independently_verified
    assert not trace.steps[1].independently_verified


def test_trace_rejects_inconsistent_or_nonterminal_outcome() -> None:
    task = plan()
    with pytest.raises(SkillTraceError):
        build_skill_execution_trace(
            task,
            TaskOutcome(
                task_id=uuid4(),
                status=ActionStatus.SUCCEEDED,
                completed_actions=2,
                reason="ALL_ACTIONS_VERIFIED",
            ),
            goal_summary="정리",
        )
    with pytest.raises(SkillTraceError):
        build_skill_execution_trace(
            task,
            TaskOutcome(
                task_id=task.task_id,
                status=ActionStatus.EXECUTING,
                completed_actions=0,
                reason="NOT_TERMINAL",
            ),
            goal_summary="정리",
        )
