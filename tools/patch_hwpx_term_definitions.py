from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


SOURCE = Path(
    r"C:\Users\YongE\Documents\카카오톡 받은 파일\SKILLA_졸업논문_2026_문체용어사실검증_최종본.hwpx"
)
OUTPUT = Path(
    r"C:\Users\YongE\Desktop\SKILLA\deliverables\SKILLA_졸업논문_2026_문체용어사실검증_최종본_본문수정.hwpx"
)
SECTION = "Contents/section0.xml"


REPLACEMENTS = {
    (
        "ReAct는 언어 모델의 추론 과정과 외부 환경에 대한 행동을 번갈아 수행하는 방식을 제안하였다. "
        "언어 모델이 관찰 결과를 다음 판단에 반영한다는 점은 PC 에이전트의 기본 반복 구조와 같다. "
        "Toolformer는 모델이 응용 프로그램 인터페이스(Application Programming Interface, API)를 언제, "
        "어떤 인자로 호출할지 학습할 수 있음을 보였다. API는 프로그램끼리 정해진 형식으로 요청과 결과를 "
        "주고받는 접속 규칙이다. 두 연구는 언어 모델의 판단을 외부 기능 실행과 연결하는 방법을 제시한다."
    ): (
        "ReAct(Reasoning and Acting, 추론과 행동)는 언어 모델이 판단한 내용을 행동으로 옮기고, 그 결과를 "
        "관찰하여 다음 판단에 반영하는 방법이다. 즉, 추론·행동·관찰을 목표를 달성할 때까지 반복한다. "
        "이 구조는 PC 에이전트가 기능을 실행한 뒤 실제 컴퓨터 상태를 다시 확인하는 과정과 연결된다. "
        "Toolformer는 언어 모델이 외부 도구를 호출할 시점과 호출에 넣을 값을 학습하도록 만든 방법이다. "
        "여기서 도구는 계산기, 검색 기능, 응용 프로그램 인터페이스(Application Programming Interface, API)처럼 "
        "모델 밖에서 실제 기능을 수행하는 수단을 뜻한다. API는 프로그램끼리 정해진 형식으로 요청과 결과를 "
        "주고받는 접속 규칙이다. 두 연구는 언어 모델의 판단을 외부 기능 실행과 연결하는 방법을 제시한다."
    ),
    (
        "Reflexion은 실행 결과를 자연어 피드백으로 저장하여 이후 시도에 사용하는 방법을 제안하였다. "
        "Voyager는 Minecraft 환경에서 실행 가능한 코드 형태의 스킬 라이브러리를 만들고, 환경 피드백과 오류를 "
        "이용해 스킬을 개선하였다. 이들 연구는 모델을 다시 학습하지 않고도 이전 실행의 경험을 다음 행동에 "
        "반영할 수 있음을 보여준다."
    ): (
        "Reflexion은 실패 원인과 개선 내용을 자연어 피드백으로 기록하고 다음 시도의 판단 자료로 사용하는 "
        "자기 성찰 방법이다. 모델의 가중치를 다시 학습하는 대신 이전 시도의 언어 기록을 다음 입력에 제공한다. "
        "Voyager는 가상 환경에서 스스로 목표를 정하고, 성공한 작업 코드를 스킬 라이브러리에 저장하여 다음 작업에서 "
        "검색·재사용하는 에이전트다. Voyager는 Minecraft 환경에서 실행 결과와 오류를 이용해 저장된 스킬을 "
        "확장하였다. 이들 연구는 모델을 다시 학습하지 않고도 이전 실행의 경험을 다음 행동에 반영할 수 있음을 보여준다."
    ),
    (
        "UFO는 Windows 응용 프로그램을 관찰하고 제어하는 다중 에이전트 구조를 제시하였다. "
        "OSWorld는 Windows, macOS와 Ubuntu의 실제 응용 프로그램을 포함하는 작업 환경과 실행 기반 평가 방법을 "
        "제공하였다. AgentBench도 상호작용 환경에서 언어 모델 에이전트의 추론과 의사결정을 정량 평가하였다. "
        "이 연구들은 최종 답변의 문장 품질보다 환경에서 목표 상태가 만들어졌는지를 측정해야 한다는 점을 "
        "공통적으로 보여준다."
    ): (
        "UFO(UI-Focused Agent, 사용자 화면 중심 에이전트)는 Windows 화면과 응용 프로그램의 조작 대상을 파악하고 "
        "작업을 나누어 수행하는 다중 에이전트 구조다. 다중 에이전트는 역할이 다른 여러 에이전트가 하나의 작업을 "
        "분담하는 방식을 뜻한다. OSWorld는 Windows, macOS와 Ubuntu의 실제 응용 프로그램에서 컴퓨터 조작 에이전트를 "
        "시험하는 평가 환경이다. 에이전트가 만든 문장이 아니라 작업 뒤의 실제 운영체제 상태로 성공 여부를 판정한다. "
        "AgentBench는 언어 모델 에이전트가 여러 상호작용 환경에서 내린 판단과 수행 결과를 같은 기준으로 비교하는 "
        "평가 체계다. 이 연구들은 최종 답변의 문장 품질보다 환경에서 목표 상태가 만들어졌는지를 측정해야 한다는 "
        "점을 공통적으로 보여준다."
    ),
}


def paragraph_texts(xml_bytes: bytes) -> list[str]:
    root = etree.fromstring(xml_bytes)
    result: list[str] = []
    for paragraph in root.xpath("//*[local-name()='p']"):
        result.append("".join(paragraph.xpath(".//*[local-name()='t']/text()")))
    return result


def patch_section(xml_bytes: bytes) -> bytes:
    text = xml_bytes.decode("utf-8")
    before_paragraphs = paragraph_texts(xml_bytes)
    if any("초록" in paragraph for paragraph in before_paragraphs):
        raise RuntimeError("기준 문서에 초록이 발견되어 작업을 중단했습니다.")

    for old, new in REPLACEMENTS.items():
        if before_paragraphs.count(old) != 1:
            raise RuntimeError(f"교체할 본문 문단을 정확히 하나 찾지 못했습니다: {old[:30]}")

        old_xml = old.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        new_xml = new.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        paragraph_pattern = re.compile(
            r"(<hp:p\b[^>]*>.*?<hp:t>)"
            + re.escape(old_xml)
            + r"(</hp:t>.*?)(<hp:linesegarray>.*?</hp:linesegarray>)(.*?</hp:p>)",
            flags=re.DOTALL,
        )
        text, count = paragraph_pattern.subn(
            lambda match: match.group(1) + new_xml + match.group(2) + match.group(4),
            text,
            count=1,
        )
        if count != 1:
            raise RuntimeError(f"본문 문단 XML 교체에 실패했습니다: {old[:30]}")

    patched = text.encode("utf-8")
    after_paragraphs = paragraph_texts(patched)
    if any("초록" in paragraph for paragraph in after_paragraphs):
        raise RuntimeError("수정 결과에 초록이 추가되었습니다.")
    for old, new in REPLACEMENTS.items():
        if old in after_paragraphs or after_paragraphs.count(new) != 1:
            raise RuntimeError(f"본문 교체 검증에 실패했습니다: {new[:30]}")
    return patched


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(SOURCE, "r") as source_zip:
        original_entries = {info.filename: source_zip.read(info.filename) for info in source_zip.infolist()}
        infos = source_zip.infolist()

    original_section = original_entries[SECTION]
    patched_section = patch_section(original_section)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".hwpx", dir=OUTPUT.parent) as temporary:
        temporary_path = Path(temporary.name)

    try:
        with zipfile.ZipFile(temporary_path, "w") as output_zip:
            for info in infos:
                data = patched_section if info.filename == SECTION else original_entries[info.filename]
                output_zip.writestr(info, data)
        shutil.move(str(temporary_path), str(OUTPUT))
    finally:
        temporary_path.unlink(missing_ok=True)

    with zipfile.ZipFile(OUTPUT, "r") as result_zip:
        result_entries = {info.filename: result_zip.read(info.filename) for info in result_zip.infolist()}

    if result_entries.keys() != original_entries.keys():
        raise RuntimeError("HWPX 내부 파일 구성이 달라졌습니다.")
    changed = [name for name in original_entries if original_entries[name] != result_entries[name]]
    if changed != [SECTION]:
        raise RuntimeError(f"본문 이외의 내부 파일이 변경되었습니다: {changed}")

    print(OUTPUT)
    print(f"changed_entries={changed}")
    print("abstract_present=False")


if __name__ == "__main__":
    main()
