from pathlib import Path

import pytest

from skilla_core import LocalSkillCatalog, SkillProposal, SkillStatus, default_registry
from skilla_core.skill_candidate_evaluation import (
    SkillCandidateDecision,
    SkillCandidateEvaluationError,
)
from skilla_core.skill_candidate_runner import (
    SkillCandidateRunMeasurement,
    collect_revision_candidate_trials,
    evaluate_catalog_revision_candidate,
)
from skilla_core.skill_runtime import SkillRecord

HASH = "a" * 64


def proposal(*, capabilities: tuple[str, ...] = ("file.list", "file.move")) -> SkillProposal:
    return SkillProposal(
        key="weekly-file-sort",
        title="주간 파일 정리",
        description="주간 파일을 과목 폴더로 정리",
        triggers=("과제 정리",),
        procedure=("목록 확인", "분류", "이동", "검증"),
        allowed_capabilities=capabilities,
    )


class Runner:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []
        self.mismatch = False

    def run(self, skill: SkillRecord, block_id: str) -> SkillCandidateRunMeasurement:
        self.calls.append((skill.version, block_id))
        return SkillCandidateRunMeasurement(
            block_id="wrong" if self.mismatch else block_id,
            skill_id=skill.skill_id,
            skill_version=skill.version,
            succeeded=True,
            elapsed_ms=100 if skill.version == 1 else 90,
            total_tokens=100 if skill.version == 1 else 80,
            model_configuration_sha256=HASH,
            tool_surface_sha256=HASH,
            initial_state_sha256=HASH,
            evidence_sha256=("b" if skill.version == 1 else "c") * 64,
        )


def catalog_pair(tmp_path: Path) -> tuple[LocalSkillCatalog, SkillRecord, SkillRecord]:
    catalog = LocalSkillCatalog((tmp_path / "skills.sqlite3").resolve(), default_registry())
    baseline = catalog.approve(catalog.propose(proposal()).skill_id)
    candidate = catalog.propose_revision(baseline.skill_id, proposal())
    return catalog, baseline, candidate


def test_catalog_candidate_runner_alternates_order_and_never_approves(
    tmp_path: Path,
) -> None:
    catalog, baseline, candidate = catalog_pair(tmp_path)
    runner = Runner()

    report = evaluate_catalog_revision_candidate(
        catalog,
        baseline.skill_id,
        candidate.skill_id,
        ("block-1", "block-2", "block-3"),
        runner,
    )

    assert runner.calls == [
        (1, "block-1"),
        (2, "block-1"),
        (2, "block-2"),
        (1, "block-2"),
        (1, "block-3"),
        (2, "block-3"),
    ]
    assert report.decision is SkillCandidateDecision.READY_FOR_HUMAN_REVIEW
    assert catalog.require(baseline.skill_id).status is SkillStatus.VERIFIED
    assert catalog.require(candidate.skill_id).status is SkillStatus.DRAFT


def test_candidate_runner_rejects_measurement_not_bound_to_schedule(
    tmp_path: Path,
) -> None:
    catalog, baseline, candidate = catalog_pair(tmp_path)
    runner = Runner()
    runner.mismatch = True

    with pytest.raises(SkillCandidateEvaluationError, match="does not match"):
        collect_revision_candidate_trials(
            catalog,
            baseline.skill_id,
            candidate.skill_id,
            ("block-1",),
            runner,
        )


def test_candidate_runner_rejects_capability_expansion(tmp_path: Path) -> None:
    catalog = LocalSkillCatalog((tmp_path / "skills.sqlite3").resolve(), default_registry())
    baseline = catalog.approve(
        catalog.propose(proposal(capabilities=("file.list",))).skill_id
    )
    candidate = catalog.propose_revision(
        baseline.skill_id,
        proposal(capabilities=("file.list", "file.move")),
    )

    with pytest.raises(SkillCandidateEvaluationError, match="expand"):
        collect_revision_candidate_trials(
            catalog,
            baseline.skill_id,
            candidate.skill_id,
            ("block-1",),
            Runner(),
        )
