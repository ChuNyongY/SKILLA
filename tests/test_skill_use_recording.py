from __future__ import annotations

import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path

import pytest

from javis_core import (
    Action,
    CatalogSkillUseRecorder,
    LocalSkillCatalog,
    Plan,
    SkillAwarePlanner,
    SkillOutcome,
    SkillPlanUsage,
    SkillProposal,
    TaskOutcome,
    product_model_configuration_sha256,
    product_tool_surface_sha256,
)
from javis_core.models import ActionStatus
from javis_core.planner import NimTransportMetrics
from javis_core.registry import CapabilityRegistry, default_registry


class Planner:
    def plan(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan:
        return Plan(
            goal=goal,
            steps=(Action(capability_id="system.info.read", purpose="read"),),
        )


def _catalog(tmp_path: Path) -> LocalSkillCatalog:
    return LocalSkillCatalog((tmp_path / "skills.sqlite3").resolve(), default_registry())


def _approved_skill(catalog: LocalSkillCatalog) -> None:
    draft = catalog.propose(
        SkillProposal(
            key="system-check",
            title="시스템 확인",
            description="시스템 정보를 확인한다.",
            triggers=("시스템 정보",),
            procedure=("현재 정보를 읽는다.",),
            allowed_capabilities=("system.info.read",),
        )
    )
    catalog.approve(draft.skill_id)


def _recorder(
    catalog: LocalSkillCatalog,
    planner: SkillAwarePlanner,
) -> CatalogSkillUseRecorder:
    return CatalogSkillUseRecorder(
        catalog,
        planner,
        model_configuration_sha256="a" * 64,
        tool_surface_sha256="b" * 64,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (ActionStatus.SUCCEEDED, SkillOutcome.SUCCEEDED),
        (ActionStatus.FAILED, SkillOutcome.FAILED),
        (ActionStatus.ABORTED, SkillOutcome.ABORTED),
    ),
)
def test_selected_skill_use_is_recorded_once_with_exact_environment(
    tmp_path: Path,
    status: ActionStatus,
    expected: SkillOutcome,
) -> None:
    catalog = _catalog(tmp_path)
    _approved_skill(catalog)
    planner = SkillAwarePlanner(Planner(), catalog)
    plan = planner.plan("시스템 정보 알려 줘")
    outcome = TaskOutcome(
        task_id=plan.task_id,
        status=status,
        completed_actions=1 if status is ActionStatus.SUCCEEDED else 0,
        reason="ALL_ACTIONS_VERIFIED" if status is ActionStatus.SUCCEEDED else "TOOL_FAILED",
    )
    recorder = _recorder(catalog, planner)

    assert recorder.observe(plan, outcome, elapsed_ms=321)
    assert not recorder.observe(plan, outcome, elapsed_ms=999)

    with sqlite3.connect(tmp_path / "skills.sqlite3") as db:
        rows = db.execute(
            """
            SELECT skill_version, outcome, detail_code, elapsed_ms,
                   model_configuration_sha256, tool_surface_sha256
            FROM skill_uses
            """
        ).fetchall()
    assert rows == [
        (
            1,
            expected.value,
            outcome.reason,
            321,
            "a" * 64,
            "b" * 64,
        )
    ]


def test_no_match_and_continuation_do_not_create_pending_skill_use(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    _approved_skill(catalog)
    planner = SkillAwarePlanner(Planner(), catalog)
    no_match = planner.plan("날씨 알려 줘")
    continuation = planner.plan(
        "시스템 정보 알려 줘",
        trusted_context={"observation_round": 2},
    )
    recorder = _recorder(catalog, planner)

    for plan in (no_match, continuation):
        outcome = TaskOutcome(
            task_id=plan.task_id,
            status=ActionStatus.SUCCEEDED,
            completed_actions=1,
            reason="ALL_ACTIONS_VERIFIED",
        )
        assert not recorder.observe(plan, outcome, elapsed_ms=1)

    verified = catalog.search("시스템 정보")[0]
    assert catalog.summarize_use(verified.skill_id).observations == 0


def test_pending_skill_selection_map_is_bounded_and_one_time(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    _approved_skill(catalog)
    planner = SkillAwarePlanner(Planner(), catalog, max_pending_selections=1)
    first = planner.plan("시스템 정보 첫 번째")
    second = planner.plan("시스템 정보 두 번째")

    assert planner.claim_selected_skill(first.task_id) is None
    selected = planner.claim_selected_skill(second.task_id)
    assert selected is not None and selected.skill.version == 1
    assert planner.claim_selected_skill(second.task_id) is None


def test_environment_hashes_are_canonical_and_sensitive_to_contract_changes() -> None:
    first_model = product_model_configuration_sha256("z-ai/glm-5.3-flash")
    second_model = product_model_configuration_sha256("z-ai/glm-5.3-flash")
    other_model = product_model_configuration_sha256("z-ai/glm-5.3")
    registry = default_registry()
    reversed_registry = CapabilityRegistry(reversed(registry.list()))

    assert first_model == second_model
    assert first_model != other_model
    assert product_tool_surface_sha256(registry) == product_tool_surface_sha256(
        reversed_registry
    )
    assert len(first_model) == 64
    with pytest.raises(ValueError, match="cannot exceed"):
        SkillPlanUsage(llm_calls=0, responses_without_usage=1)


def test_recorder_rejects_mismatched_task_without_consuming_selection(
    tmp_path: Path,
) -> None:
    catalog = _catalog(tmp_path)
    _approved_skill(catalog)
    planner = SkillAwarePlanner(Planner(), catalog)
    plan = planner.plan("시스템 정보")
    other = Plan(goal=plan.goal, steps=plan.steps)
    recorder = _recorder(catalog, planner)

    with pytest.raises(ValueError, match="did not match"):
        recorder.observe(
            plan,
            TaskOutcome(
                task_id=other.task_id,
                status=ActionStatus.SUCCEEDED,
                completed_actions=1,
                reason="ALL_ACTIONS_VERIFIED",
            ),
            elapsed_ms=1,
        )
    assert planner.claim_selected_skill(plan.task_id) is not None


class MetricPlanner(Planner):
    def __init__(self, *, requests_per_plan: int = 1, usage_missing: bool = False) -> None:
        self.requests_per_plan = requests_per_plan
        self.usage_missing = usage_missing
        self._lock = threading.Lock()
        self._metrics = NimTransportMetrics(
            requests=0,
            successful_requests=0,
            input_tokens=0,
            output_tokens=0,
            responses_without_usage=0,
        )

    def metrics_snapshot(self) -> NimTransportMetrics:
        with self._lock:
            return self._metrics.model_copy()

    def plan(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan:
        with self._lock:
            self._metrics = NimTransportMetrics(
                requests=self._metrics.requests + self.requests_per_plan,
                successful_requests=(
                    self._metrics.successful_requests + self.requests_per_plan
                ),
                input_tokens=self._metrics.input_tokens + 100 * self.requests_per_plan,
                output_tokens=self._metrics.output_tokens + 25 * self.requests_per_plan,
                responses_without_usage=(
                    self._metrics.responses_without_usage
                    + (1 if self.usage_missing else 0)
                ),
            )
        return super().plan(
            goal,
            trusted_context=trusted_context,
            untrusted_context=untrusted_context,
        )


@pytest.mark.parametrize("requests_per_plan", (1, 2))
def test_planner_usage_delta_is_bound_to_the_selected_skill(
    tmp_path: Path,
    requests_per_plan: int,
) -> None:
    catalog = _catalog(tmp_path)
    _approved_skill(catalog)
    planner = SkillAwarePlanner(
        MetricPlanner(requests_per_plan=requests_per_plan),
        catalog,
    )
    plan = planner.plan("시스템 정보")
    outcome = TaskOutcome(
        task_id=plan.task_id,
        status=ActionStatus.SUCCEEDED,
        completed_actions=1,
        reason="ALL_ACTIONS_VERIFIED",
    )

    assert _recorder(catalog, planner).observe(plan, outcome, elapsed_ms=5)

    with sqlite3.connect(tmp_path / "skills.sqlite3") as db:
        row = db.execute(
            """
            SELECT llm_calls, input_tokens, output_tokens,
                   planner_usage_complete, planner_responses_without_usage
            FROM skill_uses
            """
        ).fetchone()
    assert row == (
        requests_per_plan,
        100 * requests_per_plan,
        25 * requests_per_plan,
        1,
        0,
    )


def test_missing_usage_is_explicitly_marked_instead_of_claimed_complete(
    tmp_path: Path,
) -> None:
    catalog = _catalog(tmp_path)
    _approved_skill(catalog)
    planner = SkillAwarePlanner(MetricPlanner(usage_missing=True), catalog)
    plan = planner.plan("시스템 정보")
    outcome = TaskOutcome(
        task_id=plan.task_id,
        status=ActionStatus.SUCCEEDED,
        completed_actions=1,
        reason="ALL_ACTIONS_VERIFIED",
    )

    assert _recorder(catalog, planner).observe(plan, outcome, elapsed_ms=5)

    with sqlite3.connect(tmp_path / "skills.sqlite3") as db:
        row = db.execute(
            """
            SELECT planner_usage_complete, planner_responses_without_usage
            FROM skill_uses
            """
        ).fetchone()
    assert row == (0, 1)


def test_concurrent_metric_plans_are_serialized_without_cross_attribution(
    tmp_path: Path,
) -> None:
    catalog = _catalog(tmp_path)
    _approved_skill(catalog)
    planner = SkillAwarePlanner(MetricPlanner(), catalog)
    plans: list[Plan] = []
    plans_lock = threading.Lock()

    def run(index: int) -> None:
        plan = planner.plan(f"시스템 정보 {index}")
        with plans_lock:
            plans.append(plan)

    threads = [threading.Thread(target=run, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()

    selections = [planner.claim_selected_skill(plan.task_id) for plan in plans]
    assert len(selections) == 8
    assert all(selection is not None for selection in selections)
    assert sum(
        selection.usage.llm_calls
        for selection in selections
        if selection is not None
    ) == 8
    assert all(
        selection.usage.complete
        for selection in selections
        if selection is not None
    )
