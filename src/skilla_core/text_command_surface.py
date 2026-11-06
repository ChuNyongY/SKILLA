from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from pydantic import Field

from .always_on_runtime import (
    AlwaysOnState,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeStatusSnapshot,
)
from .models import FrozenModel
from .voice_command import validate_trusted_text_command


class TextCommandRuntime(Protocol):
    def submit_text(self, text: str) -> RuntimeEvent: ...

    def status_snapshot(self) -> RuntimeStatusSnapshot: ...


class TextCommandDisplay(FrozenModel):
    state_label: str = Field(min_length=1, max_length=80)
    detail_label: str = Field(min_length=1, max_length=120)
    result_text: str = Field(default="", max_length=1200)
    submit_enabled: bool
    stop_enabled: bool


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
_DISPLAY_SELECTOR_FAILED = "작업 화면 선택 창을 열지 못했습니다. 잠시 후 다시 시도해 주세요."

ErrorReporter = Callable[[str, str], None]


class TextCommandPresenter:
    def __init__(self, runtime: TextCommandRuntime) -> None:
        self._runtime = runtime

    def submit(self, text: str) -> RuntimeEvent:
        return self._runtime.submit_text(validate_trusted_text_command(text))

    def stop(self) -> RuntimeEvent:
        return self._runtime.submit_text("멈춰")

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
        if snapshot.result is not None:
            result_text = "\n".join((snapshot.result.title, *snapshot.result.lines))
        if snapshot.skill_review is not None:
            review = snapshot.skill_review
            result_text = "\n".join((
                review.title, f"이번 요청: {review.request}",
                "실행 계획", *review.planned_steps,
                "안전 확인", *review.safety_summary,
                "등록·재사용할 절차", *review.procedure,
            ))[:1200]
            detail_label = "검토 후 '예'를 입력하면 등록·실행, '아니요'를 입력하면 취소합니다."
        return TextCommandDisplay(
            state_label=state_label,
            detail_label=detail_label,
            result_text=result_text,
            submit_enabled=snapshot.state in {AlwaysOnState.IDLE, AlwaysOnState.REVIEWING},
            stop_enabled=active,
        )


def run_tk_text_command(
    runtime: TextCommandRuntime,
    *,
    poll_interval_ms: int = 250,
    open_display_selector: Callable[[], None] | None = None,
    review_skills: Callable[[], None] | None = None,
    review_skill_traces: Callable[[], None] | None = None,
) -> None:
    """Open a local text-command window without opening the microphone."""
    if not 100 <= poll_interval_ms <= 5_000:
        raise ValueError("poll interval must be within 100..5000 milliseconds")
    import tkinter as tk
    from tkinter import messagebox, ttk

    presenter = TextCommandPresenter(runtime)
    parent = getattr(tk, "_default_root", None)
    owns_root = parent is None
    root = tk.Tk() if owns_root else tk.Toplevel(parent)
    root.title("SKILLA 텍스트 명령")
    root.geometry("760x430")
    root.minsize(680, 390)
    if parent is not None:
        root.transient(parent)
        root.grab_set()
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="실행할 작업을 한국어로 입력하세요.").pack(anchor="w")
    command = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=command)
    entry.pack(fill="x", pady=(7, 10))
    state = tk.StringVar(value="대기 중")
    detail = tk.StringVar(value="명령을 입력할 수 있습니다.")
    ttk.Label(frame, textvariable=state).pack(anchor="w")
    ttk.Label(frame, textvariable=detail).pack(anchor="w", pady=(2, 8))
    result = tk.Text(frame, height=8, wrap="word", state="disabled")
    result.pack(fill="both", expand=True, pady=(0, 10))
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")

    def submit() -> None:
        raw = command.get()
        command.set("")
        try:
            presenter.submit(raw)
        except ValueError:
            messagebox.showerror(
                "SKILLA",
                "명령은 1~2000자로 입력하고 줄바꿈이나 제어 문자는 제외해 주세요.",
            )

    def stop() -> None:
        presenter.stop()

    submit_button = ttk.Button(buttons, text="실행", command=submit)
    submit_button.pack(side="left")
    stop_button = ttk.Button(buttons, text="현재 작업 중지", command=stop)
    stop_button.pack(side="left", padx=(8, 0))
    def close() -> None:
        if parent is not None:
            root.grab_release()
        root.destroy()

    ttk.Button(buttons, text="닫기", command=close).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", close)

    optional_actions = (
        ("스킬 관리", review_skills, _SKILL_REVIEW_FAILED),
        ("스킬 후보 검토", review_skill_traces, _TRACE_REVIEW_FAILED),
        ("작업 화면 선택", open_display_selector, _DISPLAY_SELECTOR_FAILED),
    )
    tools = None
    if any(action is not None for _label, action, _message in optional_actions):
        tools = ttk.Frame(frame)
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

    for label, action, failure_message in optional_actions:
        if tools is None or action is None:
            continue
        ttk.Button(
            tools,
            text=label,
            command=action_command(action, failure_message),
        ).pack(side="left", padx=(0, 8))
    entry.bind("<Return>", lambda _event: submit())

    def refresh() -> None:
        if not bool(root.winfo_exists()):
            return
        display = presenter.display()
        state.set(display.state_label)
        detail.set(display.detail_label)
        result.configure(state="normal")
        result.delete("1.0", "end")
        result.insert(
            "end",
            display.result_text or "작업을 실행하면 검증된 결과가 여기에 표시됩니다.",
        )
        result.configure(state="disabled")
        submit_button.configure(state="normal" if display.submit_enabled else "disabled")
        stop_button.configure(state="normal" if display.stop_enabled else "disabled")
        root.after(poll_interval_ms, refresh)

    refresh()
    entry.focus_set()
    if owns_root:
        root.mainloop()
    else:
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
