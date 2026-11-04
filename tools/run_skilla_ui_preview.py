from __future__ import annotations

import argparse
from datetime import UTC, datetime
from uuid import UUID

from javis_core.always_on_runtime import AlwaysOnState
from javis_core.skill_review_surface import (
    SkillDraftDetail,
    SkillDraftSummary,
    SkillReviewDisplay,
    TkSkillReviewView,
)
from javis_core.skill_runtime import SkillOutcome, SkillStatus
from javis_core.skill_trace_review_surface import (
    PendingTraceDetail,
    PendingTraceSummary,
    RevisionTargetSummary,
    TkSkillTraceReviewView,
    TraceReviewDisplay,
    TraceStepDisplay,
)
from javis_core.status_surface import RuntimeStatusDisplay, TkStatusView
from javis_core.user_visible_result import UserVisibleResultSnapshot
from javis_core.verified_result_surface import run_tk_verified_result

SKILL_ID = UUID("00000000-0000-4000-8000-000000000101")
TRACE_ID = UUID("00000000-0000-4000-8000-000000000201")
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


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
    parser = argparse.ArgumentParser(description="SKILLA UI를 안전한 예시 데이터로 미리 봅니다.")
    parser.add_argument(
        "screen",
        choices=("idle", "planning", "executing", "closed", "skills", "trace", "result"),
    )
    args = parser.parse_args()
    states = {
        "idle": AlwaysOnState.IDLE,
        "planning": AlwaysOnState.PLANNING,
        "executing": AlwaysOnState.EXECUTING,
        "closed": AlwaysOnState.CLOSED,
    }
    if args.screen in states:
        preview_status(states[args.screen])
    elif args.screen == "skills":
        preview_skills()
    elif args.screen == "trace":
        preview_trace()
    else:
        preview_result()


if __name__ == "__main__":
    main()
