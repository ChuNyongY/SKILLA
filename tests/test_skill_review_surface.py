from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from javis_core.skill_review_surface import (
    SkillDraftDetail,
    SkillReviewAction,
    SkillReviewConfirmation,
    SkillReviewDisplay,
    SkillReviewPresenter,
)
from javis_core.skill_runtime import SkillRecord, SkillStatus


class FakeCatalog:
    def __init__(self, records: tuple[SkillRecord, ...] = ()) -> None:
        self.records = {record.skill_id: record for record in records}
        self.approved: list[UUID] = []
        self.retired: list[UUID] = []
        self.fail_list = False
        self.fail_mutation = False

    def list(
        self,
        *,
        status: SkillStatus | None = None,
        limit: int = 20,
    ) -> tuple[SkillRecord, ...]:
        if self.fail_list:
            raise RuntimeError("private catalog path")
        records = tuple(
            record
            for record in self.records.values()
            if status is None or record.status is status
        )
        return records[:limit]

    def require(self, skill_id: UUID) -> SkillRecord:
        try:
            return self.records[skill_id]
        except KeyError:
            raise RuntimeError("private missing identifier") from None

    def approve(
        self,
        skill_id: UUID,
        *,
        now: datetime | None = None,
    ) -> SkillRecord:
        if self.fail_mutation:
            raise RuntimeError("private approval failure")
        record = self.require(skill_id)
        if record.status is not SkillStatus.DRAFT:
            raise RuntimeError("not a draft")
        updated = record.model_copy(
            update={
                "status": SkillStatus.VERIFIED,
                "updated_at": now or record.updated_at + timedelta(seconds=1),
            }
        )
        self.records[skill_id] = updated
        self.approved.append(skill_id)
        return updated

    def retire(
        self,
        skill_id: UUID,
        *,
        now: datetime | None = None,
    ) -> SkillRecord:
        if self.fail_mutation:
            raise RuntimeError("private retirement failure")
        record = self.require(skill_id)
        updated = record.model_copy(
            update={
                "status": SkillStatus.RETIRED,
                "updated_at": now or record.updated_at + timedelta(seconds=1),
            }
        )
        self.records[skill_id] = updated
        self.retired.append(skill_id)
        return updated


class FakeView:
    def __init__(self) -> None:
        self.on_select: Callable[[UUID], None] | None = None
        self.on_approve: Callable[[], None] | None = None
        self.on_reject: Callable[[], None] | None = None
        self.on_refresh: Callable[[], None] | None = None
        self.on_close: Callable[[], None] | None = None
        self.rendered: list[SkillReviewDisplay] = []
        self.closed = False
        self.ran = False

    def bind_handlers(
        self,
        *,
        on_select: Callable[[UUID], None],
        on_approve: Callable[[], None],
        on_reject: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self.on_select = on_select
        self.on_approve = on_approve
        self.on_reject = on_reject
        self.on_refresh = on_refresh
        self.on_close = on_close

    def render(self, display: SkillReviewDisplay) -> None:
        self.rendered.append(display)

    def close(self) -> None:
        self.closed = True

    def run(self) -> None:
        self.ran = True


def draft(*, version: int = 1, revision: bool = False) -> SkillRecord:
    instant = datetime(2026, 10, 14, 1, 2, 3, tzinfo=UTC)
    return SkillRecord(
        skill_id=uuid4(),
        key="course-file-sort",
        title="과제 자료 정리",
        description="과제 파일을 과목별 폴더로 정리합니다.",
        triggers=("과제 자료 정리",),
        procedure=("현재 파일 확인", "과목 판단", "파일 이동"),
        dynamic_inputs=("이번 주 파일",),
        decision_rules=("파일명과 내용을 함께 확인",),
        verification_rules=("각 파일의 목적지 확인",),
        allowed_capabilities=("file.list", "file.move"),
        version=version,
        status=SkillStatus.DRAFT,
        created_at=instant,
        updated_at=instant,
        supersedes_skill_id=uuid4() if revision else None,
    )


def presenter(
    catalog: FakeCatalog,
    view: FakeView,
    confirmations: list[SkillReviewConfirmation],
    *,
    confirmed: bool = True,
) -> SkillReviewPresenter:
    def confirm(request: SkillReviewConfirmation) -> bool:
        confirmations.append(request)
        return confirmed

    return SkillReviewPresenter(catalog=catalog, view=view, confirm=confirm)


def test_run_lists_drafts_and_binds_all_explicit_controls() -> None:
    record = draft(revision=True)
    catalog = FakeCatalog((record,))
    view = FakeView()
    review = presenter(catalog, view, [])

    review.run()

    assert view.ran
    assert all(
        callback is not None
        for callback in (
            view.on_select,
            view.on_approve,
            view.on_reject,
            view.on_refresh,
            view.on_close,
        )
    )
    assert view.rendered[-1].drafts[0].skill_id == record.skill_id
    assert view.rendered[-1].drafts[0].is_revision
    assert not view.rendered[-1].mutation_enabled


def test_selection_displays_every_reviewable_skill_field() -> None:
    record = draft(revision=True)
    catalog = FakeCatalog((record,))
    view = FakeView()
    review = presenter(catalog, view, [])
    review.refresh()

    review.select(record.skill_id)

    detail = view.rendered[-1].selected
    assert isinstance(detail, SkillDraftDetail)
    assert detail.model_dump(exclude={"supersedes_skill_id", "status"}) == {
        "skill_id": record.skill_id,
        "key": record.key,
        "title": record.title,
        "description": record.description,
        "version": record.version,
        "triggers": record.triggers,
        "procedure": record.procedure,
        "dynamic_inputs": record.dynamic_inputs,
        "decision_rules": record.decision_rules,
        "verification_rules": record.verification_rules,
        "allowed_capabilities": record.allowed_capabilities,
    }
    assert detail.supersedes_skill_id == record.supersedes_skill_id
    assert view.rendered[-1].mutation_enabled


def test_approval_requires_confirmation_and_refreshes_the_draft_list() -> None:
    record = draft()
    catalog = FakeCatalog((record,))
    view = FakeView()
    confirmations: list[SkillReviewConfirmation] = []
    review = presenter(catalog, view, confirmations)
    review.refresh()
    review.select(record.skill_id)

    review.approve()

    assert confirmations[0].action is SkillReviewAction.APPROVE
    assert confirmations[0].allowed_capabilities == record.allowed_capabilities
    assert catalog.approved == [record.skill_id]
    assert catalog.require(record.skill_id).status is SkillStatus.VERIFIED
    assert len(view.rendered[-1].drafts) == 1
    assert view.rendered[-1].drafts[0].status is SkillStatus.VERIFIED
    assert not view.rendered[-1].mutation_enabled
    assert "승인" in view.rendered[-1].notice


def test_rejection_requires_confirmation_and_retires_the_draft() -> None:
    record = draft()
    catalog = FakeCatalog((record,))
    view = FakeView()
    confirmations: list[SkillReviewConfirmation] = []
    review = presenter(catalog, view, confirmations)
    review.refresh()
    review.select(record.skill_id)

    review.reject()

    assert confirmations[0].action is SkillReviewAction.REJECT
    assert catalog.retired == [record.skill_id]
    assert catalog.require(record.skill_id).status is SkillStatus.RETIRED
    assert view.rendered[-1].drafts == ()


def test_cancel_does_not_mutate_or_clear_the_selected_draft() -> None:
    record = draft()
    catalog = FakeCatalog((record,))
    view = FakeView()
    review = presenter(catalog, view, [], confirmed=False)
    review.refresh()
    review.select(record.skill_id)

    review.approve()

    assert catalog.approved == []
    assert catalog.require(record.skill_id).status is SkillStatus.DRAFT
    assert view.rendered[-1].selected is not None
    assert "취소" in view.rendered[-1].notice


def test_stale_selection_fails_closed_before_confirmation() -> None:
    record = draft()
    catalog = FakeCatalog((record,))
    view = FakeView()
    confirmations: list[SkillReviewConfirmation] = []
    review = presenter(catalog, view, confirmations)
    review.refresh()
    review.select(record.skill_id)
    catalog.records[record.skill_id] = record.model_copy(
        update={"updated_at": record.updated_at + timedelta(seconds=1)}
    )

    review.approve()

    assert confirmations == []
    assert catalog.approved == []
    assert view.rendered[-1].selected is None
    assert "중단" in view.rendered[-1].notice


def test_catalog_failures_do_not_expose_raw_exception_or_private_path() -> None:
    record = draft()
    catalog = FakeCatalog((record,))
    view = FakeView()
    review = presenter(catalog, view, [])
    catalog.fail_list = True

    review.refresh()

    rendered = view.rendered[-1].model_dump_json()
    assert "private" not in rendered
    assert "path" not in rendered
    assert view.rendered[-1].drafts == ()
    assert not view.rendered[-1].mutation_enabled

    catalog.fail_list = False
    review.refresh()
    review.select(record.skill_id)
    catalog.fail_mutation = True
    review.approve()
    rendered = view.rendered[-1].model_dump_json()
    assert "private" not in rendered
    assert catalog.require(record.skill_id).status is SkillStatus.DRAFT


def test_empty_catalog_explains_how_to_create_a_draft() -> None:
    catalog = FakeCatalog(())
    view = FakeView()
    review = presenter(catalog, view, [])

    review.refresh()

    assert view.rendered[-1].drafts == ()
    assert "스킬 후보 검토" in view.rendered[-1].notice
