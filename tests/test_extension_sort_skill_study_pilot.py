from __future__ import annotations

from pathlib import Path

from skilla_core import Action, Plan, PolicyDecision, RiskLevel
from skilla_core.models import Decision
from skilla_core.observation_loop import ObservationLoopResult, ObservationLoopStatus
from skilla_core.skill_study import SkillStudyCondition
from tools.run_extension_sort_skill_study_pilot import (
    CONTENTS,
    TARGET_BY_NAME,
    ExactExtensionSortApproval,
    ExactExtensionSortCompletionProbe,
    _condition_context,
    _goal,
    _listed_before_first_move,
    _write_fixture,
)


def test_extension_fixture_and_probe_verify_exact_bytes(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    probe = ExactExtensionSortCompletionProbe(tmp_path)

    assert not probe.completed(_goal(tmp_path), ())
    for name, destination in TARGET_BY_NAME.items():
        (tmp_path / destination).write_bytes((tmp_path / name).read_bytes())
        (tmp_path / name).unlink()

    assert probe.completed(_goal(tmp_path), ())
    (tmp_path / "Data" / "grades.csv").write_bytes(b"changed")
    assert not probe.completed(_goal(tmp_path), ())


def test_extension_fixture_has_three_exact_lowercase_mappings(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    assert set(CONTENTS) == set(TARGET_BY_NAME)
    assert sorted(path.name for path in tmp_path.iterdir() if path.is_file()) == [
        "grades.csv",
        "notes.txt",
        "report.pdf",
    ]
    assert sorted(path.name for path in tmp_path.iterdir() if path.is_dir()) == [
        "Data",
        "Documents",
        "Text",
    ]


def test_extension_contexts_change_only_the_skill_intervention(tmp_path: Path) -> None:
    contexts = {
        condition: _condition_context(condition, tmp_path)
        for condition in SkillStudyCondition
    }

    assert all(context["authorized_root"] == str(tmp_path) for context in contexts.values())
    assert set(contexts[SkillStudyCondition.SK0_NO_SKILL]) == {"authorized_root"}
    assert "stored_instruction" in contexts[SkillStudyCondition.SK1_STORED_INSTRUCTION]
    assert "initial_skill" in contexts[SkillStudyCondition.SK2_INITIAL_SKILL]
    assert "revised_skill" in contexts[SkillStudyCondition.SK3_REVISED_SKILL]


def _move_action(source: Path, destination: Path) -> Action:
    return Action(
        capability_id="file.move",
        arguments={"source": str(source), "destination": str(destination)},
        purpose="move one exact fixture file",
        target_identity=str(source),
    )


def test_extension_approval_accepts_only_exact_mapping(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    broker = ExactExtensionSortApproval(tmp_path)
    decision = PolicyDecision(
        decision=Decision.YELLOW,
        risk=RiskLevel.R2,
        reasons=("test",),
        requires_strong_auth=False,
    )
    valid = _move_action(tmp_path / "grades.csv", tmp_path / "Data" / "grades.csv")
    wrong = _move_action(tmp_path / "notes.txt", tmp_path / "Data" / "notes.txt")

    assert broker.approve_yellow(Plan(goal="test", steps=(valid,)), valid, decision)
    assert not broker.approve_yellow(Plan(goal="test", steps=(wrong,)), wrong, decision)
    assert broker.approvals == 1


def test_extension_approval_rejects_symlink_escape_when_supported(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    _write_fixture(tmp_path)
    link = tmp_path / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        return
    broker = ExactExtensionSortApproval(tmp_path)
    action = _move_action(tmp_path / "report.pdf", link / "report.pdf")
    decision = PolicyDecision(
        decision=Decision.YELLOW,
        risk=RiskLevel.R2,
        reasons=("test",),
        requires_strong_auth=False,
    )

    assert not broker.approve_yellow(Plan(goal="test", steps=(action,)), action, decision)


def test_observe_first_check_rejects_move_before_list() -> None:
    list_action = Action(
        capability_id="file.list",
        arguments={"path": "C:/fixture"},
        purpose="list",
        target_identity="C:/fixture",
    )
    move_action = Action(
        capability_id="file.move",
        arguments={"source": "C:/fixture/a", "destination": "C:/fixture/b"},
        purpose="move",
        target_identity="C:/fixture/a",
    )
    ordered = ObservationLoopResult(
        status=ObservationLoopStatus.COMPLETED,
        reason="GOAL_POSTCONDITIONS_VERIFIED",
        rounds=2,
        observations=(),
        executed_plans=(
            Plan(goal="g", steps=(list_action,)),
            Plan(goal="g", steps=(move_action,)),
        ),
    )
    reversed_result = ordered.model_copy(
        update={"executed_plans": tuple(reversed(ordered.executed_plans))}
    )

    assert _listed_before_first_move(ordered)
    assert not _listed_before_first_move(reversed_result)
