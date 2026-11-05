import argparse
import hashlib
import json
from pathlib import Path

import pytest

from skilla_core.skill_study import SkillStudyCondition
from tools.run_skill_study_pilot import (
    _bounded_repetitions,
    _condition_context,
    _validated_output_directory,
    _write_evidence_exclusive,
    _write_report_atomic,
)


def test_repetition_argument_is_bounded_before_any_trial_runs() -> None:
    assert _bounded_repetitions("3") == 3
    with pytest.raises(argparse.ArgumentTypeError, match="within 1..100"):
        _bounded_repetitions("0")
    with pytest.raises(argparse.ArgumentTypeError, match="within 1..100"):
        _bounded_repetitions("101")
    with pytest.raises(argparse.ArgumentTypeError, match="must be an integer"):
        _bounded_repetitions("three")


def test_condition_contexts_keep_the_four_interventions_distinct(
    tmp_path: Path,
) -> None:
    contexts = {
        condition: _condition_context(condition, tmp_path)
        for condition in SkillStudyCondition
    }

    assert contexts[SkillStudyCondition.SK0_NO_SKILL] == {
        "authorized_root": str(tmp_path)
    }
    assert "stored_instruction" in contexts[SkillStudyCondition.SK1_STORED_INSTRUCTION]
    assert "initial_skill" in contexts[SkillStudyCondition.SK2_INITIAL_SKILL]
    assert "revised_skill" in contexts[SkillStudyCondition.SK3_REVISED_SKILL]


def test_output_directory_accepts_only_owned_resume_files(tmp_path: Path) -> None:
    assert _validated_output_directory(str(tmp_path.resolve())) == tmp_path.resolve()
    (tmp_path / "ledger.jsonl").write_text("", encoding="utf-8")
    assert _validated_output_directory(str(tmp_path.resolve())) == tmp_path.resolve()

    (tmp_path / "foreign.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown or unsafe"):
        _validated_output_directory(str(tmp_path.resolve()))


def test_report_write_is_atomic_and_replaces_only_exact_target(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    _write_report_atomic(report, '{"complete":false}')
    _write_report_atomic(report, '{"complete":true}')

    assert json.loads(report.read_text(encoding="utf-8")) == {"complete": True}
    assert list(tmp_path.iterdir()) == [report]


def test_evidence_write_returns_file_hash_and_never_overwrites(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence-pilot.json"
    digest = _write_evidence_exclusive(evidence, {"succeeded": True})

    assert digest == hashlib.sha256(evidence.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="already exists"):
        _write_evidence_exclusive(evidence, {"succeeded": False})
