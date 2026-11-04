from __future__ import annotations

from pathlib import Path

import pytest

from javis_core import Action, Plan, Postcondition
from javis_core.skill_study import SkillStudyCondition
from tools.run_folder_inventory_skill_study_pilot import (
    EXPECTED_NAMES,
    MODEL_CONFIGURATION,
    _condition_context,
    _goal,
    _validate_exact_plan,
    _write_fixture,
)


def _plan(root: Path) -> Plan:
    return Plan(
        goal=_goal(),
        steps=(
            Action(
                capability_id="file.list",
                arguments={"path": str(root)},
                purpose="list the exact authorized folder",
                target_identity=str(root),
                expected_postconditions=(
                    Postcondition(predicate="execution.success"),
                ),
            ),
        ),
    )


def test_inventory_fixture_is_exact_and_deterministic(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    assert tuple(sorted(path.name for path in tmp_path.iterdir())) == EXPECTED_NAMES


def test_inventory_recorded_model_configuration_matches_transport_limit() -> None:
    assert MODEL_CONFIGURATION["max_tokens"] == 1_000


def test_inventory_contexts_change_only_the_skill_intervention(tmp_path: Path) -> None:
    contexts = {
        condition: _condition_context(condition, tmp_path)
        for condition in SkillStudyCondition
    }
    common = contexts[SkillStudyCondition.SK0_NO_SKILL]["authorized_folder"]

    assert all(context["authorized_folder"] == common for context in contexts.values())
    assert set(contexts[SkillStudyCondition.SK0_NO_SKILL]) == {"authorized_folder"}
    assert "stored_instruction" in contexts[SkillStudyCondition.SK1_STORED_INSTRUCTION]
    assert "initial_skill" in contexts[SkillStudyCondition.SK2_INITIAL_SKILL]
    assert "revised_skill" in contexts[SkillStudyCondition.SK3_REVISED_SKILL]


def test_inventory_plan_guard_accepts_only_exact_read_only_action(
    tmp_path: Path,
) -> None:
    action = _validate_exact_plan(_plan(tmp_path), tmp_path)

    assert action.capability_id == "file.list"


@pytest.mark.parametrize("change", ("path", "capability", "continuation", "extra"))
def test_inventory_plan_guard_rejects_drift(tmp_path: Path, change: str) -> None:
    plan = _plan(tmp_path)
    action = plan.steps[0]
    if change == "path":
        plan = plan.model_copy(
            update={
                "steps": (
                    action.model_copy(update={"arguments": {"path": "C:/wrong"}}),
                )
            }
        )
    elif change == "capability":
        plan = plan.model_copy(
            update={"steps": (action.model_copy(update={"capability_id": "file.move"}),)}
        )
    elif change == "continuation":
        plan = plan.model_copy(update={"continue_after_verification": True})
    else:
        plan = plan.model_copy(update={"steps": (action, action.model_copy())})

    with pytest.raises(ValueError):
        _validate_exact_plan(plan, tmp_path)
