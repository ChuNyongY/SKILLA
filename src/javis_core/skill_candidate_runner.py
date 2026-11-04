from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import Field

from .models import FrozenModel
from .skill_candidate_evaluation import (
    SkillCandidateEvaluation,
    SkillCandidateEvaluationError,
    SkillCandidateTrial,
    evaluate_revision_candidate,
)
from .skill_runtime import LocalSkillCatalog, SkillRecord, SkillStatus


class SkillCandidateRunMeasurement(FrozenModel):
    block_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    skill_id: UUID
    skill_version: int = Field(ge=1)
    succeeded: bool
    elapsed_ms: int = Field(ge=0, le=86_400_000)
    total_tokens: int = Field(ge=0, le=100_000_000)
    model_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_surface_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SkillCandidateConditionRunner(Protocol):
    def run(
        self,
        skill: SkillRecord,
        block_id: str,
    ) -> SkillCandidateRunMeasurement: ...


def collect_revision_candidate_trials(
    catalog: LocalSkillCatalog,
    baseline_skill_id: UUID,
    candidate_skill_id: UUID,
    block_ids: tuple[str, ...],
    runner: SkillCandidateConditionRunner,
    *,
    start_index: int = 0,
) -> tuple[SkillCandidateTrial, ...]:
    baseline, candidate = validate_revision_candidate_pair(
        catalog,
        baseline_skill_id,
        candidate_skill_id,
    )
    if (
        not block_ids
        or len(block_ids) > 10_000
        or len(set(block_ids)) != len(block_ids)
        or start_index < 0
    ):
        raise SkillCandidateEvaluationError(
            "candidate block identifiers must be non-empty and unique"
        )
    trials: list[SkillCandidateTrial] = []
    for index, block_id in enumerate(block_ids, start=start_index):
        baseline_first = index % 2 == 0
        if baseline_first:
            baseline_result = runner.run(baseline, block_id)
            candidate_result = runner.run(candidate, block_id)
        else:
            candidate_result = runner.run(candidate, block_id)
            baseline_result = runner.run(baseline, block_id)
        _validate_measurement(baseline, block_id, baseline_result)
        _validate_measurement(candidate, block_id, candidate_result)
        trials.append(
            SkillCandidateTrial(
                block_id=block_id,
                baseline_skill_id=baseline.skill_id,
                candidate_skill_id=candidate.skill_id,
                baseline_executed_first=baseline_first,
                baseline_succeeded=baseline_result.succeeded,
                candidate_succeeded=candidate_result.succeeded,
                baseline_elapsed_ms=baseline_result.elapsed_ms,
                candidate_elapsed_ms=candidate_result.elapsed_ms,
                baseline_tokens=baseline_result.total_tokens,
                candidate_tokens=candidate_result.total_tokens,
                baseline_model_configuration_sha256=(
                    baseline_result.model_configuration_sha256
                ),
                candidate_model_configuration_sha256=(
                    candidate_result.model_configuration_sha256
                ),
                baseline_tool_surface_sha256=baseline_result.tool_surface_sha256,
                candidate_tool_surface_sha256=candidate_result.tool_surface_sha256,
                baseline_initial_state_sha256=baseline_result.initial_state_sha256,
                candidate_initial_state_sha256=candidate_result.initial_state_sha256,
                baseline_evidence_sha256=baseline_result.evidence_sha256,
                candidate_evidence_sha256=candidate_result.evidence_sha256,
            )
        )
    return tuple(trials)


def evaluate_catalog_revision_candidate(
    catalog: LocalSkillCatalog,
    baseline_skill_id: UUID,
    candidate_skill_id: UUID,
    block_ids: tuple[str, ...],
    runner: SkillCandidateConditionRunner,
    *,
    minimum_trials: int = 3,
    maximum_elapsed_ratio: float = 1.25,
    maximum_token_ratio: float = 1.25,
) -> SkillCandidateEvaluation:
    trials = collect_revision_candidate_trials(
        catalog,
        baseline_skill_id,
        candidate_skill_id,
        block_ids,
        runner,
    )
    return evaluate_revision_candidate(
        trials,
        minimum_trials=minimum_trials,
        maximum_elapsed_ratio=maximum_elapsed_ratio,
        maximum_token_ratio=maximum_token_ratio,
    )


def validate_revision_candidate_pair(
    catalog: LocalSkillCatalog,
    baseline_skill_id: UUID,
    candidate_skill_id: UUID,
) -> tuple[SkillRecord, SkillRecord]:
    baseline = catalog.require(baseline_skill_id)
    candidate = catalog.require(candidate_skill_id)
    if baseline.status is not SkillStatus.VERIFIED:
        raise SkillCandidateEvaluationError("candidate baseline must be verified")
    if candidate.status is not SkillStatus.DRAFT:
        raise SkillCandidateEvaluationError("revision candidate must remain a draft")
    if (
        candidate.supersedes_skill_id != baseline.skill_id
        or candidate.key != baseline.key
        or candidate.version != baseline.version + 1
    ):
        raise SkillCandidateEvaluationError(
            "draft candidate must be the direct next revision of the baseline"
        )
    if not set(candidate.allowed_capabilities) <= set(baseline.allowed_capabilities):
        raise SkillCandidateEvaluationError(
            "revision candidate cannot expand capability authority"
        )
    return baseline, candidate


def _validate_measurement(
    skill: SkillRecord,
    block_id: str,
    measurement: SkillCandidateRunMeasurement,
) -> None:
    if (
        measurement.block_id != block_id
        or measurement.skill_id != skill.skill_id
        or measurement.skill_version != skill.version
    ):
        raise SkillCandidateEvaluationError(
            "candidate measurement does not match the scheduled skill and block"
        )
