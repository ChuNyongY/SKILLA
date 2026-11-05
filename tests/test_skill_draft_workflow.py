from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Thread
from uuid import UUID, uuid4

import pytest

from skilla_core.skill_authoring import (
    SkillDraftArtifact,
    SkillExecutionTrace,
    SkillTraceStep,
)
from skilla_core.skill_draft_workflow import (
    InitialSkillDraftWorkflow,
    RevisionDraftTarget,
    SkillDraftWorkflowError,
)
from skilla_core.skill_runtime import (
    SkillOutcome,
    SkillPerformanceSummary,
    SkillRecord,
    SkillRevisionAssessment,
    SkillRevisionDecision,
    SkillStatus,
)
from skilla_core.skill_trace_store import PendingSkillTrace


def trace() -> SkillExecutionTrace:
    return SkillExecutionTrace(
        goal_summary="과제 자료 정리",
        outcome=SkillOutcome.SUCCEEDED,
        steps=(
            SkillTraceStep(
                sequence=1,
                capability_id="file.move",
                outcome=SkillOutcome.SUCCEEDED,
                detail_code="FILE_MOVED",
                independently_verified=True,
            ),
        ),
    )


def draft_record(
    *,
    status: SkillStatus = SkillStatus.DRAFT,
    version: int = 1,
    supersedes: UUID | None = None,
) -> SkillRecord:
    instant = datetime(2026, 10, 14, tzinfo=UTC)
    return SkillRecord(
        skill_id=uuid4(),
        key="course-file-sort",
        title="과제 자료 정리",
        description="과제 파일을 과목별로 정리합니다.",
        triggers=("과제 자료 정리",),
        procedure=("파일 확인", "파일 이동", "결과 확인"),
        allowed_capabilities=("file.move",),
        version=version,
        status=status,
        created_at=instant,
        updated_at=instant,
        supersedes_skill_id=supersedes,
    )


class Store:
    def __init__(self, value: SkillExecutionTrace) -> None:
        self.pending_trace = PendingSkillTrace(
            trace=value,
            recorded_at=datetime(2026, 10, 14, tzinfo=UTC),
        )
        self.consumed = False
        self.fail_require = False
        self.fail_consume = False

    def require_pending(self, trace_id: UUID) -> PendingSkillTrace:
        if self.fail_require or self.consumed or trace_id != self.pending_trace.trace.trace_id:
            raise RuntimeError("private trace failure")
        return self.pending_trace

    def mark_consumed(self, trace_id: UUID) -> None:
        if self.fail_consume or trace_id != self.pending_trace.trace.trace_id:
            raise RuntimeError("private consume failure")
        self.consumed = True


class Author:
    def __init__(self, artifact: SkillDraftArtifact) -> None:
        self.artifact = artifact
        self.calls = 0
        self.fail = False
        self.entered: Event | None = None
        self.release: Event | None = None
        self.revision_artifact: SkillDraftArtifact | None = None

    def draft_initial(self, value: SkillExecutionTrace) -> SkillDraftArtifact:
        self.calls += 1
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.fail:
            raise RuntimeError("private NIM failure")
        assert value.trace_id
        return self.artifact

    def draft_revision(
        self,
        skill_id: UUID,
        value: SkillExecutionTrace,
    ) -> SkillDraftArtifact:
        self.calls += 1
        if self.fail or self.revision_artifact is None:
            raise RuntimeError("private NIM revision failure")
        assert skill_id == self.revision_artifact.draft.supersedes_skill_id
        assert value.trace_id
        return self.revision_artifact


class Catalog:
    def __init__(self) -> None:
        self.retired: list[UUID] = []
        self.fail = False
        self.invalid_result = False
        self.records: dict[UUID, SkillRecord] = {}
        self.revision_allowed = True

    def require(self, skill_id: UUID) -> SkillRecord:
        try:
            return self.records[skill_id]
        except KeyError:
            raise RuntimeError("private missing skill") from None

    def assess_revision(
        self,
        skill_id: UUID,
        *,
        minimum_observations: int = 3,
        minimum_success_rate: float = 0.8,
    ) -> SkillRevisionAssessment:
        record = self.require(skill_id)
        del minimum_observations, minimum_success_rate
        return SkillRevisionAssessment(
            decision=(
                SkillRevisionDecision.PROPOSE_REVISION
                if self.revision_allowed
                else SkillRevisionDecision.KEEP
            ),
            reason_code=(
                "REPEATED_FAILURE"
                if self.revision_allowed
                else "PERFORMANCE_WITHIN_THRESHOLD"
            ),
            summary=SkillPerformanceSummary(
                skill_id=record.skill_id,
                skill_version=record.version,
                observations=3,
                succeeded=1,
                failed=2,
                aborted=0,
                success_rate=1 / 3,
                repeated_failure_code="TARGET_MISSING",
            ),
        )

    def retire(self, skill_id: UUID) -> SkillRecord:
        if self.fail:
            raise RuntimeError("private retirement failure")
        self.retired.append(skill_id)
        status = SkillStatus.DRAFT if self.invalid_result else SkillStatus.RETIRED
        existing = self.records.get(skill_id)
        if existing is None:
            existing = draft_record().model_copy(update={"skill_id": skill_id})
        retired = existing.model_copy(update={"status": status})
        self.records[skill_id] = retired
        return retired


def workflow(
    store: Store,
    author: Author,
    catalog: Catalog,
) -> InitialSkillDraftWorkflow:
    return InitialSkillDraftWorkflow(
        trace_store=store,
        author=author,
        catalog=catalog,
    )


def artifact(*, status: SkillStatus = SkillStatus.DRAFT) -> SkillDraftArtifact:
    return SkillDraftArtifact(
        draft=draft_record(status=status),
        source_trace_sha256="a" * 64,
        reason_code="VERIFIED_SUCCESS_TRACE",
    )


def assert_code(error: pytest.ExceptionInfo[SkillDraftWorkflowError], code: str) -> None:
    assert error.value.code.value == code
    assert "private" not in str(error.value)


def test_success_creates_one_draft_then_consumes_trace() -> None:
    value = trace()
    store = Store(value)
    author = Author(artifact())
    catalog = Catalog()

    result = workflow(store, author, catalog).create(value.trace_id)

    assert result == author.artifact
    assert author.calls == 1
    assert store.consumed
    assert catalog.retired == []


def test_missing_trace_and_author_failure_leave_trace_retryable() -> None:
    value = trace()
    store = Store(value)
    author = Author(artifact())
    catalog = Catalog()
    draft_workflow = workflow(store, author, catalog)
    store.fail_require = True
    with pytest.raises(SkillDraftWorkflowError) as missing:
        draft_workflow.create(value.trace_id)
    assert_code(missing, "TRACE_NOT_PENDING")
    store.fail_require = False
    author.fail = True
    with pytest.raises(SkillDraftWorkflowError) as failed:
        draft_workflow.create(value.trace_id)
    assert_code(failed, "AUTHORING_FAILED")
    assert not store.consumed
    assert catalog.retired == []


def test_consume_failure_retires_new_draft_and_keeps_trace_pending() -> None:
    value = trace()
    store = Store(value)
    store.fail_consume = True
    generated = artifact()
    author = Author(generated)
    catalog = Catalog()

    with pytest.raises(SkillDraftWorkflowError) as failed:
        workflow(store, author, catalog).create(value.trace_id)

    assert_code(failed, "FINALIZE_FAILED_DRAFT_RETIRED")
    assert catalog.retired == [generated.draft.skill_id]
    assert not store.consumed


@pytest.mark.parametrize("invalid_result", (False, True))
def test_compensation_failure_reports_manual_recovery_without_raw_detail(
    invalid_result: bool,
) -> None:
    value = trace()
    store = Store(value)
    store.fail_consume = True
    author = Author(artifact())
    catalog = Catalog()
    catalog.fail = not invalid_result
    catalog.invalid_result = invalid_result

    with pytest.raises(SkillDraftWorkflowError) as failed:
        workflow(store, author, catalog).create(value.trace_id)

    assert_code(failed, "FINALIZE_FAILED_RECOVERY_REQUIRED")
    assert not store.consumed


def test_invalid_author_result_is_never_consumed() -> None:
    value = trace()
    store = Store(value)
    author = Author(artifact(status=SkillStatus.VERIFIED))

    with pytest.raises(SkillDraftWorkflowError) as failed:
        workflow(store, author, Catalog()).create(value.trace_id)

    assert_code(failed, "AUTHORING_RESULT_INVALID")
    assert not store.consumed


def test_same_trace_is_single_flight_and_can_retry_after_completion() -> None:
    value = trace()
    store = Store(value)
    author = Author(artifact())
    author.entered = Event()
    author.release = Event()
    draft_workflow = workflow(store, author, Catalog())
    completed: list[SkillDraftArtifact] = []
    worker = Thread(target=lambda: completed.append(draft_workflow.create(value.trace_id)))
    worker.start()
    assert author.entered.wait(timeout=5)

    with pytest.raises(SkillDraftWorkflowError) as duplicate:
        draft_workflow.create(value.trace_id)
    assert_code(duplicate, "ALREADY_IN_PROGRESS")

    author.release.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(completed) == 1


def test_revision_creates_draft_and_keeps_original_verified_until_approval() -> None:
    value = trace()
    store = Store(value)
    current = draft_record(status=SkillStatus.VERIFIED)
    revised = draft_record(version=2, supersedes=current.skill_id)
    author = Author(artifact())
    author.revision_artifact = SkillDraftArtifact(
        draft=revised,
        source_trace_sha256="c" * 64,
        reason_code="REPEATED_FAILURE",
    )
    catalog = Catalog()
    catalog.records[current.skill_id] = current
    catalog.records[revised.skill_id] = revised
    target = RevisionDraftTarget(
        skill_id=current.skill_id,
        version=current.version,
        updated_at=current.updated_at,
    )

    result = workflow(store, author, catalog).create_revision(value.trace_id, target)

    assert result.draft.status is SkillStatus.DRAFT
    assert result.draft.supersedes_skill_id == current.skill_id
    assert catalog.require(current.skill_id).status is SkillStatus.VERIFIED
    assert store.consumed


@pytest.mark.parametrize("change", ("version", "status", "policy"))
def test_revision_revalidates_target_and_policy_before_authoring(change: str) -> None:
    value = trace()
    store = Store(value)
    current = draft_record(status=SkillStatus.VERIFIED)
    author = Author(artifact())
    catalog = Catalog()
    catalog.records[current.skill_id] = current
    target = RevisionDraftTarget(
        skill_id=current.skill_id,
        version=current.version,
        updated_at=current.updated_at,
    )
    if change == "version":
        catalog.records[current.skill_id] = current.model_copy(update={"version": 2})
    elif change == "status":
        catalog.records[current.skill_id] = current.model_copy(
            update={"status": SkillStatus.RETIRED}
        )
    else:
        catalog.revision_allowed = False

    with pytest.raises(SkillDraftWorkflowError) as failed:
        workflow(store, author, catalog).create_revision(value.trace_id, target)

    expected = "REVISION_POLICY_NOT_MET" if change == "policy" else "REVISION_TARGET_INVALID"
    assert_code(failed, expected)
    assert author.calls == 0
    assert not store.consumed


def test_revision_consume_failure_retires_only_new_draft() -> None:
    value = trace()
    store = Store(value)
    store.fail_consume = True
    current = draft_record(status=SkillStatus.VERIFIED)
    revised = draft_record(version=2, supersedes=current.skill_id)
    author = Author(artifact())
    author.revision_artifact = SkillDraftArtifact(
        draft=revised,
        source_trace_sha256="d" * 64,
        reason_code="REPEATED_FAILURE",
    )
    catalog = Catalog()
    catalog.records[current.skill_id] = current
    catalog.records[revised.skill_id] = revised
    target = RevisionDraftTarget(
        skill_id=current.skill_id,
        version=current.version,
        updated_at=current.updated_at,
    )

    with pytest.raises(SkillDraftWorkflowError) as failed:
        workflow(store, author, catalog).create_revision(value.trace_id, target)

    assert_code(failed, "FINALIZE_FAILED_DRAFT_RETIRED")
    assert catalog.require(current.skill_id).status is SkillStatus.VERIFIED
    assert catalog.require(revised.skill_id).status is SkillStatus.RETIRED
    assert not store.consumed
