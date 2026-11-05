from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextlib import suppress
from enum import StrEnum
from threading import Lock, Thread
from time import perf_counter_ns
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .agent_session import (
    OrchestratorFactory,
    PlannerContextProvider,
    PolicyContextProvider,
    SkillTraceObserver,
    SkillUseObserver,
)
from .cancellation import CancellationToken
from .intent import LocalStopDetector
from .models import ActionStatus, FrozenModel, Plan
from .observation_loop import (
    BoundedObservationAgent,
    ObservationLoopStatus,
    ObservationRoundRunner,
)
from .policy_context import gate_scoped_policy_context_provider
from .registry import CapabilityRegistry
from .runtime_models import TaskOutcome
from .skill_runtime import PlanProposer
from .skill_session import PendingSkillReview, SkillReviewKind, SkillSession, SkillSessionError
from .user_visible_result import UserVisibleResultSnapshot, UserVisibleResultStore
from .voice import CaptureStatus, VoiceCaptureResult
from .voice_command import (
    VoiceCommandCoordinator,
    VoiceCommandStatus,
    validate_trusted_text_command,
)
from .voice_feedback import FeedbackCode, VoiceFeedbackPresenter


class AlwaysOnState(StrEnum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    REVIEWING = "REVIEWING"
    EXECUTING = "EXECUTING"
    CLOSED = "CLOSED"


class RuntimeEventType(StrEnum):
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_ABORTED = "TASK_ABORTED"
    STOP_ACCEPTED = "STOP_ACCEPTED"
    BUSY_IGNORED = "BUSY_IGNORED"
    ROUTED = "ROUTED"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


class RuntimeEvent(FrozenModel):
    event_type: RuntimeEventType
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


class RuntimeStatusSnapshot(FrozenModel):
    state: AlwaysOnState
    last_event_type: RuntimeEventType | None = None
    last_reason: str = Field(
        default="RUNTIME_READY",
        min_length=2,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    completed_actions: int = Field(default=0, ge=0)
    feedback_delivered: bool | None = None
    skill_trace_recorded: bool | None = None
    skill_use_recorded: bool | None = None
    result: UserVisibleResultSnapshot | None = None
    skill_review: PendingSkillReview | None = None
    sequence: int = Field(default=0, ge=0)


class RuntimeCoordinatorFactory(Protocol):
    def __call__(self, cancellation: CancellationToken) -> VoiceCommandCoordinator: ...


ObservationRoundRunnerFactory = Callable[
    [CancellationToken, PolicyContextProvider], ObservationRoundRunner
]


class AlwaysOnAgentRuntime:
    """Coordinate sequential tasks while accepting an exact local STOP concurrently."""

    def __init__(
        self,
        *,
        coordinator_factory: RuntimeCoordinatorFactory,
        orchestrator_factory: OrchestratorFactory,
        policy_context_provider: PolicyContextProvider,
        feedback: VoiceFeedbackPresenter | None = None,
        stop_detector: LocalStopDetector | None = None,
        planner_context_provider: PlannerContextProvider | None = None,
        thread_factory: Callable[..., Thread] = Thread,
        skill_trace_observer: SkillTraceObserver | None = None,
        skill_use_observer: SkillUseObserver | None = None,
        observation_planner: PlanProposer | None = None,
        observation_registry: CapabilityRegistry | None = None,
        observation_round_runner_factory: ObservationRoundRunnerFactory | None = None,
        user_visible_results: UserVisibleResultStore | None = None,
        skill_session: SkillSession | None = None,
    ) -> None:
        self._coordinator_factory = coordinator_factory
        self._orchestrator_factory = orchestrator_factory
        self._policy_context_provider = policy_context_provider
        self._feedback = feedback
        self._stop_detector = stop_detector or LocalStopDetector()
        self._planner_context_provider = planner_context_provider
        self._thread_factory = thread_factory
        self._skill_trace_observer = skill_trace_observer
        self._skill_use_observer = skill_use_observer
        observation_components = (
            observation_planner,
            observation_registry,
            observation_round_runner_factory,
        )
        if any(item is None for item in observation_components) and any(
            item is not None for item in observation_components
        ):
            raise ValueError("observation loop components must be configured together")
        self._observation_planner = observation_planner
        self._observation_registry = observation_registry
        self._observation_round_runner_factory = observation_round_runner_factory
        self._user_visible_results = user_visible_results
        self._skill_session = skill_session
        self._lock = Lock()
        self._state = AlwaysOnState.IDLE
        self._task_token: CancellationToken | None = None
        self._worker: Thread | None = None
        self._events: deque[RuntimeEvent] = deque(maxlen=100)
        self._status = RuntimeStatusSnapshot(state=AlwaysOnState.IDLE)

    @property
    def state(self) -> AlwaysOnState:
        with self._lock:
            return self._state

    def status_snapshot(self) -> RuntimeStatusSnapshot:
        """Return a privacy-minimized status without consuming the event queue."""
        result = (
            None
            if self._user_visible_results is None
            else self._user_visible_results.snapshot()
        )
        with self._lock:
            review = None if self._skill_session is None else self._skill_session.snapshot()
            return self._status.model_copy(
                update={"result": result, "skill_review": review}, deep=True,
            )

    def respond_skill_review(self, review_id: UUID, accepted: bool) -> bool:
        with self._lock:
            if (
                self._state is not AlwaysOnState.REVIEWING or self._skill_session is None
                or self._task_token is None or self._task_token.is_cancelled
            ):
                return False
            return self._skill_session.respond(review_id, accepted)

    def submit_capture(
        self,
        capture: VoiceCaptureResult,
        *,
        trusted_context: dict[str, object] | None = None,
    ) -> RuntimeEvent:
        if not isinstance(capture, VoiceCaptureResult):
            raise TypeError("capture must be a VoiceCaptureResult")
        return self._submit_input(capture, trusted_context=trusted_context)

    def submit_text(
        self,
        text: str,
        *,
        trusted_context: dict[str, object] | None = None,
    ) -> RuntimeEvent:
        """Submit explicit local text without opening or imitating a microphone."""
        normalized = validate_trusted_text_command(text)
        return self._submit_input(normalized, trusted_context=trusted_context)

    def cancel_current_task(self) -> RuntimeEvent:
        """Cancel only the active task; keep the microphone and runtime available."""
        with self._lock:
            if (
                self._state in {
                    AlwaysOnState.PLANNING, AlwaysOnState.REVIEWING, AlwaysOnState.EXECUTING,
                }
                and self._task_token is not None
            ):
                self._task_token.cancel("LOCAL_STOP")
                event = RuntimeEvent(
                    event_type=RuntimeEventType.STOP_ACCEPTED,
                    reason="LOCAL_STOP_ACCEPTED",
                )
            else:
                event = RuntimeEvent(
                    event_type=RuntimeEventType.ROUTED,
                    reason="NO_ACTIVE_TASK",
                )
            self._record_status_locked(event)
            return event

    def _submit_input(
        self,
        command: VoiceCaptureResult | str,
        *,
        trusted_context: dict[str, object] | None,
    ) -> RuntimeEvent:
        with self._lock:
            if self._state is AlwaysOnState.CLOSED:
                event = RuntimeEvent(
                    event_type=RuntimeEventType.CLOSED,
                    reason="RUNTIME_CLOSED",
                )
                self._record_status_locked(event)
                return event
            if self._state in {
                AlwaysOnState.PLANNING, AlwaysOnState.REVIEWING, AlwaysOnState.EXECUTING,
            }:
                transcript = command if isinstance(command, str) else command.transcript
                if (
                    self._state is AlwaysOnState.REVIEWING and self._skill_session is not None
                    and (isinstance(command, str) or command.status is CaptureStatus.TRANSCRIBED)
                    and transcript is not None and self._task_token is not None
                    and not self._task_token.is_cancelled
                    and self._skill_session.respond_text(transcript)
                ):
                    event = RuntimeEvent(
                        event_type=RuntimeEventType.ROUTED, reason="SKILL_REVIEW_RESPONSE_ACCEPTED",
                    )
                    self._record_status_locked(event)
                    return event
                return self._handle_busy_input_locked(command)
            token = CancellationToken()
            if self._user_visible_results is not None:
                self._user_visible_results.clear()
            self._task_token = token
            self._state = AlwaysOnState.PLANNING
            try:
                worker = self._thread_factory(
                    target=self._plan_and_run,
                    args=(
                        command,
                        None if trusted_context is None else dict(trusted_context),
                        token,
                    ),
                    name="skilla-task-worker",
                    daemon=True,
                )
                self._worker = worker
                worker.start()
            except Exception:
                self._clear_task_locked(token)
                event = RuntimeEvent(
                    event_type=RuntimeEventType.FAILED,
                    reason="TASK_WORKER_START_FAILED",
                )
                self._record_status_locked(event)
                return event
            event = RuntimeEvent(
                event_type=RuntimeEventType.TASK_STARTED,
                reason="PLANNING_STARTED",
            )
            self._record_status_locked(event)
        return event

    def poll_event(self) -> RuntimeEvent | None:
        with self._lock:
            return self._events.popleft() if self._events else None

    def wait_for_idle(self, *, timeout_seconds: float = 5.0) -> RuntimeEvent | None:
        if isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be within 0..30")
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout=timeout_seconds)
            if worker.is_alive():
                return None
        return self.poll_event()

    def close(self, *, timeout_seconds: float = 5.0) -> RuntimeEvent:
        if isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be within 0..30")
        with self._lock:
            if self._state is AlwaysOnState.CLOSED:
                event = RuntimeEvent(
                    event_type=RuntimeEventType.CLOSED,
                    reason="RUNTIME_CLOSED",
                )
                self._record_status_locked(event)
                return event
            token = self._task_token
            worker = self._worker
            self._state = AlwaysOnState.CLOSED
            if token is not None:
                token.cancel("RUNTIME_SHUTDOWN")
        if worker is not None:
            worker.join(timeout=timeout_seconds)
            if worker.is_alive():
                event = RuntimeEvent(
                    event_type=RuntimeEventType.FAILED,
                    reason="RUNTIME_STOP_TIMEOUT",
                )
                with self._lock:
                    self._record_status_locked(event)
                return event
        event = RuntimeEvent(
            event_type=RuntimeEventType.CLOSED,
            reason="RUNTIME_CLOSED",
        )
        with self._lock:
            self._record_status_locked(event)
        return event

    def _handle_busy_input_locked(
        self,
        command: VoiceCaptureResult | str,
    ) -> RuntimeEvent:
        transcript = command if isinstance(command, str) else command.transcript
        if (
            (isinstance(command, str) or command.status is CaptureStatus.TRANSCRIBED)
            and transcript is not None
            and self._stop_detector.matches(transcript)
            and self._task_token is not None
        ):
            self._task_token.cancel("LOCAL_STOP")
            event = RuntimeEvent(
                event_type=RuntimeEventType.STOP_ACCEPTED,
                reason="LOCAL_STOP_ACCEPTED",
            )
            self._record_status_locked(event)
            return event
        event = RuntimeEvent(
            event_type=RuntimeEventType.BUSY_IGNORED,
            reason="ACTIVE_TASK_ACCEPTS_STOP_ONLY",
        )
        self._record_status_locked(event)
        return event

    def _plan_and_run(
        self,
        command: VoiceCaptureResult | str,
        trusted_context: dict[str, object] | None,
        token: CancellationToken,
    ) -> None:
        task_started_ns = perf_counter_ns()
        if trusted_context is None:
            try:
                trusted_context = (
                    dict(self._planner_context_provider())
                    if self._planner_context_provider is not None
                    else {}
                )
            except Exception:
                self._finish_worker(token, self._failed("CONTEXT_COLLECTION_FAILED"))
                return
        if token.is_cancelled:
            self._finish_worker(
                token,
                RuntimeEvent(
                    event_type=RuntimeEventType.ROUTED,
                    reason="PLANNING_CANCELLED",
                ),
            )
            return
        try:
            coordinator = self._coordinator_factory(token)
            if isinstance(command, str):
                decision = coordinator.process_text(
                    command,
                    task_active=False,
                    trusted_context=trusted_context,
                )
            else:
                decision = coordinator.process(
                    command,
                    task_active=False,
                    trusted_context=trusted_context,
                )
        except Exception:
            self._finish_worker(token, self._failed("COMMAND_COORDINATION_FAILED"))
            return

        with self._lock:
            if self._state is AlwaysOnState.CLOSED:
                return
            if token.is_cancelled:
                self._finish_worker_locked(
                    token,
                    RuntimeEvent(
                        event_type=RuntimeEventType.ROUTED,
                        reason="PLANNING_CANCELLED",
                    ),
                )
                return
            if decision.status is not VoiceCommandStatus.PLAN_READY:
                event_type = (
                    RuntimeEventType.FAILED
                    if decision.status
                    in {VoiceCommandStatus.FAILED, VoiceCommandStatus.CAPTURE_ABORTED}
                    else RuntimeEventType.ROUTED
                )
                self._finish_worker_locked(
                    token,
                    self._safe_event(event_type, decision.reason),
                )
                return
            if decision.plan is None:
                self._finish_worker_locked(
                    token,
                    self._failed("PLAN_READY_WITHOUT_PLAN"),
                )
                return
            plan = decision.plan
            try:
                policy_context_provider = gate_scoped_policy_context_provider(
                    self._policy_context_provider,
                    decision.gate,
                )
            except Exception:
                self._finish_worker_locked(
                    token,
                    self._failed("COMMAND_DECISION_INVALID"),
                )
                return
        if self._skill_session is not None:
            try:
                accepted = self._skill_session.prepare(
                    plan, token, policy_context_provider,
                    lambda: self._notify_skill_review(token),
                )
            except SkillSessionError as error:
                self._finish_worker(token, self._failed(str(error)))
                return
            except Exception:
                self._finish_worker(token, self._failed("SKILL_REVIEW_FAILED"))
                return
            if not accepted:
                self._finish_worker(
                    token, RuntimeEvent(
                        event_type=RuntimeEventType.TASK_ABORTED,
                        reason="SKILL_REVIEW_CANCELLED", task_id=plan.task_id,
                    ),
                )
                return
        with self._lock:
            if token.is_cancelled or self._state is AlwaysOnState.CLOSED:
                self._finish_worker_locked(token, self._failed("PLANNING_CANCELLED"))
                return
            self._state = AlwaysOnState.EXECUTING
            self._status = self._status.model_copy(
                update={
                    "state": AlwaysOnState.EXECUTING,
                    "last_reason": "EXECUTION_STARTED",
                    "sequence": self._status.sequence + 1,
                }
            )

        self._run_task(
            plan,
            token,
            policy_context_provider,
            task_started_ns=task_started_ns,
        )

    def _notify_skill_review(self, token: CancellationToken) -> None:
        with self._lock:
            if token.is_cancelled or self._state is AlwaysOnState.CLOSED:
                return
            self._state = AlwaysOnState.REVIEWING
            self._status = self._status.model_copy(update={
                "state": AlwaysOnState.REVIEWING, "last_reason": "SKILL_REVIEW_REQUIRED",
                "sequence": self._status.sequence + 1,
            })
        review = None if self._skill_session is None else self._skill_session.snapshot()
        if self._feedback is not None and review is not None:
            with suppress(Exception):
                self._feedback.present(
                    FeedbackCode.SKILL_REGISTER_REVIEW
                    if review.kind is SkillReviewKind.REGISTER else FeedbackCode.SKILL_REUSE_REVIEW,
                    cancellation=token,
                )

    def _run_task(
        self,
        plan: Plan,
        token: CancellationToken,
        policy_context_provider: PolicyContextProvider,
        *,
        task_started_ns: int,
    ) -> None:
        try:
            outcome, trace_plan = self._execute_plan(
                plan, token, policy_context_provider
            )
            skill_trace_recorded = self._record_skill_trace(trace_plan, outcome)
            skill_use_recorded = self._record_skill_use(
                plan,
                outcome,
                elapsed_ms=(perf_counter_ns() - task_started_ns) // 1_000_000,
            )
            feedback_delivered = self._deliver_feedback(outcome, token)
            event = RuntimeEvent(
                event_type=(
                    RuntimeEventType.TASK_COMPLETED
                    if outcome.status is ActionStatus.SUCCEEDED
                    else RuntimeEventType.TASK_ABORTED
                ),
                reason=outcome.reason,
                task_id=outcome.task_id,
                completed_actions=outcome.completed_actions,
                feedback_delivered=feedback_delivered,
                skill_trace_recorded=skill_trace_recorded,
                skill_use_recorded=skill_use_recorded,
            )
        except Exception:
            event = RuntimeEvent(
                event_type=RuntimeEventType.FAILED,
                reason="ORCHESTRATION_FAILED",
                task_id=plan.task_id,
            )
        self._finish_worker(token, event)

    def _execute_plan(
        self,
        plan: Plan,
        token: CancellationToken,
        policy_context_provider: PolicyContextProvider,
    ) -> tuple[TaskOutcome, Plan]:
        if not plan.continue_after_verification:
            return (
                self._orchestrator_factory(token).run(plan, policy_context_provider),
                plan,
            )
        if (
            self._observation_planner is None
            or self._observation_registry is None
            or self._observation_round_runner_factory is None
        ):
            return (
                TaskOutcome(
                    task_id=plan.task_id,
                    status=ActionStatus.ABORTED,
                    completed_actions=0,
                    reason="OBSERVATION_LOOP_UNAVAILABLE",
                ),
                plan,
            )
        loop = BoundedObservationAgent(
            self._observation_planner,
            self._observation_round_runner_factory(token, policy_context_provider),
            None,
            self._observation_registry,
        ).run(plan.goal, initial_plan=plan)
        outcome = TaskOutcome(
            task_id=plan.task_id,
            status=(
                ActionStatus.SUCCEEDED
                if loop.status is ObservationLoopStatus.COMPLETED
                else ActionStatus.ABORTED
            ),
            completed_actions=len(loop.observations),
            reason=loop.reason,
        )
        trace_plan = Plan(
            task_id=plan.task_id,
            goal=plan.goal,
            steps=tuple(
                action
                for executed_plan in loop.executed_plans
                for action in executed_plan.steps
            ),
        )
        return outcome, trace_plan

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

    def _deliver_feedback(
        self,
        outcome: TaskOutcome,
        token: CancellationToken,
    ) -> bool | None:
        if self._feedback is None or token.is_cancelled:
            return None
        try:
            self._feedback.present_outcome(outcome, cancellation=token)
        except Exception:
            return False
        return True

    def _finish_worker(self, token: CancellationToken, event: RuntimeEvent) -> None:
        with self._lock:
            self._finish_worker_locked(token, event)

    def _finish_worker_locked(
        self,
        token: CancellationToken,
        event: RuntimeEvent,
    ) -> None:
        self._events.append(event)
        if self._state is not AlwaysOnState.CLOSED and self._task_token is token:
            self._clear_task_locked(token)
        self._record_status_locked(event)

    def _clear_task_locked(self, token: CancellationToken) -> None:
        if self._task_token is token:
            self._task_token = None
            self._worker = None
            if self._state is not AlwaysOnState.CLOSED:
                self._state = AlwaysOnState.IDLE

    def _record_status_locked(self, event: RuntimeEvent) -> None:
        self._status = RuntimeStatusSnapshot(
            state=self._state,
            last_event_type=event.event_type,
            last_reason=event.reason,
            completed_actions=event.completed_actions,
            feedback_delivered=event.feedback_delivered,
            skill_trace_recorded=event.skill_trace_recorded,
            skill_use_recorded=event.skill_use_recorded,
            sequence=self._status.sequence + 1,
        )

    @staticmethod
    def _safe_event(event_type: RuntimeEventType, reason: str) -> RuntimeEvent:
        try:
            return RuntimeEvent(event_type=event_type, reason=reason)
        except ValueError:
            return RuntimeEvent(
                event_type=RuntimeEventType.FAILED,
                reason="COMMAND_DECISION_INVALID",
            )

    @staticmethod
    def _failed(reason: str) -> RuntimeEvent:
        return RuntimeEvent(event_type=RuntimeEventType.FAILED, reason=reason)
