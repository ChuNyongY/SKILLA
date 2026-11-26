from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID

from pydantic import Field

from .always_on_runtime import AlwaysOnState, RuntimeEventType, RuntimeStatusSnapshot
from .models import FrozenModel
from .skill_schedules import ScheduledSkillSuggestion
from .skill_session import PendingSkillReview, SkillReviewKind
from .skill_triggers import SkillTriggerSuggestion
from .voice import VoicePipelineDiagnostics


class RuntimeStatusDisplay(FrozenModel):
    state: AlwaysOnState
    state_label: str = Field(min_length=1, max_length=32)
    detail_label: str = Field(min_length=1, max_length=80)
    completed_actions: int = Field(ge=0)
    sequence: int = Field(ge=0)
    stop_enabled: bool
    voice_label: str = Field(default="마이크 상태 확인 중", min_length=1, max_length=80)
    heard_text: str = Field(default="", max_length=200)
    voice_title: str = ""
    result_summary: str = Field(default="", max_length=480)
    input_level: float = Field(default=0.0, ge=0.0, le=1.0)
    audio_frame_count: int = Field(default=0, ge=0)
    skill_review: PendingSkillReview | None = None
    trigger_suggestion: SkillTriggerSuggestion | None = None
    schedule_suggestion: ScheduledSkillSuggestion | None = None


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


def smooth_reactor_level(current: float, target: float) -> float:
    """Apply a quick attack and gentle release to the visible microphone meter."""
    current_level = max(0.0, min(1.0, float(current)))
    target_level = max(0.0, min(1.0, float(target)))
    factor = 0.58 if target_level > current_level else 0.20
    smoothed = current_level + (target_level - current_level) * factor
    return 0.0 if smoothed < 0.005 else smoothed


def reactor_activity_label(input_level: float) -> str:
    level = max(0.0, min(1.0, float(input_level)))
    if level >= 0.20:
        return "VOICE LINK // SPEAKING"
    if level >= 0.02:
        return "VOICE LINK // RECEIVING"
    return "VOICE LINK // STANDBY"


def wakeword_mode_label(mode: str) -> str:
    labels = {
        "whisper_korean": "로컬 Whisper 한국어 인식",
        "openwakeword": "openWakeWord",
    }
    try:
        selected = labels[mode]
    except KeyError as error:
        raise ValueError("unsupported wakeword mode") from error
    return f"호출어 감지: {selected}"


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
        trigger_suggestion_provider: Callable[[], SkillTriggerSuggestion | None] | None = None,
        schedule_suggestion_provider: Callable[[], ScheduledSkillSuggestion | None]
        | None = None,
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
        self._trigger_suggestion_provider = trigger_suggestion_provider
        self._schedule_suggestion_provider = schedule_suggestion_provider
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
            trigger_suggestion = (
                None
                if self._trigger_suggestion_provider is None
                else self._trigger_suggestion_provider()
            )
            schedule_suggestion = (
                None
                if self._schedule_suggestion_provider is None
                else self._schedule_suggestion_provider()
            )
            display = self._display(
                snapshot, diagnostics, trigger_suggestion, schedule_suggestion
            )
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
        trigger_suggestion: SkillTriggerSuggestion | None = None,
        schedule_suggestion: ScheduledSkillSuggestion | None = None,
    ) -> RuntimeStatusDisplay:
        if diagnostics is None:
            voice_label = "마이크 상태 확인 중"
        elif diagnostics.recognition_reason == "TRANSCRIBING":
            voice_label = "음성을 문장으로 변환하는 중"
        elif diagnostics.recognition_reason in {"STT_FAILED", "EMPTY_TRANSCRIPT"}:
            voice_label = "음성을 인식하지 못했습니다 · '스킬라'부터 다시 말해 주세요"
        elif diagnostics.recognition_reason == "LISTENING":
            voice_label = "듣는 중 · 말을 마치면 자동으로 인식합니다"
        elif diagnostics.wake_detected:
            voice_label = "호출어 인식됨 · 명령을 듣는 중"
        elif diagnostics.recognition_reason == "WAKE_WORD_NOT_FOUND":
            voice_label = "주변 음성 무시 · '스킬라'를 기다리는 중"
        elif diagnostics.recognition_reason == "COMMAND_RECOGNIZED":
            voice_label = "음성 명령을 인식했습니다"
        elif diagnostics.recognition_reason == "LOCAL_STOP_RECOGNIZED":
            voice_label = "음성 중지 명령을 인식했습니다"
        elif diagnostics.recognition_reason == "REVIEW_RESPONSE_RECOGNIZED":
            voice_label = "음성 검토 응답을 인식했습니다"
        elif diagnostics.recognition_reason == "REVIEW_WAITING":
            voice_label = "승인 음성 대기 중 · 예 또는 아니요"
        elif diagnostics.speech_active:
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
            voice_title=(
                "음성 인식 중" if diagnostics.recognition_reason == "TRANSCRIBING"
                else "듣는 중" if diagnostics.input_sequence else "마이크 준비 중"
            ) if diagnostics is not None else "",
            heard_text=(
                diagnostics.last_transcript or ""
                if diagnostics is not None and diagnostics.recognition_reason in {
                    "COMMAND_RECOGNIZED", "LOCAL_STOP_RECOGNIZED", "REVIEW_RESPONSE_RECOGNIZED",
                } else ""
            ),
            result_summary=(
                "\n".join((snapshot.result.title, *snapshot.result.lines[:3]))[:480]
                if snapshot.result is not None else ""
            ),
            input_level=0.0 if diagnostics is None else diagnostics.input_level,
            audio_frame_count=0 if diagnostics is None else diagnostics.input_sequence,
            skill_review=snapshot.skill_review,
            trigger_suggestion=trigger_suggestion,
            schedule_suggestion=schedule_suggestion,
        )


class TkStatusView:
    """Cyber HUD for the SKILLA local skill agent."""

    _MAIN_SIZE = "760x600"

    def __init__(
        self,
        *,
        title: str = "SKILLA · 음성 작업 도우미",
        open_display_selector: Callable[[], None] | None = None,
        open_verified_result: Callable[[], None] | None = None,
        review_skills: Callable[[], None] | None = None,
        review_skill_traces: Callable[[], None] | None = None,
        manage_skill_triggers: Callable[[], None] | None = None,
        manage_skill_schedules: Callable[[], None] | None = None,
        respond_skill_review: Callable[[UUID, bool], bool] | None = None,
        accept_trigger_suggestion: Callable[[UUID], bool] | None = None,
        dismiss_trigger_suggestion: Callable[[UUID], bool] | None = None,
        accept_schedule_suggestion: Callable[[UUID], bool] | None = None,
        dismiss_schedule_suggestion: Callable[[UUID], bool] | None = None,
        enable_voice: Callable[[], bool] | None = None,
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
        root.minsize(720, 560)
        root.geometry(self._MAIN_SIZE)
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
            text="SKILLA",
            bg=colors["bg"],
            fg=colors["cyan"],
            font=("Consolas", 22, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text="음성 전용 Windows 도우미",
            bg=colors["bg"],
            fg=colors["muted"],
            font=("맑은 고딕", 11),
            wraplength=240,
            anchor="w",
            justify="left",
        ).pack(side="left", padx=(16, 0), pady=(2, 0))

        from .control_theme import action_menu, button

        menu_items = (
            ("저장된 스킬", review_skills),
            ("개정 후보", review_skill_traces),
            ("상황 스킬", manage_skill_triggers),
            ("예약 스킬", manage_skill_schedules),
        )
        if any(action is not None for _, action in menu_items):
            action_menu(header, "스킬", menu_items).pack(side="right")
        if open_display_selector is not None:
            action_menu(header, "설정", (("작업 화면 선택", open_display_selector),)).pack(
                side="right", padx=(0, 8),
            )
        tk.Frame(shell, height=1, bg=colors["cyan_dim"]).pack(fill="x", pady=(12, 14))

        self._state = tk.StringVar(value="준비 중")
        self._detail = tk.StringVar(value="상태를 불러오고 있습니다.")
        self._voice = tk.StringVar(value="마이크 상태 확인 중")
        self._heard = tk.StringVar(value="인식된 명령이 여기에 표시됩니다.")
        self._result = tk.StringVar(value="명령을 실행하면 여기에 결과가 표시됩니다.")

        controls = tk.Frame(shell, bg=colors["bg"])
        controls.pack(side="bottom", fill="x", pady=(12, 0))
        self._stop_button = self._button(controls, "작업 중지", colors["danger"], width=13)
        self._stop_button.pack(side="left")
        self._exit_button = self._button(controls, "종료", colors["muted"], width=8)
        self._exit_button.pack(side="right")
        if open_verified_result is not None:
            button(controls, "결과 자세히", open_verified_result).pack(side="left", padx=(8, 0))
        activity = tk.Frame(shell, bg=colors["bg"], padx=16, pady=6)
        activity.pack(fill="x", pady=(0, 10))
        self._mic_meter = tk.Canvas(
            activity, width=88, height=88, bg=colors["bg"], highlightthickness=0,
        )
        self._mic_meter.pack(pady=(0, 5))
        self._mic_meter.create_oval(5, 5, 83, 83, outline=colors["line"], width=1)
        self._mic_ring = self._mic_meter.create_oval(
            16, 16, 72, 72, outline=colors["cyan_dim"], width=2,
        )
        for start in (28, 208):
            self._mic_meter.create_arc(
                8, 8, 80, 80, start=start, extent=58, style="arc",
                outline=colors["cyan_dim"], width=2,
            )
        self._mic_meter.create_oval(
            33, 33, 55, 55, outline=colors["cyan"], fill=colors["panel_alt"], width=2,
        )
        self._mic_meter.create_oval(41, 41, 47, 47, fill=colors["cyan"], width=0)
        self._state_label = tk.Label(
            activity, textvariable=self._state, bg=colors["bg"],
            fg=colors["cyan"], font=("맑은 고딕", 22, "bold"),
        )
        self._state_label.pack()
        tk.Label(
            activity, textvariable=self._detail, bg=colors["bg"],
            fg=colors["muted"], font=("맑은 고딕", 10), wraplength=600,
        ).pack(pady=(2, 3))
        tk.Label(
            activity, textvariable=self._voice, bg=colors["bg"],
            fg=colors["muted"], font=("맑은 고딕", 10), wraplength=600,
        ).pack()
        self._microphone_button = None
        self._voice_not_started = enable_voice is not None
        if enable_voice is not None:
            def start_microphone() -> None:
                assert self._microphone_button is not None
                self._microphone_button.configure(state="disabled")
                try:
                    started = enable_voice()
                except Exception:
                    started = False
                if started:
                    self._voice_not_started = False
                    self._microphone_button.pack_forget()
                else:
                    self._microphone_button.configure(text="마이크 시작 실패")

            self._microphone_button = button(activity, "마이크 켜기", start_microphone)
            self._microphone_button.pack(pady=(6, 0))

        transcript_card = tk.Frame(shell, bg=colors["panel"], padx=16, pady=10)
        transcript_card.pack(fill="x", pady=(0, 10))
        tk.Label(
            transcript_card, text="인식한 말", bg=colors["panel"],
            fg=colors["muted"], font=("맑은 고딕", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            transcript_card, textvariable=self._heard, bg=colors["panel"], fg=colors["text"],
            font=("맑은 고딕", 12), justify="left", wraplength=640,
        ).pack(anchor="w", pady=(4, 0))

        result_card = tk.Frame(shell, bg=colors["panel"], padx=16, pady=12)
        result_card.pack(fill="x")
        tk.Label(
            result_card, text="최근 결과", bg=colors["panel"],
            fg=colors["muted"], font=("맑은 고딕", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            result_card, textvariable=self._result, bg=colors["panel"], fg=colors["text"],
            font=("맑은 고딕", 11), justify="left", wraplength=640,
        ).pack(anchor="w", pady=(4, 0))

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
            self._review_panel, height=6, wrap="word", bg=colors["panel"], fg=colors["text"],
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

        self._trigger_accept = accept_trigger_suggestion
        self._trigger_dismiss = dismiss_trigger_suggestion
        self._trigger_id: UUID | None = None
        self._trigger_panel = tk.Frame(shell, bg=colors["panel_alt"], padx=12, pady=10)
        self._trigger_heading = tk.StringVar()
        tk.Label(
            self._trigger_panel,
            textvariable=self._trigger_heading,
            bg=colors["panel_alt"],
            fg=colors["warning"],
            font=("맑은 고딕", 12, "bold"),
        ).pack(side="left")
        self._trigger_yes = self._button(
            self._trigger_panel, "이 스킬 실행", colors["success"], width=13
        )
        self._trigger_yes.configure(command=self._accept_trigger)
        self._trigger_yes.pack(side="right")
        self._trigger_no = self._button(
            self._trigger_panel, "닫기", colors["danger"], width=8
        )
        self._trigger_no.configure(command=self._dismiss_trigger)
        self._trigger_no.pack(side="right", padx=8)

        self._schedule_accept = accept_schedule_suggestion
        self._schedule_dismiss = dismiss_schedule_suggestion
        self._schedule_id: UUID | None = None
        self._schedule_panel = tk.Frame(shell, bg=colors["panel_alt"], padx=12, pady=10)
        self._schedule_heading = tk.StringVar()
        tk.Label(
            self._schedule_panel,
            textvariable=self._schedule_heading,
            bg=colors["panel_alt"],
            fg=colors["warning"],
            font=("맑은 고딕", 12, "bold"),
        ).pack(side="left")
        self._schedule_yes = self._button(
            self._schedule_panel, "예약 스킬 실행", colors["success"], width=15
        )
        self._schedule_yes.configure(command=self._accept_schedule)
        self._schedule_yes.pack(side="right")
        self._schedule_no = self._button(
            self._schedule_panel, "닫기", colors["danger"], width=8
        )
        self._schedule_no.configure(command=self._dismiss_schedule)
        self._schedule_no.pack(side="right", padx=8)


        self._root = root
        self._audio_level = 0.0
        self._audio_level_target = 0.0
        self._audio_frame_count = -1
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

    def _animate_core(self) -> None:
        self._audio_level = smooth_reactor_level(self._audio_level, self._audio_level_target)
        radius = 25 + 11 * self._audio_level
        self._mic_meter.coords(self._mic_ring, 44 - radius, 44 - radius, 44 + radius, 44 + radius)
        self._mic_meter.itemconfigure(
            self._mic_ring,
            outline=self._colors["cyan"] if self._audio_level > 0.04 else self._colors["cyan_dim"],
            width=2 + round(2 * self._audio_level),
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
        self._exit_button.configure(command=on_exit)
        self._root.protocol("WM_DELETE_WINDOW", on_exit)

    def render(self, display: RuntimeStatusDisplay) -> None:
        self._render_review(display.skill_review)
        self._render_trigger_suggestion(display.trigger_suggestion)
        self._render_schedule_suggestion(display.schedule_suggestion)
        if display.audio_frame_count != self._audio_frame_count:
            self._audio_level_target = display.input_level
            self._audio_frame_count = display.audio_frame_count
        else:
            # A stalled or intentionally paused capture must not leave a frozen level.
            self._audio_level_target = 0.0
        state_colors = {
            AlwaysOnState.IDLE: self._colors["cyan"],
            AlwaysOnState.PLANNING: self._colors["warning"],
            AlwaysOnState.REVIEWING: self._colors["warning"],
            AlwaysOnState.EXECUTING: self._colors["success"],
            AlwaysOnState.CLOSED: self._colors["danger"],
        }
        color = state_colors[display.state]
        idle = display.state is AlwaysOnState.IDLE
        self._state.set(
            (
                "마이크 꺼짐" if self._voice_not_started
                else display.voice_title or display.state_label
            )
            if idle else display.state_label
        )
        self._detail.set(
            "음성 명령을 쓰려면 마이크를 켜세요."
            if self._voice_not_started and display.sequence == 0
            else "“스킬라, 시스템 정보 확인해 줘”라고 말해 보세요."
            if idle and display.sequence == 0 else display.detail_label
        )
        self._voice.set(
            "" if self._voice_not_started
            else "마이크 연결됨" if display.voice_label.startswith("마이크 수신 중")
            else display.voice_label
        )
        if display.heard_text:
            self._heard.set(display.heard_text)
        self._result.set(display.result_summary or "명령을 실행하면 여기에 결과가 표시됩니다.")
        self._state_label.configure(fg=color)
        stop_enabled = display.stop_enabled and display.state is not AlwaysOnState.IDLE
        self._stop_button.configure(state="normal" if stop_enabled else "disabled")

    def _accept_trigger(self) -> None:
        if (
            self._trigger_id is not None
            and self._trigger_accept is not None
            and self._trigger_accept(self._trigger_id)
        ):
            self._trigger_yes.configure(state="disabled")
            self._trigger_no.configure(state="disabled")

    def _dismiss_trigger(self) -> None:
        if (
            self._trigger_id is not None
            and self._trigger_dismiss is not None
            and self._trigger_dismiss(self._trigger_id)
        ):
            self._trigger_yes.configure(state="disabled")
            self._trigger_no.configure(state="disabled")

    def _render_trigger_suggestion(
        self, suggestion: SkillTriggerSuggestion | None
    ) -> None:
        suggestion_id = None if suggestion is None else suggestion.suggestion_id
        if suggestion_id == self._trigger_id:
            return
        self._trigger_id = suggestion_id
        if suggestion is None:
            self._trigger_panel.pack_forget()
            return
        self._trigger_heading.set(
            f"{suggestion.title} · {suggestion.app_id} 실행을 감지했습니다"
        )
        enabled = (
            "normal"
            if self._trigger_accept is not None and self._trigger_dismiss is not None
            else "disabled"
        )
        self._trigger_yes.configure(state=enabled)
        self._trigger_no.configure(state=enabled)
        self._trigger_panel.pack(fill="x", pady=(12, 0))

    def _accept_schedule(self) -> None:
        if (
            self._schedule_id is not None
            and self._schedule_accept is not None
            and self._schedule_accept(self._schedule_id)
        ):
            self._schedule_yes.configure(state="disabled")
            self._schedule_no.configure(state="disabled")

    def _dismiss_schedule(self) -> None:
        if (
            self._schedule_id is not None
            and self._schedule_dismiss is not None
            and self._schedule_dismiss(self._schedule_id)
        ):
            self._schedule_yes.configure(state="disabled")
            self._schedule_no.configure(state="disabled")

    def _render_schedule_suggestion(
        self, suggestion: ScheduledSkillSuggestion | None
    ) -> None:
        suggestion_id = None if suggestion is None else suggestion.suggestion_id
        if suggestion_id == self._schedule_id:
            return
        self._schedule_id = suggestion_id
        if suggestion is None:
            self._schedule_panel.pack_forget()
            return
        self._schedule_heading.set(f"{suggestion.title} · 예약 시각이 되었습니다")
        enabled = (
            "normal"
            if self._schedule_accept is not None and self._schedule_dismiss is not None
            else "disabled"
        )
        self._schedule_yes.configure(state=enabled)
        self._schedule_no.configure(state=enabled)
        self._schedule_panel.pack(fill="x", pady=(12, 0))

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
            self._root.geometry(self._MAIN_SIZE)
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
        self._root.geometry("780x810")
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
    open_display_selector: Callable[[], None] | None = None,
    open_verified_result: Callable[[], None] | None = None,
    review_skills: Callable[[], None] | None = None,
    review_skill_traces: Callable[[], None] | None = None,
    manage_skill_triggers: Callable[[], None] | None = None,
    manage_skill_schedules: Callable[[], None] | None = None,
    respond_skill_review: Callable[[UUID, bool], bool] | None = None,
    trigger_suggestion_provider: Callable[[], SkillTriggerSuggestion | None] | None = None,
    accept_trigger_suggestion: Callable[[UUID], bool] | None = None,
    dismiss_trigger_suggestion: Callable[[UUID], bool] | None = None,
    schedule_suggestion_provider: Callable[[], ScheduledSkillSuggestion | None]
    | None = None,
    accept_schedule_suggestion: Callable[[UUID], bool] | None = None,
    dismiss_schedule_suggestion: Callable[[UUID], bool] | None = None,
    enable_voice: Callable[[], bool] | None = None,
) -> None:
    RuntimeStatusPresenter(
        status_provider=status_provider,
        request_task_stop=request_task_stop,
        request_capture_stop=request_capture_stop,
        request_runtime_stop=request_runtime_stop,
        view=TkStatusView(
            open_display_selector=open_display_selector,
            open_verified_result=open_verified_result,
            review_skills=review_skills,
            review_skill_traces=review_skill_traces,
            manage_skill_triggers=manage_skill_triggers,
            manage_skill_schedules=manage_skill_schedules,
            respond_skill_review=respond_skill_review,
            accept_trigger_suggestion=accept_trigger_suggestion,
            dismiss_trigger_suggestion=dismiss_trigger_suggestion,
            accept_schedule_suggestion=accept_schedule_suggestion,
            dismiss_schedule_suggestion=dismiss_schedule_suggestion,
            enable_voice=enable_voice,
        ),
        poll_interval_ms=poll_interval_ms,
        voice_diagnostics_provider=voice_diagnostics_provider,
        trigger_suggestion_provider=trigger_suggestion_provider,
        schedule_suggestion_provider=schedule_suggestion_provider,
    ).run()
