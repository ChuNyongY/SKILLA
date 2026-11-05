from __future__ import annotations

from collections.abc import Callable

import pytest

from skilla_core.always_on_runtime import (
    AlwaysOnState,
    RuntimeEventType,
    RuntimeStatusSnapshot,
)
from skilla_core.status_surface import (
    RuntimeStatusDisplay,
    RuntimeStatusPresenter,
    reactor_level_label,
    reactor_pulse_geometry,
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
