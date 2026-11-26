from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest

from skilla_core.always_on_runtime import (
    AlwaysOnState,
    RuntimeEventType,
    RuntimeStatusSnapshot,
)
from skilla_core.skill_schedules import ScheduledSkillSuggestion
from skilla_core.skill_triggers import SkillTriggerSuggestion
from skilla_core.status_surface import (
    RuntimeStatusDisplay,
    RuntimeStatusPresenter,
    reactor_activity_label,
    reactor_level_label,
    reactor_pulse_geometry,
    smooth_reactor_level,
    wakeword_mode_label,
)
from skilla_core.voice import VoicePipelineDiagnostics


class FakeView:
    def __init__(self) -> None:
        self.on_stop: Callable[[], None] | None = None
        self.on_hide: Callable[[], None] | None = None
        self.on_exit: Callable[[], None] | None = None
        self.rendered: list[RuntimeStatusDisplay] = []
        self.scheduled: list[tuple[int, Callable[[], None]]] = []
        self.closed = False
        self.minimized = False
        self.ran = False

    def bind_handlers(
        self,
        *,
        on_stop: Callable[[], None],
        on_hide: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.on_stop = on_stop
        self.on_hide = on_hide
        self.on_exit = on_exit

    def render(self, display: RuntimeStatusDisplay) -> None:
        self.rendered.append(display)

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> None:
        self.scheduled.append((delay_ms, callback))

    def close(self) -> None:
        self.closed = True

    def minimize(self) -> None:
        self.minimized = True

    def run(self) -> None:
        self.ran = True


def snapshot(
    state: AlwaysOnState = AlwaysOnState.IDLE,
    *,
    reason: str = "RUNTIME_READY",
) -> RuntimeStatusSnapshot:
    return RuntimeStatusSnapshot(
        state=state,
        last_event_type=RuntimeEventType.ROUTED,
        last_reason=reason,
        sequence=3,
    )


def test_presenter_polls_coarse_status_and_hide_does_not_stop_agent() -> None:
    view = FakeView()
    calls: list[str] = []

    def stop_capture() -> bool:
        calls.append("capture")
        return True

    presenter = RuntimeStatusPresenter(
        status_provider=snapshot,
        request_task_stop=lambda: calls.append("task"),
        request_capture_stop=stop_capture,
        request_runtime_stop=lambda: calls.append("runtime"),
        view=view,
    )

    presenter.run()
    assert view.ran
    assert view.rendered[-1].state_label == "대기 중"
    assert view.scheduled[0][0] == 250

    assert view.on_hide is not None
    view.on_hide()
    assert view.minimized
    assert not view.closed
    assert calls == []


def test_presenter_includes_one_pending_situation_skill_suggestion() -> None:
    view = FakeView()
    item = SkillTriggerSuggestion(
        suggestion_id=uuid4(),
        rule_id=uuid4(),
        app_id="chrome",
        skill_id=uuid4(),
        skill_version=1,
        title="최근 음악 재생",
    )
    presenter = RuntimeStatusPresenter(
        status_provider=snapshot,
        request_task_stop=lambda: None,
        request_capture_stop=lambda: False,
        request_runtime_stop=lambda: None,
        view=view,
        trigger_suggestion_provider=lambda: item,
    )

    presenter.run()

    assert view.rendered[-1].trigger_suggestion == item


def test_presenter_includes_one_pending_scheduled_skill_suggestion() -> None:
    view = FakeView()
    item = ScheduledSkillSuggestion(
        suggestion_id=uuid4(),
        rule_id=uuid4(),
        skill_id=uuid4(),
        skill_version=1,
        title="아침 작업 준비",
        due_key="2026-11-16T08:30+0900",
    )
    presenter = RuntimeStatusPresenter(
        status_provider=snapshot,
        request_task_stop=lambda: None,
        request_capture_stop=lambda: False,
        request_runtime_stop=lambda: None,
        view=view,
        schedule_suggestion_provider=lambda: item,
    )

    presenter.run()

    assert view.rendered[-1].schedule_suggestion == item


def test_stop_cancels_only_current_task_and_explicit_exit_stops_runtime() -> None:
    view = FakeView()
    calls: list[str] = []

    def stop_capture() -> bool:
        calls.append("capture")
        return True

    presenter = RuntimeStatusPresenter(
        status_provider=lambda: snapshot(AlwaysOnState.IDLE),
        request_task_stop=lambda: calls.append("task"),
        request_capture_stop=stop_capture,
        request_runtime_stop=lambda: calls.append("runtime"),
        view=view,
    )
    presenter.run()

    assert view.on_stop is not None
    view.on_stop()

    assert calls == ["task"]
    assert view.rendered[-1].stop_enabled is True

    assert view.on_exit is not None
    view.on_exit()
    assert calls == ["task", "capture", "runtime"]
    assert view.closed


def test_unknown_reason_and_provider_failure_do_not_leak_details() -> None:
    view = FakeView()
    presenter = RuntimeStatusPresenter(
        status_provider=lambda: snapshot(reason="COMMAND_DECISION_INVALID"),
        request_task_stop=lambda: None,
        request_capture_stop=lambda: False,
        request_runtime_stop=lambda: None,
        view=view,
    )
    presenter.run()
    assert view.rendered[-1].detail_label == "작업 상태가 변경되었습니다."
    assert "COMMAND" not in view.rendered[-1].detail_label

    failing_view = FakeView()

    def fail() -> RuntimeStatusSnapshot:
        raise RuntimeError("secret transcript and C:\\private\\file.txt")

    RuntimeStatusPresenter(
        status_provider=fail,
        request_task_stop=lambda: None,
        request_capture_stop=lambda: False,
        request_runtime_stop=lambda: None,
        view=failing_view,
    ).run()
    rendered = failing_view.rendered[-1].model_dump_json()
    assert "secret" not in rendered
    assert "private" not in rendered


def test_idle_voice_display_distinguishes_started_capture_from_no_frames() -> None:
    no_frames = RuntimeStatusPresenter._display(
        snapshot(),
        VoicePipelineDiagnostics(
            frame_count=0,
            speech_frame_count=0,
            max_wake_confidence=0.0,
            wake_detected=False,
        ),
    )
    receiving = RuntimeStatusPresenter._display(
        snapshot(),
        VoicePipelineDiagnostics(
            frame_count=12,
            speech_frame_count=0,
            max_wake_confidence=0.0,
            wake_detected=False,
        ),
    )

    assert no_frames.voice_label == "마이크 시작 중 · 입력 신호를 기다리고 있습니다"
    assert receiving.voice_label == "마이크 수신 중 · 입력 프레임 12"


def test_display_uses_monotonic_input_sequence_for_live_meter_updates() -> None:
    display = RuntimeStatusPresenter._display(
        snapshot(),
        VoicePipelineDiagnostics(
            frame_count=3,
            speech_frame_count=1,
            max_wake_confidence=0.0,
            wake_detected=False,
            speech_active=True,
            input_level=0.42,
            input_sequence=103,
        ),
    )

    assert display.input_level == 0.42
    assert display.audio_frame_count == 103


def test_non_wake_background_speech_does_not_show_garbled_transcript() -> None:
    display = RuntimeStatusPresenter._display(
        snapshot(),
        VoicePipelineDiagnostics(
            frame_count=0,
            speech_frame_count=0,
            max_wake_confidence=0.0,
            wake_detected=False,
            last_transcript="잘못 인식된 주변 소리",
            recognition_reason="WAKE_WORD_NOT_FOUND",
        ),
    )

    assert display.voice_label == "주변 음성 무시 · '스킬라'를 기다리는 중"
    assert "잘못" not in display.voice_label
    assert display.heard_text == ""


def test_command_transcript_is_visible_separately_from_its_result() -> None:
    display = RuntimeStatusPresenter._display(
        snapshot(),
        VoicePipelineDiagnostics(
            frame_count=25,
            speech_frame_count=8,
            max_wake_confidence=1.0,
            wake_detected=False,
            last_transcript="스킬라 시스템 정보 확인해 줘",
            recognition_reason="COMMAND_RECOGNIZED",
        ),
    )

    assert display.heard_text == "스킬라 시스템 정보 확인해 줘"
    assert display.result_summary == ""


def test_historical_speech_count_does_not_claim_current_speech() -> None:
    display = RuntimeStatusPresenter._display(
        snapshot(),
        VoicePipelineDiagnostics(
            frame_count=20,
            speech_frame_count=12,
            max_wake_confidence=0.0,
            wake_detected=False,
            speech_active=False,
            input_sequence=20,
        ),
    )

    assert display.voice_label == "마이크 수신 중 · 입력 프레임 20"


def test_review_waiting_has_an_explicit_voice_instruction() -> None:
    display = RuntimeStatusPresenter._display(
        snapshot(AlwaysOnState.REVIEWING),
        VoicePipelineDiagnostics(
            frame_count=20,
            speech_frame_count=0,
            max_wake_confidence=0.0,
            wake_detected=False,
            recognition_reason="REVIEW_WAITING",
        ),
    )

    assert display.voice_label == "승인 음성 대기 중 · 예 또는 아니요"


def test_presenter_rejects_invalid_poll_interval() -> None:
    for invalid in (99, 5_001, True):
        with pytest.raises(ValueError, match="poll_interval_ms"):
            RuntimeStatusPresenter(
                status_provider=snapshot,
                request_task_stop=lambda: None,
                request_capture_stop=lambda: False,
                request_runtime_stop=lambda: None,
                view=FakeView(),
                poll_interval_ms=invalid,
            )


def test_reactor_geometry_grows_with_live_microphone_level() -> None:
    silent = reactor_pulse_geometry(0.0)
    speaking = reactor_pulse_geometry(0.5)
    loud = reactor_pulse_geometry(1.0)

    assert silent == (2, 47.0)
    assert silent[0] < speaking[0] < loud[0]
    assert silent[1] < speaking[1] < loud[1]
    assert loud == (8, 67.0)


def test_reactor_geometry_clamps_invalid_external_levels() -> None:
    assert reactor_pulse_geometry(-5) == reactor_pulse_geometry(0)
    assert reactor_pulse_geometry(5) == reactor_pulse_geometry(1)


def test_reactor_level_label_is_readable_and_clamped() -> None:
    assert reactor_level_label(0.0) == "MIC 00%"
    assert reactor_level_label(0.42) == "MIC 42%"
    assert reactor_level_label(1.0) == "MIC 100%"
    assert reactor_level_label(-1) == "MIC 00%"
    assert reactor_level_label(2) == "MIC 100%"


def test_reactor_level_smoothing_attacks_quickly_and_releases_gently() -> None:
    rising = smooth_reactor_level(0.0, 1.0)
    falling = smooth_reactor_level(1.0, 0.0)

    assert rising == pytest.approx(0.58)
    assert falling == pytest.approx(0.8)
    assert smooth_reactor_level(0.001, 0.0) == 0.0


def test_reactor_activity_tracks_the_smoothed_microphone_level() -> None:
    assert reactor_activity_label(0.0) == "VOICE LINK // STANDBY"
    assert reactor_activity_label(0.05) == "VOICE LINK // RECEIVING"
    assert reactor_activity_label(0.18) == "VOICE LINK // RECEIVING"
    assert reactor_activity_label(0.5) == "VOICE LINK // SPEAKING"


def test_wakeword_mode_label_describes_the_configured_product_path() -> None:
    assert "로컬 Whisper 한국어 인식" in wakeword_mode_label("whisper_korean")
    assert "openWakeWord" in wakeword_mode_label("openwakeword")
    assert "Hermes" not in wakeword_mode_label("whisper_korean")


def test_wakeword_mode_label_rejects_unknown_modes() -> None:
    with pytest.raises(ValueError, match="unsupported wakeword mode"):
        wakeword_mode_label("hermes")
