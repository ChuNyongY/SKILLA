from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from enum import StrEnum
from time import perf_counter_ns
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .cancellation import CancellationToken
from .models import Action, ActionStatus, FrozenModel, Plan, PolicyContext
from .orchestrator import Orchestrator
from .policy_context import gate_scoped_policy_context_provider
from .runtime_models import TaskOutcome
from .voice import AudioFrame, VoiceCaptureResult, VoicePipeline
from .voice_command import VoiceCommandCoordinator, VoiceCommandStatus
from .voice_feedback import VoiceFeedbackPresenter


class AgentSessionStatus(StrEnum):
    NO_UTTERANCE = "NO_UTTERANCE"
    ROUTED = "ROUTED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class AgentSessionResult(FrozenModel):
    status: AgentSessionStatus
    reason: str = Field(
        min_length=2,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    task_id: UUID | None = None
    completed_actions: int = Field(default=0, ge=0)
    feedback_delivered: bool | None = None
    skill_trace_recorded: bool | None = None
    skill_use_recorded: bool | None = None


class FrameSource(Protocol):
    def frames(
        self,
        cancellation: CancellationToken,
        *,
        max_frames: int,
    ) -> Iterable[AudioFrame]: ...


class CoordinatorFactory(Protocol):
    def __call__(self, cancellation: CancellationToken) -> VoiceCommandCoordinator: ...


class OrchestratorFactory(Protocol):
    def __call__(self, cancellation: CancellationToken) -> Orchestrator: ...


class SkillTraceObserver(Protocol):
    def observe(self, plan: Plan, outcome: TaskOutcome) -> None: ...


class SkillUseObserver(Protocol):
    def observe(self, plan: Plan, outcome: TaskOutcome, *, elapsed_ms: int) -> bool: ...


PlannerContextProvider = Callable[[], Mapping[str, object]]
PolicyContextProvider = Callable[[Action], PolicyContext]


class AgentSession:
    """Bounded composition root for one captured utterance and one typed task."""

    def __init__(
        self,
        *,
        frame_source: FrameSource,
        voice_pipeline: VoicePipeline,
        coordinator_factory: CoordinatorFactory,
        orchestrator_factory: OrchestratorFactory,
        policy_context_provider: PolicyContextProvider,
        planner_context_provider: PlannerContextProvider | None = None,
        feedback: VoiceFeedbackPresenter | None = None,
        skill_trace_observer: SkillTraceObserver | None = None,
        skill_use_observer: SkillUseObserver | None = None,
    ) -> None:
        self._frame_source = frame_source
        self._voice_pipeline = voice_pipeline
        self._coordinator_factory = coordinator_factory
        self._orchestrator_factory = orchestrator_factory
        self._policy_context_provider = policy_context_provider
        self._planner_context_provider = planner_context_provider
        self._feedback = feedback
        self._skill_trace_observer = skill_trace_observer
        self._skill_use_observer = skill_use_observer

    def run_once(self, *, max_frames: int = 1_500) -> AgentSessionResult:
        if type(max_frames) is not int or not 1 <= max_frames <= 1_500:
            raise ValueError("max_frames must be an integer from 1 through 1500")
        cancellation = CancellationToken()
        capture = self._capture(cancellation, max_frames)
        if isinstance(capture, AgentSessionResult):
            return capture
        task_started_ns = perf_counter_ns()
        try:
            context = (
                dict(self._planner_context_provider())
                if self._planner_context_provider is not None
                else {}
            )
        except Exception:
            return AgentSessionResult(
                status=AgentSessionStatus.FAILED,
                reason="CONTEXT_COLLECTION_FAILED",
            )
        try:
            decision = self._coordinator_factory(cancellation).process(
                capture,
                task_active=False,
                trusted_context=context,
            )
        except Exception:
            return AgentSessionResult(
                status=AgentSessionStatus.FAILED,
                reason="COMMAND_COORDINATION_FAILED",
            )
        if decision.status is not VoiceCommandStatus.PLAN_READY:
            status = (
                AgentSessionStatus.FAILED
                if decision.status
                in {VoiceCommandStatus.FAILED, VoiceCommandStatus.CAPTURE_ABORTED}
                else AgentSessionStatus.ROUTED
            )
            try:
                return AgentSessionResult(status=status, reason=decision.reason)
            except ValueError:
                return AgentSessionResult(
                    status=AgentSessionStatus.FAILED,
                    reason="COMMAND_DECISION_INVALID",
                )
        if decision.plan is None:
            return AgentSessionResult(
                status=AgentSessionStatus.FAILED,
                reason="PLAN_READY_WITHOUT_PLAN",
            )
        try:
            policy_context_provider = gate_scoped_policy_context_provider(
                self._policy_context_provider,
                decision.gate,
            )
        except Exception:
            return AgentSessionResult(
                status=AgentSessionStatus.FAILED,
                reason="COMMAND_DECISION_INVALID",
            )
        try:
            outcome = self._orchestrator_factory(cancellation).run(
                decision.plan,
                policy_context_provider,
            )
        except Exception:
            return AgentSessionResult(
                status=AgentSessionStatus.FAILED,
                reason="ORCHESTRATION_FAILED",
                task_id=decision.plan.task_id,
            )
        trace_recorded = self._record_skill_trace(decision.plan, outcome)
        use_recorded = self._record_skill_use(
            decision.plan,
            outcome,
            elapsed_ms=(perf_counter_ns() - task_started_ns) // 1_000_000,
        )
        feedback_delivered = self._deliver_feedback(outcome, cancellation)
        return AgentSessionResult(
            status=(
                AgentSessionStatus.COMPLETED
                if outcome.status is ActionStatus.SUCCEEDED
                else AgentSessionStatus.ABORTED
            ),
            reason=outcome.reason,
            task_id=outcome.task_id,
            completed_actions=outcome.completed_actions,
            feedback_delivered=feedback_delivered,
            skill_trace_recorded=trace_recorded,
            skill_use_recorded=use_recorded,
        )

    def _record_skill_trace(self, plan: Plan, outcome: TaskOutcome) -> bool | None:
        if self._skill_trace_observer is None:
            return None
        try:
            self._skill_trace_observer.observe(plan, outcome)
        except Exception:
            return False
        return True

    def _record_skill_use(
        self,
        plan: Plan,
        outcome: TaskOutcome,
        *,
        elapsed_ms: int,
    ) -> bool | None:
        if self._skill_use_observer is None:
            return None
        try:
            return True if self._skill_use_observer.observe(
                plan, outcome, elapsed_ms=elapsed_ms
            ) else None
        except Exception:
            return False

    def _capture(
        self,
        cancellation: CancellationToken,
        max_frames: int,
    ) -> VoiceCaptureResult | AgentSessionResult:
        iterator = iter(
            self._frame_source.frames(cancellation, max_frames=max_frames)
        )
        capture: VoiceCaptureResult | None = None
        capture_failed = False
        cleanup_failed = False
        try:
            for frame in iterator:
                result = self._voice_pipeline.feed(frame)
                if result is not None:
                    capture = result
                    break
        except Exception:
            capture_failed = True
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    cleanup_failed = True
        if capture_failed or cleanup_failed:
            self._voice_pipeline.cancel()
            return AgentSessionResult(
                status=AgentSessionStatus.FAILED,
                reason=(
                    "AUDIO_CAPTURE_CLEANUP_FAILED"
                    if cleanup_failed
                    else "AUDIO_CAPTURE_FAILED"
                ),
            )
        if capture is not None:
            return capture
        self._voice_pipeline.cancel()
        return AgentSessionResult(
            status=AgentSessionStatus.NO_UTTERANCE,
            reason="NO_COMPLETE_UTTERANCE",
        )

    def _deliver_feedback(
        self,
        outcome: TaskOutcome,
        cancellation: CancellationToken,
    ) -> bool | None:
        if self._feedback is None or cancellation.is_cancelled:
            return None
        try:
            self._feedback.present_outcome(outcome, cancellation=cancellation)
        except Exception:
            return False
        return True
