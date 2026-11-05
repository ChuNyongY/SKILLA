from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from threading import Lock
from typing import Protocol
from uuid import UUID

from .models import FrozenModel
from .skill_authoring import SkillDraftArtifact, SkillExecutionTrace
from .skill_runtime import (
    SkillRecord,
    SkillRevisionAssessment,
    SkillRevisionDecision,
    SkillStatus,
)
from .skill_trace_store import PendingSkillTrace


class SkillDraftWorkflowCode(StrEnum):
    TRACE_NOT_PENDING = "TRACE_NOT_PENDING"
    ALREADY_IN_PROGRESS = "ALREADY_IN_PROGRESS"
    AUTHORING_FAILED = "AUTHORING_FAILED"
    AUTHORING_RESULT_INVALID = "AUTHORING_RESULT_INVALID"
    FINALIZE_FAILED_DRAFT_RETIRED = "FINALIZE_FAILED_DRAFT_RETIRED"
    FINALIZE_FAILED_RECOVERY_REQUIRED = "FINALIZE_FAILED_RECOVERY_REQUIRED"
    REVISION_TARGET_INVALID = "REVISION_TARGET_INVALID"
    REVISION_POLICY_NOT_MET = "REVISION_POLICY_NOT_MET"
    REVISION_RESULT_INVALID = "REVISION_RESULT_INVALID"


class SkillDraftWorkflowError(RuntimeError):
    def __init__(self, code: SkillDraftWorkflowCode) -> None:
        super().__init__(code.value)
        self.code = code


class PendingTraceWorkflowStore(Protocol):
    def require_pending(self, trace_id: UUID) -> PendingSkillTrace: ...

    def mark_consumed(self, trace_id: UUID) -> None: ...


class SkillDraftWorkflowAuthor(Protocol):
    def draft_initial(self, trace: SkillExecutionTrace) -> SkillDraftArtifact: ...

    def draft_revision(
        self,
        skill_id: UUID,
        trace: SkillExecutionTrace,
    ) -> SkillDraftArtifact: ...


class DraftRetirementCatalog(Protocol):
    def require(self, skill_id: UUID) -> SkillRecord: ...

    def assess_revision(
        self,
        skill_id: UUID,
        *,
        minimum_observations: int = 3,
        minimum_success_rate: float = 0.8,
    ) -> SkillRevisionAssessment: ...

    def retire(self, skill_id: UUID) -> SkillRecord: ...


class RevisionDraftTarget(FrozenModel):
    skill_id: UUID
    version: int
    updated_at: datetime


class InitialSkillDraftWorkflow:
    """Coordinate trace-to-draft creation while preserving a retryable trace on failure."""

    def __init__(
        self,
        *,
        trace_store: PendingTraceWorkflowStore,
        author: SkillDraftWorkflowAuthor,
        catalog: DraftRetirementCatalog,
    ) -> None:
        self._trace_store = trace_store
        self._author = author
        self._catalog = catalog
        self._lock = Lock()
        self._in_progress: set[UUID] = set()

    def create(self, trace_id: UUID) -> SkillDraftArtifact:
        self._reserve(trace_id)
        try:
            try:
                pending = self._trace_store.require_pending(trace_id)
            except Exception:
                raise SkillDraftWorkflowError(
                    SkillDraftWorkflowCode.TRACE_NOT_PENDING
                ) from None
            try:
                artifact = self._author.draft_initial(pending.trace)
            except Exception:
                raise SkillDraftWorkflowError(
                    SkillDraftWorkflowCode.AUTHORING_FAILED
                ) from None
            if artifact.draft.status is not SkillStatus.DRAFT:
                raise SkillDraftWorkflowError(
                    SkillDraftWorkflowCode.AUTHORING_RESULT_INVALID
                )
            try:
                self._trace_store.mark_consumed(trace_id)
            except Exception:
                self._compensate(artifact.draft.skill_id)
            return artifact
        finally:
            with self._lock:
                self._in_progress.discard(trace_id)

    def create_revision(
        self,
        trace_id: UUID,
        target: RevisionDraftTarget,
    ) -> SkillDraftArtifact:
        self._reserve(trace_id)
        try:
            try:
                pending = self._trace_store.require_pending(trace_id)
            except Exception:
                raise SkillDraftWorkflowError(
                    SkillDraftWorkflowCode.TRACE_NOT_PENDING
                ) from None
            current = self._validated_revision_target(target)
            try:
                artifact = self._author.draft_revision(current.skill_id, pending.trace)
            except Exception:
                raise SkillDraftWorkflowError(
                    SkillDraftWorkflowCode.AUTHORING_FAILED
                ) from None
            if not _valid_revision_artifact(artifact, current):
                self._retire_created(
                    artifact.draft.skill_id,
                    SkillDraftWorkflowCode.REVISION_RESULT_INVALID,
                )
            try:
                unchanged = self._catalog.require(current.skill_id)
            except Exception:
                self._retire_created(
                    artifact.draft.skill_id,
                    SkillDraftWorkflowCode.REVISION_TARGET_INVALID,
                )
            if unchanged != current or unchanged.status is not SkillStatus.VERIFIED:
                self._retire_created(
                    artifact.draft.skill_id,
                    SkillDraftWorkflowCode.REVISION_TARGET_INVALID,
                )
            try:
                self._trace_store.mark_consumed(trace_id)
            except Exception:
                self._compensate(artifact.draft.skill_id)
            return artifact
        finally:
            with self._lock:
                self._in_progress.discard(trace_id)

    def _reserve(self, trace_id: UUID) -> None:
        with self._lock:
            if trace_id in self._in_progress:
                raise SkillDraftWorkflowError(
                    SkillDraftWorkflowCode.ALREADY_IN_PROGRESS
                )
            self._in_progress.add(trace_id)

    def _compensate(self, skill_id: UUID) -> None:
        self._retire_created(
            skill_id,
            SkillDraftWorkflowCode.FINALIZE_FAILED_DRAFT_RETIRED,
        )

    def _retire_created(
        self,
        skill_id: UUID,
        success_code: SkillDraftWorkflowCode,
    ) -> None:
        try:
            retired = self._catalog.retire(skill_id)
        except Exception:
            raise SkillDraftWorkflowError(
                SkillDraftWorkflowCode.FINALIZE_FAILED_RECOVERY_REQUIRED
            ) from None
        if retired.skill_id != skill_id or retired.status is not SkillStatus.RETIRED:
            raise SkillDraftWorkflowError(
                SkillDraftWorkflowCode.FINALIZE_FAILED_RECOVERY_REQUIRED
            )
        raise SkillDraftWorkflowError(success_code)

    def _validated_revision_target(self, target: RevisionDraftTarget) -> SkillRecord:
        try:
            current = self._catalog.require(target.skill_id)
        except Exception:
            raise SkillDraftWorkflowError(
                SkillDraftWorkflowCode.REVISION_TARGET_INVALID
            ) from None
        if (
            current.status is not SkillStatus.VERIFIED
            or current.version != target.version
            or current.updated_at != target.updated_at
        ):
            raise SkillDraftWorkflowError(
                SkillDraftWorkflowCode.REVISION_TARGET_INVALID
            )
        try:
            assessment = self._catalog.assess_revision(current.skill_id)
        except Exception:
            raise SkillDraftWorkflowError(
                SkillDraftWorkflowCode.REVISION_POLICY_NOT_MET
            ) from None
        if assessment.decision is not SkillRevisionDecision.PROPOSE_REVISION:
            raise SkillDraftWorkflowError(
                SkillDraftWorkflowCode.REVISION_POLICY_NOT_MET
            )
        return current


def _valid_revision_artifact(
    artifact: SkillDraftArtifact,
    current: SkillRecord,
) -> bool:
    draft = artifact.draft
    return (
        draft.status is SkillStatus.DRAFT
        and draft.supersedes_skill_id == current.skill_id
        and draft.key == current.key
        and draft.version == current.version + 1
        and set(draft.allowed_capabilities) <= set(current.allowed_capabilities)
    )
