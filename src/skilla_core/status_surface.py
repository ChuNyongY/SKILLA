from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from pydantic import Field

from .always_on_runtime import AlwaysOnState, RuntimeEventType, RuntimeStatusSnapshot
from .models import FrozenModel
from .skill_session import PendingSkillReview, SkillReviewKind
from .voice import VoicePipelineDiagnostics


class RuntimeStatusDisplay(FrozenModel):
    state: AlwaysOnState
    state_label: str = Field(min_length=1, max_length=32)
    detail_label: str = Field(min_length=1, max_length=80)
    completed_actions: int = Field(ge=0)
    sequence: int = Field(ge=0)
    stop_enabled: bool
    voice_label: str = Field(default="마이크 상태 확인 중", min_length=1, max_length=80)
    input_level: float = Field(default=0.0, ge=0.0, le=1.0)
    audio_frame_count: int = Field(default=0, ge=0)
    skill_review: PendingSkillReview | None = None


class StatusView(Protocol):
    def bind_handlers(
        self,
        *,
        on_stop: Callable[[], None],
        on_hide: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None: ...

    def render(self, display: RuntimeStatusDisplay) -> None: ...

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> None: ...

    def minimize(self) -> None: ...

    def close(self) -> None: ...

    def run(self) -> None: ...


_STATE_LABELS = {
    AlwaysOnState.IDLE: "대기 중",
    AlwaysOnState.PLANNING: "계획 중",
    AlwaysOnState.REVIEWING: "후보 검토 중",
    AlwaysOnState.EXECUTING: "실행 중",
    AlwaysOnState.CLOSED: "종료됨",
}

_REASON_LABELS = {
    "RUNTIME_READY": "음성 명령을 기다리고 있습니다.",
    "PLANNING_STARTED": "명령을 안전하게 검토하고 있습니다.",
    "EXECUTION_STARTED": "승인된 작업을 실행하고 있습니다.",
    "LOCAL_STOP_ACCEPTED": "중지 요청을 처리하고 있습니다.",
    "NO_ACTIVE_TASK": "현재 진행 중인 작업이 없습니다.",
    "ACTIVE_TASK_ACCEPTS_STOP_ONLY": "현재 작업 중에는 중지 명령만 받습니다.",
    "RUNTIME_CLOSED": "런타임이 종료되었습니다.",
    "RUNTIME_STOP_TIMEOUT": "런타임 종료가 제한 시간을 초과했습니다.",
    "SKILL_REVIEW_REQUIRED": "작업 내용을 확인한 뒤 예 또는 아니요로 답해 주세요.",
    "SKILL_REVIEW_RESPONSE_ACCEPTED": "검토 응답을 받았습니다.",
    "SKILL_REVIEW_CANCELLED": "등록·실행을 취소했거나 응답 시간이 지났습니다.",
    "SKILL_REVIEW_FAILED": "스킬 후보를 준비하지 못했습니다. 아무 작업도 실행하지 않았습니다.",
    "SKILL_PLAN_POLICY_DENIED": "안전 조건을 충족하지 않아 등록·실행을 차단했습니다.",
    "SKILL_CANDIDATES_AMBIGUOUS": "스킬 후보가 여러 개입니다. 요청을 더 구체적으로 말해 주세요.",
}


def reactor_pulse_geometry(input_level: float) -> tuple[int, float]:
    """Map the live microphone level to the visible reactor stroke and radius."""
    level = max(0.0, min(1.0, float(input_level)))
    return 2 + round(level * 6), 47 + level * 20


def reactor_level_label(input_level: float) -> str:
    level = max(0.0, min(1.0, float(input_level)))
    return f"MIC {round(level * 100):02d}%"


class RuntimeStatusPresenter:
    """Poll a privacy-minimized runtime snapshot on the owning UI thread."""

    def __init__(
        self,
        *,
        status_provider: Callable[[], RuntimeStatusSnapshot],
        request_task_stop: Callable[[], object],
        request_capture_stop: Callable[[], bool],
        request_runtime_stop: Callable[[], object],
        view: StatusView,
        poll_interval_ms: int = 250,
        voice_diagnostics_provider: Callable[[], VoicePipelineDiagnostics] | None = None,
    ) -> None:
        if type(poll_interval_ms) is not int or not 100 <= poll_interval_ms <= 5_000:
            raise ValueError("poll_interval_ms must be an integer within 100..5000")
        self._status_provider = status_provider
        self._request_task_stop = request_task_stop
        self._request_capture_stop = request_capture_stop
        self._request_runtime_stop = request_runtime_stop
        self._view = view
        self._poll_interval_ms = poll_interval_ms
        self._voice_diagnostics_provider = voice_diagnostics_provider
        self._active = False

    def run(self) -> None:
        if self._active:
            raise RuntimeError("status presenter is already running")
        self._active = True
        self._view.bind_handlers(
            on_stop=self.request_stop,
            on_hide=self.hide,
            on_exit=self.exit,
        )
        self.refresh()
        self._view.run()

    def refresh(self) -> None:
        if not self._active:
            return
        try:
            snapshot = self._status_provider()
            diagnostics = (
                None
                if self._voice_diagnostics_provider is None
                else self._voice_diagnostics_provider()
            )
            display = self._display(snapshot, diagnostics)
        except Exception:
            display = RuntimeStatusDisplay(
                state=AlwaysOnState.CLOSED,
                state_label="상태 오류",
                detail_label="런타임 상태를 확인할 수 없습니다.",
                completed_actions=0,
                sequence=0,
                stop_enabled=True,
            )
        self._view.render(display)
        if self._active:
            self._view.schedule(self._poll_interval_ms, self.refresh)

    def request_stop(self) -> None:
        if not self._active:
            return
        try:
            self._request_task_stop()
        except Exception:
            self._view.render(
                RuntimeStatusDisplay(
                    state=AlwaysOnState.CLOSED,
                    state_label="중지 오류",
                    detail_label="중지 요청을 완료하지 못했습니다.",
                    completed_actions=0,
                    sequence=0,
                    stop_enabled=True,
                )
            )
            return
        self.refresh()

    def exit(self) -> None:
        if not self._active:
            return
        try:
            self._request_capture_stop()
            self._request_runtime_stop()
        finally:
            self._active = False
            self._view.close()

    def hide(self) -> None:
        """Close only the HUD; agent shutdown requires the explicit Stop action."""
        if not self._active:
            return
        self._view.minimize()

    @staticmethod
    def _display(
        snapshot: RuntimeStatusSnapshot,
        diagnostics: VoicePipelineDiagnostics | None = None,
    ) -> RuntimeStatusDisplay:
        if diagnostics is None:
            voice_label = "마이크 상태 확인 중"
        elif diagnostics.wake_detected:
            voice_label = "호출어 인식됨 · 명령을 듣는 중"
        elif diagnostics.last_transcript is not None:
            heard = diagnostics.last_transcript[:32]
            if diagnostics.recognition_reason == "WAKE_WORD_NOT_FOUND":
                voice_label = "주변 음성 무시 · '스킬라'를 기다리는 중"
            elif diagnostics.recognition_reason == "COMMAND_RECOGNIZED":
                voice_label = f"명령 인식: {heard}"
            else:
                voice_label = f"들은 말: {heard}"
        elif diagnostics.recognition_reason == "TRANSCRIBING":
            voice_label = "음성을 문장으로 변환하는 중"
        elif diagnostics.recognition_reason == "REVIEW_WAITING":
            voice_label = "승인 음성 대기 중 · 예 또는 아니요"
        elif diagnostics.speech_frame_count > 0:
            voice_label = "마이크 입력 감지됨 · 호출어 확인 중"
        elif diagnostics.frame_count > 0:
            voice_label = f"마이크 수신 중 · 입력 프레임 {diagnostics.frame_count}"
        else:
            voice_label = "마이크 시작 중 · 입력 신호를 기다리고 있습니다"
        detail_label = _REASON_LABELS.get(
            snapshot.last_reason,
            "작업 상태가 변경되었습니다.",
        )
        if snapshot.last_event_type is RuntimeEventType.TASK_COMPLETED:
            detail_label = "작업을 완료하고 결과를 확인했습니다."
        if snapshot.skill_trace_recorded is True and (
            snapshot.last_event_type is RuntimeEventType.TASK_COMPLETED
        ):
            detail_label = "작업 완료 · 저장된 기록으로 스킬 후보를 만들 수 있습니다."
        return RuntimeStatusDisplay(
            state=snapshot.state,
            state_label=_STATE_LABELS[snapshot.state],
            detail_label=detail_label,
            completed_actions=snapshot.completed_actions,
            sequence=snapshot.sequence,
            stop_enabled=snapshot.state is not AlwaysOnState.CLOSED,
            voice_label=voice_label,
            input_level=0.0 if diagnostics is None else diagnostics.input_level,
            audio_frame_count=0 if diagnostics is None else diagnostics.frame_count,
            skill_review=snapshot.skill_review,
        )


class TkStatusView:
    """Cyber HUD for the SKILLA local skill agent."""

    def __init__(
        self,
        *,
        title: str = "SKILLA // CONTROL INTERFACE",
        open_text_command: Callable[[], None] | None = None,
        open_verified_result: Callable[[], None] | None = None,
        review_skills: Callable[[], None] | None = None,
        review_skill_traces: Callable[[], None] | None = None,
        respond_skill_review: Callable[[UUID, bool], bool] | None = None,
    ) -> None:
        try:
            import tkinter as tk
        except ImportError as error:
            raise RuntimeError("tkinter status HUD is unavailable") from error
        try:
            root = tk.Tk()
        except tk.TclError as error:
            raise RuntimeError("tkinter status HUD could not start") from error
        root.title(title)
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.geometry("800x570")
        root.configure(bg="#030711")

        self._colors = {
            "bg": "#030711",
            "panel": "#071421",
            "panel_alt": "#091b2b",
            "line": "#123c52",
            "cyan": "#43e6ff",
            "cyan_dim": "#1689a8",
            "text": "#d9f7ff",
            "muted": "#7fa6b5",
            "warning": "#ffb84d",
            "danger": "#ff526c",
            "success": "#5effc5",
        }
        colors = self._colors

        shell = tk.Frame(
            root,
            bg=colors["bg"],
            highlightbackground=colors["cyan_dim"],
            highlightthickness=1,
            padx=24,
            pady=18,
        )
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        header = tk.Frame(shell, bg=colors["bg"])
        header.pack(fill="x")
        tk.Label(
            header,
            text="S . K . I . L . L . A",
            bg=colors["bg"],
            fg=colors["cyan"],
            font=("Consolas", 22, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text="SKILL LOCAL AI AGENT",
            bg=colors["bg"],
            fg=colors["muted"],
            font=("Consolas", 8),
        ).pack(side="left", padx=(16, 0), pady=(10, 0))
        self._system_code = tk.Label(
            header,
            text="SYSTEM // BOOT",
            bg=colors["bg"],
            fg=colors["cyan_dim"],
            font=("Consolas", 9, "bold"),
        )
        self._system_code.pack(side="right", pady=(8, 0))

        tk.Frame(shell, height=1, bg=colors["cyan_dim"]).pack(fill="x", pady=(12, 16))

        content = tk.Frame(shell, bg=colors["bg"])
        content.pack(fill="x")

        core_panel = tk.Frame(
            content,
            width=225,
            height=260,
            bg=colors["panel"],
            highlightbackground=colors["line"],
            highlightthickness=1,
        )
        core_panel.pack(side="left", fill="y")
        core_panel.pack_propagate(False)
        tk.Label(
            core_panel,
            text="REACTOR STATUS",
            bg=colors["panel"],
            fg=colors["muted"],
            font=("Consolas", 9, "bold"),
        ).pack(pady=(16, 2))
        self._core = tk.Canvas(
            core_panel,
            width=190,
            height=190,
            bg=colors["panel"],
            highlightthickness=0,
        )
        self._core.pack()
        self._core_ring_ids = self._draw_core()
        self._core_level_id = self._core.create_text(
            95,
            178,
            text="MIC 00%",
            fill=colors["cyan_dim"],
            font=("Consolas", 8, "bold"),
        )
        self._core_caption = tk.StringVar(value="VOICE LINK // STANDBY")
        tk.Label(
            core_panel,
            textvariable=self._core_caption,
            bg=colors["panel"],
            fg=colors["cyan_dim"],
            font=("Consolas", 8, "bold"),
        ).pack()

        data_panel = tk.Frame(
            content,
            bg=colors["panel_alt"],
            highlightbackground=colors["line"],
            highlightthickness=1,
            padx=22,
            pady=16,
        )
        data_panel.pack(side="left", fill="both", expand=True, padx=(14, 0))

        self._state = tk.StringVar(value="준비 중")
        self._detail = tk.StringVar(value="상태를 불러오고 있습니다.")
        self._actions = tk.StringVar(value="완료 동작: 0")
        self._voice = tk.StringVar(value="마이크 상태 확인 중")
        tk.Label(
            data_panel,
            text="CURRENT OPERATION",
            bg=colors["panel_alt"],
            fg=colors["muted"],
            font=("Consolas", 9, "bold"),
            anchor="w",
        ).pack(fill="x")
        self._state_label = tk.Label(
            data_panel,
            textvariable=self._state,
            bg=colors["panel_alt"],
            fg=colors["cyan"],
            font=("맑은 고딕", 24, "bold"),
            anchor="w",
        )
        self._state_label.pack(fill="x", pady=(2, 8))
        tk.Label(
            data_panel,
            textvariable=self._detail,
            bg=colors["panel_alt"],
            fg=colors["text"],
            font=("맑은 고딕", 10),
            anchor="w",
            justify="left",
            wraplength=440,
        ).pack(fill="x")

        phase_row = tk.Frame(data_panel, bg=colors["panel_alt"])
        phase_row.pack(fill="x", pady=(12, 0))
        self._phase_labels: list[Any] = []
        for phase in ("요청 분석", "스킬 검색", "안전 실행", "결과 검증"):
            phase_label = tk.Label(
                phase_row,
                text=phase,
                bg=colors["panel"],
                fg=colors["muted"],
                font=("맑은 고딕", 8, "bold"),
                padx=7,
                pady=4,
                highlightbackground=colors["line"],
                highlightthickness=1,
            )
            phase_label.pack(side="left", fill="x", expand=True, padx=(0, 5))
            self._phase_labels.append(phase_label)

        tk.Frame(data_panel, height=1, bg=colors["line"]).pack(fill="x", pady=14)
        voice_header = tk.Frame(data_panel, bg=colors["panel_alt"])
        voice_header.pack(fill="x")
        self._voice_indicator = tk.Label(
            voice_header,
            text="●",
            bg=colors["panel_alt"],
            fg=colors["cyan_dim"],
            font=("Segoe UI Symbol", 10, "bold"),
        )
        self._voice_indicator.pack(side="left")
        tk.Label(
            voice_header,
            text="VOICE INTERFACE",
            bg=colors["panel_alt"],
            fg=colors["muted"],
            font=("Consolas", 9, "bold"),
        ).pack(side="left", padx=(7, 0))
        tk.Label(
            data_panel,
            textvariable=self._voice,
            bg=colors["panel_alt"],
            fg=colors["cyan"],
            font=("맑은 고딕", 10, "bold"),
            anchor="w",
            justify="left",
            wraplength=440,
        ).pack(fill="x", pady=(5, 0))

        metric = tk.Frame(data_panel, bg=colors["panel_alt"])
        metric.pack(fill="x", pady=(16, 0))
        tk.Label(
            metric,
            text="VERIFIED ACTIONS",
            bg=colors["panel_alt"],
            fg=colors["muted"],
            font=("Consolas", 8, "bold"),
        ).pack(side="left")
        tk.Label(
            metric,
            textvariable=self._actions,
            bg=colors["panel_alt"],
            fg=colors["success"],
            font=("맑은 고딕", 10, "bold"),
        ).pack(side="right")

        controls = tk.Frame(shell, bg=colors["bg"])
        controls.pack(fill="x", pady=(16, 0))
        primary = tk.Frame(controls, bg=colors["bg"])
        primary.pack(side="left")
        self._stop_button = self._button(primary, "■  현재 작업 중지", colors["danger"], width=16)
        self._stop_button.pack(side="left")
        self._hide_button = self._button(primary, "—  최소화", colors["cyan_dim"], width=11)
        self._hide_button.pack(side="left", padx=(8, 0))
        self._exit_button = self._button(primary, "×  종료", colors["muted"], width=9)
        self._exit_button.pack(side="left", padx=(8, 0))

        tools = tk.Frame(controls, bg=colors["bg"])
        tools.pack(side="right")
        for label, callback in (
            ("⌨  명령", open_text_command),
            ("✓  결과", open_verified_result),
            ("◇  후보 검토", review_skill_traces),
            ("⚙  스킬", review_skills),
        ):
            if callback is not None:
                button = self._button(tools, label, colors["cyan_dim"], width=10)
                button.configure(command=callback)
                button.pack(side="left", padx=(8, 0))

        self._review_response = respond_skill_review
        self._review_id: UUID | None = None
        self._review_panel = tk.Frame(shell, bg=colors["panel_alt"], padx=12, pady=10)
        self._review_heading = tk.StringVar()
        tk.Label(
            self._review_panel, textvariable=self._review_heading,
            bg=colors["panel_alt"], fg=colors["warning"], font=("맑은 고딕", 13, "bold"),
        ).pack(anchor="w")
        from tkinter.scrolledtext import ScrolledText

        self._review_text = ScrolledText(
            self._review_panel, height=10, wrap="word", bg=colors["panel"], fg=colors["text"],
            font=("맑은 고딕", 10), relief="flat", padx=10, pady=8,
        )
        self._review_text.pack(fill="x", pady=6)
        actions = tk.Frame(self._review_panel, bg=colors["panel_alt"])
        actions.pack(fill="x")
        self._review_yes = self._button(actions, "예 · 등록 후 실행", colors["success"], width=22)
        self._review_yes.configure(command=lambda: self._answer_review(True))
        self._review_yes.pack(side="left")
        self._review_no = self._button(actions, "아니요 · 취소", colors["danger"], width=16)
        self._review_no.configure(command=lambda: self._answer_review(False))
        self._review_no.pack(side="left", padx=12)

        footer = tk.Frame(shell, bg=colors["bg"])
        footer.pack(fill="x", side="bottom", pady=(16, 0))
        tk.Label(
            footer,
            text="LOCAL CORE  •  SKILL MEMORY  •  VERIFIED EXECUTION",
            bg=colors["bg"],
            fg="#315a69",
            font=("Consolas", 8),
        ).pack(side="left")
        tk.Label(
            footer,
            text="ONLINE",
            bg=colors["bg"],
            fg=colors["success"],
            font=("Consolas", 8, "bold"),
        ).pack(side="right")

        self._root = root
        self._pulse_step = 0
        self._animate_core()

    def _button(self, parent: Any, text: str, color: str, *, width: int) -> Any:
        import tkinter as tk

        return tk.Button(
            parent,
            text=text,
            width=width,
            bg=self._colors["panel"],
            fg=color,
            activebackground=self._colors["panel_alt"],
            activeforeground=self._colors["text"],
            disabledforeground="#405866",
            relief="flat",
            bd=0,
            highlightbackground=color,
            highlightcolor=color,
            highlightthickness=1,
            font=("맑은 고딕", 9, "bold"),
            padx=8,
            pady=7,
            cursor="hand2",
        )

    def _draw_core(self) -> tuple[int, ...]:
        colors = self._colors
        canvas = self._core
        for start, extent in ((20, 105), (165, 80), (280, 55)):
            canvas.create_arc(
                18,
                18,
                172,
                172,
                start=start,
                extent=extent,
                style="arc",
                width=2,
                outline=colors["cyan_dim"],
            )
        canvas.create_oval(35, 35, 155, 155, outline=colors["line"], width=1)
        outer = canvas.create_oval(48, 48, 142, 142, outline=colors["cyan_dim"], width=2)
        middle = canvas.create_oval(61, 61, 129, 129, outline=colors["cyan"], width=2)
        inner = canvas.create_oval(
            73,
            73,
            117,
            117,
            fill="#0b3a4d",
            outline=colors["cyan"],
            width=2,
        )
        canvas.create_text(
            95,
            95,
            text="S",
            fill=colors["text"],
            font=("Consolas", 20, "bold"),
        )
        for angle in range(0, 360, 45):
            import math

            radians = math.radians(angle)
            x1 = 95 + 61 * math.cos(radians)
            y1 = 95 + 61 * math.sin(radians)
            x2 = 95 + 70 * math.cos(radians)
            y2 = 95 + 70 * math.sin(radians)
            canvas.create_line(x1, y1, x2, y2, fill=colors["cyan_dim"], width=2)
        return outer, middle, inner

    def _animate_core(self) -> None:
        self._pulse_step = (self._pulse_step + 1) % 16
        bright = self._pulse_step < 8
        color = self._colors["cyan"] if bright else self._colors["cyan_dim"]
        level = getattr(self, "_audio_level", 0.0)
        self._audio_level = level * 0.88
        width, radius = reactor_pulse_geometry(level)
        self._core.coords(
            self._core_ring_ids[0], 95 - radius, 95 - radius, 95 + radius, 95 + radius
        )
        self._core.itemconfigure(self._core_ring_ids[0], outline=color, width=width)
        self._core.itemconfigure(
            self._core_ring_ids[1],
            outline=self._colors["cyan"] if level >= 0.2 else self._colors["cyan_dim"],
            width=max(2, width - 2),
        )
        self._core.itemconfigure(
            self._core_ring_ids[2],
            outline=self._colors["success"] if level >= 0.5 else self._colors["cyan"],
            width=max(2, width - 3),
        )
        self._core.itemconfigure(
            self._core_level_id,
            text=reactor_level_label(level),
            fill=color,
        )
        self._root.after(70, self._animate_core)

    def bind_handlers(
        self,
        *,
        on_stop: Callable[[], None],
        on_hide: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._stop_button.configure(command=on_stop)
        self._hide_button.configure(command=on_hide)
        self._exit_button.configure(command=on_exit)
        self._root.protocol("WM_DELETE_WINDOW", on_hide)

    def render(self, display: RuntimeStatusDisplay) -> None:
        self._render_review(display.skill_review)
        if display.audio_frame_count != getattr(self, "_audio_frame_count", -1):
            self._audio_level = display.input_level
            self._audio_frame_count = display.audio_frame_count
        state_colors = {
            AlwaysOnState.IDLE: self._colors["cyan"],
            AlwaysOnState.PLANNING: self._colors["warning"],
            AlwaysOnState.REVIEWING: self._colors["warning"],
            AlwaysOnState.EXECUTING: self._colors["success"],
            AlwaysOnState.CLOSED: self._colors["danger"],
        }
        state_codes = {
            AlwaysOnState.IDLE: "SYSTEM // STANDBY",
            AlwaysOnState.PLANNING: "SYSTEM // ANALYZING",
            AlwaysOnState.REVIEWING: "SYSTEM // REVIEW",
            AlwaysOnState.EXECUTING: "SYSTEM // EXECUTING",
            AlwaysOnState.CLOSED: "SYSTEM // OFFLINE",
        }
        color = state_colors[display.state]
        self._state.set(f"●  {display.state_label}")
        self._detail.set(display.detail_label)
        self._voice.set(display.voice_label)
        self._actions.set(f"{display.completed_actions:02d}")
        self._state_label.configure(fg=color)
        self._voice_indicator.configure(fg=color)
        self._system_code.configure(text=state_codes[display.state], fg=color)
        self._core_caption.set(
            "VOICE LINK // ACTIVE"
            if display.state in {
                AlwaysOnState.PLANNING, AlwaysOnState.REVIEWING, AlwaysOnState.EXECUTING,
            }
            else "VOICE LINK // STANDBY"
        )
        if display.state in {AlwaysOnState.PLANNING, AlwaysOnState.REVIEWING}:
            active_phases = 2
        elif display.state is AlwaysOnState.EXECUTING:
            active_phases = 3
        elif display.state is AlwaysOnState.IDLE and display.completed_actions > 0:
            active_phases = 4
        else:
            active_phases = 0
        for index, phase_label in enumerate(self._phase_labels):
            phase_color = color if index < active_phases else self._colors["muted"]
            phase_label.configure(
                fg=phase_color,
                highlightbackground=(
                    phase_color if index < active_phases else self._colors["line"]
                ),
            )
        for ring_id in self._core_ring_ids[1:]:
            self._core.itemconfigure(ring_id, outline=color)
        self._stop_button.configure(state="normal" if display.stop_enabled else "disabled")

    def _answer_review(self, accepted: bool) -> None:
        if (
            self._review_id is not None and self._review_response is not None
            and self._review_response(self._review_id, accepted)
        ):
            self._review_yes.configure(state="disabled")
            self._review_no.configure(state="disabled")

    def _render_review(self, review: PendingSkillReview | None) -> None:
        review_id = None if review is None else review.review_id
        if review_id == self._review_id:
            return
        self._review_id = review_id
        if review is None:
            self._review_panel.pack_forget()
            self._root.geometry("800x570")
            return
        registering = review.kind is SkillReviewKind.REGISTER
        question = "새 스킬로 등록하고 실행할까요?" if registering else "이 스킬로 실행할까요?"
        self._review_heading.set(f"{review.title} · {question}")
        lines = [f"이번 요청: {review.request}", "", "이번 실행 계획"]
        lines.extend(f"{i}. {step}" for i, step in enumerate(review.planned_steps, 1))
        for heading, items in (
            ("저장·재사용할 절차", review.procedure),
            ("매번 새로 확인할 입력", review.dynamic_inputs),
            ("결과 확인 방법", review.verification_rules),
            ("사전 안전 확인", review.safety_summary),
        ):
            lines.extend(["", heading, *(items or ("없음",))])
        lines.extend(["", "등록 동의는 PC 작업의 실행 승인을 대신하지 않습니다."])
        if registering:
            lines.append("첫 실행 전 후보입니다. 실행 성공 여부는 작업 후 별도로 확인합니다.")
        self._review_text.configure(state="normal")
        self._review_text.delete("1.0", "end")
        self._review_text.insert("1.0", "\n".join(lines))
        self._review_text.configure(state="disabled")
        enabled = "normal" if self._review_response is not None else "disabled"
        self._review_yes.configure(
            text="예 · 등록 후 실행" if registering else "예 · 실행", state=enabled,
        )
        self._review_no.configure(state=enabled)
        self._review_panel.pack(fill="x", pady=(12, 0))
        self._root.geometry("900x840")
        self._root.deiconify()

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> None:
        self._root.after(delay_ms, callback)

    def close(self) -> None:
        self._root.destroy()

    def minimize(self) -> None:
        self._root.iconify()

    def run(self) -> None:
        self._root.mainloop()


def run_tk_status_hud(
    *,
    status_provider: Callable[[], RuntimeStatusSnapshot],
    request_task_stop: Callable[[], object],
    request_capture_stop: Callable[[], bool],
    request_runtime_stop: Callable[[], object],
    poll_interval_ms: int = 250,
    voice_diagnostics_provider: Callable[[], VoicePipelineDiagnostics] | None = None,
    open_text_command: Callable[[], None] | None = None,
    open_verified_result: Callable[[], None] | None = None,
    review_skills: Callable[[], None] | None = None,
    review_skill_traces: Callable[[], None] | None = None,
    respond_skill_review: Callable[[UUID, bool], bool] | None = None,
) -> None:
    RuntimeStatusPresenter(
        status_provider=status_provider,
        request_task_stop=request_task_stop,
        request_capture_stop=request_capture_stop,
        request_runtime_stop=request_runtime_stop,
        view=TkStatusView(
            open_text_command=open_text_command,
            open_verified_result=open_verified_result,
            review_skills=review_skills,
            review_skill_traces=review_skill_traces,
            respond_skill_review=respond_skill_review,
        ),
        poll_interval_ms=poll_interval_ms,
        voice_diagnostics_provider=voice_diagnostics_provider,
    ).run()
