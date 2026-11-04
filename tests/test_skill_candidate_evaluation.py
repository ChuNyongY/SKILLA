from uuid import UUID

import pytest

from javis_core.skill_candidate_evaluation import (
    SkillCandidateDecision,
    SkillCandidateEvaluationError,
    SkillCandidateTrial,
    evaluate_revision_candidate,
)

BASELINE_ID = UUID("00000000-0000-0000-0000-000000000001")
CANDIDATE_ID = UUID("00000000-0000-0000-0000-000000000002")
HASH = "a" * 64


def trial(index: int, **updates: object) -> SkillCandidateTrial:
    values: dict[str, object] = {
        "block_id": f"block-{index}",
        "baseline_skill_id": BASELINE_ID,
        "candidate_skill_id": CANDIDATE_ID,
        "baseline_executed_first": index % 2 == 1,
        "baseline_succeeded": True,
        "candidate_succeeded": True,
        "baseline_elapsed_ms": 100,
        "candidate_elapsed_ms": 90,
        "baseline_tokens": 100,
        "candidate_tokens": 80,
        "baseline_model_configuration_sha256": HASH,
        "candidate_model_configuration_sha256": HASH,
        "baseline_tool_surface_sha256": HASH,
        "candidate_tool_surface_sha256": HASH,
        "baseline_initial_state_sha256": HASH,
        "candidate_initial_state_sha256": HASH,
        "baseline_evidence_sha256": HASH,
        "candidate_evidence_sha256": HASH,
    }
    values.update(updates)
    return SkillCandidateTrial.model_validate(values)


def test_candidate_needs_minimum_paired_evidence() -> None:
    result = evaluate_revision_candidate((trial(1), trial(2)))
    assert result.decision is SkillCandidateDecision.INSUFFICIENT_EVIDENCE


def test_success_regression_blocks_human_review_even_if_compensated() -> None:
    result = evaluate_revision_candidate(
        (
            trial(1, candidate_succeeded=False),
            trial(2, baseline_succeeded=False, candidate_succeeded=True),
            trial(3),
        )
    )
    assert result.decision is SkillCandidateDecision.REJECT_REGRESSION
    assert result.reason_code == "SUCCESS_REGRESSION"


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"candidate_elapsed_ms": 126}, "ELAPSED_TIME_REGRESSION"),
        ({"candidate_tokens": 126}, "TOKEN_REGRESSION"),
    ],
)
def test_efficiency_regression_blocks_human_review(
    updates: dict[str, object], reason: str
) -> None:
    result = evaluate_revision_candidate(
        tuple(trial(index, **updates) for index in range(1, 4))
    )
    assert result.decision is SkillCandidateDecision.REJECT_REGRESSION
    assert result.reason_code == reason


def test_non_regressing_candidate_is_only_ready_for_human_review() -> None:
    result = evaluate_revision_candidate(tuple(trial(index) for index in range(1, 4)))
    assert result.decision is SkillCandidateDecision.READY_FOR_HUMAN_REVIEW
    assert result.reason_code == "NO_MEASURED_REGRESSION"


def test_environment_mismatch_is_rejected() -> None:
    with pytest.raises(SkillCandidateEvaluationError, match="share model"):
        evaluate_revision_candidate(
            (
                trial(1),
                trial(2, candidate_tool_surface_sha256="b" * 64),
                trial(3),
            )
        )
