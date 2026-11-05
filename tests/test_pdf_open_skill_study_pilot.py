from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from skilla_core import Action, Plan, Postcondition
from skilla_core.skill_study import SkillStudyCondition
from tools.run_pdf_open_skill_study_pilot import (
    PDF_NAME,
    _condition_context,
    _goal,
    _validate_exact_plan,
)
from tools.s03_memory_pdf_smoke import _write_minimal_pdf


def _fixture(tmp_path: Path) -> tuple[Path, str]:
    document = tmp_path / PDF_NAME
    _write_minimal_pdf(document)
    return document, hashlib.sha256(document.read_bytes()).hexdigest()


def _plan(document: Path, digest: str) -> Plan:
    return Plan(
        goal=_goal(),
        steps=(
            Action(
                capability_id="file.open",
                arguments={
                    "path": str(document),
                    "sha256": digest,
                    "viewer_app_id": "edge",
                },
                purpose="open exact study PDF",
                target_identity=f"file-sha256:{digest}",
                expected_postconditions=(Postcondition(predicate="file.opened"),),
            ),
        ),
    )


def test_pdf_fixture_is_byte_identical_across_fresh_directories(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    _, first_hash = _fixture(first)
    _, second_hash = _fixture(second)

    assert first_hash == second_hash


def test_condition_contexts_change_only_the_skill_intervention(tmp_path: Path) -> None:
    document, digest = _fixture(tmp_path)
    contexts = {
        condition: _condition_context(condition, document, digest)
        for condition in SkillStudyCondition
    }
    common = contexts[SkillStudyCondition.SK0_NO_SKILL]["authorized_pdf"]

    assert all(context["authorized_pdf"] == common for context in contexts.values())
    assert set(contexts[SkillStudyCondition.SK0_NO_SKILL]) == {"authorized_pdf"}
    assert "stored_instruction" in contexts[SkillStudyCondition.SK1_STORED_INSTRUCTION]
    assert "initial_skill" in contexts[SkillStudyCondition.SK2_INITIAL_SKILL]
    assert "revised_skill" in contexts[SkillStudyCondition.SK3_REVISED_SKILL]


def test_exact_plan_guard_accepts_only_one_fully_bound_open(tmp_path: Path) -> None:
    document, digest = _fixture(tmp_path)

    action = _validate_exact_plan(_plan(document, digest), document, digest)

    assert action.arguments["sha256"] == digest


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ("path", "immutable binding"),
        ("target", "immutable binding"),
        ("continuation", "immutable binding"),
        ("extra-step", "exactly one action"),
    ),
)
def test_exact_plan_guard_rejects_drift(
    tmp_path: Path,
    change: str,
    message: str,
) -> None:
    document, digest = _fixture(tmp_path)
    plan = _plan(document, digest)
    action = plan.steps[0]
    if change == "path":
        plan = plan.model_copy(
            update={
                "steps": (
                    action.model_copy(
                        update={"arguments": {**action.arguments, "path": "C:/wrong.pdf"}}
                    ),
                )
            }
        )
    elif change == "target":
        plan = plan.model_copy(
            update={"steps": (action.model_copy(update={"target_identity": str(document)}),)}
        )
    elif change == "continuation":
        plan = plan.model_copy(update={"continue_after_verification": True})
    else:
        plan = plan.model_copy(update={"steps": (action, action.model_copy())})

    with pytest.raises(ValueError, match=message):
        _validate_exact_plan(plan, document, digest)
