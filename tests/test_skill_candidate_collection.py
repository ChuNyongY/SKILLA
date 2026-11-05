import json
from pathlib import Path

import pytest

from skilla_core import LocalSkillCatalog, SkillProposal, default_registry
from skilla_core.skill_candidate_collection import SkillCandidateCollector
from skilla_core.skill_candidate_evaluation import (
    SkillCandidateDecision,
    SkillCandidateEvaluationError,
)
from skilla_core.skill_candidate_runner import SkillCandidateRunMeasurement
from skilla_core.skill_runtime import SkillRecord

HASH = "a" * 64


class Runner:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def run(self, skill: SkillRecord, block_id: str) -> SkillCandidateRunMeasurement:
        self.calls.append((skill.version, block_id))
        return SkillCandidateRunMeasurement(
            block_id=block_id,
            skill_id=skill.skill_id,
            skill_version=skill.version,
            succeeded=True,
            elapsed_ms=100,
            total_tokens=100,
            model_configuration_sha256=HASH,
            tool_surface_sha256=HASH,
            initial_state_sha256=HASH,
            evidence_sha256=("b" if skill.version == 1 else "c") * 64,
        )


def pair(tmp_path: Path) -> tuple[LocalSkillCatalog, SkillRecord, SkillRecord]:
    catalog = LocalSkillCatalog((tmp_path / "skills.sqlite3").resolve(), default_registry())
    proposal = SkillProposal(
        key="weekly-file-sort",
        title="주간 파일 정리",
        description="주간 파일 분류",
        triggers=("과제 정리",),
        procedure=("목록", "이동", "검증"),
        allowed_capabilities=("file.list", "file.move"),
    )
    baseline = catalog.approve(catalog.propose(proposal).skill_id)
    candidate = catalog.propose_revision(baseline.skill_id, proposal)
    return catalog, baseline, candidate


def test_candidate_collector_resumes_exact_schedule_and_alternates_order(
    tmp_path: Path,
) -> None:
    catalog, baseline, candidate = pair(tmp_path)
    ledger = (tmp_path / "candidate.jsonl").resolve()
    blocks = ("block-1", "block-2", "block-3")
    first_runner = Runner()
    collector = SkillCandidateCollector(
        catalog, baseline.skill_id, candidate.skill_id, blocks, ledger
    )
    collector.collect_next(first_runner)
    assert first_runner.calls == [(1, "block-1"), (2, "block-1")]

    runner = Runner()
    resumed = SkillCandidateCollector(
        catalog, baseline.skill_id, candidate.skill_id, blocks, ledger
    )
    resumed.collect_next(runner)
    resumed.collect_next(runner)
    assert runner.calls == [
        (2, "block-2"),
        (1, "block-2"),
        (1, "block-3"),
        (2, "block-3"),
    ]
    assert resumed.complete
    assert resumed.evaluate().decision is SkillCandidateDecision.READY_FOR_HUMAN_REVIEW
    export = (tmp_path / "trials.json").resolve()
    resumed.export_trials(export)
    assert len(json.loads(export.read_text(encoding="utf-8"))) == 3


def test_candidate_collector_refuses_incomplete_export_and_evaluation(
    tmp_path: Path,
) -> None:
    catalog, baseline, candidate = pair(tmp_path)
    collector = SkillCandidateCollector(
        catalog,
        baseline.skill_id,
        candidate.skill_id,
        ("block-1", "block-2", "block-3"),
        (tmp_path / "candidate.jsonl").resolve(),
    )

    with pytest.raises(SkillCandidateEvaluationError, match="incomplete"):
        collector.evaluate()
    with pytest.raises(SkillCandidateEvaluationError, match="incomplete"):
        collector.export_trials((tmp_path / "trials.json").resolve())


def test_candidate_collector_rejects_schedule_drift_on_resume(tmp_path: Path) -> None:
    catalog, baseline, candidate = pair(tmp_path)
    ledger = (tmp_path / "candidate.jsonl").resolve()
    collector = SkillCandidateCollector(
        catalog,
        baseline.skill_id,
        candidate.skill_id,
        ("block-1",),
        ledger,
    )
    collector.collect_next(Runner())

    with pytest.raises(SkillCandidateEvaluationError, match="fixed schedule"):
        SkillCandidateCollector(
            catalog,
            baseline.skill_id,
            candidate.skill_id,
            ("different-block",),
            ledger,
        )


def test_candidate_collector_rejects_internal_blank_ledger_record(
    tmp_path: Path,
) -> None:
    catalog, baseline, candidate = pair(tmp_path)
    ledger = (tmp_path / "candidate.jsonl").resolve()
    collector = SkillCandidateCollector(
        catalog,
        baseline.skill_id,
        candidate.skill_id,
        ("block-1",),
        ledger,
    )
    collector.collect_next(Runner())
    ledger.write_text(ledger.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")

    with pytest.raises(SkillCandidateEvaluationError, match="invalid"):
        SkillCandidateCollector(
            catalog,
            baseline.skill_id,
            candidate.skill_id,
            ("block-1",),
            ledger,
        )
