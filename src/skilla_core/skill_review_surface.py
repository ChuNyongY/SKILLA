from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .cyber_theme import COLORS, button, configure_window, footer, header, label, panel
from .models import FrozenModel
from .skill_runtime import SkillRecord, SkillStatus


class SkillReviewAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class SkillDraftSummary(FrozenModel):
    skill_id: UUID
    key: str
    title: str
    version: int = Field(ge=1)
    is_revision: bool
    status: SkillStatus


class SkillDraftDetail(FrozenModel):
    skill_id: UUID
    key: str
    title: str
    description: str
    version: int = Field(ge=1)
    triggers: tuple[str, ...]
    procedure: tuple[str, ...]
    dynamic_inputs: tuple[str, ...]
    decision_rules: tuple[str, ...]
    verification_rules: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    supersedes_skill_id: UUID | None
    status: SkillStatus


class SkillReviewDisplay(FrozenModel):
    drafts: tuple[SkillDraftSummary, ...]
    selected: SkillDraftDetail | None = None
    notice: str = Field(min_length=1, max_length=160)
    mutation_enabled: bool = False


class SkillReviewConfirmation(FrozenModel):
    action: SkillReviewAction
    skill_id: UUID
    key: str
    title: str
    version: int = Field(ge=1)
    allowed_capabilities: tuple[str, ...]


class SkillReviewCatalog(Protocol):
    def list(
        self,
        *,
        status: SkillStatus | None = None,
        limit: int = 20,
    ) -> tuple[SkillRecord, ...]: ...

    def require(self, skill_id: UUID) -> SkillRecord: ...

    def approve(self, skill_id: UUID, *, now: datetime | None = None) -> SkillRecord: ...

    def retire(self, skill_id: UUID, *, now: datetime | None = None) -> SkillRecord: ...


class SkillReviewView(Protocol):
    def bind_handlers(
        self,
        *,
        on_select: Callable[[UUID], None],
        on_approve: Callable[[], None],
        on_reject: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None: ...

    def render(self, display: SkillReviewDisplay) -> None: ...

    def close(self) -> None: ...

    def run(self) -> None: ...


ConfirmationCallback = Callable[[SkillReviewConfirmation], bool]


class _Selection(FrozenModel):
    skill_id: UUID
    version: int
    updated_at: datetime


class SkillReviewPresenter:
    """Review local drafts without giving the UI authority beyond explicit choices."""

    def __init__(
        self,
        *,
        catalog: SkillReviewCatalog,
        view: SkillReviewView,
        confirm: ConfirmationCallback,
    ) -> None:
        self._catalog = catalog
        self._view = view
        self._confirm = confirm
        self._drafts: tuple[SkillDraftSummary, ...] = ()
        self._selected_record: SkillRecord | None = None
        self._selection: _Selection | None = None

    def run(self) -> None:
        self._view.bind_handlers(
            on_select=self.select,
            on_approve=self.approve,
            on_reject=self.reject,
            on_refresh=self.refresh,
            on_close=self._view.close,
        )
        self.refresh()
        self._view.run()

    def refresh(self, notice: str = "저장된 스킬을 불러왔습니다.") -> None:
        try:
            records = tuple(
                record
                for record in self._catalog.list(status=None, limit=100)
                if record.status in {SkillStatus.DRAFT, SkillStatus.VERIFIED}
            )
        except Exception:
            self._drafts = ()
            self._clear_selection()
            self._render("스킬 초안을 불러오지 못했습니다.")
            return
        self._drafts = tuple(_summary(record) for record in records)
        self._clear_selection()
        if not self._drafts and notice == "저장된 스킬을 불러왔습니다.":
            notice = (
                "현재 저장된 스킬이 없습니다. "
                "먼저 '스킬 후보 검토'에서 실행 기록을 초안으로 만드세요."
            )
        self._render(notice)

    def select(self, skill_id: UUID) -> None:
        try:
            record = self._catalog.require(skill_id)
        except Exception:
            self.refresh("선택한 초안을 찾을 수 없어 목록을 새로 고쳤습니다.")
            return
        listed_ids = {draft.skill_id for draft in self._drafts}
        if (
            record.status not in {SkillStatus.DRAFT, SkillStatus.VERIFIED}
            or record.skill_id not in listed_ids
        ):
            self.refresh("선택한 스킬의 상태가 변경되어 목록을 새로 고쳤습니다.")
            return
        self._selected_record = record
        self._selection = _Selection(
            skill_id=record.skill_id,
            version=record.version,
            updated_at=record.updated_at,
        )
        notice = (
            "내용과 허용 기능을 확인한 뒤 승인 또는 거절하세요."
            if record.status is SkillStatus.DRAFT
            else "현재 사용 가능한 스킬입니다. 내용과 허용 기능을 확인할 수 있습니다."
        )
        self._render(notice)

    def approve(self) -> None:
        self._mutate(SkillReviewAction.APPROVE)

    def reject(self) -> None:
        self._mutate(SkillReviewAction.REJECT)

    def _mutate(self, action: SkillReviewAction) -> None:
        selection = self._selection
        selected = self._selected_record
        if selection is None or selected is None:
            self._render("먼저 검토할 스킬 초안을 선택하세요.")
            return
        current = self._current_selection(selection)
        if current is None:
            self.refresh("선택한 초안의 상태가 변경되어 작업을 중단했습니다.")
            return
        confirmation = SkillReviewConfirmation(
            action=action,
            skill_id=current.skill_id,
            key=current.key,
            title=current.title,
            version=current.version,
            allowed_capabilities=current.allowed_capabilities,
        )
        try:
            confirmed = self._confirm(confirmation)
        except Exception:
            confirmed = False
        if not confirmed:
            self._render("요청을 취소했습니다. 스킬 상태는 변경되지 않았습니다.")
            return
        current = self._current_selection(selection)
        if current is None:
            self.refresh("확인 중 초안의 상태가 변경되어 작업을 중단했습니다.")
            return
        try:
            result = (
                self._catalog.approve(current.skill_id)
                if action is SkillReviewAction.APPROVE
                else self._catalog.retire(current.skill_id)
            )
        except Exception:
            self.refresh("스킬 상태를 변경하지 못했습니다. 목록을 다시 확인하세요.")
            return
        expected = (
            SkillStatus.VERIFIED if action is SkillReviewAction.APPROVE else SkillStatus.RETIRED
        )
        if result.skill_id != current.skill_id or result.status is not expected:
            self.refresh("스킬 상태 확인에 실패했습니다. 목록을 다시 확인하세요.")
            return
        notice = (
            "스킬을 승인했습니다. 이제 관련 요청에서 사용할 수 있습니다."
            if action is SkillReviewAction.APPROVE
            else "스킬 초안을 거절하고 보관 상태로 전환했습니다."
        )
        self.refresh(notice)

    def _current_selection(self, selection: _Selection) -> SkillRecord | None:
        try:
            current = self._catalog.require(selection.skill_id)
        except Exception:
            return None
        if (
            current.status is not SkillStatus.DRAFT
            or current.version != selection.version
            or current.updated_at != selection.updated_at
        ):
            return None
        return current

    def _clear_selection(self) -> None:
        self._selected_record = None
        self._selection = None

    def _render(self, notice: str) -> None:
        selected = _detail(self._selected_record) if self._selected_record is not None else None
        self._view.render(
            SkillReviewDisplay(
                drafts=self._drafts,
                selected=selected,
                notice=notice,
                mutation_enabled=(selected is not None and selected.status is SkillStatus.DRAFT),
            )
        )


class TkSkillReviewView:
    """Thin tkinter view; every callback executes on the owning UI thread."""

    def __init__(self, *, title: str = "SKILLA 스킬 검토") -> None:
        try:
            import tkinter as tk
            from tkinter import messagebox
        except ImportError as error:
            raise RuntimeError("tkinter skill review is unavailable") from error
        try:
            parent = getattr(tk, "_default_root", None)
            has_parent = parent is not None and bool(parent.winfo_exists())
            root = tk.Toplevel(parent) if has_parent else tk.Tk()
            if has_parent:
                root.transient(parent)
            owns_mainloop = not has_parent
        except tk.TclError as error:
            raise RuntimeError("tkinter skill review could not start") from error
        configure_window(root, title=title, geometry="1120x760", minsize=(980, 680))
        outer = tk.Frame(root, bg=COLORS["bg"], padx=20, pady=16)
        outer.pack(fill="both", expand=True)
        header(outer, system_code="SYSTEM // SKILL MEMORY", heading="스킬 관리")
        footer(outer)

        body = tk.PanedWindow(
            outer,
            orient="horizontal",
            sashrelief="flat",
            bg=COLORS["bg"],
            bd=0,
            sashwidth=10,
        )
        body.pack(fill="both", expand=True, pady=(8, 8))
        left = panel(body)
        right = panel(body, alternate=True)
        body.add(left, minsize=260)
        body.add(right, minsize=520)

        label(left, "저장된 스킬", color=COLORS["muted"], size=10, bold=True).pack(
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
            height=15,
        )
        list_scroll = tk.Scrollbar(left, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=list_scroll.set)
        self._listbox.pack(side="left", fill="both", expand=True)
        list_scroll.pack(side="right", fill="y")

        label(right, "선택한 스킬", color=COLORS["muted"], size=10, bold=True).pack(
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
            height=15,
        )
        detail_scroll = tk.Scrollbar(right, command=self._detail.yview)
        self._detail.configure(yscrollcommand=detail_scroll.set)
        self._detail.pack(side="left", fill="both", expand=True)
        detail_scroll.pack(side="right", fill="y")

        self._notice = tk.StringVar(value="스킬 초안을 불러오고 있습니다.")
        label(
            outer,
            textvariable=self._notice,
            color=COLORS["warning"],
            size=10,
        ).pack(fill="x")
        buttons = tk.Frame(outer, bg=COLORS["bg"])
        buttons.pack(fill="x", pady=(8, 0))
        self._approve_button = button(buttons, "✓  승인", color=COLORS["success"])
        self._approve_button.pack(side="left", padx=(0, 6))
        self._reject_button = button(buttons, "×  거절", color=COLORS["danger"])
        self._reject_button.pack(side="left", padx=(0, 6))
        self._refresh_button = button(buttons, "↻  새로 고침", color=COLORS["cyan_dim"])
        self._refresh_button.pack(side="left")
        self._close_button = button(buttons, "닫기", color=COLORS["muted"])
        self._close_button.pack(side="right")
        self._root = root
        self._owns_mainloop = owns_mainloop
        self._messagebox = messagebox
        self._draft_ids: tuple[UUID, ...] = ()
        self._on_select: Callable[[UUID], None] = lambda _skill_id: None

    def bind_handlers(
        self,
        *,
        on_select: Callable[[UUID], None],
        on_approve: Callable[[], None],
        on_reject: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._on_select = on_select
        self._listbox.bind("<<ListboxSelect>>", self._handle_select)
        self._approve_button.configure(command=on_approve)
        self._reject_button.configure(command=on_reject)
        self._refresh_button.configure(command=on_refresh)
        self._close_button.configure(command=on_close)
        self._root.protocol("WM_DELETE_WINDOW", on_close)

    def render(self, display: SkillReviewDisplay) -> None:
        selected_id = display.selected.skill_id if display.selected is not None else None
        self._draft_ids = tuple(draft.skill_id for draft in display.drafts)
        self._listbox.delete(0, "end")
        selected_index: int | None = None
        for index, draft in enumerate(display.drafts):
            if draft.status is SkillStatus.VERIFIED:
                kind = "사용 가능"
            else:
                kind = "개정 초안" if draft.is_revision else "신규 초안"
            self._listbox.insert("end", f"[{kind}] {draft.title} (v{draft.version})")
            if draft.skill_id == selected_id:
                selected_index = index
        if selected_index is not None:
            self._listbox.selection_set(selected_index)
        self._detail.configure(state="normal")
        self._detail.delete("1.0", "end")
        if display.selected is None:
            self._detail.insert("end", "왼쪽 목록에서 검토할 스킬을 선택하세요.")
        else:
            self._detail.insert("end", _format_detail(display.selected))
        self._detail.configure(state="disabled")
        self._notice.set(display.notice)
        if display.mutation_enabled:
            self._approve_button.configure(state="normal")
            self._reject_button.configure(state="normal")
        else:
            self._approve_button.configure(state="disabled")
            self._reject_button.configure(state="disabled")

    def confirm(self, request: SkillReviewConfirmation) -> bool:
        capabilities = ", ".join(request.allowed_capabilities)
        if request.action is SkillReviewAction.APPROVE:
            title = "스킬 승인 확인"
            consequence = "승인하면 관련 요청에서 이 스킬을 사용할 수 있습니다."
        else:
            title = "스킬 거절 확인"
            consequence = "거절하면 이 초안은 실행에 사용되지 않습니다."
        return bool(
            self._messagebox.askyesno(
                title,
                f"{request.title} (v{request.version})\n허용 기능: {capabilities}\n\n{consequence}",
                parent=self._root,
            )
        )

    def _handle_select(self, _event: object) -> None:
        selected = self._listbox.curselection()  # type: ignore[no-untyped-call]
        if len(selected) != 1:
            return
        index = int(selected[0])
        if 0 <= index < len(self._draft_ids):
            self._on_select(self._draft_ids[index])

    def close(self) -> None:
        self._root.destroy()

    def run(self) -> None:
        if self._owns_mainloop:
            self._root.mainloop()
        else:
            self._root.wait_window()


def run_tk_skill_review(catalog: SkillReviewCatalog) -> None:
    view = TkSkillReviewView()
    SkillReviewPresenter(
        catalog=catalog,
        view=view,
        confirm=view.confirm,
    ).run()


def _summary(record: SkillRecord) -> SkillDraftSummary:
    return SkillDraftSummary(
        skill_id=record.skill_id,
        key=record.key,
        title=record.title,
        version=record.version,
        is_revision=record.supersedes_skill_id is not None,
        status=record.status,
    )


def _detail(record: SkillRecord) -> SkillDraftDetail:
    return SkillDraftDetail(
        skill_id=record.skill_id,
        key=record.key,
        title=record.title,
        description=record.description,
        version=record.version,
        triggers=record.triggers,
        procedure=record.procedure,
        dynamic_inputs=record.dynamic_inputs,
        decision_rules=record.decision_rules,
        verification_rules=record.verification_rules,
        allowed_capabilities=record.allowed_capabilities,
        supersedes_skill_id=record.supersedes_skill_id,
        status=record.status,
    )


def _format_detail(detail: SkillDraftDetail) -> str:
    sections = (
        ("이름", (detail.title,)),
        ("키", (detail.key,)),
        (
            "상태",
            ("사용 가능" if detail.status is SkillStatus.VERIFIED else "승인 전 초안",),
        ),
        ("버전", (str(detail.version),)),
        ("설명", (detail.description,)),
        ("호출 표현", detail.triggers),
        ("작업 절차", detail.procedure),
        ("매번 확인할 입력", detail.dynamic_inputs),
        ("판단 규칙", detail.decision_rules),
        ("결과 확인 규칙", detail.verification_rules),
        ("허용 기능", detail.allowed_capabilities),
        (
            "개정 대상",
            (str(detail.supersedes_skill_id) if detail.supersedes_skill_id else "신규 스킬",),
        ),
    )
    lines: list[str] = []
    for heading, values in sections:
        lines.append(f"[{heading}]")
        lines.extend(f"{index}. {value}" for index, value in enumerate(values, start=1))
        if not values:
            lines.append("없음")
        lines.append("")
    return "\n".join(lines).rstrip()
