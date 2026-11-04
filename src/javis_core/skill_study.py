from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from enum import StrEnum
from pathlib import Path

from pydantic import Field, model_validator

from .confidence_intervals import wilson_interval_95
from .models import FrozenModel
from .study_analysis import exact_mcnemar_p, holm_adjust


class SkillStudyError(ValueError):
    pass


class SkillStudyCondition(StrEnum):
    """Skill-effect conditions kept separate from the safety B0/B1/P1/P2 study."""

    SK0_NO_SKILL = "SK0_NO_SKILL"
    SK1_STORED_INSTRUCTION = "SK1_STORED_INSTRUCTION"
    SK2_INITIAL_SKILL = "SK2_INITIAL_SKILL"
    SK3_REVISED_SKILL = "SK3_REVISED_SKILL"


class SkillTrialObservation(FrozenModel):
    participant_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    task_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    repetition: int = Field(ge=1, le=10_000)
    condition: SkillStudyCondition
    succeeded: bool
    elapsed_ms: int = Field(ge=0, le=86_400_000)
    llm_calls: int = Field(ge=0, le=1_000)
    input_tokens: int = Field(ge=0, le=100_000_000)
    output_tokens: int = Field(ge=0, le=100_000_000)
    user_interventions: int = Field(ge=0, le=1_000)
    run_cost_microunits: int = Field(ge=0, le=10**15)
    model_id: str = Field(min_length=1, max_length=120)
    model_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_surface_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcome_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class SkillConditionSummary(FrozenModel):
    condition: SkillStudyCondition
    observations: int = Field(ge=1)
    successes: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    success_ci95_low: float = Field(ge=0.0, le=1.0)
    success_ci95_high: float = Field(ge=0.0, le=1.0)
    mean_elapsed_ms: float = Field(ge=0.0)
    mean_llm_calls: float = Field(ge=0.0)
    mean_tokens: float = Field(ge=0.0)
    mean_user_interventions: float = Field(ge=0.0)
    mean_run_cost_microunits: float = Field(ge=0.0)


class SkillSuccessComparison(FrozenModel):
    baseline: SkillStudyCondition
    comparator: SkillStudyCondition = SkillStudyCondition.SK3_REVISED_SKILL
    paired_blocks: int = Field(ge=1)
    baseline_successes: int = Field(ge=0)
    comparator_successes: int = Field(ge=0)
    baseline_fail_comparator_success: int = Field(ge=0)
    baseline_success_comparator_fail: int = Field(ge=0)
    success_rate_delta: float = Field(ge=-1.0, le=1.0)
    raw_p_value: float = Field(ge=0.0, le=1.0)
    holm_adjusted_p_value: float = Field(ge=0.0, le=1.0)


class SkillStudyReport(FrozenModel):
    complete_blocks: int = Field(ge=1)
    conditions: tuple[SkillConditionSummary, ...] = Field(min_length=4, max_length=4)
    success_comparisons: tuple[SkillSuccessComparison, ...] = Field(
        min_length=3, max_length=3
    )

    @model_validator(mode="after")
    def has_every_condition_once(self) -> SkillStudyReport:
        values = tuple(item.condition for item in self.conditions)
        if set(values) != set(SkillStudyCondition) or len(values) != len(set(values)):
            raise ValueError("skill study report must contain every condition exactly once")
        return self


class SkillBreakEvenResult(FrozenModel):
    preparation_cost_microunits: int = Field(ge=0)
    baseline_run_cost_microunits: int = Field(ge=0)
    skill_run_cost_microunits: int = Field(ge=0)
    repetitions: int | None = Field(default=None, ge=1)


class SkillStudyScheduleCell(FrozenModel):
    participant_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    task_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    repetition: int = Field(ge=1, le=10_000)
    order: int = Field(ge=1, le=4)
    condition: SkillStudyCondition


def evaluate_skill_study(
    observations: tuple[SkillTrialObservation, ...],
) -> SkillStudyReport:
    if not observations:
        raise SkillStudyError("skill study requires observations")
    blocks: dict[tuple[str, str, int], dict[SkillStudyCondition, SkillTrialObservation]] = (
        defaultdict(dict)
    )
    for observation in observations:
        key = (
            observation.participant_id,
            observation.task_id,
            observation.repetition,
        )
        if observation.condition in blocks[key]:
            raise SkillStudyError("duplicate skill study condition in a paired block")
        blocks[key][observation.condition] = observation
    if any(set(block) != set(SkillStudyCondition) for block in blocks.values()):
        raise SkillStudyError("each paired block must contain SK0, SK1, SK2, and SK3")
    for block in blocks.values():
        identities = {
            (
                item.model_id,
                item.model_configuration_sha256,
                item.tool_surface_sha256,
                item.initial_state_sha256,
            )
            for item in block.values()
        }
        if len(identities) != 1:
            raise SkillStudyError(
                "paired conditions must share model, configuration, tools, and initial state"
            )

    summaries: list[SkillConditionSummary] = []
    for condition in SkillStudyCondition:
        items = tuple(block[condition] for block in blocks.values())
        count = len(items)
        successes = sum(item.succeeded for item in items)
        interval = wilson_interval_95(successes, count)
        summaries.append(
            SkillConditionSummary(
                condition=condition,
                observations=count,
                successes=successes,
                success_rate=successes / count,
                success_ci95_low=interval[0],
                success_ci95_high=interval[1],
                mean_elapsed_ms=sum(item.elapsed_ms for item in items) / count,
                mean_llm_calls=sum(item.llm_calls for item in items) / count,
                mean_tokens=sum(item.total_tokens for item in items) / count,
                mean_user_interventions=(
                    sum(item.user_interventions for item in items) / count
                ),
                mean_run_cost_microunits=(
                    sum(item.run_cost_microunits for item in items) / count
                ),
            )
        )
    baselines = (
        SkillStudyCondition.SK0_NO_SKILL,
        SkillStudyCondition.SK1_STORED_INSTRUCTION,
        SkillStudyCondition.SK2_INITIAL_SKILL,
    )
    preliminary = tuple(_success_comparison(blocks, baseline) for baseline in baselines)
    adjusted = holm_adjust(tuple(item.raw_p_value for item in preliminary))
    comparisons = tuple(
        item.model_copy(update={"holm_adjusted_p_value": adjusted[index]})
        for index, item in enumerate(preliminary)
    )
    return SkillStudyReport(
        complete_blocks=len(blocks),
        conditions=tuple(summaries),
        success_comparisons=comparisons,
    )


def calculate_break_even_repetitions(
    *,
    preparation_cost_microunits: int,
    baseline_run_cost_microunits: int,
    skill_run_cost_microunits: int,
) -> SkillBreakEvenResult:
    if min(
        preparation_cost_microunits,
        baseline_run_cost_microunits,
        skill_run_cost_microunits,
    ) < 0:
        raise ValueError("skill costs must be non-negative")
    savings = baseline_run_cost_microunits - skill_run_cost_microunits
    repetitions = None if savings <= 0 else max(1, math.ceil(preparation_cost_microunits / savings))
    return SkillBreakEvenResult(
        preparation_cost_microunits=preparation_cost_microunits,
        baseline_run_cost_microunits=baseline_run_cost_microunits,
        skill_run_cost_microunits=skill_run_cost_microunits,
        repetitions=repetitions,
    )


def build_skill_study_schedule(
    *,
    participant_id: str,
    task_ids: tuple[str, ...],
    repetitions: int,
    seed: int,
) -> tuple[SkillStudyScheduleCell, ...]:
    if not task_ids or len(set(task_ids)) != len(task_ids):
        raise SkillStudyError("skill study task identifiers must be non-empty and unique")
    if not 1 <= repetitions <= 10_000:
        raise SkillStudyError("skill study repetitions must be within 1..10000")
    base = list(SkillStudyCondition)
    random.Random(seed).shuffle(base)
    cells: list[SkillStudyScheduleCell] = []
    block_number = 0
    for repetition in range(1, repetitions + 1):
        for task_id in task_ids:
            offset = block_number % len(base)
            ordered = base[offset:] + base[:offset]
            cells.extend(
                SkillStudyScheduleCell(
                    participant_id=participant_id,
                    task_id=task_id,
                    repetition=repetition,
                    order=order,
                    condition=condition,
                )
                for order, condition in enumerate(ordered, start=1)
            )
            block_number += 1
    return tuple(cells)


def load_skill_study_observations(path: Path) -> tuple[SkillTrialObservation, ...]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise SkillStudyError("skill study observation path must be an absolute regular file")
    if path.stat().st_size > 10_000_000:
        raise SkillStudyError("skill study observation file exceeded size limit")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, list):
            raise TypeError
        return tuple(SkillTrialObservation.model_validate(item) for item in document)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SkillStudyError("invalid skill study observation document") from exc


def _success_comparison(
    blocks: dict[
        tuple[str, str, int], dict[SkillStudyCondition, SkillTrialObservation]
    ],
    baseline: SkillStudyCondition,
) -> SkillSuccessComparison:
    pairs = tuple(
        (
            block[baseline].succeeded,
            block[SkillStudyCondition.SK3_REVISED_SKILL].succeeded,
        )
        for block in blocks.values()
    )
    baseline_successes = sum(left for left, _right in pairs)
    comparator_successes = sum(right for _left, right in pairs)
    zero_one = sum(not left and right for left, right in pairs)
    one_zero = sum(left and not right for left, right in pairs)
    return SkillSuccessComparison(
        baseline=baseline,
        paired_blocks=len(pairs),
        baseline_successes=baseline_successes,
        comparator_successes=comparator_successes,
        baseline_fail_comparator_success=zero_one,
        baseline_success_comparator_fail=one_zero,
        success_rate_delta=(comparator_successes - baseline_successes) / len(pairs),
        raw_p_value=exact_mcnemar_p(zero_one, one_zero),
        holm_adjusted_p_value=1.0,
    )
