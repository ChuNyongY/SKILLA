from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field, JsonValue

from .models import (
    Action,
    ActionStatus,
    FrozenModel,
    Plan,
    PolicyContext,
    VerificationResult,
    canonical_arguments_hash,
)
from .orchestrator import Orchestrator
from .registry import CapabilityRegistry
from .runtime_models import ExecutionResult, TaskOutcome
from .skill_runtime import PlanProposer


class ObservationLoopError(RuntimeError):
    pass


class VerifiedActionObservation(FrozenModel):
    action_id: UUID
    capability_id: str = Field(min_length=1, max_length=80)
    verification_reason: str = Field(pattern=r"^[A-Za-z0-9_.:-]{2,256}$")
    observed: dict[str, JsonValue] = Field(default_factory=dict)


class ObservationRoundResult(FrozenModel):
    outcome: TaskOutcome
    verified_observations: tuple[VerifiedActionObservation, ...] = Field(
        default=(), max_length=20
    )


class ObservationRoundRunner(Protocol):
    def run(self, plan: Plan) -> ObservationRoundResult: ...


class InMemoryVerifiedResultObserver:
    def __init__(self) -> None:
        self._items: list[VerifiedActionObservation] = []

    @property
    def observations(self) -> tuple[VerifiedActionObservation, ...]:
        return tuple(self._items)

    def observe(
        self,
        action: Action,
        execution: ExecutionResult,
        verification: VerificationResult,
    ) -> None:
        if (
            execution.action_id != action.action_id
            or not verification.success
        ):
            raise ObservationLoopError("only successful verified results may be observed")
        self._items.append(
            VerifiedActionObservation(
                action_id=action.action_id,
                capability_id=action.capability_id,
                verification_reason=verification.reason,
                observed=execution.observed,
            )
        )


class OrchestratorRoundRunner:
    def __init__(
        self,
        orchestrator_factory: Callable[[InMemoryVerifiedResultObserver], Orchestrator],
        policy_context_provider: Callable[[Action], PolicyContext],
    ) -> None:
        self._factory = orchestrator_factory
        self._policy_context_provider = policy_context_provider

    def run(self, plan: Plan) -> ObservationRoundResult:
        observer = InMemoryVerifiedResultObserver()
        outcome = self._factory(observer).run(plan, self._policy_context_provider)
        return ObservationRoundResult(
            outcome=outcome,
            verified_observations=observer.observations,
        )


class CompletionProbe(Protocol):
    def completed(
        self,
        goal: str,
        observations: tuple[VerifiedActionObservation, ...],
    ) -> bool: ...


class ObservationLoopStatus(StrEnum):
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ObservationLoopResult(FrozenModel):
    status: ObservationLoopStatus
    reason: str = Field(pattern=r"^[A-Z0-9_.:-]{2,80}$")
    rounds: int = Field(ge=1, le=10)
    observations: tuple[VerifiedActionObservation, ...] = Field(max_length=200)
    executed_plans: tuple[Plan, ...] = Field(min_length=1, max_length=10)


class BoundedObservationAgent:
    """Finite observe-plan-act loop; only independently verified data is recycled."""

    def __init__(
        self,
        planner: PlanProposer,
        runner: ObservationRoundRunner,
        completion_probe: CompletionProbe | None,
        registry: CapabilityRegistry,
        *,
        max_rounds: int = 4,
        max_context_bytes: int = 100_000,
    ) -> None:
        if not 1 <= max_rounds <= 10 or max_context_bytes < 1_024:
            raise ValueError("invalid observation loop limits")
        self._planner = planner
        self._runner = runner
        self._probe = completion_probe
        self._registry = registry
        self._max_rounds = max_rounds
        self._max_context_bytes = max_context_bytes

    def run(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None = None,
        untrusted_context: str | None = None,
        initial_plan: Plan | None = None,
    ) -> ObservationLoopResult:
        if initial_plan is not None and initial_plan.goal != goal:
            raise ObservationLoopError("initial plan goal did not match the loop goal")
        observations: tuple[VerifiedActionObservation, ...] = ()
        external_effects: set[tuple[str, str, str | None]] = set()
        action_ids: set[UUID] = set()
        executed_plans: tuple[Plan, ...] = ()
        for round_number in range(1, self._max_rounds + 1):
            context = dict(trusted_context or {})
            context["observation_round"] = round_number
            context["verified_observations"] = [
                item.model_dump(mode="json") for item in observations
            ]
            encoded = json.dumps(
                context,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(encoded) > self._max_context_bytes:
                raise ObservationLoopError("verified observation context exceeded size limit")
            plan = (
                initial_plan
                if round_number == 1 and initial_plan is not None
                else self._planner.plan(
                    goal,
                    trusted_context=context,
                    untrusted_context=untrusted_context,
                )
            )
            self._validate_continuation_plan(plan)
            if any(action.action_id in action_ids for action in plan.steps):
                raise ObservationLoopError("planner reused an action identifier across rounds")
            action_ids.update(action.action_id for action in plan.steps)
            self._reject_repeated_external_effects(plan, external_effects)
            result = self._runner.run(plan)
            self._validate_round(plan, result)
            executed_plans += (plan,)
            if result.outcome.status is not ActionStatus.SUCCEEDED:
                return ObservationLoopResult(
                    status=ObservationLoopStatus.ABORTED,
                    reason=_safe_reason(result.outcome.reason),
                    rounds=round_number,
                    observations=observations + result.verified_observations,
                    executed_plans=executed_plans,
                )
            observations += result.verified_observations
            if (
                self._probe.completed(goal, observations)
                if self._probe is not None
                else not plan.continue_after_verification
            ):
                return ObservationLoopResult(
                    status=ObservationLoopStatus.COMPLETED,
                    reason="GOAL_POSTCONDITIONS_VERIFIED",
                    rounds=round_number,
                    observations=observations,
                    executed_plans=executed_plans,
                )
        return ObservationLoopResult(
            status=ObservationLoopStatus.BUDGET_EXHAUSTED,
            reason="OBSERVATION_ROUND_BUDGET_EXHAUSTED",
            rounds=self._max_rounds,
            observations=observations,
            executed_plans=executed_plans,
        )

    def _reject_repeated_external_effects(
        self,
        plan: Plan,
        previous: set[tuple[str, str, str | None]],
    ) -> None:
        for action in plan.steps:
            capability = self._registry.get(action.capability_id)
            if capability is None:
                raise ObservationLoopError("plan referenced an unknown capability")
            if not capability.state_changing:
                continue
            fingerprint = (
                action.capability_id,
                canonical_arguments_hash(action.arguments),
                action.target_identity,
            )
            if fingerprint in previous:
                raise ObservationLoopError("planner repeated an external effect")
            previous.add(fingerprint)

    def _validate_continuation_plan(self, plan: Plan) -> None:
        if not plan.continue_after_verification:
            return
        for action in plan.steps:
            capability = self._registry.get(action.capability_id)
            if capability is None or capability.state_changing:
                raise ObservationLoopError(
                    "continuation plans must contain only read-only capabilities"
                )

    @staticmethod
    def _validate_round(plan: Plan, result: ObservationRoundResult) -> None:
        if result.outcome.task_id != plan.task_id:
            raise ObservationLoopError("round outcome task identifier mismatch")
        if result.outcome.completed_actions > len(plan.steps):
            raise ObservationLoopError("round completed action count exceeded the plan")
        if (
            result.outcome.status is ActionStatus.SUCCEEDED
            and result.outcome.completed_actions != len(plan.steps)
        ):
            raise ObservationLoopError("successful round did not complete every action")
        if len(result.verified_observations) != result.outcome.completed_actions:
            raise ObservationLoopError("verified observation count did not match completion")
        action_by_id = {action.action_id: action for action in plan.steps}
        if len(action_by_id) != len(plan.steps):
            raise ObservationLoopError("round plan action identifiers were not unique")
        observed_ids: set[UUID] = set()
        for observation in result.verified_observations:
            action = action_by_id.get(observation.action_id)
            if (
                action is None
                or observation.action_id in observed_ids
                or observation.capability_id != action.capability_id
            ):
                raise ObservationLoopError("verified observation did not match the plan")
            observed_ids.add(observation.action_id)


def _safe_reason(reason: str) -> str:
    value = reason.upper()[:80]
    return value if value else "ROUND_ABORTED"
