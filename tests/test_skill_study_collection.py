from pathlib import Path

import pytest

from skilla_core import (
    SkillStudyCondition,
    SkillStudyError,
    SkillStudyScheduleCell,
    SkillTrialObservation,
    build_skill_study_schedule,
    load_skill_study_observations,
)
from skilla_core.skill_study_collection import SkillStudyCollector


class Runner:
    def __init__(self, *, wrong_condition: bool = False) -> None:
        self.wrong_condition = wrong_condition

    def run(self, cell: SkillStudyScheduleCell) -> SkillTrialObservation:
        condition = (
            SkillStudyCondition.SK0_NO_SKILL
            if self.wrong_condition
            else cell.condition
        )
        return SkillTrialObservation(
            participant_id=cell.participant_id,
            task_id=cell.task_id,
            repetition=cell.repetition,
            condition=condition,
            succeeded=True,
            elapsed_ms=100,
            llm_calls=1,
            input_tokens=10,
            output_tokens=5,
            user_interventions=0,
            run_cost_microunits=1,
            model_id="z-ai/glm-5.3-flash",
            model_configuration_sha256="a" * 64,
            tool_surface_sha256="b" * 64,
            initial_state_sha256="c" * 64,
            outcome_evidence_sha256=(str(cell.order) * 64)[:64],
        )


def test_collector_appends_resumes_and_exports_only_complete_schedule(tmp_path: Path) -> None:
    schedule = build_skill_study_schedule(
        participant_id="p01", task_ids=("file-sort",), repetitions=1, seed=1
    )
    ledger = (tmp_path / "ledger.jsonl").resolve()
    collector = SkillStudyCollector(schedule, ledger)
    collector.collect_next(Runner())
    resumed = SkillStudyCollector(schedule, ledger)
    assert len(resumed.observations) == 1
    with pytest.raises(SkillStudyError, match="incomplete"):
        resumed.export_observations((tmp_path / "observations.json").resolve())
    while not resumed.complete:
        resumed.collect_next(Runner())
    destination = (tmp_path / "observations.json").resolve()
    resumed.export_observations(destination)
    assert len(load_skill_study_observations(destination)) == 4


def test_collector_rejects_runner_identity_drift(tmp_path: Path) -> None:
    schedule = build_skill_study_schedule(
        participant_id="p01", task_ids=("file-sort",), repetitions=1, seed=3
    )
    if schedule[0].condition is SkillStudyCondition.SK0_NO_SKILL:
        schedule = schedule[1:] + schedule[:1]
    collector = SkillStudyCollector(schedule, (tmp_path / "ledger.jsonl").resolve())
    with pytest.raises(SkillStudyError, match="scheduled cell"):
        collector.collect_next(Runner(wrong_condition=True))
    assert not (tmp_path / "ledger.jsonl").exists()
