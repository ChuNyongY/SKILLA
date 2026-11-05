from __future__ import annotations

import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest

from skilla_core.cancellation import CancellationToken
from skilla_core.models import Action, Plan, PolicyContext
from skilla_core.registry import default_registry
from skilla_core.skill_runtime import (
    LocalSkillCatalog,
    SkillAwarePlanner,
    SkillProposal,
    SkillStatus,
)
from skilla_core.skill_session import SkillSession


class Planner:
    def plan(self, goal: str, **kwargs: object) -> Plan:
        return Plan(
            goal=goal, steps=(Action(capability_id="system.info.read", purpose="정보 확인"),)
        )


def proposal(_plan: Plan) -> SkillProposal:
    return SkillProposal(
        key="system-information-check",
        title="시스템 정보 확인",
        description="시스템 정보 확인",
        triggers=("시스템 정보 확인",),
        procedure=("현재 운영체제와 장치 정보 조회",),
        verification_rules=("실제 조회한 값을 표시",),
        allowed_capabilities=("system.info.read",),
    )


def context(_action: Action) -> PolicyContext:
    return PolicyContext(
        addressed_confidence=1,
        intent_confidence=1,
        target_confidence=1,
        target_matches_plan=True,
    )


def make_session(tmp_path: Path, *, timeout: float = 2) -> tuple:
    catalog = LocalSkillCatalog(tmp_path / "skills.sqlite3", default_registry())
    planner = SkillAwarePlanner(Planner(), catalog)
    session = SkillSession(catalog, planner, default_registry(), proposal, timeout_seconds=timeout)
    return catalog, planner, session


def start_review(session: SkillSession, plan: Plan, *, policy=context) -> tuple:
    token = CancellationToken()
    waiting = threading.Event()
    result: dict[str, object] = {}

    def run() -> None:
        try:
            result["accepted"] = session.prepare(plan, token, policy, waiting.set)
        except Exception as error:
            result["error"] = error

    thread = threading.Thread(target=run)
    thread.start()
    return token, waiting, result, thread


def test_new_skill_is_not_stored_before_yes_and_is_selected_after_registration(
    tmp_path: Path,
) -> None:
    catalog, planner, session = make_session(tmp_path)
    plan = planner.plan("시스템 정보 확인")
    _token, waiting, result, thread = start_review(session, plan)
    assert waiting.wait(1)
    pending = session.snapshot()
    assert pending is not None and pending.kind == "REGISTER"
    assert not catalog.list()
    assert not session.respond(uuid4(), True)
    assert not session.respond_text("네 아니요 하지 마")
    assert session.respond_text("네.")
    assert not session.respond(pending.review_id, True)
    thread.join(2)
    assert result == {"accepted": True}
    assert catalog.list()[0].status is SkillStatus.VERIFIED
    assert planner.peek_selected_skill(plan.task_id) is not None
    assert session.snapshot() is None
    assert not session.respond(pending.review_id, True)


@pytest.mark.parametrize("reply", ("아니요", "취소"))
def test_declining_never_registers_a_skill(tmp_path: Path, reply: str) -> None:
    catalog, planner, session = make_session(tmp_path)
    _token, waiting, result, thread = start_review(session, planner.plan("시스템 정보 확인"))
    assert waiting.wait(1)
    assert session.respond_text(reply)
    thread.join(2)
    assert result == {"accepted": False}
    assert not catalog.list()


def test_stop_and_timeout_clear_the_pending_request_without_registration(tmp_path: Path) -> None:
    catalog, planner, session = make_session(tmp_path, timeout=0.06)
    _token, waiting, result, thread = start_review(session, planner.plan("시스템 정보 확인"))
    assert waiting.wait(1)
    thread.join(1)
    assert result == {"accepted": False}
    assert session.snapshot() is None
    token, waiting, result, thread = start_review(session, planner.plan("시스템 정보 확인"))
    assert waiting.wait(1)
    token.cancel()
    thread.join(1)
    assert result == {"accepted": False}
    assert not catalog.list()


def test_existing_skill_reuses_exact_reviewed_version_and_detects_retirement(
    tmp_path: Path,
) -> None:
    catalog, planner, session = make_session(tmp_path)
    approved = catalog.approve(catalog.propose(proposal(Planner().plan("확인"))).skill_id)
    plan = planner.plan("시스템 정보 확인")
    _token, waiting, result, thread = start_review(session, plan)
    assert waiting.wait(1)
    assert session.snapshot().kind == "REUSE"
    catalog.retire(approved.skill_id)
    assert session.respond_text("예")
    thread.join(2)
    assert str(result["error"]) == "SKILL_CHANGED_DURING_REVIEW"
    assert "accepted" not in result


def test_policy_denial_precedes_candidate_creation_and_review(tmp_path: Path) -> None:
    catalog, planner, session = make_session(tmp_path)

    def denied(action: Action) -> PolicyContext:
        return context(action).model_copy(update={"target_matches_plan": False})

    _token, waiting, result, thread = start_review(
        session,
        planner.plan("시스템 정보 확인"),
        policy=denied,
    )
    thread.join(1)
    assert not waiting.is_set()
    assert str(result["error"]) == "SKILL_PLAN_POLICY_DENIED"
    assert not catalog.list()


def test_runtime_does_not_execute_until_review_response_and_then_accepts_next_task(
    tmp_path: Path,
) -> None:
    from skilla_core.always_on_runtime import AlwaysOnAgentRuntime, AlwaysOnState
    from skilla_core.intent import GateResult, GateRoute
    from skilla_core.models import ActionStatus
    from skilla_core.runtime_models import TaskOutcome
    from skilla_core.voice_command import VoiceCommandDecision, VoiceCommandStatus

    _catalog, planner, session = make_session(tmp_path)
    executed = []

    class Coordinator:
        def process_text(self, text: str, **kwargs: object) -> VoiceCommandDecision:
            return VoiceCommandDecision(
                status=VoiceCommandStatus.PLAN_READY,
                reason="TYPED_PLAN_READY",
                gate=GateResult(
                    route=GateRoute.PLAN,
                    accepted=True,
                    reason="COMMAND_ACCEPTED",
                    confidence=1,
                ),
                plan=planner.plan(text),
            )

    class Orchestrator:
        def run(self, plan: Plan, provider: object) -> TaskOutcome:
            executed.append(plan.task_id)
            return TaskOutcome(
                task_id=plan.task_id,
                status=ActionStatus.SUCCEEDED,
                completed_actions=1,
                reason="POSTCONDITIONS_VERIFIED",
            )

    runtime = AlwaysOnAgentRuntime(
        coordinator_factory=lambda _token: Coordinator(),
        orchestrator_factory=lambda _token: Orchestrator(),
        policy_context_provider=context,
        skill_session=session,
    )
    try:
        for expected_kind in ("REGISTER", "REUSE"):
            runtime.submit_text("시스템 정보 확인")
            deadline = time.monotonic() + 2
            while runtime.state is not AlwaysOnState.REVIEWING and time.monotonic() < deadline:
                time.sleep(0.01)
            assert runtime.state is AlwaysOnState.REVIEWING
            snapshot = runtime.status_snapshot()
            assert snapshot.skill_review.kind == expected_kind
            assert len(executed) == (0 if expected_kind == "REGISTER" else 1)
            assert runtime.submit_text("네").reason == "SKILL_REVIEW_RESPONSE_ACCEPTED"
            runtime.wait_for_idle(timeout_seconds=2)
            assert runtime.state is AlwaysOnState.IDLE
        assert len(executed) == 2
    finally:
        runtime.close()
