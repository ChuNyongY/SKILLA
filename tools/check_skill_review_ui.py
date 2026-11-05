"""Exercise the real review HUD with a temporary skill store and read-only execution."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from skilla_core.always_on_runtime import AlwaysOnAgentRuntime
from skilla_core.approval import ApprovalTokenService
from skilla_core.audit import InMemoryAuditSink
from skilla_core.intent import GateResult, GateRoute
from skilla_core.models import Action, Plan, PolicyContext, Postcondition
from skilla_core.native_readonly import NativeReadOnlyExecutor
from skilla_core.orchestrator import Orchestrator
from skilla_core.policy import PolicyEngine
from skilla_core.registry import default_registry
from skilla_core.skill_authoring import SkillDraftAuthor
from skilla_core.skill_runtime import LocalSkillCatalog, SkillAwarePlanner, SkillProposal
from skilla_core.skill_session import SkillSession
from skilla_core.status_surface import RuntimeStatusPresenter, TkStatusView
from skilla_core.verifier import PredicateVerifier
from skilla_core.voice_command import VoiceCommandDecision, VoiceCommandStatus


class ReadOnlyPlanner:
    def plan(self, goal: str, **_kwargs: object) -> Plan:
        return Plan(
            goal=goal,
            steps=(
                Action(
                    capability_id="system.info.read",
                    purpose="현재 Windows 시스템 정보 확인",
                    expected_postconditions=(Postcondition(predicate="execution.success"),),
                ),
            ),
        )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    generated = json.loads((root / "output/skill_plan_proposal_nim_smoke.json").read_text("utf-8"))
    proposed = SkillProposal.model_validate(generated["proposal"])
    if proposed.allowed_capabilities != ("system.info.read",):
        raise ValueError("this UI check only permits system.info.read")
    with tempfile.TemporaryDirectory(prefix="skilla-ui-review-") as temporary:
        registry = default_registry()
        catalog = LocalSkillCatalog(Path(temporary) / "skills.sqlite3", registry)
        planner = SkillAwarePlanner(ReadOnlyPlanner(), catalog)

        class RecordedProposal:
            def complete(self, _system: str, _user: str) -> str:
                return json.dumps(generated["proposal"], ensure_ascii=False)

        session = SkillSession(
            catalog,
            planner,
            registry,
            SkillDraftAuthor(RecordedProposal(), catalog).propose_from_plan,
            timeout_seconds=600,
        )

        class Coordinator:
            def process_text(self, text: str, **_kwargs: object) -> VoiceCommandDecision:
                return VoiceCommandDecision(
                    status=VoiceCommandStatus.PLAN_READY,
                    reason="TYPED_PLAN_READY",
                    plan=planner.plan(text),
                    gate=GateResult(
                        accepted=True,
                        route=GateRoute.PLAN,
                        reason="COMMAND_ACCEPTED",
                        confidence=1,
                    ),
                )

        runtime = AlwaysOnAgentRuntime(
            coordinator_factory=lambda _token: Coordinator(),
            orchestrator_factory=lambda token: Orchestrator(
                policy=PolicyEngine(registry),
                executor=NativeReadOnlyExecutor((root,)),
                verifier=PredicateVerifier(),
                audit=InMemoryAuditSink(),
                approvals=ApprovalTokenService(b"ui-check-only-not-a-product-secret"),
                cancellation=token,
            ),
            policy_context_provider=lambda _action: PolicyContext(
                addressed_confidence=1,
                intent_confidence=1,
                target_confidence=1,
                target_matches_plan=True,
            ),
            skill_session=session,
        )
        view = TkStatusView(
            title="SKILLA 읽기 전용 흐름 검증 · 마이크와 스피커 미사용",
            respond_skill_review=runtime.respond_skill_review,
            open_text_command=lambda: runtime.submit_text("시스템 정보 확인"),
        )
        view.schedule(300, lambda: runtime.submit_text("시스템 정보 확인"))
        terminal_outcomes = []

        def snapshot_provider():
            snapshot = runtime.status_snapshot()
            if snapshot.last_event_type is not None and snapshot.last_event_type.value in {
                "TASK_COMPLETED",
                "TASK_ABORTED",
                "FAILED",
            }:
                entry = {
                    "sequence": snapshot.sequence,
                    "event": snapshot.last_event_type.value,
                    "reason": snapshot.last_reason,
                    "completed_actions": snapshot.completed_actions,
                }
                if not terminal_outcomes or terminal_outcomes[-1] != entry:
                    terminal_outcomes.append(entry)
            return snapshot

        try:
            RuntimeStatusPresenter(
                status_provider=snapshot_provider,
                request_task_stop=runtime.cancel_current_task,
                request_capture_stop=lambda: True,
                request_runtime_stop=runtime.close,
                view=view,
            ).run()
        finally:
            snapshot = runtime.status_snapshot()
            report = {
                "state": snapshot.state.value,
                "last_reason": snapshot.last_reason,
                "completed_actions": snapshot.completed_actions,
                "stored_skills": len(catalog.list()),
                "microphone_used": False,
                "speaker_used": False,
                "terminal_outcomes": terminal_outcomes,
            }
            (root / "output/skill_review_ui_smoke.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            runtime.close()


if __name__ == "__main__":
    main()
