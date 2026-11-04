from __future__ import annotations

from javis_core.always_on_runtime import (
    AlwaysOnState,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeStatusSnapshot,
)
from javis_core.text_command_surface import TextCommandPresenter, invoke_surface_action
from javis_core.user_visible_result import UserVisibleResultSnapshot


class Runtime:
    def __init__(self, snapshot: RuntimeStatusSnapshot) -> None:
        self.snapshot = snapshot
        self.commands: list[str] = []

    def submit_text(self, text: str) -> RuntimeEvent:
        self.commands.append(text)
        return RuntimeEvent(
            event_type=RuntimeEventType.TASK_STARTED,
            reason="PLANNING_STARTED",
        )

    def status_snapshot(self) -> RuntimeStatusSnapshot:
        return self.snapshot


def test_presenter_submits_normalized_text_without_displaying_it() -> None:
    runtime = Runtime(RuntimeStatusSnapshot(state=AlwaysOnState.IDLE))
    presenter = TextCommandPresenter(runtime)

    event = presenter.submit("  개인 파일 정리  ")
    display = presenter.display()

    assert runtime.commands == ["개인 파일 정리"]
    assert event.event_type is RuntimeEventType.TASK_STARTED
    assert display.submit_enabled
    assert not display.stop_enabled
    assert "개인 파일" not in display.model_dump_json()


def test_presenter_stop_uses_exact_local_phrase_and_active_state() -> None:
    runtime = Runtime(
        RuntimeStatusSnapshot(
            state=AlwaysOnState.EXECUTING,
            last_event_type=RuntimeEventType.TASK_STARTED,
            last_reason="EXECUTION_STARTED",
        )
    )
    presenter = TextCommandPresenter(runtime)

    presenter.stop()
    display = presenter.display()

    assert runtime.commands == ["멈춰"]
    assert not display.submit_enabled
    assert display.stop_enabled


def test_presenter_renders_only_fixed_failure_message() -> None:
    runtime = Runtime(
        RuntimeStatusSnapshot(
            state=AlwaysOnState.IDLE,
            last_event_type=RuntimeEventType.FAILED,
            last_reason="PRIVATE_INTERNAL_REASON",
        )
    )

    rendered = TextCommandPresenter(runtime).display().model_dump_json()

    assert "작업을 처리하지 못했습니다" in rendered
    assert "PRIVATE" not in rendered


def test_presenter_renders_verified_result_without_contradictory_idle_message() -> None:
    runtime = Runtime(
        RuntimeStatusSnapshot(
            state=AlwaysOnState.IDLE,
            last_event_type=RuntimeEventType.TASK_COMPLETED,
            last_reason="ALL_ACTIONS_VERIFIED",
            result=UserVisibleResultSnapshot(
                capability_id="system.info.read",
                title="확인된 컴퓨터 시스템 정보",
                lines=("운영체제: Windows", "시스템 종류: AMD64"),
            ),
        )
    )

    display = TextCommandPresenter(runtime).display()

    assert display.state_label == "작업을 완료했습니다."
    assert display.detail_label == "아래에서 검증된 결과를 확인하세요."
    assert "운영체제: Windows" in display.result_text
    assert "명령을 입력할 수 있습니다" not in display.model_dump_json()


def test_surface_action_invokes_callback_without_reporting_failure() -> None:
    calls: list[str] = []

    invoke_surface_action(
        lambda: calls.append("skill-review"),
        "고정 오류",
        lambda _title, _message: calls.append("error"),
    )

    assert calls == ["skill-review"]


def test_surface_action_redacts_callback_exception() -> None:
    reports: list[tuple[str, str]] = []

    def fail() -> None:
        raise RuntimeError("private path nvapi-private")

    invoke_surface_action(
        fail,
        "스킬 관리 화면을 열지 못했습니다. 잠시 후 다시 시도해 주세요.",
        lambda title, message: reports.append((title, message)),
    )

    assert reports == [
        (
            "SKILLA",
            "스킬 관리 화면을 열지 못했습니다. 잠시 후 다시 시도해 주세요.",
        )
    ]
    assert "private" not in str(reports)
