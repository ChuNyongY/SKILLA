from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "SKILLA_논문_적용_방법론_정리.pdf"
FONT_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

NAVY = colors.HexColor("#173B61")
BLUE = colors.HexColor("#2368A2")
TEAL = colors.HexColor("#168786")
PALE_BLUE = colors.HexColor("#EEF4F9")
PALE_TEAL = colors.HexColor("#EAF6F5")
LIGHT_GRAY = colors.HexColor("#F5F7F9")
MID_GRAY = colors.HexColor("#D7DEE6")
TEXT = colors.HexColor("#202B36")
MUTED = colors.HexColor("#5B6875")


def register_fonts() -> None:
    if not FONT_REGULAR.exists() or not FONT_BOLD.exists():
        raise FileNotFoundError("맑은 고딕 글꼴을 찾을 수 없습니다.")
    pdfmetrics.registerFont(TTFont("Malgun", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("Malgun-Bold", str(FONT_BOLD)))


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def method_block(number: str, title: str, source_method: str, applied: str, not_applied: str, styles: dict[str, ParagraphStyle]):
    heading = Table(
        [[p(number, styles["method_no"]), p(title, styles["method_title"])]],
        colWidths=[18 * mm, 154 * mm],
        rowHeights=[12 * mm],
    )
    heading.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), TEAL),
                ("BACKGROUND", (1, 0), (1, 0), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    body = Table(
        [
            [p("원 논문의 방법", styles["cell_label"]), p(source_method, styles["cell_body"])],
            [p("SKILLA에 적용", styles["cell_label"]), p(applied, styles["cell_body"])],
            [p("적용하지 않음", styles["cell_label"]), p(not_applied, styles["cell_body"])],
        ],
        colWidths=[33 * mm, 139 * mm],
    )
    body.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.45, MID_GRAY),
                ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return KeepTogether([heading, body, Spacer(1, 6 * mm)])


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName="Malgun-Bold", fontSize=24,
            leading=35, alignment=TA_CENTER, textColor=NAVY, spaceAfter=12 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", parent=base["Normal"], fontName="Malgun", fontSize=12,
            leading=20, alignment=TA_CENTER, textColor=MUTED,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="Malgun-Bold", fontSize=17,
            leading=24, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Malgun-Bold", fontSize=12.5,
            leading=18, textColor=BLUE, spaceBefore=4 * mm, spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="Malgun", fontSize=9.6,
            leading=16.2, alignment=TA_JUSTIFY, textColor=TEXT, spaceAfter=3 * mm,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="Malgun", fontSize=8.3,
            leading=13.5, alignment=TA_LEFT, textColor=TEXT,
        ),
        "caption": ParagraphStyle(
            "Caption", parent=base["BodyText"], fontName="Malgun", fontSize=8.1,
            leading=12, alignment=TA_LEFT, textColor=MUTED, spaceBefore=1.5 * mm,
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["BodyText"], fontName="Malgun-Bold", fontSize=8.2,
            leading=12, alignment=TA_CENTER, textColor=colors.white,
        ),
        "table_body": ParagraphStyle(
            "TableBody", parent=base["BodyText"], fontName="Malgun", fontSize=7.9,
            leading=12.3, alignment=TA_LEFT, textColor=TEXT,
        ),
        "method_no": ParagraphStyle(
            "MethodNo", parent=base["BodyText"], fontName="Malgun-Bold", fontSize=10,
            leading=14, alignment=TA_CENTER, textColor=colors.white,
        ),
        "method_title": ParagraphStyle(
            "MethodTitle", parent=base["BodyText"], fontName="Malgun-Bold", fontSize=11.5,
            leading=15, alignment=TA_LEFT, textColor=colors.white,
        ),
        "cell_label": ParagraphStyle(
            "CellLabel", parent=base["BodyText"], fontName="Malgun-Bold", fontSize=8.5,
            leading=13, alignment=TA_LEFT, textColor=NAVY,
        ),
        "cell_body": ParagraphStyle(
            "CellBody", parent=base["BodyText"], fontName="Malgun", fontSize=8.4,
            leading=13.5, alignment=TA_LEFT, textColor=TEXT,
        ),
        "ref": ParagraphStyle(
            "Reference", parent=base["BodyText"], fontName="Malgun", fontSize=7.8,
            leading=12.5, alignment=TA_LEFT, textColor=TEXT, leftIndent=6 * mm,
            firstLineIndent=-6 * mm, spaceAfter=2 * mm,
        ),
    }


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    if doc.page > 1:
        canvas.setStrokeColor(MID_GRAY)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, height - 14 * mm, width - 20 * mm, height - 14 * mm)
        canvas.setFont("Malgun", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, height - 10.5 * mm, "SKILLA 논문 적용 방법론 정리")
        canvas.drawRightString(width - 20 * mm, 11 * mm, f"{doc.page}")
    canvas.restoreState()


def build() -> None:
    register_fonts()
    styles = build_styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=19 * mm, bottomMargin=18 * mm, title="SKILLA 논문 적용 방법론 정리",
        author="SKILLA 프로젝트", subject="관련 연구와 실험 방법론의 적용 범위",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(PageTemplate(id="all", frames=[frame], onPage=draw_page))

    story = []
    story.extend(
        [
            Spacer(1, 54 * mm),
            p("SKILLA 논문에 적용한 방법론", styles["cover_title"]),
            p("스킬 기반 Windows PC 에이전트의 설계 근거와 실험 방법", styles["cover_subtitle"]),
            Spacer(1, 15 * mm),
            p("정리 범위", styles["h2"]),
            p("관련 연구 7편에서 채택한 설계 원리, SKILLA에서 실제 구현한 부분, 적용하지 않은 원 방법, 네 조건 대응 실험과 통계 분석 절차를 구분하여 정리하였다.", styles["body"]),
            Spacer(1, 42 * mm),
            p("2026년 10월", styles["cover_subtitle"]),
            PageBreak(),
        ]
    )

    story.append(p("1 연구 방법의 전체 구조", styles["h1"]))
    story.append(
        p(
            "이 연구는 새로운 대형 언어 모델을 학습시키는 연구가 아니다. 기존 에이전트 연구에서 제안한 행동과 관찰의 반복, 구조화된 도구 호출, 실패 경험 재사용, 스킬 저장과 검색, 실행 기반 평가를 개인 Windows PC 환경에 맞게 결합하였다. 연구의 독립변수는 모델이 아니라 계획기에 제공되는 스킬 정보다.",
            styles["body"],
        )
    )
    summary_rows = [
        ["방법론", "원 연구의 핵심", "SKILLA에 적용한 부분"],
        ["ReAct", "추론, 행동, 관찰의 반복", "계획, 기능 실행, 실제 상태 관찰의 반복"],
        ["Toolformer", "API 호출 시점과 인자의 학습", "기능 이름, 인자, 결과를 갖는 구조화된 호출"],
        ["Reflexion", "언어 피드백을 다음 시도에 재사용", "실패 코드와 검증 근거를 개정 초안 입력으로 사용"],
        ["Voyager", "실행 코드 스킬의 저장, 검색, 개선", "절차형 스킬 저장소, 버전 관리, 검색, 개정"],
        ["UFO", "Windows 앱 선택과 앱 내부 조작 분리", "요청 분석과 앱별 실행 어댑터 분리"],
        ["OSWorld", "초기 상태 복원과 실행 기반 평가", "작업 fixture 복원, 독립 완료 판정"],
        ["AgentBench", "상호작용 환경에서 실제 성공 측정", "성공률, 실패 유형, 비용 지표 기록"],
    ]
    summary = Table(
        [[p(cell, styles["table_head"] if r == 0 else styles["table_body"]) for cell in row] for r, row in enumerate(summary_rows)],
        colWidths=[25 * mm, 66 * mm, 81 * mm], repeatRows=1,
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.45, MID_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ]
        )
    )
    story.extend([summary, Spacer(1, 4 * mm)])
    story.append(p("표 1은 논문의 인용과 실제 구현 사이의 관계를 요약한다. 원 논문의 알고리즘 전체를 복제했다는 뜻이 아니며, 각 연구에서 어떤 원리를 선택했는지 뒤에서 구분한다.", styles["caption"]))
    story.append(PageBreak())

    story.append(p("2 추론과 도구 사용 방법론", styles["h1"]))
    story.append(
        method_block(
            "01", "ReAct의 행동과 관찰 반복",
            "ReAct는 언어 모델이 추론과 환경 행동을 번갈아 수행하고, 행동 결과를 다음 판단에 반영하도록 한다. 질문 답변과 사실 검증에서는 외부 API를 사용하고, ALFWorld와 WebShop에서는 환경과 상호작용한다.",
            "사용자 요청을 형식화된 계획으로 바꾸고 등록된 기능을 한 단계씩 실행한다. 실행 뒤 파일, 프로세스, 창 상태를 다시 관찰한다. 완료 조건이 맞지 않으면 성공으로 기록하지 않고 실패 또는 재계획 경로로 보낸다.",
            "모델의 자유 형식 사고 과정은 저장하지 않는다. 추론 문장을 감사 근거로 사용하지 않고 기능 이름, 인자, 실행 결과와 운영체제 증거만 기록한다.", styles,
        )
    )
    story.append(
        method_block(
            "02", "Toolformer의 구조화된 도구 호출",
            "Toolformer는 소수의 API 예시에서 호출 후보를 만들고 실제 API 결과가 다음 토큰 예측 손실을 줄이는 사례를 선별하여 모델을 미세조정한다. 모델은 어떤 API를 언제 어떤 인자로 호출할지 학습한다.",
            "계획은 기능 이름과 입력 인자를 가진 자료 구조로 제한한다. 기능 등록부가 입력 형식, 최소 위험도와 완료 조건을 관리하고 실행 결과를 다음 단계에 전달한다.",
            "자기지도 자료 생성과 모델 미세조정은 수행하지 않는다. NIM 모델의 가중치를 바꾸지 않으며 기능 허용 여부는 정책 모듈이 결정한다.", styles,
        )
    )
    story.append(PageBreak())

    story.append(p("3 경험 재사용과 스킬 관리 방법론", styles["h1"]))
    story.append(
        method_block(
            "03", "Reflexion의 실패 경험 재사용",
            "Reflexion은 모델 가중치를 바꾸지 않고 실행 평가와 자연어 반성 결과를 기억에 남겨 다음 시도에 제공한다. Actor, Evaluator와 Self-Reflection 모듈을 사용한다.",
            "각 실행에서 성공 여부, 실패 코드, 실행 시간, 호출 수, 토큰 수와 검증 근거를 저장한다. 반복 실패가 확인되면 이 기록을 새 스킬 개정 초안의 입력으로 사용한다.",
            "자유 형식 반성문만으로 기존 스킬을 자동 변경하지 않는다. 개정안은 DRAFT로 저장하며 사용자가 승인한 VERIFIED 버전만 검색과 실행에 사용한다.", styles,
        )
    )
    story.append(
        method_block(
            "04", "Voyager의 스킬 저장소와 반복 개선",
            "Voyager는 Minecraft에서 자동 교육과정, 실행 코드 스킬 저장소와 환경 피드백 기반 코드 개선을 사용한다. 성공한 코드 스킬을 검색해 새 작업의 프롬프트에 제공한다.",
            "반복 작업의 이름, 호출 표현, 작업 순서, 동적 입력, 판단 규칙, 검증 규칙과 허용 기능을 스킬로 저장한다. 요청과 관련된 VERIFIED 스킬을 검색하고 사용한 스킬 식별자와 버전을 실행 기록에 연결한다.",
            "임의 실행 코드를 스킬로 저장하지 않는다. 자동 교육과정과 무인 승인을 사용하지 않는다. 기존 버전을 덮어쓰지 않고 DRAFT, VERIFIED, RETIRED 상태로 이력을 보존한다.", styles,
        )
    )
    story.append(PageBreak())

    story.append(p("4 Windows 에이전트와 실행 기반 평가", styles["h1"]))
    story.append(
        method_block(
            "05", "UFO의 Windows 작업 분리",
            "UFO는 전체 요청과 사용할 앱을 정하는 HostAgent, 선택한 앱의 화면과 컨트롤을 조작하는 AppAgent로 Windows 작업을 나눈다.",
            "요청 분석 단계에서 대상 앱과 기능을 정하고 앱별 실행 어댑터가 실제 동작을 맡는다. 화면 조작이 필요해도 대상 프로세스와 창의 범위를 먼저 고정한다.",
            "HostAgent와 AppAgent를 각각 별도 언어 모델로 실행하는 이중 에이전트 구조는 구현하지 않았다.", styles,
        )
    )
    story.append(
        method_block(
            "06", "OSWorld의 초기 상태와 실행 기반 판정",
            "OSWorld는 실제 운영체제의 작업별 초기 상태를 설정하고, 에이전트의 최종 문장 대신 작업 후 환경 상태를 검사하는 평가 스크립트를 제공한다.",
            "각 조건 실행 전에 같은 임시 작업 자료를 복원하고 초기 상태 해시를 확인한다. 파일 이동은 목적 폴더와 파일 내용을, 앱 실행은 새 프로세스와 대상 창을 실행기와 별도의 판정기로 검사한다.",
            "OSWorld의 369개 작업과 가상 환경 전체를 가져오지 않았다. 자체 Windows 작업 다섯 개에 평가 원리만 적용했다.", styles,
        )
    )
    story.append(
        method_block(
            "07", "AgentBench의 상호작용 성능 평가",
            "AgentBench는 여러 상호작용 환경과 언어 모델을 비교하고 최종 성공률과 실패 원인을 분석한다.",
            "답변 문장의 품질이 아니라 실제 작업 성공 여부를 주 지표로 삼고 실행 시간, 호출 수, 토큰 수, 사용자 확인 횟수와 실패 원인을 함께 기록한다.",
            "여러 모델이나 8개 환경의 대규모 비교는 수행하지 않았다. 같은 모델과 기능을 고정하고 스킬 제공 조건만 비교했다.", styles,
        )
    )
    story.append(PageBreak())

    story.append(p("5 자체 실험에 적용한 방법", styles["h1"]))
    story.append(p("5.1 대응 비교 설계", styles["h2"]))
    story.append(p("같은 작업, 반복 번호, 모델 설정, 기능 목록과 초기 상태를 하나의 블록으로 묶었다. 각 블록 안에서 SK0, SK1, SK2, SK3을 모두 실행하여 작업 난이도와 초기 상태 차이를 줄였다. 조건 실행 순서는 고정 난수로 섞었다.", styles["body"]))
    cond_rows = [
        ["조건", "계획기에 제공한 정보", "비교 목적"],
        ["SK0", "스킬 없음", "기본 실행 성능"],
        ["SK1", "반복 절차를 일반 문장 지침으로 제공", "단순 프롬프트 저장 효과"],
        ["SK2", "구조화한 최초 스킬 제공", "스킬 계약과 검색 효과"],
        ["SK3", "실패 기록을 반영한 개정 스킬 제공", "개정의 추가 효과"],
    ]
    cond = Table(
        [[p(c, styles["table_head"] if r == 0 else styles["table_body"]) for c in row] for r, row in enumerate(cond_rows)],
        colWidths=[22 * mm, 91 * mm, 59 * mm], repeatRows=1,
    )
    cond.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.45, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([cond, Spacer(1, 4 * mm)])
    story.append(p("5.2 독립 완료 판정", styles["h2"]))
    story.append(p("실행기의 성공 반환값을 최종 판정으로 사용하지 않았다. 작업별 판정기가 파일 위치와 내용, 프로세스, 새 창과 시스템 정보 형식을 다시 확인했다. 계획 오류와 실행 오류도 실패에 포함했다.", styles["body"]))
    story.append(p("5.3 측정 지표", styles["h2"]))
    story.append(p("주 지표는 독립 검증을 통과한 작업 성공률이다. 보조 지표는 실행 시간, 대형 언어 모델 호출 수, 입력과 출력 토큰 합, 사용자 확인 횟수다. 비용 감소와 사용자 확인 부담을 함께 해석하였다.", styles["body"]))
    story.append(p("5.4 확인 실험의 자료", styles["h2"]))
    story.append(p("다섯 작업을 세 번씩 반복하여 15개 완전 대응 블록과 60개 관측값을 만들었다. 개발 중 수집한 32개 블록은 구현 수정에 사용된 자료이므로 확인 실험과 합치지 않았다. 실패한 실행도 제외하지 않았다.", styles["body"]))
    story.append(PageBreak())

    story.append(p("6 통계 분석과 재현성 확보", styles["h1"]))
    stats_rows = [
        ["분석", "사용 이유", "논문에서의 적용"],
        ["Wilson 95% 신뢰구간", "15회처럼 작은 표본의 성공 비율 범위를 보고", "각 조건 성공률과 함께 하한과 상한 제시"],
        ["정확 McNemar 검정", "같은 블록의 두 조건에서 성공과 실패가 뒤바뀐 횟수를 비교", "SK3와 SK0, SK1, SK2의 대응 성공 여부 비교"],
        ["Holm 보정", "세 번의 비교에서 다중검정 오류를 줄임", "원 p값을 정렬하여 보정한 p값 보고"],
        ["기술통계", "시간, 호출과 토큰의 평균 차이를 설명", "평균과 기준 조건 대비 감소율 보고"],
        ["SHA-256 무결성", "관측값과 근거 파일의 변경 여부 확인", "60개 근거 파일과 원장, 보고서 해시 대조"],
    ]
    stats = Table(
        [[p(c, styles["table_head"] if r == 0 else styles["table_body"]) for c in row] for r, row in enumerate(stats_rows)],
        colWidths=[37 * mm, 65 * mm, 70 * mm], repeatRows=1,
    )
    stats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.45, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([stats, Spacer(1, 5 * mm)])
    story.append(p("확인 실험에서 SK3의 성공률은 14/15로 가장 높았지만, SK3와 세 기준 조건의 Holm 보정 p값은 모두 0.05보다 컸다. 따라서 논문은 관측된 개선 경향과 통계적 유의성을 구분한다.", styles["body"]))
    story.append(p("자료 수집 과정에서는 작업, 반복 번호, 조건과 모델 설정이 모두 일치할 때만 완전 대응 블록으로 인정했다. 중단된 실행은 원장에서 다음 셀부터 재개했고 완료된 셀을 다시 실행하지 않았다.", styles["body"]))
    story.append(PageBreak())

    story.append(p("7 적용 범위와 해석상의 한계", styles["h1"]))
    limits = [
        ["구분", "논문에서 주장하는 범위", "주장하지 않는 범위"],
        ["모델", "같은 모델에서 스킬 제공 방식의 영향", "새 모델 학습법 또는 모델 자체의 성능 향상"],
        ["스킬", "절차, 판단, 검증 규칙의 저장과 버전 관리", "임의 코드 자동 실행 또는 무인 자기 수정"],
        ["실험", "개발자 1명, Windows PC 1대, 다섯 작업의 확인 결과", "일반 사용자와 모든 PC 환경에 대한 일반화"],
        ["효율", "평균 시간, 호출 수와 토큰 수의 관측 차이", "통계적으로 확정된 우월성 또는 실제 API 비용 절감액"],
        ["제품", "졸업작품 시연이 가능한 연구용 로컬 시제품", "코드 서명을 마친 공개 상용 배포판"],
    ]
    limit_table = Table(
        [[p(c, styles["table_head"] if r == 0 else styles["table_body"]) for c in row] for r, row in enumerate(limits)],
        colWidths=[24 * mm, 76 * mm, 72 * mm], repeatRows=1,
    )
    limit_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.45, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([limit_table, Spacer(1, 6 * mm)])
    story.append(p("핵심 정리", styles["h2"]))
    story.append(p("SKILLA의 방법론은 ReAct의 행동과 관찰 반복, Toolformer의 구조화된 기능 호출, Reflexion의 실패 경험 재사용, Voyager의 스킬 저장과 검색, UFO의 Windows 작업 분리, OSWorld의 실행 기반 판정을 제한된 기능 계약과 사람 승인 절차로 결합한 것이다. 실험에서는 같은 모델과 작업을 유지한 대응 비교로 스킬의 영향을 측정하였다.", styles["body"]))
    story.append(PageBreak())

    story.append(p("8 참고문헌", styles["h1"]))
    refs = [
        "[1] S. Yao et al., ReAct: Synergizing Reasoning and Acting in Language Models, ICLR, 2023. https://arxiv.org/abs/2210.03629",
        "[2] T. Schick et al., Toolformer: Language Models Can Teach Themselves to Use Tools, NeurIPS, 2023. https://arxiv.org/abs/2302.04761",
        "[3] N. Shinn et al., Reflexion: Language Agents with Verbal Reinforcement Learning, NeurIPS, 2023. https://arxiv.org/abs/2303.11366",
        "[4] G. Wang et al., Voyager: An Open-Ended Embodied Agent with Large Language Models, TMLR, 2024. https://arxiv.org/abs/2305.16291",
        "[5] C. Zhang et al., UFO: A UI-Focused Agent for Windows OS Interaction, NAACL, 2025. https://aclanthology.org/2025.naacl-long.26/",
        "[6] T. Xie et al., OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments, NeurIPS, 2024. https://arxiv.org/abs/2404.07972",
        "[7] X. Liu et al., AgentBench: Evaluating LLMs as Agents, ICLR, 2024. https://openreview.net/forum?id=zAdUB0aCTQ",
    ]
    for ref in refs:
        story.append(p(ref, styles["ref"]))
    story.extend([Spacer(1, 8 * mm), p("자료 근거", styles["h2"])])
    story.append(p("SKILLA 논문 본문, 관련 연구 방법론 정리, 확인 실험 report.json과 60개 실행 근거를 바탕으로 작성하였다. 논문에서 구현하지 않은 학습 절차와 대규모 벤치마크는 적용하지 않은 방법으로 구분하였다.", styles["body"]))

    doc.build(story)


if __name__ == "__main__":
    build()
