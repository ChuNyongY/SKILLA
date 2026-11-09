from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "SKILLA_졸업작품_포스터_전체균형재설계_v20.pdf"

WAITING = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-5700f659-f45d-4833-b0fb-21cc1d891e12.png")
PLANNING = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-08ded65d-5849-495a-820f-66a2c59d3c2d.png")
EXECUTING = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-5802972e-5a5a-464a-9da1-6950f8563bc6.png")
RESULT = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-b8477a05-6925-4824-a9ee-b3b6a9056ec7.png")
REVISION = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-1a9e4d27-218d-4753-a06c-6c6b57a4c82d.png")
SKILL = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-fa4af923-3975-485d-b513-35200fa0d938.png")
FLOW = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-6740b88c-3db0-4787-be0b-e6110c2fa34e.png")

W, H = 1683.75, 2384.25
BLUE = HexColor("#2D789F")
BLUE_DARK = HexColor("#1F668C")
BLUE_PALE = HexColor("#EAF4F8")
BLUE_LINE = HexColor("#BCD6E3")
INK = HexColor("#243A48")
MUTED = HexColor("#647985")
WHITE = HexColor("#FFFFFF")
MINT = HexColor("#EAF5F2")
GREEN = HexColor("#2F8B74")
ORANGE = HexColor("#C96C32")
ROW = HexColor("#EFF6F8")

FONT = "MalgunGothic"
FONT_BOLD = "MalgunGothicBold"


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT, r"C:\Windows\Fonts\malgun.ttf"))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, r"C:\Windows\Fonts\malgunbd.ttf"))


def top_y(y: float, height: float = 0) -> float:
    return H - y - height


def box(c: canvas.Canvas, x: float, y: float, w: float, h: float, fill, stroke=BLUE_LINE, radius: float = 8) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x, top_y(y, h), w, h, radius, fill=1, stroke=1)


def text(c: canvas.Canvas, value: str, x: float, y: float, size: float, color=INK, bold: bool = False) -> None:
    c.setFillColor(color)
    c.setFont(FONT_BOLD if bold else FONT, size)
    c.drawString(x, H - y - size, value)


def centered(c: canvas.Canvas, value: str, cx: float, y: float, size: float, color=INK, bold: bool = False) -> None:
    font = FONT_BOLD if bold else FONT
    c.setFont(font, size)
    c.setFillColor(color)
    width = pdfmetrics.stringWidth(value, font, size)
    c.drawString(cx - width / 2, H - y - size, value)


def wrap_lines(value: str, max_width: float, size: float, bold: bool = False) -> list[str]:
    font = FONT_BOLD if bold else FONT
    lines: list[str] = []
    for paragraph in value.split("\n"):
        current = ""
        for ch in paragraph:
            candidate = current + ch
            if current and pdfmetrics.stringWidth(candidate, font, size) > max_width:
                lines.append(current)
                current = ch
            else:
                current = candidate
        lines.append(current)
    return lines


def wrapped(c: canvas.Canvas, value: str, x: float, y: float, w: float, size: float, leading: float | None = None, color=INK, bold: bool = False) -> float:
    leading = leading or size * 1.45
    lines = wrap_lines(value, w, size, bold)
    for index, line in enumerate(lines):
        text(c, line, x, y + index * leading, size, color, bold)
    return y + len(lines) * leading


def bullet_list(c: canvas.Canvas, items: list[str], x: float, y: float, w: float, size: float = 16, leading: float = 25) -> float:
    cursor = y
    for item in items:
        text(c, "•", x, cursor, size, BLUE, True)
        lines = wrap_lines(item, w - 24, size)
        for index, line in enumerate(lines):
            text(c, line, x + 22, cursor + index * leading, size, INK)
        cursor += max(1, len(lines)) * leading + 4
    return cursor


def section(c: canvas.Canvas, number: int, title: str, x: float, y: float, w: float, h: float) -> None:
    box(c, x, y, w, h, WHITE, BLUE_LINE, 10)
    c.setFillColor(BLUE)
    c.roundRect(x, top_y(y, 42), w, 42, 9, fill=1, stroke=0)
    text(c, f"{number:02d}   {title}", x + 16, y + 8, 21, WHITE, True)


def image_fit(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float, border: bool = True) -> None:
    with Image.open(path) as image:
        iw, ih = image.size
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
    if border:
        box(c, x, y, w, h, WHITE, BLUE_LINE, 4)
    c.drawImage(ImageReader(str(path)), dx, top_y(dy, dh), dw, dh, mask="auto")


def metric_card(c: canvas.Canvas, x: float, y: float, w: float, title: str, value: str, note: str) -> None:
    box(c, x, y, w, 116, MINT, BLUE_LINE, 7)
    centered(c, title, x + w / 2, y + 12, 15, MUTED, True)
    centered(c, value, x + w / 2, y + 42, 21, INK, True)
    centered(c, note, x + w / 2, y + 76, 16, GREEN, True)


def draw_header(c: canvas.Canvas) -> None:
    c.setFillColor(BLUE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    centered(c, "SKILLA", W / 2, 24, 48, WHITE, True)
    centered(c, "반복작업 스킬로 저장 후 사용하는 로컬 인공지능 에이전트 SKILLA", W / 2, 82, 27, WHITE, True)
    centered(c, "스킬: 반복 작업의 순서·판단 기준·완료 확인 방법을 저장한 재사용 설명서", W / 2, 126, 16, HexColor("#D8EDF5"))
    c.setFillColor(WHITE)
    c.roundRect(24, 24, W - 48, H - 194, 12, fill=1, stroke=0)


def draw_left(c: canvas.Canvas, x: float, w: float) -> None:
    # 01
    y, h = 190, 390
    section(c, 1, "문제와 연구 목적", x, y, w, h)
    text(c, "반복 작업에서 겪는 불편", x + 18, y + 58, 19, BLUE, True)
    cursor = bullet_list(c, [
        "매주 과제 파일을 확인하고 과목별 폴더로 옮기는 과정 반복",
        "같은 요청에도 작업 순서와 분류 기준을 다시 결정",
        "잘못 처리한 파일과 예외를 다음 작업에 반영하기 어려움",
    ], x + 18, y + 88, w - 36, 16, 23)
    text(c, "개발 목표", x + 18, cursor + 6, 19, BLUE, True)
    cursor = bullet_list(c, [
        "작업 순서·판단 기준·완료 확인 방법을 스킬로 저장",
        "다음 요청에서는 현재 파일만 확인하고 저장한 방법 재사용",
        "스킬 사용 전후의 성공률·시간·토큰 사용량 비교",
    ], x + 18, cursor + 35, w - 36, 16, 23)
    box(c, x + 14, y + h - 64, w - 28, 48, BLUE_PALE, BLUE_PALE, 6)
    wrapped(c, "토큰: 인공지능이 요청과 답을 처리할 때 세는 글자·단어의 일부 단위", x + 26, y + h - 53, w - 52, 14, 19, MUTED)

    # 02
    y, h = 600, 490
    section(c, 2, "스킬 사용 전후의 작업 흐름과 하네스", x, y, w, h)
    box(c, x + 14, y + 54, w - 28, 70, BLUE_PALE, BLUE_PALE, 6)
    wrapped(c, "하네스: 모델 호출·승인·도구 실행·중단·결과 확인·기록을 연결하고 관리하는 프로그램 내부 체계", x + 26, y + 65, w - 52, 15, 22, INK, True)
    image_fit(c, FLOW, x + 14, y + 137, w - 28, 304, False)
    centered(c, "스킬이 있으면 저장한 절차를 재사용하고, 없으면 새 계획을 만든다", x + w / 2, y + 451, 14, MUTED)

    # 03
    y, h = 1110, 455
    section(c, 3, "사용 예시와 완료 확인 방법", x, y, w, h)
    box(c, x + 14, y + 56, w - 28, 165, BLUE_PALE, BLUE_PALE, 6)
    text(c, "예시 A  이번 주 과제 자료 정리", x + 26, y + 70, 19, BLUE, True)
    wrapped(c, "저장한 방법  파일 확인 → 과목 구분 → 폴더 이동 → 결과 확인\n매번 확인  파일명·내용·개수, 과목을 알기 어려운 파일\n완료 기준  정답 폴더 비교, 원본 누락 검사", x + 26, y + 104, w - 52, 15, 24)
    box(c, x + 14, y + 236, w - 28, 150, MINT, BLUE_LINE, 6)
    text(c, "예시 B  PDF 문서 열기", x + 26, y + 250, 19, BLUE, True)
    wrapped(c, "저장한 방법  대상 확인 → 프로그램 실행 → 새 창 확인\n매번 확인  문서와 보기 프로그램의 실행 상태\n완료 기준  새 창에서 지정한 문서가 열렸는지 검사", x + 26, y + 284, w - 52, 15, 24)
    wrapped(c, "예외 처리: 모호한 파일은 사용자에게 확인하거나 따로 분리하고, 일반 질문은 PC 실행 명령과 구분", x + 22, y + 404, w - 44, 13.5, 19, MUTED, True)

    # 05
    y, h = 1585, 755
    section(c, 5, "사용 모델과 실행 위치", x, y, w, h)
    model_data = [
        ("STT  음성 인식", "Whisper large-v3-turbo", "사람의 말을 글자로 변환", "사용자 PC · CPU int8"),
        ("LLM  대규모 언어 모델", "NVIDIA NIM z-ai/glm-5.3-flash", "요청·스킬·현재 상태를 읽고 작업 계획 생성", "NVIDIA 모델 호스팅 서비스"),
        ("TTS  음성 합성", "Supertonic 3 int8", "완료·확인 문장을 음성으로 전달", "사용자 PC · CPU"),
    ]
    row_y = y + 58
    for index, (name, model, role, location) in enumerate(model_data):
        fill = BLUE_PALE if index != 1 else MINT
        box(c, x + 14, row_y, w - 28, 188, fill, BLUE_LINE, 7)
        text(c, name, x + 28, row_y + 14, 20, BLUE, True)
        text(c, model, x + 28, row_y + 52, 17, INK, True)
        wrapped(c, f"역할  {role}\n실행 위치  {location}", x + 28, row_y + 85, w - 56, 15, 23, INK)
        row_y += 202
    box(c, x + 14, y + h - 76, w - 28, 55, ROW, ROW, 5)
    wrapped(c, "마이크 원음과 사용자 파일 전체는 외부 모델에 전송하지 않음", x + 28, y + h - 61, w - 56, 14, 20, MUTED, True)


def draw_right(c: canvas.Canvas, x: float, w: float) -> None:
    # 04
    y, h = 190, 1120
    section(c, 4, "SKILLA 실제 사용 화면", x, y, w, h)
    text(c, "요청 상태를 바로 확인", x + 18, y + 57, 18, BLUE, True)
    gap = 12
    card_w = (w - 36 - gap * 2) / 3
    paths = ((WAITING, "1  대기"), (PLANNING, "2  계획"), (EXECUTING, "3  실행"))
    for index, (path, label) in enumerate(paths):
        cx = x + 18 + index * (card_w + gap)
        text(c, label, cx, y + 86, 15, BLUE, True)
        image_fit(c, path, cx, y + 111, card_w, 102, True)
        if index < 2:
            centered(c, "→", cx + card_w + gap / 2, y + 143, 20, BLUE, True)

    text(c, "4  실행 결과 검증", x + 18, y + 235, 18, BLUE, True)
    image_fit(c, RESULT, x + 18, y + 266, w - 36, 366, True)
    centered(c, "실제 파일 개수·이동 결과·원본 누락을 다시 확인", x + w / 2, y + 642, 14, MUTED)

    half = (w - 48) / 2
    text(c, "5  저장된 스킬 요약", x + 18, y + 676, 18, BLUE, True)
    text(c, "6  개정 근거", x + 30 + half, y + 676, 18, BLUE, True)
    image_fit(c, SKILL, x + 18, y + 707, half, 230, True)
    image_fit(c, REVISION, x + 30 + half, y + 707, half, 230, True)
    wrapped(c, "호출 표현·작업 절차·바뀌는 입력·완료 확인 방법 저장", x + 22, y + 951, half - 8, 13.5, 19, MUTED)
    wrapped(c, "실패·예외 기록을 다음 버전 초안의 근거로 사용", x + 34 + half, y + 951, half - 8, 13.5, 19, MUTED)
    box(c, x + 18, y + 1022, w - 36, 72, BLUE_PALE, BLUE_PALE, 6)
    centered(c, "요청 상태 → 결과 검증 → 스킬 승인 → 실패·예외 기록으로 개정", x + w / 2, y + 1044, 16, BLUE_DARK, True)

    # 06
    y, h = 1330, 1010
    section(c, 6, "실험 환경·평가 기준·결과", x, y, w, h)
    box(c, x + 14, y + 56, w - 28, 120, BLUE_PALE, BLUE_PALE, 6)
    text(c, "실험 환경", x + 28, y + 70, 18, BLUE, True)
    wrapped(c, "Windows 11 Home · Ryzen 5 9500F · 메모리 15.4GB · RTX 5060 Ti\n작업 5종 × 3회 × 4조건 = 60회 · 매번 초기 파일 복원 · 개발자 1명", x + 28, y + 101, w - 56, 15, 23)

    text(c, "비교 조건", x + 18, y + 192, 18, BLUE, True)
    conditions = (("SK0", "스킬 없음"), ("SK1", "일반 지침"), ("SK2", "최초 스킬"), ("SK3", "개정 스킬"))
    cond_w = (w - 54) / 4
    for index, (code, label) in enumerate(conditions):
        cx = x + 15 + index * (cond_w + 8)
        box(c, cx, y + 225, cond_w, 72, MINT if index == 3 else ROW, BLUE_LINE, 5)
        centered(c, code, cx + cond_w / 2, y + 237, 18, GREEN if index == 3 else BLUE_DARK, True)
        centered(c, label, cx + cond_w / 2, y + 264, 14, INK)

    # 결과 표
    table_x, table_y, table_w = x + 14, y + 320, w - 28
    cols = [0.13, 0.16, 0.19, 0.18, 0.18, 0.16]
    headers = ["조건", "성공", "평균 시간", "평균 호출", "평균 토큰", "사용자 확인"]
    rows = [
        ["SK0", "10/15", "18.783초", "2.200", "3,759.5", "0.333회"],
        ["SK1", "12/15", "18.614초", "2.467", "4,268.9", "0.600회"],
        ["SK2", "12/15", "25.742초", "3.000", "5,680.9", "0.533회"],
        ["SK3", "14/15", "12.367초", "1.867", "3,135.7", "1.000회"],
    ]
    row_h = 42
    c.setFillColor(BLUE)
    c.rect(table_x, top_y(table_y, row_h), table_w, row_h, fill=1, stroke=0)
    cursor_x = table_x
    for index, header in enumerate(headers):
        cw = table_w * cols[index]
        centered(c, header, cursor_x + cw / 2, table_y + 10, 13.5, WHITE, True)
        cursor_x += cw
    for row_index, row in enumerate(rows):
        ry = table_y + row_h * (row_index + 1)
        fill = MINT if row_index == 3 else (WHITE if row_index % 2 == 0 else ROW)
        c.setFillColor(fill)
        c.rect(table_x, top_y(ry, row_h), table_w, row_h, fill=1, stroke=0)
        cursor_x = table_x
        for index, value in enumerate(row):
            cw = table_w * cols[index]
            centered(c, value, cursor_x + cw / 2, ry + 10, 13.5, INK, row_index == 3)
            cursor_x += cw

    metric_y = table_y + row_h * 5 + 26
    m_gap = 10
    m_w = (w - 28 - m_gap * 2) / 3
    metric_card(c, x + 14, metric_y, m_w, "성공 횟수", "10/15 → 14/15", "+26.7%p")
    metric_card(c, x + 14 + m_w + m_gap, metric_y, m_w, "평균 시간", "18.783 → 12.367초", "34.2% 감소")
    metric_card(c, x + 14 + (m_w + m_gap) * 2, metric_y, m_w, "평균 토큰", "3,759.5 → 3,135.7", "16.6% 감소")

    note_y = metric_y + 136
    box(c, x + 14, note_y, w - 28, 126, ROW, ROW, 6)
    wrapped(c, "평가 기준  성공 여부·실행 시간·모델 호출 수·토큰 사용량·사용자 확인 횟수\n통계 확인  McNemar 검정과 Holm 보정 결과 0.375 > 0.05, 통계적 유의성 미확인\n해석  개정 스킬에서 시간과 토큰이 줄고 성공 횟수가 늘었으나 추가 사용자 시험 필요", x + 28, note_y + 14, w - 56, 14, 21, INK)

    refs_y = note_y + 146
    text(c, "주요 참고논문", x + 18, refs_y, 17, BLUE, True)
    wrapped(c, "[1] Wang et al. (2023) Voyager  [2] Shinn et al. (2023) Reflexion\n[3] Yao et al. (2023) ReAct  [4] Xie et al. (2024) OSWorld", x + 18, refs_y + 31, w - 36, 12.5, 18, MUTED)


def main() -> None:
    register_fonts()
    assets = (WAITING, PLANNING, EXECUTING, RESULT, REVISION, SKILL, FLOW)
    missing = [str(path) for path in assets if not path.exists()]
    if missing:
        raise SystemExit("이미지를 찾을 수 없습니다:\n" + "\n".join(missing))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle("SKILLA 졸업작품 포스터 전체 균형 재설계")
    draw_header(c)
    margin, gutter = 42, 24
    col_w = (W - margin * 2 - gutter) / 2
    draw_left(c, margin, col_w)
    draw_right(c, margin + col_w + gutter, col_w)
    c.showPage()
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
