from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from javis_core.skill_study import SkillStudyCondition, SkillTrialObservation
from tools.bundle_skill_study import build_bundle


def _write_source(
    root: Path,
    task_id: str,
    *,
    succeeded: bool = True,
) -> tuple[Path, Path]:
    root.mkdir()
    observations: list[SkillTrialObservation] = []
    for condition in SkillStudyCondition:
        evidence = {
            "participant_id": "pilot",
            "task_id": task_id,
            "repetition": 1,
            "condition": condition.value,
            "succeeded": succeeded,
        }
        payload = json.dumps(
            evidence,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        evidence_path = root / f"evidence-pilot-{task_id}-1-{condition.value}.json"
        evidence_path.write_bytes(payload)
        observations.append(
            SkillTrialObservation(
                participant_id="pilot",
                task_id=task_id,
                repetition=1,
                condition=condition,
                succeeded=succeeded,
                elapsed_ms=10,
                llm_calls=1,
                input_tokens=10,
                output_tokens=5,
                user_interventions=0,
                run_cost_microunits=0,
                model_id="model",
                model_configuration_sha256="a" * 64,
                tool_surface_sha256=("b" if task_id == "one" else "c") * 64,
                initial_state_sha256=("d" if task_id == "one" else "e") * 64,
                outcome_evidence_sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
    observations_path = root / "observations.json"
    observations_path.write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in observations],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return observations_path.resolve(), root.resolve()


def test_bundle_copies_and_verifies_two_complete_tasks(tmp_path: Path) -> None:
    first = _write_source(tmp_path / "first", "one", succeeded=False)
    second = _write_source(tmp_path / "second", "two")
    output = tmp_path / "bundle"
    output.mkdir()

    manifest = build_bundle(output.resolve(), (first, second))

    assert manifest["tasks"] == ["one", "two"]
    assert manifest["scope"].startswith("2-task developer pilot;")
    assert manifest["observations"] == 8
    assert manifest["complete_blocks"] == 2
    assert len(manifest["evidence"]) == 8
    assert len(list((output / "evidence").iterdir())) == 8
    assert "C:\\" not in (output / "manifest.json").read_text(encoding="utf-8")
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["complete_blocks"] == 2


def test_bundle_rejects_duplicate_cells_across_sources(tmp_path: Path) -> None:
    first = _write_source(tmp_path / "first", "same")
    second = _write_source(tmp_path / "second", "same")
    output = tmp_path / "bundle"
    output.mkdir()

    with pytest.raises(ValueError, match="duplicate observation"):
        build_bundle(output.resolve(), (first, second))


def test_bundle_rejects_tampered_evidence(tmp_path: Path) -> None:
    first = _write_source(tmp_path / "first", "one")
    second = _write_source(tmp_path / "second", "two")
    target = next(first[1].glob("evidence-*.json"))
    target.write_text("{}", encoding="utf-8")
    output = tmp_path / "bundle"
    output.mkdir()

    with pytest.raises(ValueError, match="identity|hash"):
        build_bundle(output.resolve(), (first, second))


def test_bundle_rejects_extra_evidence(tmp_path: Path) -> None:
    first = _write_source(tmp_path / "first", "one")
    second = _write_source(tmp_path / "second", "two")
    (first[1] / "evidence-extra.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "bundle"
    output.mkdir()

    with pytest.raises(ValueError, match="exactly cover"):
        build_bundle(output.resolve(), (first, second))


def test_bundle_requires_two_sources(tmp_path: Path) -> None:
    first = _write_source(tmp_path / "first", "one")
    output = tmp_path / "bundle"
    output.mkdir()

    with pytest.raises(ValueError, match="at least two"):
        build_bundle(output.resolve(), (first,))
