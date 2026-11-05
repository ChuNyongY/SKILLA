from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from threading import Event, Lock
from time import monotonic
from uuid import UUID, uuid4

from .agent_session import PolicyContextProvider
from .cancellation import CancellationToken
from .models import Decision, FrozenModel, Plan
from .policy import PolicyEngine
from .registry import CapabilityRegistry
from .review_response import parse_review_response
from .skill_runtime import (
    LocalSkillCatalog,
    SkillAwarePlanner,
    SkillProposal,
    SkillRecord,
    SkillRetrievalDecision,
    SkillStatus,
)


class SkillReviewKind(StrEnum):
    REUSE = "REUSE"
    REGISTER = "REGISTER"


class PendingSkillReview(FrozenModel):
    review_id: UUID
    task_id: UUID
    kind: SkillReviewKind
    title: str
    request: str
    planned_steps: tuple[str, ...]
    procedure: tuple[str, ...]
    dynamic_inputs: tuple[str, ...]
    verification_rules: tuple[str, ...]
    safety_summary: tuple[str, ...]


class SkillSessionError(RuntimeError):
    pass


class SkillSession:
    """Bind one human review to one exact plan; never grant action approval."""

    def __init__(
        self,
        catalog: LocalSkillCatalog,
        planner: SkillAwarePlanner,
        registry: CapabilityRegistry,
        proposal_author: Callable[[Plan], SkillProposal],
        *,
        timeout_seconds: float = 120,
    ) -> None:
        if not 0 < timeout_seconds <= 600:
            raise ValueError("invalid skill review timeout")
        self._catalog = catalog
        self._planner = planner
        self._policy = PolicyEngine(registry)
        self._proposal_author = proposal_author
        self._timeout = timeout_seconds
        self._lock = Lock()
        self._event = Event()
        self._pending: PendingSkillReview | None = None
        self._accepted: bool | None = None
        self._deadline = 0.0

    def snapshot(self) -> PendingSkillReview | None:
        with self._lock:
            return self._pending

    def respond(self, review_id: UUID, accepted: bool) -> bool:
        if type(accepted) is not bool:
            return False
        with self._lock:
            if (
                self._pending is None
                or self._pending.review_id != review_id
                or self._accepted is not None
                or monotonic() >= self._deadline
            ):
                return False
            self._accepted = accepted
            self._event.set()
            return True

    def respond_text(self, text: str) -> bool:
        accepted = parse_review_response(text)
        if accepted is None:
            return False
        pending = self.snapshot()
        return pending is not None and self.respond(pending.review_id, accepted)

    def prepare(
        self,
        plan: Plan,
        cancellation: CancellationToken,
        context_provider: PolicyContextProvider,
        on_waiting: Callable[[], None],
    ) -> bool:
        summaries = []
        for index, action in enumerate(plan.steps, 1):
            decision = self._policy.evaluate(action, context_provider(action))
            if decision.decision is Decision.DENY:
                raise SkillSessionError("SKILL_PLAN_POLICY_DENIED")
            label = {
                Decision.GREEN: "기본 안전 조건 충족",
                Decision.YELLOW: "실행 전 별도 승인 필요",
                Decision.RED: "높은 위험 · 실행 전 별도 승인 필요",
            }[decision.decision]
            summaries.append(f"{index}. {label} (R{int(decision.risk)})")
        selection = self._planner.peek_selected_skill(plan.task_id)
        current = None if selection is None else selection.skill
        if current is None:
            retrieval = self._catalog.retrieve(plan.goal)
            if retrieval.decision is SkillRetrievalDecision.AMBIGUOUS:
                raise SkillSessionError("SKILL_CANDIDATES_AMBIGUOUS")
        proposal = self._proposal_author(plan) if current is None else current
        if current is None and (
            set(proposal.allowed_capabilities) != {step.capability_id for step in plan.steps}
        ):
            raise SkillSessionError("SKILL_PROPOSAL_CAPABILITIES_CHANGED")
        if cancellation.is_cancelled:
            return False
        review = PendingSkillReview(
            review_id=uuid4(),
            task_id=plan.task_id,
            kind=SkillReviewKind.REGISTER if current is None else SkillReviewKind.REUSE,
            title=proposal.title,
            request=plan.goal[:400],
            planned_steps=tuple(step.purpose[:400] for step in plan.steps),
            procedure=proposal.procedure,
            dynamic_inputs=proposal.dynamic_inputs,
            verification_rules=proposal.verification_rules,
            safety_summary=tuple(summaries),
        )
        with self._lock:
            if self._pending is not None:
                raise SkillSessionError("SKILL_REVIEW_ALREADY_PENDING")
            self._event.clear()
            self._accepted = None
            self._deadline = monotonic() + self._timeout
            self._pending = review
        try:
            on_waiting()
            while not self._event.wait(0.05):
                if cancellation.is_cancelled or monotonic() >= self._deadline:
                    return False
            with self._lock:
                accepted = self._accepted
            if not accepted or cancellation.is_cancelled:
                return False
            if current is None:
                # The proposal is user-reviewed but has no successful execution evidence yet.
                draft = self._catalog.propose(proposal)
                current = self._catalog.approve(draft.skill_id)
                self._planner.bind_reviewed_skill(plan.task_id, current)
            else:
                self._check_current(current, plan)
            return not cancellation.is_cancelled
        finally:
            with self._lock:
                self._pending = None
                self._accepted = None
                self._event.clear()

    def _check_current(self, selected: SkillRecord, plan: Plan) -> None:
        current = self._catalog.require(selected.skill_id)
        if (
            current != selected
            or current.status is not SkillStatus.VERIFIED
            or not {step.capability_id for step in plan.steps} <= set(current.allowed_capabilities)
        ):
            raise SkillSessionError("SKILL_CHANGED_DURING_REVIEW")
