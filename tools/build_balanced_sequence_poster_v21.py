from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from build_balanced_final_poster_v20 import (
    BLUE,
    BLUE_DARK,
    BLUE_LINE,
    BLUE_PALE,
    EXECUTING,
    FLOW,
    GREEN,
    H,
    INK,
    MINT,
    MUTED,
    PLANNING,
    RESULT,
    REVISION,
    ROOT,
    ROW,
    SKILL,
    W,
    WAITING,
    box,
    bullet_list,
    centered,
    draw_header,
    image_fit,
    register_fonts,
    section,
    text,
    top_y,
    wrapped,
)


OUT = ROOT / "output" / "pdf" / "SKILLA_졸업작품_포스터_시각무게균형_v21.pdf"
WHITE = HexColor("#FFFFFF")


def metric_box(c: canvas.Canvas, x: float, y: float, w: float, title: str, value: str, note: str) -> None:
    box(c, x, y, w, 88, MINT, BLUE_LINE, 7)
    centered(c, title, x + w / 2, y + 10, 14, MUTED, True)
    centered(c, value, x + w / 2, y + 36, 18, INK, True)
    centered(c, note, x + w / 2, y + 62, 14, GREEN, True)


def draw_problem(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 1, "문제와 연구 목적", x, y, w, h)
    text(c, "반복 작업에서 겪는 불편", x + 20, y + 58, 21, BLUE, True)
    cursor = bullet_list(c, [
        "매주 같은 파일을 확인하고 과목별 폴더로 옮기는 작업 반복",
        "같은 요청에도 작업 순서와 분류 기준을 다시 결정",
        "실패와 예외를 다음 작업에 반영할 방법 부족",
    ], x + 20, y + 94, w - 40, 18, 27)
    text(c, "개발 목표", x + 20, cursor + 5, 21, BLUE, True)
    bullet_list(c, [
        "작업 순서·판단 기준·완료 확인 방법을 스킬로 저장",
        "다음 작업에서는 현재 값만 확인하고 저장한 방법 재사용",
        "성공률·실행 시간·토큰 사용량으로 효과 확인",
    ], x + 20, cursor + 42, w - 40, 18, 27)
    box(c, x + 16, y + h - 60, w - 32, 44, BLUE_PALE, BLUE_PALE, 6)
    centered(c, "토큰: 인공지능이 요청과 답을 처리할 때 세는 글 단위", x + w / 2, y + h - 47, 15, MUTED)


def draw_flow(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 2, "스킬 사용 전후의 작업 흐름과 하네스", x, y, w, h)
    box(c, x + 16, y + 56, w - 32, 64, BLUE_PALE, BLUE_PALE, 6)
    wrapped(c, "하네스: 모델 호출·사용자 승인·도구 실행·중단·결과 확인·기록을 연결하는 프로그램 내부 체계", x + 30, y + 69, w - 60, 17, 24, INK, True)
    image_fit(c, FLOW, x + 18, y + 132, w - 36, 245, False)
    centered(c, "저장된 스킬이 있으면 재사용하고, 없으면 새 계획을 만든다", x + w / 2, y + 381, 16, BLUE_DARK, True)


def draw_examples(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 3, "사용 예시와 완료 확인 방법", x, y, w, h)
    box(c, x + 16, y + 58, w - 32, 242, BLUE_PALE, BLUE_PALE, 7)
    text(c, "예시 A  이번 주 과제 자료 정리", x + 30, y + 76, 22, BLUE, True)
    wrapped(c, "저장한 방법\n파일 확인 → 과목 판단 → 폴더 이동 → 결과 확인\n\n매번 새로 확인\n파일명·내용·개수, 과목이 모호한 파일\n\n완료 기준\n정답 폴더 비교, 원본 누락 검사", x + 30, y + 116, w - 60, 17, 24)
    box(c, x + 16, y + 316, w - 32, 226, MINT, BLUE_LINE, 7)
    text(c, "예시 B  PDF 문서 열기", x + 30, y + 334, 22, BLUE, True)
    wrapped(c, "저장한 방법\n대상 확인 → 프로그램 실행 → 새 창 확인\n\n매번 새로 확인\n문서와 보기 프로그램의 실행 상태\n\n완료 기준\n새 창에서 지정한 문서가 열렸는지 검사", x + 30, y + 374, w - 60, 17, 24)
    box(c, x + 16, y + h - 76, w - 32, 58, ROW, ROW, 6)
    wrapped(c, "예외 처리: 모호한 파일은 사용자에게 확인하거나 따로 분리하고, 일반 질문은 PC 실행 명령과 구분", x + 28, y + h - 61, w - 56, 15, 21, MUTED, True)


def draw_main_ui(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 4, "요청 상태와 실행 결과 검증", x, y, w, h)
    text(c, "상태 변화", x + 18, y + 58, 20, BLUE, True)
    gap = 12
    card_w = (w - 36 - gap * 2) / 3
    for index, (path, label) in enumerate(((WAITING, "1  대기"), (PLANNING, "2  계획"), (EXECUTING, "3  실행"))):
        cx = x + 18 + index * (card_w + gap)
        text(c, label, cx, y + 92, 17, BLUE, True)
        image_fit(c, path, cx, y + 121, card_w, 112, True)
    text(c, "실행 뒤 실제 상태 확인", x + 18, y + 254, 20, BLUE, True)
    image_fit(c, RESULT, x + 18, y + 288, w - 36, 300, True)
    box(c, x + 18, y + h - 70, w - 36, 52, BLUE_PALE, BLUE_PALE, 6)
    centered(c, "파일 개수·이동 결과·원본 누락을 다시 검사해 성공 여부를 표시", x + w / 2, y + h - 54, 16, BLUE_DARK, True)


def draw_skill_panel(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 4, "저장된 스킬을 확인하고 승인", x, y, w, h)
    image_fit(c, SKILL, x + 18, y + 58, w * 0.58, h - 82, True)
    tx = x + w * 0.61
    text(c, "스킬에 저장되는 내용", tx, y + 70, 21, BLUE, True)
    bullet_list(c, [
        "명령을 찾는 호출 표현",
        "반복되는 작업 절차",
        "매번 달라지는 입력",
        "판단 기준과 완료 확인",
        "실행을 허용한 기능",
    ], tx, y + 112, w * 0.36, 17, 28)
    box(c, tx, y + h - 76, w * 0.35, 52, MINT, BLUE_LINE, 5)
    centered(c, "사용자가 승인한 버전만 재사용", tx + w * 0.175, y + h - 59, 15, GREEN, True)


def draw_revision_panel(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 4, "실패·예외 기록으로 스킬 개정", x, y, w, h)
    tx = x + 18
    text(c, "개정 근거", tx, y + 70, 21, BLUE, True)
    bullet_list(c, [
        "실행 단계와 성공 여부",
        "이번 작업에서 바뀐 입력",
        "판단하지 못한 예외",
        "독립적으로 확인한 완료 결과",
    ], tx, y + 112, w * 0.36, 17, 29)
    box(c, tx, y + h - 76, w * 0.35, 52, BLUE_PALE, BLUE_PALE, 5)
    centered(c, "기존 스킬은 유지하고 개정 초안 생성", tx + w * 0.175, y + h - 59, 15, BLUE_DARK, True)
    image_fit(c, REVISION, x + w * 0.40, y + 58, w * 0.58, h - 82, True)


def draw_models(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 5, "사용 모델과 실행 위치", x, y, w, h)
    data = [
        ("STT  음성 인식", "Whisper large-v3-turbo", "사람의 말을 글자로 변환", "사용자 PC · CPU int8"),
        ("LLM  대규모 언어 모델", "NVIDIA NIM z-ai/glm-5.3-flash", "요청·스킬·현재 상태를 읽고 계획 생성", "NVIDIA 모델 호스팅 서비스"),
        ("TTS  음성 합성", "Supertonic 3 int8", "완료·확인 문장을 음성으로 전달", "사용자 PC · CPU"),
    ]
    row_y = y + 58
    row_h = 147
    for index, (name, model, role, location) in enumerate(data):
        box(c, x + 16, row_y, w - 32, row_h, MINT if index == 1 else BLUE_PALE, BLUE_LINE, 7)
        text(c, name, x + 30, row_y + 14, 21, BLUE, True)
        text(c, model, x + 30, row_y + 51, 17, INK, True)
        wrapped(c, f"역할  {role}\n실행 위치  {location}", x + 30, row_y + 82, w - 60, 16, 23)
        row_y += row_h + 12
    box(c, x + 16, y + h - 62, w - 32, 44, ROW, ROW, 5)
    centered(c, "마이크 원음과 사용자 파일 전체는 외부 모델에 전송하지 않음", x + w / 2, y + h - 48, 14, MUTED, True)


def draw_experiment(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    section(c, 6, "실험 환경·평가 기준·결과", x, y, w, h)
    text(c, "실험 환경", x + 18, y + 58, 19, BLUE, True)
    wrapped(c, "Windows 11 · Ryzen 5 9500F · 메모리 15.4GB · RTX 5060 Ti\n작업 5종 × 3회 × 4조건 = 60회 · 매번 초기 파일 복원 · 개발자 1명", x + 150, y + 58, w - 168, 15, 22)
    cond_y = y + 112
    conds = (("SK0", "스킬 없음"), ("SK1", "일반 지침"), ("SK2", "최초 스킬"), ("SK3", "개정 스킬"))
    cw = (w - 54) / 4
    for index, (code, label) in enumerate(conds):
        cx = x + 15 + index * (cw + 8)
        box(c, cx, cond_y, cw, 58, MINT if index == 3 else ROW, BLUE_LINE, 5)
        centered(c, f"{code}  {label}", cx + cw / 2, cond_y + 19, 15, GREEN if index == 3 else INK, True)
    table_y = y + 186
    table_x, table_w = x + 14, w - 28
    cols = [0.13, 0.16, 0.19, 0.18, 0.18, 0.16]
    headers = ["조건", "성공", "평균 시간", "평균 호출", "평균 토큰", "사용자 확인"]
    rows = [
        ["SK0", "10/15", "18.783초", "2.200", "3,759.5", "0.333회"],
        ["SK1", "12/15", "18.614초", "2.467", "4,268.9", "0.600회"],
        ["SK2", "12/15", "25.742초", "3.000", "5,680.9", "0.533회"],
        ["SK3", "14/15", "12.367초", "1.867", "3,135.7", "1.000회"],
    ]
    row_h = 34
    c.setFillColor(BLUE)
    c.rect(table_x, top_y(table_y, row_h), table_w, row_h, fill=1, stroke=0)
    cx = table_x
    for index, value in enumerate(headers):
        cell_w = table_w * cols[index]
        centered(c, value, cx + cell_w / 2, table_y + 8, 12.5, WHITE, True)
        cx += cell_w
    for ri, row in enumerate(rows):
        ry = table_y + row_h * (ri + 1)
        c.setFillColor(MINT if ri == 3 else (WHITE if ri % 2 == 0 else ROW))
        c.rect(table_x, top_y(ry, row_h), table_w, row_h, fill=1, stroke=0)
        cx = table_x
        for index, value in enumerate(row):
            cell_w = table_w * cols[index]
            centered(c, value, cx + cell_w / 2, ry + 8, 12.5, INK, ri == 3)
            cx += cell_w
    my = table_y + row_h * 5 + 16
    gap = 8
    mw = (w - 28 - gap * 2) / 3
    metric_box(c, x + 14, my, mw, "성공 횟수", "10/15 → 14/15", "+26.7%p")
    metric_box(c, x + 14 + mw + gap, my, mw, "평균 시간", "18.783 → 12.367초", "34.2% 감소")
    metric_box(c, x + 14 + (mw + gap) * 2, my, mw, "평균 토큰", "3,759.5 → 3,135.7", "16.6% 감소")
    wrapped(c, "평가 기준  성공 여부·실행 시간·모델 호출 수·토큰 사용량·사용자 확인 횟수\n통계 확인  McNemar 검정과 Holm 보정 결과 0.375 > 0.05, 통계적 유의성 미확인\n해석  개정 스킬에서 시간과 토큰이 줄고 성공 횟수가 늘었으나 추가 사용자 시험 필요", x + 18, my + 104, w - 36, 13.5, 19)
    text(c, "참고논문", x + 18, y + h - 54, 14, BLUE, True)
    wrapped(c, "Voyager · Reflexion · ReAct · OSWorld", x + 118, y + h - 54, w - 136, 12.5, 18, MUTED)


def main() -> None:
    register_fonts()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle("SKILLA 졸업작품 포스터 시각 무게 균형본")
    draw_header(c)

    left_x, gap = 42, 22
    inner_w = W - 84

    # 1행: 글 중심 문제 설명과 그림 중심 비교 흐름을 서로 맞댄다.
    row1_y, row1_h = 190, 410
    row1_left = 710
    draw_problem(c, left_x, row1_y, row1_left, row1_h)
    draw_flow(c, left_x + row1_left + gap, row1_y, inner_w - row1_left - gap, row1_h)

    # 2행: 구체적 설명과 실제 실행 화면을 같은 높이로 배치한다.
    row2_y, row2_h = 620, 650
    row2_left = 585
    draw_examples(c, left_x, row2_y, row2_left, row2_h)
    draw_main_ui(c, left_x + row2_left + gap, row2_y, inner_w - row2_left - gap, row2_h)

    # 3행: 이미지 옆에 큰 설명을 배치해 이미지끼리 뭉치지 않게 한다.
    row3_y, row3_h = 1290, 430
    half = (inner_w - gap) / 2
    draw_skill_panel(c, left_x, row3_y, half, row3_h)
    draw_revision_panel(c, left_x + half + gap, row3_y, half, row3_h)

    # 4행: 모델 설명과 실험 결과를 같은 무게로 마무리한다.
    row4_y, row4_h = 1740, 600
    row4_left = 690
    draw_models(c, left_x, row4_y, row4_left, row4_h)
    draw_experiment(c, left_x + row4_left + gap, row4_y, inner_w - row4_left - gap, row4_h)

    c.showPage()
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
