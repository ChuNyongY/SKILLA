from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .always_on_runtime import (
    AlwaysOnState,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeStatusSnapshot,
)
from .models import FrozenModel
from .skill_session import SkillReviewKind
from .voice_command import validate_trusted_text_command


class TextCommandRuntime(Protocol):
    def submit_text(self, text: str) -> RuntimeEvent: ...

    def status_snapshot(self) -> RuntimeStatusSnapshot: ...

    def respond_skill_review(self, review_id: UUID, accepted: bool) -> bool: ...


class TextCommandDisplay(FrozenModel):
    state_label: str = Field(min_length=1, max_length=80)
    detail_label: str = Field(min_length=1, max_length=120)
    result_text: str = Field(default="", max_length=1200)
    submit_enabled: bool
    stop_enabled: bool
    review_id: UUID | None = None
    review_accept_label: str = "이 스킬로 실행"


_STATE_LABELS = {
    AlwaysOnState.IDLE: "명령을 입력할 수 있습니다.",
    AlwaysOnState.PLANNING: "명령을 검토하고 있습니다.",
    AlwaysOnState.REVIEWING: "스킬 후보를 확인하고 예 또는 아니요를 입력하세요.",
    AlwaysOnState.EXECUTING: "승인된 작업을 실행하고 있습니다.",
    AlwaysOnState.CLOSED: "SKILLA가 종료되었습니다.",
}

_EVENT_LABELS = {
    None: "대기 중",
    RuntimeEventType.TASK_STARTED: "작업을 시작했습니다.",
    RuntimeEventType.TASK_COMPLETED: "작업을 완료했습니다.",
    RuntimeEventType.TASK_ABORTED: "작업이 중단되었습니다.",
    RuntimeEventType.STOP_ACCEPTED: "중지 요청을 받았습니다.",
    RuntimeEventType.BUSY_IGNORED: "진행 중에는 중지 명령만 받을 수 있습니다.",
    RuntimeEventType.ROUTED: "실행할 작업이 아닙니다.",
    RuntimeEventType.FAILED: "작업을 처리하지 못했습니다.",
    RuntimeEventType.CLOSED: "SKILLA가 종료되었습니다.",
}

_SKILL_REVIEW_FAILED = "스킬 관리 화면을 열지 못했습니다. 잠시 후 다시 시도해 주세요."
_TRACE_REVIEW_FAILED = "스킬 후보 검토 화면을 열지 못했습니다. 잠시 후 다시 시도해 주세요."
_TRIGGER_REVIEW_FAILED = "상황 스킬 화면을 열지 못했습니다. 잠시 후 다시 시도해 주세요."
_SCHEDULE_REVIEW_FAILED = "예약 스킬 화면을 열지 못했습니다. 잠시 후 다시 시도해 주세요."
_DISPLAY_SELECTOR_FAILED = "작업 화면 선택 창을 열지 못했습니다. 잠시 후 다시 시도해 주세요."

ErrorReporter = Callable[[str, str], None]


class TextCommandPresenter:
    def __init__(self, runtime: TextCommandRuntime) -> None:
        self._runtime = runtime

    def submit(self, text: str) -> RuntimeEvent:
        return self._runtime.submit_text(validate_trusted_text_command(text))

    def stop(self) -> RuntimeEvent:
        return self._runtime.submit_text("멈춰")

    def respond_review(self, review_id: UUID, accepted: bool) -> bool:
        return self._runtime.respond_skill_review(review_id, accepted)

    def display(self) -> TextCommandDisplay:
        snapshot = self._runtime.status_snapshot()
        active = snapshot.state in {
            AlwaysOnState.PLANNING, AlwaysOnState.REVIEWING, AlwaysOnState.EXECUTING,
        }
        event_label = _EVENT_LABELS[snapshot.last_event_type]
        state_label = _STATE_LABELS[snapshot.state]
        detail_label = event_label
        if snapshot.state is AlwaysOnState.IDLE and snapshot.last_event_type is not None:
            state_label = event_label
            detail_label = (
                "아래에서 검증된 결과를 확인하세요."
                if snapshot.result is not None
                else "다음 명령을 입력할 수 있습니다."
            )
        result_text = ""
        review = snapshot.skill_review
        if snapshot.result is not None:
            result_text = "\n".join((snapshot.result.title, *snapshot.result.lines))
        if review is not None:
            result_text = "\n".join((
                review.title, f"이번 요청: {review.request}",
                "실행 계획", *review.planned_steps,
                "안전 확인", *review.safety_summary,
                "등록·재사용할 절차", *review.procedure,
            ))[:1200]
            detail_label = "아래에서 실행 계획을 확인한 뒤 계속하거나 취소하세요."
        return TextCommandDisplay(
            state_label=state_label,
            detail_label=detail_label,
            result_text=result_text,
            submit_enabled=snapshot.state in {AlwaysOnState.IDLE, AlwaysOnState.REVIEWING},
            stop_enabled=active,
            review_id=None if review is None else review.review_id,
            review_accept_label=(
                "스킬 등록 후 실행"
                if review is not None and review.kind is SkillReviewKind.REGISTER
                else "이 스킬로 실행"
            ),
        )


def run_tk_text_command(
    runtime: TextCommandRuntime,
    *,
    poll_interval_ms: int = 250,
    open_display_selector: Callable[[], None] | None = None,
    review_skills: Callable[[], None] | None = None,
    review_skill_traces: Callable[[], None] | None = None,
    manage_skill_triggers: Callable[[], None] | None = None,
    manage_skill_schedules: Callable[[], None] | None = None,
) -> None:
    """Open a local text-command window without opening the microphone."""
    if not 100 <= poll_interval_ms <= 5_000:
        raise ValueError("poll interval must be within 100..5000 milliseconds")
    import tkinter as tk
    from tkinter import messagebox
    from tkinter.scrolledtext import ScrolledText

    from . import control_theme as theme

    presenter = TextCommandPresenter(runtime)
    parent = getattr(tk, "_default_root", None)
    owns_root = parent is None
    root = tk.Tk() if owns_root else tk.Toplevel(parent)
    root.title("SKILLA 텍스트 명령")
    root.geometry("790x560")
    root.minsize(670, 510)
    root.configure(bg=theme.BACKGROUND)
    if parent is not None:
        root.transient(parent)
    frame = tk.Frame(root, bg=theme.BACKGROUND, padx=22, pady=18)
    frame.pack(fill="both", expand=True)
    theme.heading(frame, "텍스트 명령", "예: 시스템 정보 확인해 줘  ·  Enter로 실행")
    tk.Label(frame, text="실행할 작업", bg=theme.BACKGROUND, fg=theme.TEXT,
             font=theme.FONT).pack(anchor="w")
    command = tk.StringVar()
    entry = tk.Entry(
        frame, textvariable=command, bg=theme.FIELD, fg=theme.TEXT,
        insertbackground=theme.ACCENT, disabledbackground=theme.FIELD,
        disabledforeground=theme.MUTED, relief="flat", font=("맑은 고딕", 13),
        highlightthickness=1, highlightcolor=theme.ACCENT, highlightbackground=theme.BORDER,
    )
    entry.pack(fill="x", ipady=8, pady=(4, 8))
    buttons = tk.Frame(frame, bg=theme.BACKGROUND)
    buttons.pack(fill="x", pady=(0, 12))
    card = tk.Frame(frame, bg=theme.PANEL, padx=14, pady=11)
    card.pack(fill="both", expand=True)
    state = tk.StringVar(value="대기 중")
    detail = tk.StringVar(value="명령을 입력할 수 있습니다.")
    tk.Label(card, textvariable=state, bg=theme.PANEL, fg=theme.ACCENT,
             font=("맑은 고딕", 14, "bold")).pack(anchor="w")
    tk.Label(card, textvariable=detail, bg=theme.PANEL, fg=theme.MUTED,
             font=theme.FONT).pack(anchor="w", pady=(2, 8))
    result = ScrolledText(card, height=5, wrap="word", state="disabled", relief="flat",
                          bg=theme.FIELD, fg=theme.TEXT, font=theme.FONT, padx=10, pady=8)
    result.pack(fill="both", expand=True)
    review_actions = tk.Frame(card, bg=theme.PANEL)

    inline_error = tk.StringVar()
    tk.Label(buttons, textvariable=inline_error, fg=theme.DANGER, bg=theme.BACKGROUND,
             font=theme.FONT).pack(side="bottom", anchor="w")

    def submit() -> None:
        if not presenter.display().submit_enabled:
            return
        raw = command.get()
        try:
            presenter.submit(raw)
        except ValueError:
            inline_error.set("명령을 1~2000자 한 줄로 입력하세요.")
        else:
            inline_error.set("")
            command.set("")

    def stop() -> None:
        presenter.stop()

    submit_button = theme.button(buttons, "명령 실행", submit, primary=True)
    submit_button.pack(side="left")
    stop_button = theme.button(buttons, "작업 중지", stop, color=theme.DANGER)
    stop_button.pack(side="left", padx=(8, 0))

    def close() -> None:
        root.destroy()

    theme.button(buttons, "닫기", close).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", close)

    review_yes = theme.button(review_actions, "이 스킬로 실행", lambda: None, primary=True)
    review_yes.pack(side="left", padx=(0, 8))
    review_no = theme.button(review_actions, "취소", lambda: None)
    review_no.pack(side="left")

    optional_actions = (
        ("스킬 관리", review_skills, _SKILL_REVIEW_FAILED),
        ("스킬 후보 검토", review_skill_traces, _TRACE_REVIEW_FAILED),
        ("상황 스킬", manage_skill_triggers, _TRIGGER_REVIEW_FAILED),
        ("예약 스킬", manage_skill_schedules, _SCHEDULE_REVIEW_FAILED),
        ("작업 화면 선택", open_display_selector, _DISPLAY_SELECTOR_FAILED),
    )
    tools = None
    if any(action is not None for _label, action, _message in optional_actions):
        tools = tk.Frame(frame, bg=theme.BACKGROUND)
        tools.pack(fill="x", pady=(9, 0))

    def report_failure(title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=root)

    def action_command(
        callback: Callable[[], None],
        message: str,
    ) -> Callable[[], None]:
        def invoke() -> None:
            invoke_surface_action(callback, message, report_failure)

        return invoke

    if tools is not None:
        skill_entries = tuple(
            (label, action_command(action, failure_message))
            for label, action, failure_message in optional_actions[:-1]
            if action is not None
        )
        if skill_entries:
            theme.action_menu(tools, "스킬", skill_entries).pack(side="left", padx=(0, 8))
        if open_display_selector is not None:
            theme.button(
                tools, "작업 화면 선택",
                action_command(open_display_selector, _DISPLAY_SELECTOR_FAILED),
            ).pack(side="left", padx=(0, 8))
    entry.bind("<Return>", lambda _event: submit())

    previous_result = None
    refresh_id: str | None = None

    def refresh() -> None:
        nonlocal previous_result, refresh_id
        display = presenter.display()
        state.set(display.state_label)
        detail.set(display.detail_label)
        if display.result_text != previous_result:
            result.configure(state="normal")
            result.delete("1.0", "end")
            result.insert("end", display.result_text or "실행이 끝나면 결과가 여기에 표시됩니다.")
            result.configure(state="disabled")
            previous_result = display.result_text
        if display.review_id is not None:
            review_id = display.review_id
            review_yes.configure(
                text=display.review_accept_label,
                command=lambda: presenter.respond_review(review_id, True),
            )
            review_no.configure(command=lambda: presenter.respond_review(review_id, False))
            review_actions.pack(anchor="w", pady=(8, 0))
        else:
            review_actions.pack_forget()
        submit_button.configure(state="normal" if display.submit_enabled else "disabled")
        stop_button.configure(state="normal" if display.stop_enabled else "disabled")
        refresh_id = root.after(poll_interval_ms, refresh)

    def cancel_refresh(event: tk.Event[tk.Misc]) -> None:
        if event.widget == root and refresh_id is not None:
            root.after_cancel(refresh_id)

    root.bind("<Destroy>", cancel_refresh)
    refresh()
    entry.focus_set()
    if owns_root:
        root.mainloop()
    else:
        assert parent is not None
        parent.wait_window(root)


def invoke_surface_action(
    action: Callable[[], None],
    failure_message: str,
    report_failure: ErrorReporter,
) -> None:
    """Run a local UI callback while keeping private exception data out of the window."""
    if not failure_message:
        raise ValueError("failure message must not be empty")
    try:
        action()
    except Exception:
        report_failure("SKILLA", failure_message)
