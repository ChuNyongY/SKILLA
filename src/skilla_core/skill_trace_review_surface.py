from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from queue import Empty, Queue
from threading import Thread
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .cyber_theme import COLORS, button, configure_window, footer, header, label, panel
from .models import FrozenModel
from .skill_authoring import SkillDraftArtifact, SkillExecutionTrace
from .skill_draft_workflow import (
    InitialSkillDraftWorkflow,
    RevisionDraftTarget,
    SkillDraftWorkflowCode,
    SkillDraftWorkflowError,
)
from .skill_runtime import (
    SkillOutcome,
    SkillRecord,
    SkillRevisionAssessment,
    SkillRevisionDecision,
    SkillStatus,
)
from .skill_trace_store import PendingSkillTrace


class TraceReviewAction(StrEnum):
    CREATE_INITIAL_DRAFT = "CREATE_INITIAL_DRAFT"
    CREATE_REVISION_DRAFT = "CREATE_REVISION_DRAFT"
    DISCARD = "DISCARD"


class TraceStepDisplay(FrozenModel):
    sequence: int = Field(ge=1)
    capability_id: str
    outcome: SkillOutcome
    detail_code: str
    independently_verified: bool


class PendingTraceSummary(FrozenModel):
    trace_id: UUID
    goal_summary: str
    outcome: SkillOutcome
    recorded_at: datetime
    step_count: int = Field(ge=1)


class PendingTraceDetail(PendingTraceSummary):
    steps: tuple[TraceStepDisplay, ...]
    dynamic_input_labels: tuple[str, ...]
    decision_notes: tuple[str, ...]
    verification_notes: tuple[str, ...]


class RevisionTargetSummary(FrozenModel):
    skill_id: UUID
    key: str
    title: str
    version: int = Field(ge=1)
    updated_at: datetime
    reason_code: str
    observations: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)


class TraceReviewDisplay(FrozenModel):
    pending: tuple[PendingTraceSummary, ...]
    revision_targets: tuple[RevisionTargetSummary, ...] = ()
    selected_revision_skill_id: UUID | None = None
    selected: PendingTraceDetail | None = None
    notice: str = Field(min_length=1, max_length=200)
    busy: bool = False
    actions_enabled: bool = False


class TraceReviewConfirmation(FrozenModel):
    action: TraceReviewAction
    trace_id: UUID
    goal_summary: str
    capabilities: tuple[str, ...]
    revision_title: str | None = None
    revision_version: int | None = Field(default=None, ge=1)
    revision_reason_code: str | None = None


class TraceReviewStore(Protocol):
    def pending(self, *, limit: int = 20) -> tuple[PendingSkillTrace, ...]: ...

    def require_pending(self, trace_id: UUID) -> PendingSkillTrace: ...

    def discard(self, trace_id: UUID) -> None: ...


class RevisionReviewCatalog(Protocol):
    def list(
        self,
        *,
        status: SkillStatus | None = None,
        limit: int = 20,
    ) -> tuple[SkillRecord, ...]: ...

    def require(self, skill_id: UUID) -> SkillRecord: ...

    def assess_revision(
        self,
        skill_id: UUID,
        *,
        minimum_observations: int = 3,
        minimum_success_rate: float = 0.8,
    ) -> SkillRevisionAssessment: ...


class TraceReviewView(Protocol):
    def bind_handlers(
        self,
        *,
        on_select: Callable[[UUID], None],
        on_select_revision: Callable[[UUID | None], None],
        on_create: Callable[[], None],
        on_discard: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None: ...

    def render(self, display: TraceReviewDisplay) -> None: ...

    def notify(self, title: str, message: str) -> None: ...

    def close(self) -> None: ...

    def run(self) -> None: ...


DraftWork = Callable[[], SkillDraftArtifact]
DraftSuccess = Callable[[SkillDraftArtifact], None]
DraftFailure = Callable[[SkillDraftWorkflowCode], None]
TraceConfirmationCallback = Callable[[TraceReviewConfirmation], bool]


class DraftDispatcher(Protocol):
    def submit(
        self,
        work: DraftWork,
        on_success: DraftSuccess,
        on_failure: DraftFailure,
    ) -> bool: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class _Completion:
    artifact: SkillDraftArtifact | None
    error: SkillDraftWorkflowCode | None
    on_success: DraftSuccess
    on_failure: DraftFailure


class ThreadedDraftDispatcher:
    """Run NIM off-thread and deliver queue results only from the Tk/UI thread."""

    def __init__(
        self,
        *,
        schedule: Callable[[int, Callable[[], None]], object],
        poll_interval_ms: int = 50,
    ) -> None:
        if type(poll_interval_ms) is not int or not 10 <= poll_interval_ms <= 1_000:
            raise ValueError("poll_interval_ms must be an integer within 10..1000")
        self._schedule = schedule
        self._poll_interval_ms = poll_interval_ms
        self._queue: Queue[_Completion] = Queue()
        self._closed = False
        self._schedule(self._poll_interval_ms, self._poll)

    def submit(
        self,
        work: DraftWork,
        on_success: DraftSuccess,
        on_failure: DraftFailure,
    ) -> bool:
        if self._closed:
            return False
        Thread(
            target=self._run,
            args=(work, on_success, on_failure),
            daemon=True,
            name="skilla-skill-draft",
        ).start()
        return True

    def close(self) -> None:
        self._closed = True

    def _run(
        self,
        work: DraftWork,
        on_success: DraftSuccess,
        on_failure: DraftFailure,
    ) -> None:
        try:
            artifact = work()
        except SkillDraftWorkflowError as error:
            completion = _Completion(
                artifact=None,
                error=error.code,
                on_success=on_success,
                on_failure=on_failure,
            )
        except Exception:
            completion = _Completion(
                artifact=None,
                error=SkillDraftWorkflowCode.AUTHORING_FAILED,
                on_success=on_success,
                on_failure=on_failure,
            )
        else:
            completion = _Completion(
                artifact=artifact,
                error=None,
                on_success=on_success,
                on_failure=on_failure,
            )
        self._queue.put(completion)

    def _poll(self) -> None:
        if self._closed:
            return
        while True:
            try:
                completion = self._queue.get_nowait()
            except Empty:
                break
            if completion.artifact is not None:
                completion.on_success(completion.artifact)
            elif completion.error is not None:
                completion.on_failure(completion.error)
        if not self._closed:
            self._schedule(self._poll_interval_ms, self._poll)


class SkillTraceReviewPresenter:
    def __init__(
        self,
        *,
        trace_store: TraceReviewStore,
        revision_catalog: RevisionReviewCatalog,
        workflow: InitialSkillDraftWorkflow,
        dispatcher: DraftDispatcher,
        view: TraceReviewView,
        confirm: TraceConfirmationCallback,
    ) -> None:
        self._trace_store = trace_store
        self._revision_catalog = revision_catalog
        self._workflow = workflow
        self._dispatcher = dispatcher
        self._view = view
        self._confirm = confirm
        self._pending: tuple[PendingTraceSummary, ...] = ()
        self._revision_targets: tuple[RevisionTargetSummary, ...] = ()
        self._selected: PendingSkillTrace | None = None
        self._selected_revision: RevisionTargetSummary | None = None
        self._busy = False

    def run(self) -> None:
        self._view.bind_handlers(
            on_select=self.select,
            on_select_revision=self.select_revision,
            on_create=self.create_draft,
            on_discard=self.discard,
            on_refresh=self.refresh,
            on_close=self.close,
        )
        self.refresh()
        self._view.run()

    def refresh(self, notice: str = "검토할 실행 기록을 불러왔습니다.") -> None:
        if self._busy:
            self._render("스킬 초안을 생성하는 동안 기다려 주세요.")
            return
        try:
            records = self._trace_store.pending(limit=100)
            revision_targets = self._load_revision_targets()
        except Exception:
            self._pending = ()
            self._revision_targets = ()
            self._selected = None
            self._selected_revision = None
            self._render("실행 기록을 불러오지 못했습니다.")
            return
        self._pending = tuple(_summary(record) for record in records)
        self._revision_targets = revision_targets
        self._selected = None
        self._selected_revision = None
        self._render(notice)

    def select(self, trace_id: UUID) -> None:
        if self._busy:
            return
        try:
            pending = self._trace_store.require_pending(trace_id)
        except Exception:
            self.refresh("선택한 실행 기록이 없어 목록을 새로 고쳤습니다.")
            return
        summaries = {item.trace_id: item for item in self._pending}
        summary = summaries.get(trace_id)
        if summary is None or summary.recorded_at != pending.recorded_at:
            self.refresh("선택한 실행 기록이 변경되어 목록을 새로 고쳤습니다.")
            return
        self._selected = pending
        self._render("전송될 최소화 기록을 확인한 뒤 초안 생성을 선택하세요.")

    def select_revision(self, skill_id: UUID | None) -> None:
        if self._busy:
            return
        if skill_id is None:
            self._selected_revision = None
            self._render("새 스킬의 최초 DRAFT를 생성하도록 선택했습니다.")
            return
        selected = next(
            (target for target in self._revision_targets if target.skill_id == skill_id),
            None,
        )
        if selected is None or self._current_revision_target(selected) is None:
            self.refresh("개정 대상의 상태가 변경되어 목록을 새로 고쳤습니다.")
            return
        self._selected_revision = selected
        self._render(
            f"'{selected.title}' v{selected.version}의 개정 DRAFT를 생성하도록 선택했습니다."
        )

    def create_draft(self) -> None:
        selected = self._selected
        if self._busy:
            self._render("이미 스킬 초안을 생성하고 있습니다.")
            return
        if selected is None:
            self._render("먼저 실행 기록을 선택하세요.")
            return
        current = self._current_selection(selected)
        if current is None:
            self.refresh("실행 기록이 변경되어 초안 생성을 중단했습니다.")
            return
        revision = self._selected_revision
        if revision is not None and self._current_revision_target(revision) is None:
            self.refresh("개정 대상의 상태가 변경되어 초안 생성을 중단했습니다.")
            return
        action = (
            TraceReviewAction.CREATE_REVISION_DRAFT
            if revision is not None
            else TraceReviewAction.CREATE_INITIAL_DRAFT
        )
        confirmation = _confirmation(action, current.trace, revision=revision)
        try:
            confirmed = self._confirm(confirmation)
        except Exception:
            confirmed = False
        if not confirmed:
            self._render("초안 생성을 취소했습니다. 실행 기록은 그대로 보존됩니다.")
            return
        current = self._current_selection(selected)
        if current is None:
            self.refresh("확인 중 실행 기록이 변경되어 초안 생성을 중단했습니다.")
            return
        if revision is not None and self._current_revision_target(revision) is None:
            self.refresh("확인 중 개정 대상이 변경되어 초안 생성을 중단했습니다.")
            return
        self._busy = True
        self._render("NIM이 스킬 초안을 생성하고 있습니다. 창을 닫지 마세요.")
        if revision is not None:
            revision_target = RevisionDraftTarget(
                skill_id=revision.skill_id,
                version=revision.version,
                updated_at=revision.updated_at,
            )

            def work() -> SkillDraftArtifact:
                return self._workflow.create_revision(
                    current.trace.trace_id,
                    revision_target,
                )

        else:

            def work() -> SkillDraftArtifact:
                return self._workflow.create(current.trace.trace_id)

        submitted = self._dispatcher.submit(
            work,
            self._draft_created,
            self._draft_failed,
        )
        if not submitted:
            self._busy = False
            self.refresh("초안 생성 작업을 시작하지 못했습니다. 실행 기록은 보존됩니다.")

    def discard(self) -> None:
        selected = self._selected
        if self._busy:
            self._render("초안 생성이 끝난 뒤 다시 시도하세요.")
            return
        if selected is None:
            self._render("먼저 실행 기록을 선택하세요.")
            return
        current = self._current_selection(selected)
        if current is None:
            self.refresh("실행 기록이 변경되어 폐기를 중단했습니다.")
            return
        confirmation = _confirmation(TraceReviewAction.DISCARD, current.trace)
        try:
            confirmed = self._confirm(confirmation)
        except Exception:
            confirmed = False
        if not confirmed:
            self._render("폐기를 취소했습니다. 실행 기록은 그대로 보존됩니다.")
            return
        current = self._current_selection(selected)
        if current is None:
            self.refresh("확인 중 실행 기록이 변경되어 폐기를 중단했습니다.")
            return
        try:
            self._trace_store.discard(current.trace.trace_id)
        except Exception:
            self.refresh("실행 기록을 폐기하지 못했습니다. 목록을 다시 확인하세요.")
            return
        self.refresh("실행 기록을 삭제하지 않고 폐기 상태로 전환했습니다.")

    def close(self) -> None:
        if self._busy:
            self._render("초안 생성이 끝날 때까지 창을 닫을 수 없습니다.")
            return
        self._dispatcher.close()
        self._view.close()

    def _current_selection(self, selected: PendingSkillTrace) -> PendingSkillTrace | None:
        try:
            current = self._trace_store.require_pending(selected.trace.trace_id)
        except Exception:
            return None
        if current.recorded_at != selected.recorded_at or current.trace != selected.trace:
            return None
        return current

    def _load_revision_targets(self) -> tuple[RevisionTargetSummary, ...]:
        drafts = self._revision_catalog.list(status=SkillStatus.DRAFT, limit=100)
        pending_supersedes = {
            draft.supersedes_skill_id for draft in drafts if draft.supersedes_skill_id is not None
        }
        targets: list[RevisionTargetSummary] = []
        for record in self._revision_catalog.list(status=SkillStatus.VERIFIED, limit=100):
            if record.skill_id in pending_supersedes:
                continue
            assessment = self._revision_catalog.assess_revision(record.skill_id)
            if assessment.decision is SkillRevisionDecision.PROPOSE_REVISION:
                targets.append(_revision_summary(record, assessment))
        return tuple(targets)

    def _current_revision_target(
        self,
        selected: RevisionTargetSummary,
    ) -> SkillRecord | None:
        try:
            current = self._revision_catalog.require(selected.skill_id)
            assessment = self._revision_catalog.assess_revision(selected.skill_id)
            drafts = self._revision_catalog.list(status=SkillStatus.DRAFT, limit=100)
        except Exception:
            return None
        if (
            current.status is not SkillStatus.VERIFIED
            or current.version != selected.version
            or current.updated_at != selected.updated_at
            or assessment.decision is not SkillRevisionDecision.PROPOSE_REVISION
            or any(draft.supersedes_skill_id == current.skill_id for draft in drafts)
        ):
            return None
        return current

    def _draft_created(self, artifact: SkillDraftArtifact) -> None:
        self._busy = False
        notice = (
            f"'{artifact.draft.title}' 검토 대기 초안을 만들었습니다. "
            "스킬 관리에서 내용을 확인하고 승인하세요."
        )
        self.refresh(notice)
        self._view.notify("스킬 초안 생성 완료", notice)

    def _draft_failed(self, code: SkillDraftWorkflowCode) -> None:
        self._busy = False
        self.refresh(_WORKFLOW_NOTICES[code])

    def _render(self, notice: str) -> None:
        self._view.render(
            TraceReviewDisplay(
                pending=self._pending,
                revision_targets=self._revision_targets,
                selected_revision_skill_id=(
                    self._selected_revision.skill_id
                    if self._selected_revision is not None
                    else None
                ),
                selected=_detail(self._selected) if self._selected is not None else None,
                notice=notice,
                busy=self._busy,
                actions_enabled=self._selected is not None and not self._busy,
            )
        )


_WORKFLOW_NOTICES = {
    SkillDraftWorkflowCode.TRACE_NOT_PENDING: (
        "실행 기록이 더 이상 대기 상태가 아닙니다. 목록을 다시 확인하세요."
    ),
    SkillDraftWorkflowCode.ALREADY_IN_PROGRESS: "같은 기록의 초안을 이미 생성하고 있습니다.",
    SkillDraftWorkflowCode.AUTHORING_FAILED: (
        "NIM 초안 생성에 실패했습니다. 실행 기록은 보존되었습니다."
    ),
    SkillDraftWorkflowCode.AUTHORING_RESULT_INVALID: (
        "생성 결과가 안전 계약을 충족하지 않아 실행 기록을 보존했습니다."
    ),
    SkillDraftWorkflowCode.FINALIZE_FAILED_DRAFT_RETIRED: (
        "기록 완료 처리에 실패해 새 초안을 회수했습니다. 실행 기록은 보존되었습니다."
    ),
    SkillDraftWorkflowCode.FINALIZE_FAILED_RECOVERY_REQUIRED: (
        "저장 상태를 자동 복구하지 못했습니다. 상태 점검이 필요합니다."
    ),
    SkillDraftWorkflowCode.REVISION_TARGET_INVALID: (
        "개정 대상의 버전이나 상태가 변경되었습니다. 목록을 다시 확인하세요."
    ),
    SkillDraftWorkflowCode.REVISION_POLICY_NOT_MET: (
        "개정 근거가 현재 기준을 충족하지 않아 실행 기록을 보존했습니다."
    ),
    SkillDraftWorkflowCode.REVISION_RESULT_INVALID: (
        "개정 결과가 기존 스킬의 권한·버전 계약을 충족하지 않아 회수했습니다."
    ),
}


class TkSkillTraceReviewView:
    def __init__(self, *, title: str = "SKILLA 실행 기록 검토") -> None:
        try:
            import tkinter as tk
            from tkinter import messagebox, ttk
        except ImportError as error:
            raise RuntimeError("tkinter trace review is unavailable") from error
        try:
            root = tk.Tk()
        except tk.TclError as error:
            raise RuntimeError("tkinter trace review could not start") from error
        configure_window(root, title=title, geometry="1160x800", minsize=(1020, 700))
        outer = tk.Frame(root, bg=COLORS["bg"], padx=20, pady=16)
        outer.pack(fill="both", expand=True)
        header(outer, system_code="SYSTEM // REVIEW REQUIRED", heading="스킬 개정 후보 검토")
        footer(outer)
        label(
            outer,
            "경로·URL·이메일·원문 인자를 제외한 최소화 실행 기록만 표시",
            color=COLORS["muted"],
            size=9,
        ).pack(fill="x", pady=(0, 8))
        body = tk.PanedWindow(
            outer,
            orient="horizontal",
            sashrelief="flat",
            bg=COLORS["bg"],
            bd=0,
            sashwidth=10,
        )
        body.pack(fill="both", expand=True)
        left = panel(body)
        right = panel(body, alternate=True)
        body.add(left, minsize=300)
        body.add(right, minsize=520)
        label(left, "검토 대기", color=COLORS["muted"], size=10, bold=True).pack(
            fill="x", pady=(0, 8)
        )
        self._listbox = tk.Listbox(
            left,
            exportselection=False,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            selectbackground="#0b4b5e",
            selectforeground=COLORS["cyan"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            relief="flat",
            font=("맑은 고딕", 11),
            height=13,
        )
        list_scroll = tk.Scrollbar(left, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=list_scroll.set)
        self._listbox.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")
        label(right, "실행 기록과 개정 근거", color=COLORS["muted"], size=10, bold=True).pack(
            fill="x", pady=(0, 8)
        )
        self._detail = tk.Text(
            right,
            wrap="word",
            state="disabled",
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            selectbackground="#0b4b5e",
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            relief="flat",
            font=("맑은 고딕", 11),
            padx=14,
            pady=12,
            height=13,
        )
        detail_scroll = tk.Scrollbar(right, command=self._detail.yview)
        self._detail.configure(yscrollcommand=detail_scroll.set)
        self._detail.pack(side="left", fill="both", expand=True)
        detail_scroll.pack(side="right", fill="y")
        self._notice = tk.StringVar(value="실행 기록을 불러오고 있습니다.")
        label(outer, textvariable=self._notice, color=COLORS["warning"], size=10).pack(
            fill="x", pady=(8, 0)
        )
        mode = tk.Frame(outer, bg=COLORS["bg"])
        mode.pack(fill="x", pady=(8, 0))
        label(mode, "초안 종류", color=COLORS["muted"], size=9, bold=True).pack(
            side="left", padx=(0, 8)
        )
        self._revision_choice = ttk.Combobox(mode, state="readonly", width=72)
        self._revision_choice.pack(side="left", fill="x", expand=True)
        buttons = tk.Frame(outer, bg=COLORS["bg"])
        buttons.pack(fill="x", pady=(8, 0))
        self._create_button = button(
            buttons, "NIM으로 초안 생성", color=COLORS["success"], width=20
        )
        self._create_button.pack(side="left", padx=(0, 6))
        self._discard_button = button(buttons, "기록 제외", color=COLORS["danger"])
        self._discard_button.pack(side="left", padx=(0, 6))
        self._refresh_button = button(buttons, "새로 고침", color=COLORS["cyan_dim"])
        self._refresh_button.pack(side="left")
        self._close_button = button(buttons, "닫기", color=COLORS["muted"])
        self._close_button.pack(side="right")
        self._root = root
        self._messagebox = messagebox
        self._trace_ids: tuple[UUID, ...] = ()
        self._revision_ids: tuple[UUID | None, ...] = (None,)
        self._on_select: Callable[[UUID], None] = lambda _trace_id: None
        self._on_select_revision: Callable[[UUID | None], None] = lambda _skill_id: None

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
        self._on_select = on_select
        self._on_select_revision = on_select_revision
        self._listbox.bind("<<ListboxSelect>>", self._handle_select)
        self._revision_choice.bind("<<ComboboxSelected>>", self._handle_revision_select)
        self._create_button.configure(command=on_create)
        self._discard_button.configure(command=on_discard)
        self._refresh_button.configure(command=on_refresh)
        self._close_button.configure(command=on_close)
        self._root.protocol("WM_DELETE_WINDOW", on_close)

    def render(self, display: TraceReviewDisplay) -> None:
        selected_id = display.selected.trace_id if display.selected is not None else None
        self._trace_ids = tuple(item.trace_id for item in display.pending)
        self._listbox.delete(0, "end")
        selected_index: int | None = None
        for index, item in enumerate(display.pending):
            self._listbox.insert("end", f"{item.goal_summary} ({item.step_count}단계)")
            if item.trace_id == selected_id:
                selected_index = index
        if selected_index is not None:
            self._listbox.selection_set(selected_index)
        self._detail.configure(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert(
            "end",
            _format_detail(display.selected)
            if display.selected is not None
            else "왼쪽 목록에서 검토할 실행 기록을 선택하세요.",
        )
        self._detail.configure(state="disabled")
        self._notice.set(display.notice)
        revision_values = ["새 스킬의 최초 검토 대기 초안 생성"]
        revision_values.extend(
            (
                f"기존 스킬 개정: {target.title} v{target.version} / "
                f"{target.reason_code} / 관측 {target.observations}회"
            )
            for target in display.revision_targets
        )
        self._revision_ids = (None,) + tuple(target.skill_id for target in display.revision_targets)
        self._revision_choice.configure(values=revision_values)
        revision_index = 0
        if display.selected_revision_skill_id is not None:
            try:
                revision_index = self._revision_ids.index(display.selected_revision_skill_id)
            except ValueError:
                revision_index = 0
        self._revision_choice.current(revision_index)
        self._create_button.configure(
            text=("NIM으로 개정 초안 생성" if revision_index > 0 else "NIM으로 최초 초안 생성")
        )
        if display.actions_enabled:
            self._create_button.configure(state="normal")
            self._discard_button.configure(state="normal")
        else:
            self._create_button.configure(state="disabled")
            self._discard_button.configure(state="disabled")
        if display.busy:
            self._refresh_button.configure(state="disabled")
            self._close_button.configure(state="disabled")
            self._revision_choice.configure(state="disabled")
        else:
            self._refresh_button.configure(state="normal")
            self._close_button.configure(state="normal")
            self._revision_choice.configure(state="readonly")

    def confirm(self, request: TraceReviewConfirmation) -> bool:
        capabilities = ", ".join(request.capabilities)
        if request.action is TraceReviewAction.CREATE_INITIAL_DRAFT:
            title = "NIM 스킬 초안 생성 확인"
            message = (
                f"요청 요약: {request.goal_summary}\n"
                f"사용 기능: {capabilities}\n\n"
                "화면에 표시된 개인정보 최소화 실행 기록을 NVIDIA NIM에 전송해 "
                "스킬 초안을 생성합니다. 계속할까요?"
            )
        elif request.action is TraceReviewAction.CREATE_REVISION_DRAFT:
            title = "NIM 개정 초안 생성 확인"
            message = (
                f"요청 요약: {request.goal_summary}\n"
                f"사용 기능: {capabilities}\n"
                f"개정 대상: {request.revision_title} v{request.revision_version}\n"
                f"개정 근거: {request.revision_reason_code}\n\n"
                "화면에 표시된 개인정보 최소화 실행 기록과 기존 스킬을 NVIDIA NIM에 "
                "전송해 개정 DRAFT를 생성합니다. 기존 VERIFIED 버전은 유지됩니다. 계속할까요?"
            )
        else:
            title = "실행 기록 폐기 확인"
            message = (
                f"요청 요약: {request.goal_summary}\n\n"
                "기록을 삭제하지 않고 검토 목록에서 제외합니다. 계속할까요?"
            )
        return bool(self._messagebox.askyesno(title, message, parent=self._root))

    def notify(self, title: str, message: str) -> None:
        self._messagebox.showinfo(title, message, parent=self._root)

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> object:
        return self._root.after(delay_ms, callback)

    def _handle_select(self, _event: object) -> None:
        selected = self._listbox.curselection()  # type: ignore[no-untyped-call]
        if len(selected) != 1:
            return
        index = int(selected[0])
        if 0 <= index < len(self._trace_ids):
            self._on_select(self._trace_ids[index])

    def _handle_revision_select(self, _event: object) -> None:
        index = self._revision_choice.current()
        if 0 <= index < len(self._revision_ids):
            self._on_select_revision(self._revision_ids[index])

    def close(self) -> None:
        self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()


def run_tk_skill_trace_review(
    trace_store: TraceReviewStore,
    workflow: InitialSkillDraftWorkflow,
    revision_catalog: RevisionReviewCatalog,
) -> None:
    view = TkSkillTraceReviewView()
    dispatcher = ThreadedDraftDispatcher(schedule=view.schedule)
    SkillTraceReviewPresenter(
        trace_store=trace_store,
        revision_catalog=revision_catalog,
        workflow=workflow,
        dispatcher=dispatcher,
        view=view,
        confirm=view.confirm,
    ).run()


def _summary(pending: PendingSkillTrace) -> PendingTraceSummary:
    trace = pending.trace
    return PendingTraceSummary(
        trace_id=trace.trace_id,
        goal_summary=trace.goal_summary,
        outcome=trace.outcome,
        recorded_at=pending.recorded_at,
        step_count=len(trace.steps),
    )


def _detail(pending: PendingSkillTrace) -> PendingTraceDetail:
    trace = pending.trace
    return PendingTraceDetail(
        **_summary(pending).model_dump(),
        steps=tuple(
            TraceStepDisplay(
                sequence=step.sequence,
                capability_id=step.capability_id,
                outcome=step.outcome,
                detail_code=step.detail_code,
                independently_verified=step.independently_verified,
            )
            for step in trace.steps
        ),
        dynamic_input_labels=trace.dynamic_input_labels,
        decision_notes=trace.decision_notes,
        verification_notes=trace.verification_notes,
    )


def _confirmation(
    action: TraceReviewAction,
    trace: SkillExecutionTrace,
    *,
    revision: RevisionTargetSummary | None = None,
) -> TraceReviewConfirmation:
    return TraceReviewConfirmation(
        action=action,
        trace_id=trace.trace_id,
        goal_summary=trace.goal_summary,
        capabilities=tuple(dict.fromkeys(step.capability_id for step in trace.steps)),
        revision_title=revision.title if revision is not None else None,
        revision_version=revision.version if revision is not None else None,
        revision_reason_code=revision.reason_code if revision is not None else None,
    )


def _revision_summary(
    record: SkillRecord,
    assessment: SkillRevisionAssessment,
) -> RevisionTargetSummary:
    return RevisionTargetSummary(
        skill_id=record.skill_id,
        key=record.key,
        title=record.title,
        version=record.version,
        updated_at=record.updated_at,
        reason_code=assessment.reason_code,
        observations=assessment.summary.observations,
        success_rate=assessment.summary.success_rate,
    )


def _format_detail(detail: PendingTraceDetail) -> str:
    lines = [
        "[요청 요약]",
        detail.goal_summary,
        "",
        "[전체 결과]",
        _outcome_label(detail.outcome),
        "",
        "[실행 단계]",
    ]
    lines.extend(
        (
            f"{step.sequence}. {_capability_label(step.capability_id)} / "
            f"{_outcome_label(step.outcome)} / {_detail_code_label(step.detail_code)} / 독립 검증: "
            f"{'예' if step.independently_verified else '아니요'}"
        )
        for step in detail.steps
    )
    for heading, values in (
        ("매번 달라지는 입력", detail.dynamic_input_labels),
        ("판단 근거", detail.decision_notes),
        ("검증 근거", detail.verification_notes),
    ):
        lines.extend(("", f"[{heading}]"))
        lines.extend(f"{index}. {value}" for index, value in enumerate(values, start=1))
        if not values:
            lines.append("없음")
    return "\n".join(lines)


_CAPABILITY_LABELS = {
    "system.info.read": "시스템 정보 읽기",
    "file.list": "폴더 내용 확인",
    "file.read": "파일 읽기",
    "file.copy": "파일 복사",
    "file.move": "파일 이동",
    "file.write": "파일 작성",
    "file.delete": "파일 삭제",
    "browser.open": "웹 페이지 열기",
    "browser.search": "웹 검색",
    "app.launch": "프로그램 실행",
    "document.open": "문서 열기",
    "folder.open": "폴더 열기",
}

_DETAIL_CODE_LABELS = {
    "POSTCONDITIONS_VERIFIED": "결과 조건 검증 완료",
    "ALL_ACTIONS_VERIFIED": "모든 단계 검증 완료",
    "FILES_LISTED": "폴더 내용 확인 완료",
    "FILE_MOVED": "파일 이동 확인 완료",
}


def _outcome_label(outcome: SkillOutcome) -> str:
    return {
        SkillOutcome.SUCCEEDED: "성공",
        SkillOutcome.FAILED: "실패",
        SkillOutcome.ABORTED: "중단",
    }[outcome]


def _capability_label(capability_id: str) -> str:
    return _CAPABILITY_LABELS.get(capability_id, capability_id)


def _detail_code_label(code: str) -> str:
    return _DETAIL_CODE_LABELS.get(code, code)
