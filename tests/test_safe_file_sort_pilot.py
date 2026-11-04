from pathlib import Path

from javis_core import Action, Plan, PolicyDecision, RiskLevel
from javis_core.models import Decision
from tools.run_safe_file_sort_pilot import (
    ExactFileSortCompletionProbe,
    SandboxYellowApproval,
    _pilot_registry,
)


def _decision() -> PolicyDecision:
    return PolicyDecision(
        decision=Decision.YELLOW,
        risk=RiskLevel.R2,
        reasons=("CAPABILITY_FLOOR_R2",),
    )


def _move(source: Path, destination: Path) -> tuple[Plan, Action]:
    action = Action(
        capability_id="file.move",
        arguments={"source": str(source), "destination": str(destination)},
        purpose="sandbox move",
        target_identity=str(source.resolve()),
    )
    return Plan(goal="move", steps=(action,)), action


def test_pilot_registry_exposes_only_list_and_move() -> None:
    assert {item.capability_id for item in _pilot_registry().list()} == {
        "file.list",
        "file.move",
    }


def test_sandbox_approval_rejects_destination_outside_root(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    plan, action = _move(source, outside / "source.txt")

    assert not SandboxYellowApproval(tmp_path).approve_yellow(
        plan, action, _decision()
    )


def test_completion_probe_checks_absence_location_and_contents(tmp_path: Path) -> None:
    (tmp_path / "math").mkdir()
    (tmp_path / "english").mkdir()
    (tmp_path / "math" / "math_week1.txt").write_text("algebra", encoding="utf-8")
    (tmp_path / "english" / "english_week1.txt").write_text("essay", encoding="utf-8")

    probe = ExactFileSortCompletionProbe(tmp_path)
    assert probe.completed("sort", ())

    (tmp_path / "math" / "math_week1.txt").write_text("changed", encoding="utf-8")
    assert not probe.completed("sort", ())
