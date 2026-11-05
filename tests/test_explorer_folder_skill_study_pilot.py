from __future__ import annotations

from pathlib import Path

import pytest

from skilla_core import Action, Plan, Postcondition
from skilla_core.runtime_models import ExecutionResult
from skilla_core.skill_study import SkillStudyCondition
from tools.run_explorer_folder_skill_study_pilot import (
    MARKER_CONTENT,
    MARKER_NAME,
    RELATIVE_PATH,
    ROOT_ID,
    _close_execution_window,
    _condition_context,
    _goal,
    _marker_sha256,
    _registry,
    _validate_exact_plan,
    _write_fixture,
)


def _plan(target_identity: str) -> Plan:
    return Plan(
        goal=_goal(),
        steps=(
            Action(
                capability_id="explorer.folder.open",
                arguments={"root_id": ROOT_ID, "relative_path": RELATIVE_PATH},
                purpose="open the exact authorized folder",
                target_identity=target_identity,
                expected_postconditions=(
                    Postcondition(predicate="explorer.folder.verified"),
                ),
            ),
        ),
    )


def test_explorer_skill_fixture_is_exact_and_hashable(tmp_path: Path) -> None:
    folder = _write_fixture(tmp_path)

    assert folder == tmp_path / RELATIVE_PATH
    assert (folder / MARKER_NAME).read_bytes() == MARKER_CONTENT
    assert len(_marker_sha256(folder)) == 64


def test_explorer_skill_registry_has_only_folder_open() -> None:
    assert [item.capability_id for item in _registry().list()] == [
        "explorer.folder.open"
    ]


def test_explorer_skill_contexts_change_only_intervention() -> None:
    target = "explorer-folder:" + "a" * 64
    contexts = {
        condition: _condition_context(condition, target)
        for condition in SkillStudyCondition
    }
    common = contexts[SkillStudyCondition.SK0_NO_SKILL]["authorized_folder"]

    assert all(context["authorized_folder"] == common for context in contexts.values())
    assert set(contexts[SkillStudyCondition.SK0_NO_SKILL]) == {"authorized_folder"}
    assert "stored_instruction" in contexts[SkillStudyCondition.SK1_STORED_INSTRUCTION]
    assert "initial_skill" in contexts[SkillStudyCondition.SK2_INITIAL_SKILL]
    assert "revised_skill" in contexts[SkillStudyCondition.SK3_REVISED_SKILL]


@pytest.mark.parametrize(
    "change",
    ("goal", "extra", "capability", "arguments", "target", "postcondition", "continue"),
)
def test_explorer_skill_plan_guard_rejects_drift(change: str) -> None:
    target = "explorer-folder:" + "b" * 64
    plan = _plan(target)
    action = plan.steps[0]
    if change == "goal":
        plan = plan.model_copy(update={"goal": "wrong"})
    elif change == "extra":
        plan = plan.model_copy(update={"steps": (action, action.model_copy())})
    elif change == "capability":
        plan = plan.model_copy(
            update={"steps": (action.model_copy(update={"capability_id": "file.list"}),)}
        )
    elif change == "arguments":
        plan = plan.model_copy(
            update={
                "steps": (
                    action.model_copy(
                        update={
                            "arguments": {"root_id": ROOT_ID, "relative_path": "Other"}
                        }
                    ),
                )
            }
        )
    elif change == "target":
        plan = plan.model_copy(
            update={"steps": (action.model_copy(update={"target_identity": "wrong"}),)}
        )
    elif change == "postcondition":
        plan = plan.model_copy(
            update={
                "steps": (
                    action.model_copy(
                        update={
                            "expected_postconditions": (
                                Postcondition(predicate="execution.success"),
                            )
                        }
                    ),
                )
            }
        )
    else:
        plan = plan.model_copy(update={"continue_after_verification": True})

    with pytest.raises(ValueError):
        _validate_exact_plan(plan, target)


def test_explorer_skill_plan_guard_accepts_only_exact_plan() -> None:
    target = "explorer-folder:" + "c" * 64

    assert _validate_exact_plan(_plan(target), target).target_identity == target


def test_cleanup_uses_only_successful_result_hwnd() -> None:
    action = Action(
        capability_id="explorer.folder.open",
        purpose="test",
    )
    called: list[int] = []

    def close(hwnd: int) -> bool:
        called.append(hwnd)
        return True

    result = ExecutionResult(
        action_id=action.action_id,
        executor="native",
        success=True,
        observed={"hwnd": 123},
        duration_ms=1,
    )
    failed = result.model_copy(update={"success": False, "error_code": "FAILED"})

    assert _close_execution_window(result, close)
    assert not _close_execution_window(failed, close)
    assert not _close_execution_window(None, close)
    assert called == [123]
