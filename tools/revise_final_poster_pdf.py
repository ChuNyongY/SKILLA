from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / "Downloads" / "SKILLA_졸업작품_포스터_최종본02.pdf"
OUTPUT = ROOT / "output" / "pdf" / "SKILLA_졸업작품_포스터_이미지반영_균형본_v19.pdf"

WAITING = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-5700f659-f45d-4833-b0fb-21cc1d891e12.png")
PLANNING = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-08ded65d-5849-495a-820f-66a2c59d3c2d.png")
EXECUTING = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-5802972e-5a5a-464a-9da1-6950f8563bc6.png")
RESULT = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-b8477a05-6925-4824-a9ee-b3b6a9056ec7.png")
REVISION = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-1a9e4d27-218d-4753-a06c-6c6b57a4c82d.png")
SKILL = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-fa4af923-3975-485d-b513-35200fa0d938.png")
FLOW = Path(r"C:\Users\YongE\AppData\Local\Temp\codex-clipboard-6740b88c-3db0-4787-be0b-e6110c2fa34e.png")

REF_W = 2105.0
REF_H = 2981.0
TEAL = HexColor("#2D789F")
DARK = HexColor("#0B2433")
MUTED = HexColor("#647985")
FONT_NAME = "MalgunGothicBold"


def draw_image_top(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    c.drawImage(ImageReader(str(path)), x, y, w, h, preserveAspectRatio=True, anchor="c", mask="auto")


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"원본 PDF를 찾을 수 없습니다: {SOURCE}")
    assets = (WAITING, PLANNING, EXECUTING, RESULT, REVISION, SKILL, FLOW)
    missing = [str(path) for path in assets if not path.exists()]
    if missing:
        raise SystemExit("이미지 파일을 찾을 수 없습니다:\n" + "\n".join(missing))

    reader = PdfReader(str(SOURCE))
    page = reader.pages[0]
    page_w = float(page.mediabox.width)
    page_h = float(page.mediabox.height)
    sx = page_w / REF_W
    sy = page_h / REF_H

    def rect_top(c: canvas.Canvas, x: float, y: float, w: float, h: float, color) -> None:
        c.setFillColor(color)
        c.setStrokeColor(color)
        c.rect(x * sx, page_h - (y + h) * sy, w * sx, h * sy, fill=1, stroke=0)

    def image_top(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
        draw_image_top(c, path, x * sx, page_h - (y + h) * sy, w * sx, h * sy)

    def text_top(c: canvas.Canvas, text: str, x: float, y: float, size: float, color=DARK) -> None:
        c.setFillColor(color)
        c.setFont(FONT_NAME, size * sx)
        c.drawString(x * sx, page_h - y * sy, text)

    def text_center_top(c: canvas.Canvas, text: str, center_x: float, y: float, size: float, color=DARK) -> None:
        c.setFillColor(color)
        c.setFont(FONT_NAME, size * sx)
        width = pdfmetrics.stringWidth(text, FONT_NAME, size * sx)
        c.drawString(center_x * sx - width / 2, page_h - y * sy, text)

    overlay_buffer = BytesIO()
    pdfmetrics.registerFont(TTFont(FONT_NAME, r"C:\Windows\Fonts\malgunbd.ttf"))
    c = canvas.Canvas(overlay_buffer, pagesize=(page_w, page_h))

    # 기존 흐름도 영역을 사용자가 선택한 비교 그림으로 교체한다.
    rect_top(c, 72, 1140, 958, 395, HexColor("#FFFFFF"))
    image_top(c, FLOW, 72, 1145, 958, 375)

    # 04번 사용 화면 영역을 3개의 상태 화면과 3개의 요약 화면으로 재배치한다.
    rect_top(c, 1070, 355, 970, 1280, HexColor("#FFFFFF"))
    text_top(c, "1  요청 대기", 1090, 395, 18, TEAL)
    text_top(c, "2  계획", 1408, 395, 18, TEAL)
    text_top(c, "3  실행", 1719, 395, 18, TEAL)
    image_top(c, WAITING, 1090, 415, 290, 110)
    image_top(c, PLANNING, 1405, 415, 290, 110)
    image_top(c, EXECUTING, 1720, 415, 290, 110)

    text_top(c, "4  실행 결과 검증", 1090, 575, 20, TEAL)
    image_top(c, RESULT, 1090, 595, 920, 468)

    text_top(c, "5  저장된 스킬 요약", 1090, 1110, 20, TEAL)
    text_top(c, "6  개정 근거", 1560, 1110, 20, TEAL)
    image_top(c, SKILL, 1090, 1130, 445, 242)
    image_top(c, REVISION, 1560, 1130, 450, 227)
    text_top(c, "작업 절차와 바뀌는 입력, 완료 확인 방법을 저장", 1090, 1400, 14, MUTED)
    text_top(c, "실패와 예외 기록을 다음 개정 초안의 근거로 사용", 1560, 1400, 14, MUTED)
    rect_top(c, 1090, 1460, 920, 105, HexColor("#EAF4F8"))
    text_center_top(c, "화면 확인 순서", 1550, 1492, 18, TEAL)
    text_center_top(
        c,
        "요청 상태  →  실행 결과 검증  →  스킬 승인  →  실패·예외 기록으로 개정",
        1550,
        1533,
        16,
        DARK,
    )

    c.save()
    overlay_buffer.seek(0)
    overlay_page = PdfReader(overlay_buffer).pages[0]
    writer = PdfWriter(clone_from=str(SOURCE))
    writer.pages[0].merge_page(overlay_page, over=True, expand=False)
    writer.add_metadata({
        "/Title": "SKILLA 졸업작품 포스터 이미지 반영 균형본",
        "/Subject": "실제 구현 UI와 비교 흐름 반영",
    })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("wb") as stream:
        writer.write(stream)
    print(OUTPUT)


if __name__ == "__main__":
    main()
