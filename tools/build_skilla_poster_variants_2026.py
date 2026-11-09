from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Users\YongE\Downloads\SKILLA_포스터_A1_예시색상_2단배치_v14.pptx")
OUT = ROOT / "posters" / "2026_final_variants"
ASSET = ROOT / ".build" / "poster_2026_assets"
UI = ROOT / "output" / "ui_actual"

NAVY = RGBColor(24, 49, 66)
CYAN = RGBColor(25, 198, 221)
TEAL = RGBColor(26, 139, 124)
ORANGE = RGBColor(225, 132, 18)
INK = RGBColor(30, 45, 55)
MUTED = RGBColor(76, 95, 107)
PALE = RGBColor(239, 245, 247)
WHITE = RGBColor(255, 255, 255)
LINE = RGBColor(197, 210, 216)
FONT = "Malgun Gothic"


def crop_ui(src: Path, dst: Path, *, mode: str = "main") -> Path:
    image = Image.open(src).convert("RGB")
    w, h = image.size
    if mode == "main":
        # 제목 표시줄과 큰 하단 여백을 덜어 상태·명령·진행 단계가 포스터에서 보이게 한다.
        box = (8, max(28, int(h * 0.045)), w - 8, min(h - 8, int(h * 0.82)))
    elif mode == "result":
        box = (5, max(25, int(h * 0.035)), w - 5, h - 8)
    else:
        box = (5, max(25, int(h * 0.035)), w - 5, h - 8)
    image.crop(box).save(dst, quality=95)
    return dst


def make_sequence(paths: list[tuple[str, Path]], dst: Path) -> Path:
    cards: list[Image.Image] = []
    for label, path in paths:
        im = Image.open(path).convert("RGB")
        im.thumbnail((1100, 650), Image.Resampling.LANCZOS)
        card = Image.new("RGB", (1140, 760), "white")
        card.paste(im, ((1140 - im.width) // 2, 72))
        draw = ImageDraw.Draw(card)
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 42)
        except OSError:
            font = ImageFont.load_default()
        draw.rounded_rectangle((15, 12, 1125, 70), radius=18, fill=(24, 49, 66))
        draw.text((570, 41), label, font=font, fill="white", anchor="mm")
        cards.append(card)
    canvas = Image.new("RGB", (2300, 1535), "white")
    positions = [(0, 0), (1160, 0), (0, 775), (1160, 775)]
    for card, pos in zip(cards, positions):
        canvas.paste(card, pos)
    draw = ImageDraw.Draw(canvas)
    try:
        arrow_font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 64)
    except OSError:
        arrow_font = ImageFont.load_default()
    draw.text((1148, 382), "→", font=arrow_font, fill=(26, 139, 124), anchor="mm")
    draw.text((1148, 1158), "←", font=arrow_font, fill=(26, 139, 124), anchor="mm")
    draw.text((2220, 765), "↓", font=arrow_font, fill=(26, 139, 124), anchor="mm")
    canvas.save(dst, quality=95)
    return dst


def set_shape_text(shape, text: str, *, size: float | None = None, bold: bool | None = None,
                   color: RGBColor | None = None) -> None:
    shape.text = text
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.name = FONT
            if color is not None:
                run.font.color.rgb = color
            if size is not None:
                run.font.size = Pt(size)
            if bold is not None:
                run.font.bold = bold


def add_box(slide, x, y, w, h, *, fill=WHITE, line=LINE, radius=True):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                                   Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(1.2)
    return shape


def add_text(slide, text, x, y, w, h, *, size=16, bold=False, color=INK,
             align=PP_ALIGN.LEFT, fill=None, valign=MSO_ANCHOR.MIDDLE):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is not None:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    shape.line.fill.background()
    tf = shape.text_frame
    tf.clear()
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.04)
    tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return shape


def add_picture_fit(slide, path: Path, x, y, w, h):
    # 화면의 좌우가 잘리지 않도록 대상 비율의 어두운 캔버스 안에 전체 화면을 맞춘다.
    target_w = max(400, round(900 * w / h))
    target_h = 900
    image = Image.open(path).convert("RGB")
    scale = min(target_w / image.width, target_h / image.height)
    image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                         Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), (3, 13, 24))
    canvas.paste(image, ((target_w - image.width) // 2, (target_h - image.height) // 2))
    fitted = ASSET / f"{path.stem}_{target_w}x{target_h}.jpg"
    canvas.save(fitted, quality=94)
    return slide.shapes.add_picture(str(fitted), Inches(x), Inches(y), width=Inches(w), height=Inches(h))


def update_common(prs: Presentation) -> None:
    slide = prs.slides[0]
    set_shape_text(slide.shapes[1], "SKILLA", size=46, bold=True, color=WHITE)
    set_shape_text(slide.shapes[2], "반복 작업을 스킬로 저장하고 다시 사용하는 Windows 인공지능 에이전트")
    set_shape_text(slide.shapes[32],
                   "Speech to Text, 사람의 말을 글자로 바꾸는 기술\n"
                   "마이크 음성을 실행 명령으로 변환\n"
                   "사용 모델: Whisper large-v3-turbo, CPU int8\n"
                   "실행 위치: 사용자 PC")
    set_shape_text(slide.shapes[34],
                   "Large Language Model, 요청을 읽고 계획을 만드는 인공지능\n"
                   "요청·스킬·현재 상태를 바탕으로 작업 순서 작성\n"
                   "사용 모델: z-ai/glm-5.3-flash\n"
                   "실행 위치: NVIDIA NIM")
    set_shape_text(slide.shapes[36],
                   "Text to Speech, 글자를 말소리로 바꾸는 기술\n"
                   "작업 상태와 완료 안내를 음성으로 전달\n"
                   "사용 모델: Supertonic 3 int8, sherpa-onnx\n"
                   "실행 위치: 사용자 PC")
    set_shape_text(slide.shapes[58],
                   "• 개발 PC: Windows 11 Home / Ryzen 5 9500F 6코어 12스레드\n"
                   "• 메모리 15.4GB / RTX 5060 Ti / 2560×1440 화면\n"
                   "• 계획 모델: z-ai/glm-5.3-flash, 생성 설정과 도구 목록 고정\n"
                   "• 5개 작업 × 3회 × 4조건 = 60개 독립 확인 관측")
    set_shape_text(slide.shapes[59],
                   "• SK0 스킬 없음 / SK1 일반 지침 / SK2 최초 스킬 / SK3 개정 스킬\n"
                   "• 매 조건 전에 같은 초기 파일 복원, 해시와 완료 기준 검사\n"
                   "• 성공은 모델 답변이 아니라 실제 파일·프로세스·창 상태로 판정\n"
                   "• 성공률·시간·LLM 호출·토큰·사용자 확인 횟수 기록")
    set_shape_text(slide.shapes[123],
                   "해석: 확인 실험에서 SK3의 평균 시간과 토큰이 가장 적었지만 보정 검정은 유의하지 않음\n"
                   "개발 PC 1대의 결과이며 음성 인식률·장시간 사용성·일반 사용자 효과는 별도 검증 필요")
    # 구현 검증 결과를 기존 모델 블록 아래 빈 여백에 명시한다.
    add_box(slide, 0.89, 31.25, 10.42, 0.96, fill=PALE, line=TEAL)
    add_text(slide,
             "구현 검증  자동 시험 1,152개 통과·5개 건너뜀 | 배포 파일 1,868개 무결성 확인\n"
             "실제 음성 명령→신규 스킬 후보→음성 승인→등록→실행→독립 검증 완료",
             1.03, 31.32, 10.14, 0.8, size=13.5, bold=True, color=TEAL)


def draw_sequence_panel(slide, paths: dict[str, Path], *, compact=False) -> None:
    # 기존 작은 화면·화살표를 덮고 실제 구현 화면을 다시 배치한다.
    add_box(slide, 11.88, 3.95, 10.82, 14.42, fill=WHITE, line=WHITE, radius=False)
    if compact:
        labels = [
            ("① 대기 — 음성·텍스트 명령 수신", "wait"),
            ("② 계획 — 요청 분석·스킬 검색", "plan"),
            ("③ 실행 — 승인된 기능만 수행", "run"),
            ("④ 검증 — 실제 PC 상태 재확인", "result"),
        ]
        coords = [(12.05, 4.15), (17.42, 4.15), (12.05, 9.2), (17.42, 9.2)]
        for (label, key), (x, y) in zip(labels, coords):
            add_text(slide, label, x, y, 5.1, 0.48, size=15.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
            add_box(slide, x, y + 0.54, 5.1, 3.82, fill=PALE, line=LINE)
            add_picture_fit(slide, paths[key], x + 0.08, y + 0.62, 4.94, 3.5)
            role = {
                "wait": "역할: 입력 대기와 마이크 상태 표시",
                "plan": "역할: 인식한 명령과 진행 단계 표시",
                "run": "역할: 현재 실행 상태와 중단 기능 제공",
                "result": "역할: 독립 검증 근거와 최종 상태 표시",
            }[key]
            add_text(slide, role, x, y + 4.2, 5.1, 0.42, size=12.5, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        add_box(slide, 12.18, 14.18, 10.18, 3.55, fill=PALE, line=TEAL)
        add_picture_fit(slide, paths["skill"], 12.35, 14.36, 5.65, 3.12)
        add_text(slide, "⑤ 작업 후 스킬 검토", 18.18, 14.42, 3.86, 0.55,
                 size=17, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        add_text(slide,
                 "실행 기록에서 성공·실패 원인을 확인\n새 스킬 또는 개정 초안을 사람에게 제시\n승인된 버전만 다음 요청에서 검색·재사용",
                 18.15, 15.22, 3.9, 1.55, size=14.2, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        add_text(slide, "역할: 실행 경험을 다음 작업에서 쓸 수 있는 절차와 검증 규칙으로 저장",
                 12.4, 17.34, 9.55, 0.34, size=12.5, bold=True, color=MUTED, align=PP_ALIGN.CENTER)
    else:
        seq = make_sequence([
            ("① 대기·명령 입력", paths["wait"]),
            ("② 요청 분석·스킬 검색", paths["plan"]),
            ("④ 독립 결과 검증", paths["result"]),
            ("③ 승인된 기능 실행", paths["run"]),
        ], ASSET / "ui_sequence.png")
        slide.shapes.add_picture(str(seq), Inches(12.05), Inches(4.18), width=Inches(10.47), height=Inches(6.99))
        add_box(slide, 12.18, 11.4, 10.18, 6.35, fill=PALE, line=TEAL)
        add_picture_fit(slide, paths["skill"], 12.42, 11.72, 6.0, 5.45)
        add_text(slide, "⑤ 작업 후 스킬 검토", 18.55, 12.0, 3.45, 0.65,
                 size=17, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
        add_text(slide, "성공·실패 기록을 확인하고\n새 스킬 또는 개정 초안을\n사용자가 승인한 뒤 저장",
                 18.55, 13.0, 3.45, 2.0, size=15.5, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        add_text(slide, "역할: 실행 경험을 다음 작업의 재사용 가능한 절차로 바꾸는 화면",
                 18.48, 15.4, 3.6, 1.0, size=13, bold=True, color=MUTED, align=PP_ALIGN.CENTER)


def build_variant(name: str, mode: str, paths: dict[str, Path]) -> Path:
    prs = Presentation(str(SOURCE))
    update_common(prs)
    slide = prs.slides[0]
    if mode == "balanced":
        draw_sequence_panel(slide, paths, compact=True)
        set_shape_text(slide.shapes[39], "SKILLA 실제 사용 화면 — 각 화면의 역할")
    elif mode == "demo":
        draw_sequence_panel(slide, paths, compact=False)
        set_shape_text(slide.shapes[39], "실제 구현 화면으로 본 작업 흐름")
        # UI 블록과 실험 블록의 시각적 무게가 비슷하도록 구분 띠를 추가한다.
        add_text(slide, "실제 시연 화면", 20.1, 3.35, 2.3, 0.5, size=14, bold=True,
                 color=WHITE, align=PP_ALIGN.CENTER, fill=TEAL)
    else:
        # 한 장의 큰 흐름 그림으로 먼 거리에서도 단계와 UI 역할을 읽게 한다.
        add_box(slide, 11.88, 3.95, 10.82, 14.42, fill=WHITE, line=WHITE, radius=False)
        seq = make_sequence([
            ("① 사용자 요청", paths["wait"]),
            ("② 하네스가 계획 구성", paths["plan"]),
            ("③ 등록 기능 실행", paths["run"]),
            ("④ 실제 상태 검증", paths["result"]),
        ], ASSET / "ui_sequence_system.png")
        slide.shapes.add_picture(str(seq), Inches(12.02), Inches(4.1), width=Inches(10.52), height=Inches(7.02))
        add_box(slide, 12.1, 11.36, 10.35, 6.42, fill=PALE, line=TEAL)
        add_text(slide, "하네스가 맡는 일", 12.35, 11.58, 9.85, 0.48, size=17, bold=True,
                 color=NAVY, align=PP_ALIGN.CENTER)
        add_text(slide,
                 "모델 호출 → 스킬 검색 → 계획 형식 검사 → 승인·중단 → 등록 기능 실행 → 실제 상태 검증 → 기록",
                 12.45, 12.18, 9.65, 0.58, size=13.2, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        add_text(slide,
                 "언어 모델은 계획을 제안하지만 실행 권한과 성공 판정은 하네스가 관리\n"
                 "같은 모델도 하네스가 제공하는 스킬·도구·검증 방식에 따라 시스템 성능이 달라짐",
                 12.35, 13.0, 9.85, 0.92, size=13.5, bold=True, color=INK, align=PP_ALIGN.CENTER)
        add_picture_fit(slide, paths["skill"], 12.42, 14.1, 5.8, 3.25)
        add_text(slide, "스킬 관리 화면\n절차·판단 기준·완료 조건·버전 확인\n승인한 버전만 다음 요청에서 재사용",
                 18.35, 14.12, 3.7, 3.15,
                 size=14, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        set_shape_text(slide.shapes[39], "SKILLA 실행 화면과 하네스의 역할")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    prs.save(path)
    return path


def main() -> None:
    ASSET.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    paths = {
        "wait": crop_ui(UI / "SKILLA_실제구현_대기중.png", ASSET / "wait.png"),
        "plan": crop_ui(UI / "SKILLA_실제구현_계획중.png", ASSET / "plan.png"),
        "run": crop_ui(UI / "SKILLA_실제구현_실행중.png", ASSET / "run.png"),
        "result": crop_ui(UI / "SKILLA_실제구현_결과검증.png", ASSET / "result.png", mode="result"),
        "skill": crop_ui(UI / "SKILLA_실제구현_스킬관리.png", ASSET / "skill.png", mode="skill"),
    }
    outputs = [
        build_variant("SKILLA_포스터_A1_안1_균형형.pptx", "balanced", paths),
        build_variant("SKILLA_포스터_A1_안2_UI시연형.pptx", "demo", paths),
        build_variant("SKILLA_포스터_A1_안3_시스템설명형.pptx", "system", paths),
    ]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
