import json
from pathlib import Path

import pytest

from javis_core import (
    SkillStudyCondition,
    SkillStudyError,
    SkillStudyScheduleCell,
    SkillTrialObservation,
    build_skill_study_schedule,
    calculate_break_even_repetitions,
    evaluate_skill_study,
    load_skill_study_observations,
)


def observation(condition: SkillStudyCondition, **updates: object) -> SkillTrialObservation:
    values: dict[str, object] = {
        "participant_id": "p01",
        "task_id": "weekly-file-sort",
        "repetition": 1,
        "condition": condition,
        "succeeded": condition is not SkillStudyCondition.SK0_NO_SKILL,
        "elapsed_ms": 1000,
        "llm_calls": 1,
        "input_tokens": 100,
        "output_tokens": 50,
        "user_interventions": 0,
        "run_cost_microunits": 100,
        "model_id": "z-ai/glm-5.3-flash",
        "model_configuration_sha256": "a" * 64,
        "tool_surface_sha256": "b" * 64,
        "initial_state_sha256": "c" * 64,
        "outcome_evidence_sha256": "d" * 64,
    }
    values.update(updates)
    return SkillTrialObservation(**values)  # type: ignore[arg-type]


def test_skill_study_requires_complete_paired_blocks() -> None:
    complete = tuple(observation(condition) for condition in SkillStudyCondition)
    report = evaluate_skill_study(complete)
    assert report.complete_blocks == 1
    assert report.conditions[0].success_rate == 0.0
    assert report.conditions[2].success_rate == 1.0
    assert report.conditions[0].success_ci95_low == 0.0
    assert report.conditions[0].success_ci95_high > 0.0
    assert len(report.success_comparisons) == 3
    assert report.success_comparisons[0].success_rate_delta == 1.0
    assert report.success_comparisons[0].raw_p_value == 1.0

    with pytest.raises(SkillStudyError, match="each paired block"):
        evaluate_skill_study(complete[:-1])


def test_skill_study_rejects_duplicate_condition() -> None:
    duplicate = (
        observation(SkillStudyCondition.SK0_NO_SKILL),
        observation(SkillStudyCondition.SK0_NO_SKILL),
    )
    with pytest.raises(SkillStudyError, match="duplicate"):
        evaluate_skill_study(duplicate)


def test_skill_study_rejects_environment_drift_within_paired_block() -> None:
    complete = tuple(observation(condition) for condition in SkillStudyCondition)
    drifted = complete[:-1] + (
        complete[-1].model_copy(update={"tool_surface_sha256": "e" * 64}),
    )
    with pytest.raises(SkillStudyError, match="share model"):
        evaluate_skill_study(drifted)


def test_schedule_is_deterministic_balanced_and_loads_strict_observations(
    tmp_path: Path,
) -> None:
    schedule = build_skill_study_schedule(
        participant_id="p01",
        task_ids=("file-sort", "pdf-open"),
        repetitions=2,
        seed=7,
    )
    assert schedule == build_skill_study_schedule(
        participant_id="p01",
        task_ids=("file-sort", "pdf-open"),
        repetitions=2,
        seed=7,
    )
    assert len(schedule) == 16
    assert all(isinstance(item, SkillStudyScheduleCell) for item in schedule)
    first_block = schedule[:4]
    assert {item.condition for item in first_block} == set(SkillStudyCondition)
    assert tuple(item.order for item in first_block) == (1, 2, 3, 4)

    observations = [
        observation(condition).model_dump(mode="json")
        for condition in SkillStudyCondition
    ]
    path = (tmp_path / "observations.json").resolve()
    path.write_text(json.dumps(observations), encoding="utf-8")
    assert len(load_skill_study_observations(path)) == 4


def test_break_even_includes_preparation_cost_and_reports_no_savings() -> None:
    result = calculate_break_even_repetitions(
        preparation_cost_microunits=100,
        baseline_run_cost_microunits=20,
        skill_run_cost_microunits=10,
    )
    assert result.repetitions == 10
    no_savings = calculate_break_even_repetitions(
        preparation_cost_microunits=100,
        baseline_run_cost_microunits=10,
        skill_run_cost_microunits=10,
    )
    assert no_savings.repetitions is None
