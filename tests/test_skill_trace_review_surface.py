from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event, get_ident
from uuid import UUID, uuid4

from javis_core.skill_authoring import (
    SkillDraftArtifact,
    SkillExecutionTrace,
    SkillTraceStep,
)
from javis_core.skill_draft_workflow import (
    InitialSkillDraftWorkflow,
    SkillDraftWorkflowCode,
)
from javis_core.skill_runtime import (
    SkillOutcome,
    SkillPerformanceSummary,
    SkillRecord,
    SkillRevisionAssessment,
    SkillRevisionDecision,
    SkillStatus,
)
from javis_core.skill_trace_review_surface import (
    DraftFailure,
    DraftSuccess,
    DraftWork,
    SkillTraceReviewPresenter,
    ThreadedDraftDispatcher,
    TraceReviewAction,
    TraceReviewConfirmation,
    TraceReviewDisplay,
)
from javis_core.skill_trace_store import PendingSkillTrace


def trace() -> SkillExecutionTrace:
    return SkillExecutionTrace(
        goal_summary="과제 자료를 과목별 폴더로 정리",
        outcome=SkillOutcome.SUCCEEDED,
        steps=(
            SkillTraceStep(
                sequence=1,
                capability_id="file.list",
                outcome=SkillOutcome.SUCCEEDED,
                detail_code="FILES_LISTED",
                independently_verified=True,
            ),
            SkillTraceStep(
                sequence=2,
                capability_id="file.move",
                outcome=SkillOutcome.SUCCEEDED,
                detail_code="FILE_MOVED",
                independently_verified=True,
            ),
        ),
        dynamic_input_labels=("이번 주 파일",),
        decision_notes=("파일명으로 과목을 판단",),
        verification_notes=("이동 뒤 목적지를 확인",),
    )


def draft_artifact() -> SkillDraftArtifact:
    instant = datetime(2026, 10, 14, tzinfo=UTC)
    return SkillDraftArtifact(
        draft=SkillRecord(
            skill_id=uuid4(),
            key="course-file-sort",
            title="과제 자료 정리",
            description="과제 파일을 과목별 폴더로 정리합니다.",
            triggers=("과제 자료 정리",),
            procedure=("파일 확인", "파일 이동", "결과 확인"),
            allowed_capabilities=("file.list", "file.move"),
            version=1,
            status=SkillStatus.DRAFT,
            created_at=instant,
            updated_at=instant,
        ),
        source_trace_sha256="b" * 64,
        reason_code="VERIFIED_SUCCESS_TRACE",
    )


class Store:
    def __init__(self, value: SkillExecutionTrace) -> None:
        self.record = PendingSkillTrace(
            trace=value,
            recorded_at=datetime(2026, 10, 14, 3, 4, 5, tzinfo=UTC),
        )
        self.consumed = False
        self.discarded = False
        self.fail = False

    def pending(self, *, limit: int = 20) -> tuple[PendingSkillTrace, ...]:
        if self.fail:
            raise RuntimeError("private pending path")
        if self.consumed or self.discarded:
            return ()
        return (self.record,)[:limit]

    def require_pending(self, trace_id: UUID) -> PendingSkillTrace:
        if (
            self.fail
            or self.consumed
            or self.discarded
            or trace_id != self.record.trace.trace_id
        ):
            raise RuntimeError("private missing trace")
        return self.record

    def mark_consumed(self, trace_id: UUID) -> None:
        self.require_pending(trace_id)
        self.consumed = True

    def discard(self, trace_id: UUID) -> None:
        self.require_pending(trace_id)
        self.discarded = True


class Author:
    def __init__(self, artifact: SkillDraftArtifact) -> None:
        self.artifact = artifact
        self.calls = 0
        self.fail = False
        self.revision_artifact: SkillDraftArtifact | None = None

    def draft_initial(self, value: SkillExecutionTrace) -> SkillDraftArtifact:
        self.calls += 1
        if self.fail:
            raise RuntimeError("private NIM response")
        assert value.outcome is SkillOutcome.SUCCEEDED
        return self.artifact

    def draft_revision(
        self,
        skill_id: UUID,
        value: SkillExecutionTrace,
    ) -> SkillDraftArtifact:
        self.calls += 1
        if self.fail or self.revision_artifact is None:
            raise RuntimeError("private NIM revision response")
        assert self.revision_artifact.draft.supersedes_skill_id == skill_id
        assert value.trace_id
        return self.revision_artifact


class Catalog:
    def __init__(self) -> None:
        self.retired: list[UUID] = []
        self.records: dict[UUID, SkillRecord] = {}
        self.revision_allowed: set[UUID] = set()

    def list(
        self,
        *,
        status: SkillStatus | None = None,
        limit: int = 20,
    ) -> tuple[SkillRecord, ...]:
        return tuple(
            record
            for record in self.records.values()
            if status is None or record.status is status
        )[:limit]

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
        allowed = skill_id in self.revision_allowed
        return SkillRevisionAssessment(
            decision=(
                SkillRevisionDecision.PROPOSE_REVISION
                if allowed
                else SkillRevisionDecision.KEEP
            ),
            reason_code="REPEATED_FAILURE" if allowed else "PERFORMANCE_WITHIN_THRESHOLD",
            summary=SkillPerformanceSummary(
                skill_id=record.skill_id,
                skill_version=record.version,
                observations=3,
                succeeded=1,
                failed=2,
                aborted=0,
                success_rate=1 / 3,
                repeated_failure_code="TARGET_MISSING" if allowed else None,
            ),
        )

    def retire(self, skill_id: UUID) -> SkillRecord:
        self.retired.append(skill_id)
        record = self.records.get(skill_id)
        if record is None:
            record = draft_artifact().draft.model_copy(update={"skill_id": skill_id})
        retired = record.model_copy(update={"status": SkillStatus.RETIRED})
        self.records[skill_id] = retired
        return retired


class ManualDispatcher:
    def __init__(self) -> None:
        self.job: tuple[DraftWork, DraftSuccess, DraftFailure] | None = None
        self.closed = False

    def submit(
        self,
        work: DraftWork,
        on_success: DraftSuccess,
        on_failure: DraftFailure,
    ) -> bool:
        if self.closed or self.job is not None:
            return False
        self.job = (work, on_success, on_failure)
        return True

    def complete(self) -> None:
        assert self.job is not None
        work, on_success, on_failure = self.job
        self.job = None
        try:
            artifact = work()
        except Exception as error:
            code = getattr(error, "code", SkillDraftWorkflowCode.AUTHORING_FAILED)
            on_failure(code)
        else:
            on_success(artifact)

    def close(self) -> None:
        self.closed = True


class View:
    def __init__(self) -> None:
        self.on_select: Callable[[UUID], None] | None = None
        self.on_create: Callable[[], None] | None = None
        self.on_select_revision: Callable[[UUID | None], None] | None = None
        self.on_discard: Callable[[], None] | None = None
        self.on_refresh: Callable[[], None] | None = None
        self.on_close: Callable[[], None] | None = None
        self.rendered: list[TraceReviewDisplay] = []
        self.closed = False
        self.ran = False
        self.notifications: list[tuple[str, str]] = []

    def bind_handlers(
        self,
        *,
        on_select: Callable[[UUID], None],
        on_select_revision: Callable[[UUID | None], None],
        on_create: Callable[[], None],
        on_discard: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self.on_select = on_select
        self.on_select_revision = on_select_revision
        self.on_create = on_create
        self.on_discard = on_discard
        self.on_refresh = on_refresh
        self.on_close = on_close

    def render(self, display: TraceReviewDisplay) -> None:
        self.rendered.append(display)

    def notify(self, title: str, message: str) -> None:
        self.notifications.append((title, message))

    def close(self) -> None:
        self.closed = True

    def run(self) -> None:
        self.ran = True


def build(
    store: Store,
    author: Author,
    dispatcher: ManualDispatcher,
    view: View,
    confirmations: list[TraceReviewConfirmation],
    *,
    confirmed: bool = True,
    catalog: Catalog | None = None,
) -> SkillTraceReviewPresenter:
    revision_catalog = catalog or Catalog()
    workflow = InitialSkillDraftWorkflow(
        trace_store=store,
        author=author,
        catalog=revision_catalog,
    )

    def confirm(request: TraceReviewConfirmation) -> bool:
        confirmations.append(request)
        return confirmed

    return SkillTraceReviewPresenter(
        trace_store=store,
        revision_catalog=revision_catalog,
        workflow=workflow,
        dispatcher=dispatcher,
        view=view,
        confirm=confirm,
    )


def test_lists_and_displays_only_minimized_trace_fields() -> None:
    value = trace()
    store = Store(value)
    view = View()
    review = build(store, Author(draft_artifact()), ManualDispatcher(), view, [])

    review.run()
    review.select(value.trace_id)

    assert view.ran
    detail = view.rendered[-1].selected
    assert detail is not None
    assert detail.goal_summary == value.goal_summary
    assert tuple(step.capability_id for step in detail.steps) == ("file.list", "file.move")
    serialized = detail.model_dump_json()
    assert "arguments" not in serialized
    assert "path" not in serialized


def test_explicit_confirmation_precedes_dispatch_and_success_consumes_trace() -> None:
    value = trace()
    store = Store(value)
    author = Author(draft_artifact())
    dispatcher = ManualDispatcher()
    view = View()
    confirmations: list[TraceReviewConfirmation] = []
    review = build(store, author, dispatcher, view, confirmations)
    review.refresh()
    review.select(value.trace_id)

    review.create_draft()

    assert confirmations[0].action is TraceReviewAction.CREATE_INITIAL_DRAFT
    assert confirmations[0].capabilities == ("file.list", "file.move")
    assert author.calls == 0
    assert view.rendered[-1].busy
    dispatcher.complete()
    assert author.calls == 1
    assert store.consumed
    assert view.rendered[-1].pending == ()
    assert "검토 대기 초안" in view.rendered[-1].notice
    assert view.notifications[-1][0] == "스킬 초안 생성 완료"


def test_cancel_and_author_failure_both_preserve_pending_trace() -> None:
    value = trace()
    store = Store(value)
    author = Author(draft_artifact())
    dispatcher = ManualDispatcher()
    view = View()
    cancelled = build(store, author, dispatcher, view, [], confirmed=False)
    cancelled.refresh()
    cancelled.select(value.trace_id)
    cancelled.create_draft()
    assert dispatcher.job is None
    assert not store.consumed
    assert "취소" in view.rendered[-1].notice

    failed = build(store, author, dispatcher, view, [], confirmed=True)
    failed.refresh()
    failed.select(value.trace_id)
    author.fail = True
    failed.create_draft()
    dispatcher.complete()
    assert not store.consumed
    assert len(view.rendered[-1].pending) == 1
    assert "보존" in view.rendered[-1].notice
    assert "private" not in view.rendered[-1].model_dump_json()


def test_discard_is_confirmed_and_recoverably_hidden() -> None:
    value = trace()
    store = Store(value)
    view = View()
    confirmations: list[TraceReviewConfirmation] = []
    review = build(
        store,
        Author(draft_artifact()),
        ManualDispatcher(),
        view,
        confirmations,
    )
    review.refresh()
    review.select(value.trace_id)

    review.discard()

    assert confirmations[0].action is TraceReviewAction.DISCARD
    assert store.discarded
    assert view.rendered[-1].pending == ()


def test_stale_selection_and_store_errors_fail_closed_without_raw_detail() -> None:
    value = trace()
    store = Store(value)
    view = View()
    confirmations: list[TraceReviewConfirmation] = []
    review = build(
        store,
        Author(draft_artifact()),
        ManualDispatcher(),
        view,
        confirmations,
    )
    review.refresh()
    review.select(value.trace_id)
    store.record = store.record.model_copy(
        update={"recorded_at": store.record.recorded_at + timedelta(seconds=1)}
    )

    review.create_draft()

    assert confirmations == []
    assert view.rendered[-1].selected is None
    store.fail = True
    review.refresh()
    serialized = view.rendered[-1].model_dump_json()
    assert "private" not in serialized
    assert "path" not in serialized
    assert not view.rendered[-1].actions_enabled


def test_busy_window_cannot_close_until_dispatch_completes() -> None:
    value = trace()
    store = Store(value)
    dispatcher = ManualDispatcher()
    view = View()
    review = build(store, Author(draft_artifact()), dispatcher, view, [])
    review.refresh()
    review.select(value.trace_id)
    review.create_draft()

    review.close()

    assert not view.closed
    assert "닫을 수 없습니다" in view.rendered[-1].notice
    dispatcher.complete()
    review.close()
    assert view.closed
    assert dispatcher.closed


def test_threaded_dispatcher_invokes_callback_only_when_ui_poll_runs() -> None:
    scheduled: list[Callable[[], None]] = []
    worker_finished = Event()
    callback_threads: list[int] = []
    ui_thread = get_ident()
    dispatcher = ThreadedDraftDispatcher(
        schedule=lambda _delay, callback: scheduled.append(callback)
    )

    def work() -> SkillDraftArtifact:
        worker_finished.set()
        return draft_artifact()

    assert dispatcher.submit(
        work,
        lambda _artifact: callback_threads.append(get_ident()),
        lambda _code: callback_threads.append(get_ident()),
    )
    assert worker_finished.wait(timeout=5)
    assert callback_threads == []

    scheduled.pop(0)()

    assert callback_threads == [ui_thread]
    dispatcher.close()


def test_revision_target_requires_policy_selection_and_keeps_original_verified() -> None:
    value = trace()
    store = Store(value)
    current = draft_artifact().draft.model_copy(
        update={"status": SkillStatus.VERIFIED}
    )
    revised = draft_artifact().draft.model_copy(
        update={
            "skill_id": uuid4(),
            "version": current.version + 1,
            "supersedes_skill_id": current.skill_id,
        }
    )
    author = Author(draft_artifact())
    author.revision_artifact = SkillDraftArtifact(
        draft=revised,
        source_trace_sha256="e" * 64,
        reason_code="REPEATED_FAILURE",
    )
    catalog = Catalog()
    catalog.records[current.skill_id] = current
    catalog.revision_allowed.add(current.skill_id)
    dispatcher = ManualDispatcher()
    view = View()
    confirmations: list[TraceReviewConfirmation] = []
    review = build(
        store,
        author,
        dispatcher,
        view,
        confirmations,
        catalog=catalog,
    )
    review.refresh()
    assert tuple(target.skill_id for target in view.rendered[-1].revision_targets) == (
        current.skill_id,
    )
    review.select(value.trace_id)
    review.select_revision(current.skill_id)

    review.create_draft()

    assert confirmations[0].action is TraceReviewAction.CREATE_REVISION_DRAFT
    assert confirmations[0].revision_title == current.title
    assert confirmations[0].revision_version == current.version
    assert confirmations[0].revision_reason_code == "REPEATED_FAILURE"
    catalog.records[revised.skill_id] = revised
    dispatcher.complete()
    assert store.consumed
    assert catalog.require(current.skill_id).status is SkillStatus.VERIFIED
    assert catalog.require(revised.skill_id).status is SkillStatus.DRAFT


def test_existing_revision_draft_hides_duplicate_revision_target() -> None:
    current = draft_artifact().draft.model_copy(
        update={"status": SkillStatus.VERIFIED}
    )
    existing = draft_artifact().draft.model_copy(
        update={
            "skill_id": uuid4(),
            "version": current.version + 1,
            "supersedes_skill_id": current.skill_id,
        }
    )
    catalog = Catalog()
    catalog.records[current.skill_id] = current
    catalog.records[existing.skill_id] = existing
    catalog.revision_allowed.add(current.skill_id)
    store = Store(trace())
    view = View()
    review = build(
        store,
        Author(draft_artifact()),
        ManualDispatcher(),
        view,
        [],
        catalog=catalog,
    )

    review.refresh()

    assert view.rendered[-1].revision_targets == ()
