from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from pydantic import Field

from .models import FrozenModel


class SkillCandidateEvaluationError(ValueError):
    pass


class SkillCandidateDecision(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECT_REGRESSION = "REJECT_REGRESSION"
    READY_FOR_HUMAN_REVIEW = "READY_FOR_HUMAN_REVIEW"


class SkillCandidateTrial(FrozenModel):
    block_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    baseline_skill_id: UUID
    candidate_skill_id: UUID
    baseline_executed_first: bool
    baseline_succeeded: bool
    candidate_succeeded: bool
    baseline_elapsed_ms: int = Field(ge=0, le=86_400_000)
    candidate_elapsed_ms: int = Field(ge=0, le=86_400_000)
    baseline_tokens: int = Field(ge=0, le=100_000_000)
    candidate_tokens: int = Field(ge=0, le=100_000_000)
    baseline_model_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_model_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_tool_surface_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_tool_surface_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_initial_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_initial_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SkillCandidateEvaluation(FrozenModel):
    baseline_skill_id: UUID
    candidate_skill_id: UUID
    decision: SkillCandidateDecision
    reason_code: str = Field(pattern=r"^[A-Z0-9_.:-]{2,80}$")
    paired_trials: int = Field(ge=1)
    baseline_successes: int = Field(ge=0)
    candidate_successes: int = Field(ge=0)
    baseline_success_candidate_failure: int = Field(ge=0)
    baseline_mean_elapsed_ms: float = Field(ge=0.0)
    candidate_mean_elapsed_ms: float = Field(ge=0.0)
    baseline_mean_tokens: float = Field(ge=0.0)
    candidate_mean_tokens: float = Field(ge=0.0)


def evaluate_revision_candidate(
    trials: tuple[SkillCandidateTrial, ...],
    *,
    minimum_trials: int = 3,
    maximum_elapsed_ratio: float = 1.25,
    maximum_token_ratio: float = 1.25,
) -> SkillCandidateEvaluation:
    if (
        not trials
        or minimum_trials < 1
        or maximum_elapsed_ratio < 1.0
        or maximum_token_ratio < 1.0
    ):
        raise ValueError("invalid candidate evaluation configuration")
    if len({item.block_id for item in trials}) != len(trials):
        raise SkillCandidateEvaluationError("candidate trial block identifiers must be unique")
    skill_pairs = {
        (item.baseline_skill_id, item.candidate_skill_id) for item in trials
    }
    if len(skill_pairs) != 1:
        raise SkillCandidateEvaluationError("candidate trials must compare one exact skill pair")
    baseline_skill_id, candidate_skill_id = next(iter(skill_pairs))
    if baseline_skill_id == candidate_skill_id:
        raise SkillCandidateEvaluationError("candidate must be a distinct skill version")
    for trial in trials:
        if (
            trial.baseline_model_configuration_sha256
            != trial.candidate_model_configuration_sha256
            or trial.baseline_tool_surface_sha256
            != trial.candidate_tool_surface_sha256
            or trial.baseline_initial_state_sha256
            != trial.candidate_initial_state_sha256
        ):
            raise SkillCandidateEvaluationError(
                "paired candidate trials must share model, tools, and initial state"
            )

    count = len(trials)
    baseline_successes = sum(item.baseline_succeeded for item in trials)
    candidate_successes = sum(item.candidate_succeeded for item in trials)
    regressions = sum(
        item.baseline_succeeded and not item.candidate_succeeded for item in trials
    )
    baseline_elapsed = sum(item.baseline_elapsed_ms for item in trials) / count
    candidate_elapsed = sum(item.candidate_elapsed_ms for item in trials) / count
    baseline_tokens = sum(item.baseline_tokens for item in trials) / count
    candidate_tokens = sum(item.candidate_tokens for item in trials) / count

    if count < minimum_trials:
        decision = SkillCandidateDecision.INSUFFICIENT_EVIDENCE
        reason = "TOO_FEW_PAIRED_TRIALS"
    elif regressions or candidate_successes < baseline_successes:
        decision = SkillCandidateDecision.REJECT_REGRESSION
        reason = "SUCCESS_REGRESSION"
    elif _exceeds_ratio(candidate_elapsed, baseline_elapsed, maximum_elapsed_ratio):
        decision = SkillCandidateDecision.REJECT_REGRESSION
        reason = "ELAPSED_TIME_REGRESSION"
    elif _exceeds_ratio(candidate_tokens, baseline_tokens, maximum_token_ratio):
        decision = SkillCandidateDecision.REJECT_REGRESSION
        reason = "TOKEN_REGRESSION"
    else:
        decision = SkillCandidateDecision.READY_FOR_HUMAN_REVIEW
        reason = "NO_MEASURED_REGRESSION"
    return SkillCandidateEvaluation(
        baseline_skill_id=baseline_skill_id,
        candidate_skill_id=candidate_skill_id,
        decision=decision,
        reason_code=reason,
        paired_trials=count,
        baseline_successes=baseline_successes,
        candidate_successes=candidate_successes,
        baseline_success_candidate_failure=regressions,
        baseline_mean_elapsed_ms=baseline_elapsed,
        candidate_mean_elapsed_ms=candidate_elapsed,
        baseline_mean_tokens=baseline_tokens,
        candidate_mean_tokens=candidate_tokens,
    )


def load_skill_candidate_trials(path: Path) -> tuple[SkillCandidateTrial, ...]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise SkillCandidateEvaluationError(
            "candidate trial path must be an absolute regular file"
        )
    if path.stat().st_size > 10_000_000:
        raise SkillCandidateEvaluationError("candidate trial file exceeded size limit")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, list):
            raise TypeError
        return tuple(SkillCandidateTrial.model_validate(item) for item in document)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise SkillCandidateEvaluationError("invalid candidate trial document") from error


def _exceeds_ratio(candidate: float, baseline: float, maximum_ratio: float) -> bool:
    if baseline == 0.0:
        return candidate > 0.0
    return candidate > baseline * maximum_ratio
