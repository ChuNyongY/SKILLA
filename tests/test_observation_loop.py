from javis_core import (
    Action,
    ActionStatus,
    ApprovalTokenService,
    InMemoryAuditSink,
    MockExecutor,
    Orchestrator,
    Plan,
    PolicyContext,
    PolicyEngine,
    PredicateVerifier,
    TaskOutcome,
    default_registry,
)
from javis_core.observation_loop import (
    BoundedObservationAgent,
    ObservationLoopError,
    ObservationLoopStatus,
    ObservationRoundResult,
    OrchestratorRoundRunner,
    VerifiedActionObservation,
)


class Planner:
    def __init__(self, *, repeat_move: bool = False) -> None:
        self.contexts: list[dict[str, object]] = []
        self.repeat_move = repeat_move

    def plan(
        self,
        goal: str,
        *,
        trusted_context: dict[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan:
        context = dict(trusted_context or {})
        self.contexts.append(context)
        if len(self.contexts) == 1 and not self.repeat_move:
            action = Action(capability_id="file.list", purpose="observe")
            continue_after_verification = True
        else:
            action = Action(
                capability_id="file.move",
                purpose="move",
                arguments={"source": "a", "destination": "b"},
                target_identity="a",
            )
            continue_after_verification = False
        return Plan(
            goal=goal,
            steps=(action,),
            continue_after_verification=continue_after_verification,
        )


class Runner:
    def __init__(self) -> None:
        self.rounds = 0

    def run(self, plan: Plan) -> ObservationRoundResult:
        self.rounds += 1
        action = plan.steps[0]
        observed = (
            {"entries": ["a.txt"]}
            if action.capability_id == "file.list"
            else {"destination": "b"}
        )
        return ObservationRoundResult(
            outcome=TaskOutcome(
                task_id=plan.task_id,
                status=ActionStatus.SUCCEEDED,
                completed_actions=1,
                reason="ALL_ACTIONS_VERIFIED",
            ),
            verified_observations=(
                VerifiedActionObservation(
                    action_id=action.action_id,
                    capability_id=action.capability_id,
                    verification_reason="VERIFIED",
                    observed=observed,
                ),
            ),
        )


class Probe:
    def completed(self, goal: str, observations: tuple[VerifiedActionObservation, ...]) -> bool:
        return any(item.capability_id == "file.move" for item in observations)


def test_verified_observation_drives_a_bounded_second_plan() -> None:
    planner = Planner()
    result = BoundedObservationAgent(
        planner, Runner(), Probe(), default_registry(), max_rounds=3
    ).run("자료 정리")
    assert result.status is ObservationLoopStatus.COMPLETED
    assert result.rounds == 2
    assert planner.contexts[1]["observation_round"] == 2
    prior = planner.contexts[1]["verified_observations"]
    assert isinstance(prior, list) and prior[0]["capability_id"] == "file.list"


def test_repeated_external_effect_is_rejected() -> None:
    planner = Planner(repeat_move=True)
    agent = BoundedObservationAgent(
        planner, Runner(), lambda_goal_probe(), default_registry(), max_rounds=3
    )
    try:
        agent.run("자료 정리")
    except ObservationLoopError as error:
        assert "repeated" in str(error)
    else:
        raise AssertionError("repeated external effect was accepted")


class MismatchedRunner:
    def run(self, plan: Plan) -> ObservationRoundResult:
        return ObservationRoundResult(
            outcome=TaskOutcome(
                task_id=plan.task_id,
                status=ActionStatus.SUCCEEDED,
                completed_actions=1,
                reason="ALL_ACTIONS_VERIFIED",
            ),
            verified_observations=(),
        )


def test_unbound_verified_observation_is_rejected() -> None:
    agent = BoundedObservationAgent(
        Planner(), MismatchedRunner(), Probe(), default_registry(), max_rounds=2
    )
    try:
        agent.run("자료 정리")
    except ObservationLoopError as error:
        assert "count" in str(error)
    else:
        raise AssertionError("unbound observation was accepted")


def test_state_changing_continuation_plan_is_rejected_before_execution() -> None:
    class UnsafeContinuationPlanner(Planner):
        def plan(
            self,
            goal: str,
            *,
            trusted_context: dict[str, object] | None = None,
            untrusted_context: str | None = None,
        ) -> Plan:
            planned = super().plan(
                goal,
                trusted_context=trusted_context,
                untrusted_context=untrusted_context,
            )
            return planned.model_copy(update={"continue_after_verification": True})

    agent = BoundedObservationAgent(
        UnsafeContinuationPlanner(repeat_move=True),
        Runner(),
        Probe(),
        default_registry(),
        max_rounds=2,
    )
    try:
        agent.run("자료 정리")
    except ObservationLoopError as error:
        assert "read-only" in str(error)
    else:
        raise AssertionError("state-changing continuation plan was accepted")


class lambda_goal_probe:
    def completed(self, goal: str, observations: tuple[VerifiedActionObservation, ...]) -> bool:
        return False


def test_orchestrator_round_runner_collects_only_verified_results() -> None:
    def factory(observer: object) -> Orchestrator:
        return Orchestrator(
            policy=PolicyEngine(default_registry()),
            executor=MockExecutor({"system.info.read": lambda _action: {"os": "Windows"}}),
            verifier=PredicateVerifier(),
            audit=InMemoryAuditSink(),
            approvals=ApprovalTokenService(b"o" * 32),
            verified_result_observer=observer,  # type: ignore[arg-type]
        )

    runner = OrchestratorRoundRunner(
        factory,
        lambda _action: PolicyContext(
            addressed_confidence=1.0,
            intent_confidence=1.0,
            target_confidence=1.0,
            target_matches_plan=True,
        ),
    )
    plan = Plan(goal="정보 확인", steps=(Action(capability_id="system.info.read", purpose="read"),))
    result = runner.run(plan)
    assert result.outcome.status is ActionStatus.SUCCEEDED
    assert result.verified_observations[0].observed == {"os": "Windows"}
