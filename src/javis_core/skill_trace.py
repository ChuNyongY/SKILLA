from __future__ import annotations

from .models import ActionStatus, Plan
from .runtime_models import TaskOutcome
from .skill_authoring import SkillExecutionTrace, SkillTraceStep
from .skill_runtime import SkillOutcome


class SkillTraceError(ValueError):
    pass


def build_skill_execution_trace(
    plan: Plan,
    outcome: TaskOutcome,
    *,
    goal_summary: str,
) -> SkillExecutionTrace:
    """Convert verified orchestration state without copying action arguments."""

    if plan.task_id != outcome.task_id:
        raise SkillTraceError("plan and outcome task identifiers differ")
    if outcome.completed_actions > len(plan.steps):
        raise SkillTraceError("completed action count exceeds the plan")
    if outcome.status is ActionStatus.SUCCEEDED:
        if outcome.completed_actions != len(plan.steps):
            raise SkillTraceError("successful outcome must complete every plan action")
        trace_outcome = SkillOutcome.SUCCEEDED
        included = len(plan.steps)
    elif outcome.status is ActionStatus.ABORTED:
        trace_outcome = SkillOutcome.ABORTED
        included = min(outcome.completed_actions + 1, len(plan.steps))
    elif outcome.status is ActionStatus.FAILED:
        trace_outcome = SkillOutcome.FAILED
        included = min(outcome.completed_actions + 1, len(plan.steps))
    else:
        raise SkillTraceError("outcome is not terminal")

    steps = []
    for index, action in enumerate(plan.steps[:included]):
        completed = index < outcome.completed_actions
        steps.append(
            SkillTraceStep(
                sequence=index + 1,
                capability_id=action.capability_id,
                outcome=SkillOutcome.SUCCEEDED if completed else trace_outcome,
                detail_code=(
                    "POSTCONDITIONS_VERIFIED" if completed else outcome.reason[:80]
                ),
                independently_verified=completed,
            )
        )
    if not steps:
        raise SkillTraceError("terminal trace must contain an attempted action")
    return SkillExecutionTrace(
        goal_summary=goal_summary,
        outcome=trace_outcome,
        steps=tuple(steps),
        dynamic_input_labels=tuple(
            f"step_{index}_runtime_arguments" for index in range(1, len(steps) + 1)
        ),
        verification_notes=("각 단계는 실행 후 독립 검증 결과로 판정한다.",),
    )
