from __future__ import annotations

import re
from pathlib import Path

from hwpx import HwpxDocument


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "SKILLA_THESIS_DRAFT.md"
REWRITTEN = ROOT / "tmp" / "SKILLA_THESIS_HWP_REWRITE.md"
OUTPUT = ROOT / "output" / "SKILLA_스킬기반_Windows_PC에이전트_졸업논문_예시반영본_v2.hwp"
FIGURE_DIR = ROOT / "output" / "figures"

STYLE_NAMES = {
    "title": "논문 제목",
    "subtitle": "표지 부제",
    "h2": "장 제목",
    "h3": "절 제목",
    "toc_title": "차례 제목",
    "toc_main": "차례 1",
    "toc_sub": "차례 2",
    "caption": "그림 표 제목",
    "bullet": "본문",
    "body": "본문",
}

FIGURES_AFTER_HEADING = {
    "3.1 전체 구조": (FIGURE_DIR / "skilla_system_flow.png", "[그림 3-1] SKILLA의 전체 실행 흐름"),
    "3.2 스킬 계약": (FIGURE_DIR / "skilla_skill_structure.png", "[그림 3-2] 스킬에 저장하는 정보와 실행 시 확인하는 값"),
    "5.1 연구 방법": (FIGURE_DIR / "skilla_experiment_design.png", "[그림 5-1] 네 조건 완전 대응 블록 실험 설계"),
}


METHOD_SECTION = r"""
### 2.4 선행 연구 방법론의 적용 범위

본 연구는 선행 연구의 이름만 인용하지 않고, 각 연구에서 가져온 설계 원리와 적용하지 않은 범위를 구분하였다. 이는 기존 알고리즘 전체를 재현했다는 오해를 막고, SKILLA의 구현을 어떤 근거로 설계했는지 밝히기 위한 것이다.

| 선행 연구 | 가져온 방법 | SKILLA에서의 적용 | 적용하지 않은 범위 |
|---|---|---|---|
| ReAct | 관찰과 행동을 번갈아 수행 | 기능 실행 뒤 Windows 상태를 다시 읽어 다음 단계와 성공 여부를 결정 | 자유 형식 사고 과정의 저장·공개 |
| Toolformer | 언어 모델과 외부 도구 호출의 결합 | 등록된 기능 이름, 입력 형식과 완료 조건을 계획 계약으로 검사 | 도구 사용을 학습시키는 자기지도 학습 |
| Reflexion | 실패 피드백을 다음 시도에 활용 | 실패 코드와 실행 기록을 스킬 개정 후보의 근거로 저장 | 모델 내부 기억의 자동 갱신과 기존 스킬 자동 덮어쓰기 |
| Voyager | 스킬 라이브러리의 검색·재사용·개선 | 스킬 카탈로그, 버전 상태, 검색과 개정 후보 절차로 구현 | 임의 실행 코드 스킬과 자동 교육과정 생성 |
| UFO | Windows 작업의 단계 분해와 응용 프로그램 제어 | 계획기와 기능별 실행기를 분리하고 Windows 기능을 제한적으로 연결 | HostAgent와 AppAgent로 구성된 원 논문의 다중 에이전트 구조 |
| OSWorld | 초기 상태 복원과 실행 결과 기반 평가 | 작업별 고정 자료를 새로 만들고 실행기와 분리된 검증기로 완료 상태를 판정 | 세 운영체제와 수백 개 과제를 포함한 전체 벤치마크 재현 |
| AgentBench | 상호작용형 에이전트의 정량 평가 | 성공률, 실행 시간, 호출 수, 토큰 수와 사용자 확인 횟수를 함께 측정 | 여러 환경과 여러 모델을 포괄하는 원 벤치마크 재현 |

따라서 SKILLA는 ReAct, Toolformer, Reflexion 또는 Voyager를 그대로 구현한 프로그램이 아니다. 관찰-행동 반복, 구조화된 기능 호출, 실패 경험의 재사용과 스킬 라이브러리라는 설계 원리를 Windows 반복 작업에 맞게 결합하였다. 평가에서는 OSWorld와 AgentBench의 실행 기반 평가 원리를 좁은 범위로 적용하였다.

""".strip()


IMPLEMENTATION_SECTION = r"""
### 5.2 방법론과 구현 모듈의 연결

선행 연구에서 가져온 방법이 설명에만 머물지 않도록 실제 구현 파일과 연결하였다. 아래 표는 연구 방법이 실행 경로에 들어간 위치를 나타낸다.

| 적용 방법 | 구현 위치 | 확인 내용 |
|---|---|---|
| 관찰-행동 반복과 구조화된 계획 | `src/skilla_core/planner.py` | 요청, 관찰 결과와 스킬을 받아 등록된 기능으로만 계획 생성 |
| 스킬 검색·재사용과 버전 상태 | `src/skilla_core/skill_runtime.py` | VERIFIED 상태의 스킬만 검색 결과와 실행 문맥에 제공 |
| 실패 경험 저장과 개정 후보 생성 | `src/skilla_core/skill_trace_store.py`, `skill_candidate_evaluation.py` | 실행 흔적을 저장하고 충분한 근거가 있을 때만 DRAFT 후보 생성 |
| 제한된 Windows 기능 실행 | `src/skilla_core/executor_router.py`, `uia_executor.py` | 기능별 실행기로 분기하고 임의 명령 실행을 차단 |
| 실행 결과 기반 평가 | `src/skilla_core/verifier_router.py` | 실행기의 성공 응답과 별도로 파일·프로세스·창 상태를 확인 |
| 대응 실험과 통계 분석 | `src/skilla_core/skill_study_collection.py`, `study_analysis.py` | 블록 일정, 무결성 검사, 성공률과 대응 검정을 계산 |

이 연결은 선행 논문의 모든 구성요소를 복제했다는 뜻이 아니다. 본 연구에 필요한 설계 원리만 선택하여 현재 코드에서 확인할 수 있는 경로로 구현하였다.

""".strip()


EXPERIMENT_SECTION = r"""
### 6.1 연구 방법

실험은 같은 작업·반복 번호 안에서 네 조건을 모두 수행하는 완전 대응 블록 설계로 구성하였다. 독립변수는 계획기에 제공되는 스킬 정보의 형태이며 SK0, SK1, SK2와 SK3의 네 수준이다. 종속변수는 독립 검증을 통과한 성공 여부, 실행 시간, 언어 모델 호출 수, 토큰 사용량과 사용자 확인 횟수다. 모델 ID와 설정, 기능 목록, 작업 자료와 초기 상태는 블록 안에서 같게 유지하였다.

| 구분 | 내용 |
|---|---|
| 실험 설계 | 작업과 반복 번호를 기준으로 한 네 조건 완전 대응 비교 |
| 독립변수 | 스킬 없음, 일반 지침, 최초 스킬, 개정 스킬 |
| 주 종속변수 | 독립 검증을 통과한 작업 성공 여부와 성공률 |
| 보조 종속변수 | 실행 시간, LLM 호출 수, 토큰 수, 사용자 확인 횟수 |
| 통제 항목 | 모델과 생성 설정, 기능 목록, 초기 파일, 완료 판정 기준 |
| 순서 통제 | 고정 난수 초기값으로 조건 순서를 섞고 블록마다 순환 |
| 성공률 분석 | Wilson 95% 신뢰구간, 정확 McNemar 검정, Holm 다중비교 보정 |

이 방법은 한 사용자가 네 조건을 주관적으로 평가하는 사용자 연구가 아니다. 동일한 초기 상태에서 프로그램 조건만 바꾼 개발자 실행 실험이며, 성공 여부는 실행기와 분리된 검증기가 판정한다.

""".strip()


def rewrite_source(text: str) -> str:
    text = text.replace(
        "SKILLA 연구 보고서\n\n2026년 10월",
        "졸업논문 제출본\n\nSKILLA 연구 보고서\n\n2026년 10월",
    )
    text = text.replace(
        "### 2.4 기존 JARVIS 계열과의 차이",
        METHOD_SECTION + "\n\n### 2.5 기존 JARVIS 계열과의 차이",
    )
    text = text.replace(
        "### 5.2 사용자 인터페이스",
        IMPLEMENTATION_SECTION + "\n\n### 5.3 사용자 인터페이스",
    )
    text = text.replace("### 5.3 설치와 자동 시험", "### 5.4 설치와 자동 시험")
    text = text.replace("### 5.4 실험 수집과 무결성", "### 5.5 실험 수집과 무결성")
    text = text.replace(
        "### 6.1 비교 조건",
        EXPERIMENT_SECTION + "\n\n### 6.2 비교 조건",
    )
    text = text.replace("### 6.2 평가 작업", "### 6.3 평가 작업")
    text = text.replace("### 6.3 측정 지표", "### 6.4 측정 지표")
    text = text.replace("### 6.4 개발 자료와 확인 실험", "### 6.5 개발 자료와 확인 실험")
    return restructure_like_reference(text)


def _subsection(text: str, title: str) -> str:
    pattern = rf"^### {re.escape(title)}\s*$\n(.*?)(?=^### |^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"원고에서 절을 찾지 못했습니다: {title}")
    return match.group(1).strip()


def _chapter_body(text: str, title: str) -> str:
    pattern = rf"^## {re.escape(title)}\s*$\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"원고에서 장을 찾지 못했습니다: {title}")
    body = match.group(1).strip()
    return re.sub(r"^### .*?$.*", "", body, count=1, flags=re.MULTILINE | re.DOTALL).strip()


def restructure_like_reference(text: str) -> str:
    """예시 논문의 6장 구성과 장별 개요 문장 형식으로 원고를 재배열한다."""
    front = text.split("## 목차", 1)[0].rstrip()
    references = text[text.index("## 참고문헌"):].strip()

    toc = """## 차 례

1. 서론
  1.1 연구배경 및 목적
  1.2 연구범위
  1.3 연구 질문 및 논문 구성
2. 이론적 배경
  2.1 언어 모델의 추론과 도구 사용
  2.2 실행 경험과 스킬 재사용
  2.3 PC 조작 에이전트와 평가
  2.4 선행 연구 방법론의 적용 범위
  2.5 기존 JARVIS 계열과의 차이
3. 시스템 설계
  3.1 전체 구조
  3.2 스킬 계약
  3.3 최소 권한 실행
  3.4 독립 결과 검증
  3.5 스킬 개정
4. 프로그램 구현
  4.1 실행 환경과 저장 구조
  4.2 방법론과 구현 모듈의 연결
  4.3 사용자 인터페이스
  4.4 설치와 자동 시험
  4.5 실험 수집과 무결성
5. 실험
  5.1 연구 방법
  5.2 비교 조건
  5.3 평가 작업
  5.4 측정 지표
  5.5 개발 자료와 확인 실험
  5.6 개발 단계 결과
  5.7 확인 실험의 조건별 결과
  5.8 작업별 결과
  5.9 대응 성공률 비교
  5.10 실패와 실행 기록 검증
  5.11 연구 질문별 해석
  5.12 실행 하네스가 모델 성능에 미치는 영향
  5.13 제한점
6. 결론
  6.1 연구 결과 요약
  6.2 연구의 의의와 적용 조건
  6.3 후속 연구
참고문헌

## 표 목 차

표 2-1 선행 연구별 방법론 적용 범위
표 3-1 SKILLA의 구성 요소와 역할
표 4-1 선행 연구 방법과 구현 모듈의 연결
표 5-1 대응 실험 설계
표 5-2 비교 조건
표 5-3 평가 작업
표 5-4 확인 실험의 조건별 결과
표 5-5 작업별 성공 횟수
표 5-6 조건 간 대응 성공률 비교
"""
    toc = "\n\n".join(line for line in toc.splitlines() if line.strip())

    toc += """

## 그 림 목 차

그림 3-1 SKILLA의 전체 실행 흐름

그림 3-2 스킬에 저장하는 정보와 실행 시 확인하는 값

그림 5-1 네 조건 완전 대응 블록 실험 설계
"""

    chapter1 = f"""## 1. 서론

이 장은 연구 배경과 목적, 연구 범위, 연구 질문과 논문 구성을 제시한다.

### 1.1 연구배경 및 목적

{_subsection(text, '1.1 연구 배경')}

{_subsection(text, '1.2 연구 목적')}

### 1.2 연구범위

{_subsection(text, '3.2 연구 범위')}

### 1.3 연구 질문 및 논문 구성

{_subsection(text, '3.1 연구 질문')}

2장은 도구 사용 에이전트와 실행 경험 재사용 연구를 정리한다. 3장은 SKILLA의 스킬 계약과 실행 구조를 설명하고, 4장은 실제 구현 모듈과 사용자 인터페이스를 다룬다. 5장은 비교 조건, 평가 작업, 측정 지표와 실험 결과를 제시한다. 6장은 연구 결과와 적용 범위, 후속 연구 과제를 정리한다.
"""

    chapter2 = f"""## 2. 이론적 배경

이 장은 도구 사용 에이전트, 실행 경험의 재사용, PC 조작 에이전트와 본 연구에 적용한 선행 방법론을 정리한다.

### 2.1 언어 모델의 추론과 도구 사용

{_subsection(text, '2.1 언어 모델의 추론과 도구 사용')}

### 2.2 실행 경험과 스킬 재사용

{_subsection(text, '2.2 실행 경험과 스킬 재사용')}

### 2.3 PC 조작 에이전트와 평가

{_subsection(text, '2.3 PC 조작 에이전트와 평가')}

### 2.4 선행 연구 방법론의 적용 범위

{_subsection(text, '2.4 선행 연구 방법론의 적용 범위')}

### 2.5 기존 JARVIS 계열과의 차이

{_subsection(text, '2.5 기존 JARVIS 계열과의 차이')}
"""

    chapter3 = f"""## 3. 시스템 설계

이 장은 SKILLA의 전체 실행 구조와 스킬 계약, 실행 권한, 결과 검증과 스킬 개정 절차를 설명한다.

### 3.1 전체 구조

{_subsection(text, '4.1 전체 구조')}

### 3.2 스킬 계약

{_subsection(text, '4.2 스킬 계약')}

### 3.3 최소 권한 실행

{_subsection(text, '4.3 최소 권한 실행')}

### 3.4 독립 결과 검증

{_subsection(text, '4.4 독립 결과 검증')}

### 3.5 스킬 개정

{_subsection(text, '4.5 스킬 개정')}
"""

    chapter4 = f"""## 4. 프로그램 구현

이 장은 연구 방법이 실제 프로그램의 모듈과 사용자 인터페이스, 설치 및 실험 수집 절차에 구현된 위치를 설명한다.

### 4.1 실행 환경과 저장 구조

{_subsection(text, '5.1 실행 환경과 저장 구조')}

### 4.2 방법론과 구현 모듈의 연결

{_subsection(text, '5.2 방법론과 구현 모듈의 연결')}

### 4.3 사용자 인터페이스

{_subsection(text, '5.3 사용자 인터페이스')}

### 4.4 설치와 자동 시험

{_subsection(text, '5.4 설치와 자동 시험')}

### 4.5 실험 수집과 무결성

{_subsection(text, '5.5 실험 수집과 무결성')}
"""

    experiment_titles = [
        ('5.1 연구 방법', '6.1 연구 방법'), ('5.2 비교 조건', '6.2 비교 조건'),
        ('5.3 평가 작업', '6.3 평가 작업'), ('5.4 측정 지표', '6.4 측정 지표'),
        ('5.5 개발 자료와 확인 실험', '6.5 개발 자료와 확인 실험'),
        ('5.6 개발 단계 결과', '7.1 개발 단계 결과'),
        ('5.7 확인 실험의 조건별 결과', '7.2 확인 실험의 조건별 결과'),
        ('5.8 작업별 결과', '7.3 작업별 결과'),
        ('5.9 대응 성공률 비교', '7.4 대응 성공률 비교'),
        ('5.10 실패와 실행 기록 검증', '7.5 실패와 실행 기록 검증'),
        ('5.11 연구 질문별 해석', '8.1 연구 질문별 해석'),
        ('5.12 실행 하네스가 모델 성능에 미치는 영향', '8.2 실행 하네스가 모델 성능에 미치는 영향'),
        ('5.13 제한점', '8.3 제한점'),
    ]
    chapter5_parts = ["## 5. 실험", "이 장은 비교 조건과 평가 작업, 측정 지표, 실험 결과와 연구 질문별 해석을 제시한다."]
    for new_title, old_title in experiment_titles:
        chapter5_parts.extend([f"### {new_title}", _subsection(text, old_title)])
    chapter5 = "\n\n".join(chapter5_parts)

    conclusion = _chapter_body(text, '9. 결론')
    conclusion_paras = [p.strip() for p in conclusion.split('\n\n') if p.strip()]
    chapter6 = f"""## 6. 결론

이 장은 연구 결과를 요약하고, 결과를 적용할 수 있는 범위와 후속 연구 과제를 정리한다.

### 6.1 연구 결과 요약

{conclusion_paras[0]}

{conclusion_paras[1] if len(conclusion_paras) > 1 else ''}

### 6.2 연구의 의의와 적용 조건

본 연구의 의의는 같은 언어 모델과 기능을 유지한 채 스킬 제공 방식만 바꾸어 실행 결과를 비교할 수 있는 Windows 실험 하네스를 구현한 데 있다. 확인 실험은 개정 스킬이 복수 파일의 분류·이동처럼 판단이 반복되는 작업에서 실행 비용을 줄일 가능성을 보였다. 반면 단순 조회와 폴더 열기에서는 성공률 이점이 없었다. 따라서 스킬은 모든 요청에 일괄 적용하기보다 반복성과 판단 단계가 충분한 작업에 선택적으로 적용해야 한다.

### 6.3 후속 연구

{conclusion_paras[2] if len(conclusion_paras) > 2 else ''}
"""

    return "\n\n<!--PAGEBREAK-->\n\n".join([
        front, toc.strip(), chapter1.strip(), chapter2.strip(), chapter3.strip(),
        chapter4.strip(), chapter5.strip(), chapter6.strip(), references,
    ]) + "\n"


def split_blocks(text: str) -> list[tuple[str, object]]:
    lines = text.splitlines()
    blocks: list[tuple[str, object]] = []
    paragraph: list[str] = []
    i = 0

    def flush() -> None:
        if paragraph:
            blocks.append(("paragraph", " ".join(part.strip() for part in paragraph)))
            paragraph.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush()
            i += 1
            continue
        if line.strip() == "<!--PAGEBREAK-->":
            flush()
            blocks.append(("pagebreak", ""))
            i += 1
            continue
        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            blocks.append(("heading", (level, line[level:].strip())))
            i += 1
            continue
        if line.startswith("|---") or line.startswith("| ---"):
            i += 1
            continue
        if line.startswith("|"):
            flush()
            table_lines: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                candidate = lines[i].strip()
                if not re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", candidate):
                    table_lines.append(candidate)
                i += 1
            rows = [[cell.strip() for cell in row.strip("|").split("|")] for row in table_lines]
            blocks.append(("table", rows))
            continue
        if line.startswith("- "):
            flush()
            blocks.append(("bullet", line[2:].strip()))
            i += 1
            continue
        paragraph.append(line)
        i += 1
    flush()
    return blocks


def clean_inline(text: str) -> str:
    return re.sub(r"[`*]", "", text)


def register_styles(doc: HwpxDocument) -> None:
    """한글 스타일 목록에 논문용 문단 스타일을 등록한다."""
    bases = {
        "논문 제목": 2,
        "표지 부제": 1,
        "장 제목": 2,
        "절 제목": 3,
        "차례 제목": 18,
        "차례 1": 19,
        "차례 2": 20,
        "그림 표 제목": 22,
        "본문": 1,
        "표 내용": 1,
    }
    for name, base_name in bases.items():
        base = doc.styles.resolve(base_name)
        style_id = doc.styles.ensure_style(
            name,
            style_type="PARA",
            eng_name=name,
            para_pr_id_ref=base.para_pr_id_ref,
            char_pr_id_ref=base.char_pr_id_ref,
            lang_id=1042,
        )
        doc.styles.ensure_style(name, next_style_id_ref=style_id)


def add_paragraph(doc: HwpxDocument, text: str, *, kind: str = "body", pagebreak: bool = False) -> None:
    if len(doc.paragraphs) == 1 and not doc.paragraphs[0].text:
        p = doc.paragraphs[0]
    else:
        p = doc.add_paragraph(inherit_style=False)
    p.clear_text()
    text = clean_inline(text)
    p.style_id_ref = doc.styles.resolve(STYLE_NAMES.get(kind, "본문")).id

    if kind == "title":
        p.add_run(text, bold=True, font="한양신명조", size=20)
        fmt = dict(alignment="CENTER", line_spacing_percent=160, spacing_before_pt=30, spacing_after_pt=24)
    elif kind == "h2":
        p.add_run(text, bold=True, font="한양신명조", size=15)
        fmt = dict(alignment="LEFT", line_spacing_percent=160, spacing_before_pt=15, spacing_after_pt=8,
                   keep_with_next=True)
    elif kind == "h3":
        p.add_run(text, bold=True, font="한양신명조", size=11)
        fmt = dict(alignment="LEFT", line_spacing_percent=160, spacing_before_pt=11, spacing_after_pt=5,
                   keep_with_next=True)
    elif kind == "toc_title":
        p.add_run(text, bold=True, font="한양신명조", size=15)
        fmt = dict(alignment="CENTER", line_spacing_percent=160, spacing_before_pt=18, spacing_after_pt=14,
                   keep_with_next=True)
    elif kind == "toc_main":
        p.add_run(text, bold=True, font="한양신명조", size=12)
        fmt = dict(alignment="LEFT", line_spacing_percent=160, spacing_before_pt=2, spacing_after_pt=2)
    elif kind == "toc_sub":
        p.add_run(text, font="한양신명조", size=11)
        fmt = dict(alignment="LEFT", line_spacing_percent=150, indent_left_mm=7,
                   spacing_before_pt=0, spacing_after_pt=1)
    elif kind == "caption":
        p.add_run(text, font="돋움", size=10)
        fmt = dict(alignment="CENTER", line_spacing_percent=145, spacing_before_pt=5,
                   spacing_after_pt=4, keep_with_next=True)
    elif kind == "subtitle":
        p.add_run(text, font="한양신명조", size=12)
        fmt = dict(alignment="CENTER", line_spacing_percent=160, spacing_before_pt=4, spacing_after_pt=6)
    elif kind == "bullet":
        p.add_run("• " + text, font="함초롬바탕", size=10)
        fmt = dict(alignment="JUSTIFY", line_spacing_percent=160, indent_left_mm=5, first_line_indent_mm=-3,
                   spacing_after_pt=3)
    else:
        p.add_run(text, font="함초롬바탕", size=10)
        fmt = dict(alignment="JUSTIFY", line_spacing_percent=160, first_line_indent_mm=3,
                   spacing_after_pt=4, keep_lines=True)

    if pagebreak:
        fmt["page_break_before"] = True
    doc.set_paragraph_format(paragraph_index=len(doc.paragraphs) - 1, **fmt)


def add_figure(doc: HwpxDocument, image_path: Path, caption: str) -> None:
    if not image_path.exists():
        raise FileNotFoundError(f"논문 그림 파일이 없습니다: {image_path}")
    doc.add_picture(
        image_path.read_bytes(),
        "png",
        width_mm=145,
        height_mm=81.56,
        align="CENTER",
        style="본문",
        line_color="#B7B7B7",
    )
    add_paragraph(doc, caption, kind="caption")


def add_table(doc: HwpxDocument, rows: list[list[str]], *, pagebreak: bool = False) -> None:
    if not rows:
        return
    cols = max(len(row) for row in rows)
    if pagebreak:
        add_paragraph(doc, "", pagebreak=True)
    table = doc.add_table(len(rows), cols, inherit_style=False)
    # 표를 담는 최상위 문단도 바탕글로 남기지 않는다. 한글의 스타일
    # 콤보 상자에서 표를 선택했을 때도 논문용 표 스타일이 표시되게 한다.
    doc.paragraphs[-1].style_id_ref = doc.styles.resolve("표 내용").id
    lengths = [max(4, max((len(clean_inline(row[c])) if c < len(row) else 0) for row in rows)) for c in range(cols)]
    table.set_column_widths(lengths)
    for r, row in enumerate(rows):
        for c in range(cols):
            value = clean_inline(row[c]) if c < len(row) else ""
            cell = table.cell(r, c)
            cell.set_text("")
            # python-hwpx cell margins use HWP units (1 mm is about 283 units).
            cell.set_margins(left=340, right=340, top=225, bottom=225)
            cp = cell.paragraphs[0]
            cp.clear_text()
            cp.style_id_ref = doc.styles.resolve("표 내용").id
            cp.add_run(value, bold=(r == 0), font="돋움", size=8.5)
            table.set_cell_borders(r, c, color="#666666", line_type="SOLID")
            if r == 0:
                table.set_cell_shading(r, c, "#E5E5E5")
    add_paragraph(doc, "", kind="body")


def build() -> Path:
    rewritten = rewrite_source(SOURCE.read_text(encoding="utf-8"))
    REWRITTEN.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    REWRITTEN.write_text(rewritten, encoding="utf-8")

    doc = HwpxDocument.new()
    register_styles(doc)
    doc.set_page_setup(
        paper_size="A4",
        orientation="portrait",
        margins_mm={"left": 30, "right": 30, "top": 20, "bottom": 20, "header": 12, "footer": 12},
    )
    try:
        doc.set_page_number(target="footer", page_type="BOTH", format="page", align="CENTER", position="BOTTOM_CENTER")
    except Exception:
        pass

    next_break = False
    title_seen = False
    title_page = True
    chapter_no = 0
    table_no = 0
    table_titles = {
        (2, 1): "선행 연구별 방법론 적용 범위",
        (3, 1): "SKILLA의 구성 요소와 역할",
        (4, 1): "선행 연구 방법과 구현 모듈의 연결",
        (5, 1): "대응 실험 설계",
        (5, 2): "비교 조건",
        (5, 3): "평가 작업",
        (5, 4): "확인 실험의 조건별 결과",
        (5, 5): "작업별 성공 횟수",
        (5, 6): "조건 간 대응 성공률 비교",
    }
    for block_type, value in split_blocks(rewritten):
        if block_type == "pagebreak":
            next_break = True
            title_page = False
            continue
        if block_type == "heading":
            level, heading = value
            if level == 1:
                add_paragraph(doc, heading, kind="title", pagebreak=next_break)
                title_seen = True
            elif level == 2:
                if heading in {"차 례", "표 목 차"}:
                    add_paragraph(doc, heading, kind="toc_title", pagebreak=next_break)
                else:
                    match = re.match(r"(\d+)\.", heading)
                    if match:
                        chapter_no = int(match.group(1))
                        table_no = 0
                    add_paragraph(doc, heading, kind="h2", pagebreak=next_break)
            else:
                add_paragraph(doc, heading, kind="h3", pagebreak=next_break)
                figure = FIGURES_AFTER_HEADING.get(heading)
                if figure:
                    add_figure(doc, figure[0], figure[1])
            next_break = False
        elif block_type == "table":
            table_no += 1
            first = clean_inline(value[0][0]) if value and value[0] else ""
            caption = table_titles.get((chapter_no, table_no), f"{first} 관련 정리")
            add_paragraph(doc, f"[표 {chapter_no}-{table_no}] {caption}", kind="caption", pagebreak=next_break)
            next_break = False
            add_table(doc, value, pagebreak=next_break)
            next_break = False
        elif block_type == "bullet":
            add_paragraph(doc, value, kind="bullet", pagebreak=next_break)
            next_break = False
        else:
            clean_value = str(value).strip()
            if title_seen and title_page:
                kind = "subtitle"
            elif re.match(r"^\d+\.\s", clean_value) or clean_value == "참고문헌":
                kind = "toc_main"
            elif re.match(r"^\d+\.\d+\s", clean_value):
                kind = "toc_sub"
            elif clean_value.startswith("표 "):
                kind = "toc_sub"
            elif clean_value.startswith("그림 "):
                kind = "toc_sub"
            else:
                kind = "body"
            add_paragraph(doc, value, kind=kind, pagebreak=next_break)
            next_break = False

    doc.save_to_path(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
