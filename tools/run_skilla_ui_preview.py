from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from skilla_core.always_on_runtime import AlwaysOnState
from skilla_core.cyber_theme import COLORS, button, configure_window, footer, header, label, panel
from skilla_core.skill_review_surface import (
    SkillDraftDetail,
    SkillDraftSummary,
    SkillReviewDisplay,
    TkSkillReviewView,
)
from skilla_core.skill_runtime import SkillOutcome, SkillStatus
from skilla_core.skill_trace_review_surface import (
    PendingTraceDetail,
    PendingTraceSummary,
    RevisionTargetSummary,
    TkSkillTraceReviewView,
    TraceReviewDisplay,
    TraceStepDisplay,
)
from skilla_core.status_surface import RuntimeStatusDisplay, TkStatusView
from skilla_core.user_visible_result import UserVisibleResultSnapshot
from skilla_core.verified_result_surface import run_tk_verified_result

SKILL_ID = UUID("00000000-0000-4000-8000-000000000101")
TRACE_ID = UUID("00000000-0000-4000-8000-000000000201")
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
THIS_SCRIPT = Path(__file__).resolve()


def preview_showcase() -> None:
    """Open a screenshot-friendly launcher for every implemented SKILLA UI."""
    import tkinter as tk

    root = tk.Tk()
    configure_window(
        root,
        title="SKILLA 실제 구현 UI 촬영 모드",
        geometry="1180x800",
        minsize=(1080, 720),
    )
    outer = tk.Frame(root, bg=COLORS["bg"], padx=24, pady=18)
    outer.pack(fill="both", expand=True)
    header(
        outer,
        system_code="SYSTEM // UI SHOWCASE",
        heading="실제 구현 UI 촬영 모드",
    )
    footer(outer)
    label(
        outer,
        "각 버튼은 포스터 시안 이미지가 아니라 SKILLA가 실제로 사용하는 UI 코드를 실행합니다.",
        color=COLORS["muted"],
        size=11,
    ).pack(fill="x", pady=(0, 14))

    grid = tk.Frame(outer, bg=COLORS["bg"])
    grid.pack(fill="both", expand=True)
    for column in range(3):
        grid.grid_columnconfigure(column, weight=1, uniform="ui-card")
    for row in range(2):
        grid.grid_rowconfigure(row, weight=1, uniform="ui-card")

    screens = (
        ("idle", "1  요청 대기", "음성·텍스트 명령을 기다리는 기본 화면", COLORS["cyan"]),
        ("planning", "2  요청 분석과 계획", "명령을 분석하고 관련 스킬과 실행 순서를 표시", COLORS["warning"]),
        ("executing", "3  승인된 작업 실행", "현재 실행 단계와 즉시 중지 기능을 함께 표시", COLORS["success"]),
        ("result", "4  실제 결과 검증", "파일·프로그램의 실제 상태를 다시 확인한 결과", COLORS["success"]),
        ("skills", "5  스킬 관리와 승인", "작업 절차·판단 기준·완료 조건과 버전을 검토", COLORS["cyan"]),
        ("trace", "6  스킬 개정 후보", "실패·예외 기록을 근거로 다음 버전 초안을 검토", COLORS["warning"]),
    )

    children: list[subprocess.Popen[bytes]] = []

    def launch(screen: str) -> None:
        children.append(
            subprocess.Popen(
                [sys.executable, str(THIS_SCRIPT), screen],
                cwd=str(THIS_SCRIPT.parents[1]),
            )
        )

    for index, (screen, title, description, accent) in enumerate(screens):
        card = panel(grid, alternate=(index % 2 == 1), padx=18, pady=16)
        card.grid(
            row=index // 3,
            column=index % 3,
            sticky="nsew",
            padx=8,
            pady=8,
        )
        label(card, title, color=accent, size=15, bold=True).pack(fill="x", pady=(0, 12))
        label(card, description, color=COLORS["text"], size=10).pack(
            fill="both", expand=True, anchor="nw"
        )
        open_button = button(card, "실제 화면 열기", color=accent, width=18)
        open_button.configure(command=lambda value=screen: launch(value))
        open_button.pack(fill="x", pady=(14, 0))

    label(
        outer,
        "촬영 순서  요청 대기 → 계획 → 실행 → 결과 검증 → 스킬 관리 → 개정 후보",
        color=COLORS["cyan"],
        size=10,
        bold=True,
        anchor="center",
    ).pack(fill="x", pady=(14, 0))
    root.mainloop()


def preview_status(state: AlwaysOnState) -> None:
    labels = {
        AlwaysOnState.IDLE: ("대기 중", "음성 명령을 기다리고 있습니다.", "마이크 입력 대기"),
        AlwaysOnState.PLANNING: (
            "계획 중",
            "요청을 분석하고 관련 스킬을 검색합니다.",
            "명령 인식: 과제 자료 정리",
        ),
        AlwaysOnState.EXECUTING: (
            "실행 중",
            "승인된 작업을 실행하고 있습니다.",
            "음성 입력 잠시 대기",
        ),
        AlwaysOnState.CLOSED: ("종료됨", "런타임이 종료되었습니다.", "마이크 연결 종료"),
    }
    state_label, detail, voice = labels[state]
    view = TkStatusView()
    view._root.title(f"SKILLA 구현 화면 미리보기 - {labels[state][0]}")
    view.bind_handlers(on_stop=lambda: None, on_hide=view.minimize, on_exit=view.close)
    view.render(
        RuntimeStatusDisplay(
            state=state,
            state_label=state_label,
            detail_label=detail,
            completed_actions=1 if state is AlwaysOnState.IDLE else 0,
            sequence=1,
            stop_enabled=state is not AlwaysOnState.CLOSED,
            voice_label=voice,
        )
    )
    view.run()


def preview_skills() -> None:
    view = TkSkillReviewView()
    view.bind_handlers(
        on_select=lambda _skill_id: None,
        on_approve=lambda: None,
        on_reject=lambda: None,
        on_refresh=lambda: None,
        on_close=view.close,
    )
    summary = SkillDraftSummary(
        skill_id=SKILL_ID,
        key="coursework-sort",
        title="과제 자료 정리",
        version=4,
        is_revision=True,
        status=SkillStatus.DRAFT,
    )
    view.render(
        SkillReviewDisplay(
            drafts=(summary,),
            selected=SkillDraftDetail(
                skill_id=SKILL_ID,
                key=summary.key,
                title=summary.title,
                description="과제 파일을 과목별 폴더로 정리하고 결과를 확인합니다.",
                version=4,
                triggers=("과제 자료 정리", "이번 주 자료 정리"),
                procedure=("파일 찾기", "과목 판단", "모호한 파일 분리", "폴더 이동", "결과 확인"),
                dynamic_inputs=("현재 폴더", "이번 주 파일"),
                decision_rules=("과목을 확정할 수 없으면 확인 필요 폴더로 분리",),
                verification_rules=("이동 전후 파일 개수 일치", "원본 누락 없음"),
                allowed_capabilities=("file.list", "file.move"),
                supersedes_skill_id=None,
                status=SkillStatus.DRAFT,
            ),
            notice="개정 내용을 확인한 뒤 승인 또는 거절하세요.",
            mutation_enabled=True,
        )
    )
    view.run()


def preview_trace() -> None:
    view = TkSkillTraceReviewView()
    view.bind_handlers(
        on_select=lambda _trace_id: None,
        on_select_revision=lambda _skill_id: None,
        on_create=lambda: None,
        on_discard=lambda: None,
        on_refresh=lambda: None,
        on_close=view.close,
    )
    summary = PendingTraceSummary(
        trace_id=TRACE_ID,
        goal_summary="이번 주 과제 자료 정리",
        outcome=SkillOutcome.SUCCEEDED,
        recorded_at=NOW,
        step_count=2,
    )
    view.render(
        TraceReviewDisplay(
            pending=(summary,),
            revision_targets=(
                RevisionTargetSummary(
                    skill_id=SKILL_ID,
                    key="coursework-sort",
                    title="과제 자료 정리",
                    version=3,
                    updated_at=NOW,
                    reason_code="AMBIGUOUS_FILE_OBSERVED",
                    observations=15,
                    success_rate=0.93,
                ),
            ),
            selected_revision_skill_id=SKILL_ID,
            selected=PendingTraceDetail(
                **summary.model_dump(),
                steps=(
                    TraceStepDisplay(
                        sequence=1,
                        capability_id="file.list",
                        outcome=SkillOutcome.SUCCEEDED,
                        detail_code="FILES_LISTED",
                        independently_verified=True,
                    ),
                    TraceStepDisplay(
                        sequence=2,
                        capability_id="file.move",
                        outcome=SkillOutcome.SUCCEEDED,
                        detail_code="FILE_MOVED",
                        independently_verified=True,
                    ),
                ),
                dynamic_input_labels=("이번 주 파일명", "파일 개수"),
                decision_notes=("과목을 판단하지 못한 파일 1개를 분리",),
                verification_notes=("이동 전후 파일 개수 일치",),
            ),
            notice="실패·예외 기록을 근거로 개정 초안을 만들 수 있습니다.",
            actions_enabled=True,
        )
    )
    view.run()


def preview_result() -> None:
    result = UserVisibleResultSnapshot(
        capability_id="file.list",
        title="과제 자료 정리 결과",
        lines=(
            "정리 전 파일 8개를 확인했습니다.",
            "과목별 폴더로 파일 8개를 이동했습니다.",
            "이동 전후 파일 개수가 일치합니다.",
            "원본 누락이 없습니다.",
        ),
    )
    run_tk_verified_result(lambda: result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "실제 SKILLA UI 코드에 안전한 시연 데이터를 넣어 실행합니다. "
            "포스터 캡처에도 같은 화면을 사용합니다."
        )
    )
    parser.add_argument(
        "screen",
        choices=(
            "showcase",
            "idle",
            "planning",
            "executing",
            "closed",
            "skills",
            "trace",
            "result",
        ),
    )
    args = parser.parse_args()
    states = {
        "idle": AlwaysOnState.IDLE,
        "planning": AlwaysOnState.PLANNING,
        "executing": AlwaysOnState.EXECUTING,
        "closed": AlwaysOnState.CLOSED,
    }
    if args.screen == "showcase":
        preview_showcase()
    elif args.screen in states:
        preview_status(states[args.screen])
    elif args.screen == "skills":
        preview_skills()
    elif args.screen == "trace":
        preview_trace()
    else:
        preview_result()


if __name__ == "__main__":
    main()
