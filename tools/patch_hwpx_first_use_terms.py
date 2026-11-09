from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

from lxml import etree


SOURCE = Path(
    r"C:\Users\YongE\Desktop\SKILLA\deliverables\SKILLA_졸업논문_2026_문체용어사실검증_최종본_본문수정.hwpx"
)
OUTPUT = Path(
    r"C:\Users\YongE\Desktop\SKILLA\deliverables\SKILLA_졸업논문_2026_문체용어사실검증_최종본_본문용어최종보완.hwpx"
)
SECTION = "Contents/section0.xml"


REPLACEMENTS = {
    "PC 에이전트는 사용자의 자연어 요청을 실행 가능한 단계로 바꾸고 파일 시스템, 응용 프로그램과 웹 브라우저를 조작한다. 언어 모델은 같은 요청에도 다른 계획을 만들 수 있고, 현재 화면과 파일 상태도 실행할 때마다 달라진다. 실행 결과를 모델의 답변만으로 판단하면 실제 파일 상태와 성공 기록이 어긋날 수 있다.":
    "PC 에이전트는 사용자의 자연어 요청을 실행 가능한 단계로 바꾸고 파일 시스템, 응용 프로그램과 웹 브라우저를 조작하는 프로그램이다. 로컬 인공지능 에이전트는 반복 작업 정보의 저장·검색, PC 기능 실행과 결과 확인을 사용자의 PC에서 수행한다. 대규모 언어 모델(Large Language Model, LLM; 이하 언어 모델)은 자연어 요청의 뜻을 파악하고 실행 계획을 만드는 인공지능 모델이다. 언어 모델은 같은 요청에도 다른 계획을 만들 수 있고, 현재 화면과 파일 상태도 실행할 때마다 달라진다. 실행 결과를 모델의 답변만으로 판단하면 실제 파일 상태와 성공 기록이 어긋날 수 있다.",

    "반복 작업에서는 이 문제가 더 분명하다. 예를 들어 “이번 주 과제 자료를 정리해 줘”라는 요청은 파일 찾기, 과목 판단, 폴더 이동과 결과 확인을 거친다. 다음 주에는 파일명과 개수가 바뀌지만 분류 기준과 확인 방법은 반복된다. 계획 전체를 매번 다시 생성하면 동일한 판단에 호출과 토큰을 다시 사용한다. 반대로 과거 파일명과 경로까지 고정하면 환경이 바뀌었을 때 잘못된 대상을 처리한다.":
    "반복 작업에서는 이 문제가 더 분명하다. 예를 들어 “이번 주 과제 자료를 정리해 줘”라는 요청은 파일 찾기, 과목 판단, 폴더 이동과 결과 확인을 거친다. 다음 주에는 파일명과 개수가 바뀌지만 분류 기준과 확인 방법은 반복된다. 계획 전체를 매번 다시 생성하면 동일한 판단에 모델 호출과 토큰을 다시 사용한다. 모델 호출은 언어 모델에 요청을 보내 응답을 받는 한 번의 과정을 뜻하고, 토큰은 모델이 입력과 출력을 처리할 때 사용하는 글자 또는 단어 조각 단위다. 반대로 과거 파일명과 경로까지 고정하면 환경이 바뀌었을 때 잘못된 대상을 처리한다.",

    "본 연구는 반복되는 작업 방법과 실행할 때마다 바뀌는 값을 분리하였다. 절차와 판단 기준은 스킬에 저장하고, 파일명과 경로는 실행 직전에 다시 관찰한다. 성공과 실패는 실제 운영체제 상태로 확인하며, 반복 실패가 확인되면 기존 버전을 보존한 채 개정 초안을 만든다.":
    "본 연구는 반복되는 작업 방법과 실행할 때마다 바뀌는 값을 분리하였다. 여기서 스킬은 반복 작업의 절차, 판단 기준, 완료 확인 방법과 사용할 수 있는 기능을 묶어 저장한 재사용 단위다. 절차와 판단 기준은 스킬에 저장하고, 파일명과 경로는 실행 직전에 다시 관찰한다. 성공과 실패는 실제 운영체제 상태로 확인하며, 반복 실패가 확인되면 기존 버전을 보존한 채 개정 초안을 만든다.",

    "SK0~SK3 비교 실험은 조건마다 같은 명령 문장을 제공하기 위해 텍스트 입력을 사용하였다. 음성 경로는 실제 사용자 발화 네 건으로 별도 기능 검사를 수행하였다. 음성을 글자로 바꾸고, 신규 스킬 후보 표시와 음성 승인, 등록·실행·독립 검증까지 이어지는 흐름을 확인하였다. 음성 검사의 범위는 네 발화의 전사 결과와 기능 연결 상태다.":
    "비교 실험의 네 조건은 SK0(스킬 없음), SK1(일반 문장 지침), SK2(처음 작성한 최초 스킬), SK3(실패 원인과 개선 규칙을 추가한 개정 스킬)로 구분하였다. 조건마다 같은 명령 문장을 제공하기 위해 텍스트 입력을 사용하였다. 음성 경로는 실제 사용자 발화 네 건으로 별도 기능 검사를 수행하였다. 음성을 글자로 바꾸고, 신규 스킬 후보 표시와 음성 승인, 등록·실행·독립 검증까지 이어지는 흐름을 확인하였다. 독립 검증은 실행기의 완료 보고만 믿지 않고 실제 파일·프로세스·창 상태를 별도의 검증기가 다시 확인하는 절차다. 음성 검사의 범위는 네 발화의 전사 결과와 기능 연결 상태다.",

    "• 연구 질문 2: 스킬 재사용은 실행 시간, 언어 모델 호출 수와 토큰 사용량을 줄이는가?":
    "• 연구 질문 2: 스킬 재사용은 실행 시간, 언어 모델에 요청을 보낸 횟수인 호출 수와 토큰 사용량을 줄이는가?",

    "ReAct(Reasoning and Acting, 추론과 행동)는 언어 모델이 판단한 내용을 행동으로 옮기고, 그 결과를 관찰하여 다음 판단에 반영하는 방법이다. 즉, 추론·행동·관찰을 목표를 달성할 때까지 반복한다. 이 구조는 PC 에이전트가 기능을 실행한 뒤 실제 컴퓨터 상태를 다시 확인하는 과정과 연결된다. Toolformer는 언어 모델이 외부 도구를 호출할 시점과 호출에 넣을 값을 학습하도록 만든 방법이다. 여기서 도구는 계산기, 검색 기능, 응용 프로그램 인터페이스(Application Programming Interface, API)처럼 모델 밖에서 실제 기능을 수행하는 수단을 뜻한다. API는 프로그램끼리 정해진 형식으로 요청과 결과를 주고받는 접속 규칙이다. 두 연구는 언어 모델의 판단을 외부 기능 실행과 연결하는 방법을 제시한다.":
    "ReAct(Reasoning and Acting, 추론과 행동)는 언어 모델이 판단한 내용을 행동으로 옮기고, 그 결과를 관찰하여 다음 판단에 반영하는 방법이다[1]. 즉, 추론·행동·관찰을 목표를 달성할 때까지 반복한다. 이 구조는 PC 에이전트가 기능을 실행한 뒤 실제 컴퓨터 상태를 다시 확인하는 과정과 연결된다. Toolformer는 언어 모델이 외부 도구를 호출할 시점과 호출에 넣을 값을 학습하도록 만든 방법이다[2]. 여기서 도구는 계산기, 검색 기능, 응용 프로그램 인터페이스(Application Programming Interface, API)처럼 모델 밖에서 실제 기능을 수행하는 수단을 뜻한다. API는 프로그램끼리 정해진 형식으로 요청과 결과를 주고받는 접속 규칙이다. 두 연구는 언어 모델의 판단을 외부 기능 실행과 연결하는 방법을 제시한다.",

    "Reflexion은 실패 원인과 개선 내용을 자연어 피드백으로 기록하고 다음 시도의 판단 자료로 사용하는 자기 성찰 방법이다. 모델의 가중치를 다시 학습하는 대신 이전 시도의 언어 기록을 다음 입력에 제공한다. Voyager는 가상 환경에서 스스로 목표를 정하고, 성공한 작업 코드를 스킬 라이브러리에 저장하여 다음 작업에서 검색·재사용하는 에이전트다. Voyager는 Minecraft 환경에서 실행 결과와 오류를 이용해 저장된 스킬을 확장하였다. 이들 연구는 모델을 다시 학습하지 않고도 이전 실행의 경험을 다음 행동에 반영할 수 있음을 보여준다.":
    "Reflexion은 실패 원인과 개선 내용을 자연어 피드백으로 기록하고 다음 시도의 판단 자료로 사용하는 자기 성찰 방법이다[3]. 모델의 가중치를 다시 학습하는 대신 이전 시도의 언어 기록을 다음 입력에 제공한다. Voyager는 가상 환경에서 스스로 목표를 정하고, 성공한 작업 코드를 스킬 라이브러리에 저장하여 다음 작업에서 검색·재사용하는 에이전트다[4]. Voyager는 Minecraft 환경에서 실행 결과와 오류를 이용해 저장된 스킬을 확장하였다. 이들 연구는 모델을 다시 학습하지 않고도 이전 실행의 경험을 다음 행동에 반영할 수 있음을 보여준다.",

    "Voyager는 실행 가능한 코드를 스킬로 저장한다. SKILLA는 작업 절차, 동적 입력, 판단 규칙, 검증 규칙과 허용 기능 목록을 스킬로 저장하고 실제 동작은 등록된 기능이 담당한다. 개정안은 초안으로 보관하며, 사람이 승인한 버전을 검색 대상으로 삼는다.":
    "Voyager는 실행 가능한 코드를 스킬로 저장한다. SKILLA는 작업 절차, 동적 입력, 판단 규칙, 검증 규칙과 허용 기능 목록을 스킬로 저장하고 실제 동작은 등록된 기능이 담당한다. 동적 입력은 파일명·경로·파일 수처럼 실행할 때마다 달라지는 값이며, 허용 기능 목록은 해당 스킬이 사용할 수 있도록 미리 제한한 PC 기능의 목록이다. 개정안은 초안으로 보관하며, 사람이 승인한 버전을 검색 대상으로 삼는다.",

    "UFO(UI-Focused Agent, 사용자 화면 중심 에이전트)는 Windows 화면과 응용 프로그램의 조작 대상을 파악하고 작업을 나누어 수행하는 다중 에이전트 구조다. 다중 에이전트는 역할이 다른 여러 에이전트가 하나의 작업을 분담하는 방식을 뜻한다. OSWorld는 Windows, macOS와 Ubuntu의 실제 응용 프로그램에서 컴퓨터 조작 에이전트를 시험하는 평가 환경이다. 에이전트가 만든 문장이 아니라 작업 뒤의 실제 운영체제 상태로 성공 여부를 판정한다. AgentBench는 언어 모델 에이전트가 여러 상호작용 환경에서 내린 판단과 수행 결과를 같은 기준으로 비교하는 평가 체계다. 이 연구들은 최종 답변의 문장 품질보다 환경에서 목표 상태가 만들어졌는지를 측정해야 한다는 점을 공통적으로 보여준다.":
    "UFO(UI-Focused Agent, 사용자 화면 중심 에이전트)는 Windows 화면과 응용 프로그램의 조작 대상을 파악하고 작업을 나누어 수행하는 다중 에이전트 구조다[5]. 다중 에이전트는 역할이 다른 여러 에이전트가 하나의 작업을 분담하는 방식을 뜻한다. OSWorld는 Windows, macOS와 Ubuntu의 실제 응용 프로그램에서 컴퓨터 조작 에이전트를 시험하는 평가 환경이다[6]. 에이전트가 만든 문장이 아니라 작업 뒤의 실제 운영체제 상태로 성공 여부를 판정한다. AgentBench는 언어 모델 에이전트가 여러 상호작용 환경에서 내린 판단과 수행 결과를 같은 기준으로 비교하는 평가 체계다[7]. 이 연구들은 최종 답변의 문장 품질보다 환경에서 목표 상태가 만들어졌는지를 측정해야 한다는 점을 공통적으로 보여준다.",

    "등록된 기능 이름, 입력 형식과 완료 조건을 계획 계약으로 검사":
    "등록된 기능 이름, 입력 형식과 완료 조건을 계획 형식 규칙으로 검사",
    "도구 학습 대신 등록 기능 호출 계약":
    "도구 학습 대신 등록 기능 호출 규칙",
    "실행 가능한 Windows 기능과 입력 계약 관리":
    "실행 가능한 Windows 기능과 입력 형식 규칙 관리",
    "VERIFIED 상태의 스킬만 검색 결과와 실행 문맥에 제공":
    "VERIFIED 상태의 스킬만 검색 결과와 계획 생성 정보에 제공",

    "스킬은 제목과 호출 표현, 반복 절차, 동적 입력, 판단 규칙, 검증 규칙, 허용 기능 목록과 버전 상태로 구성된다. 예를 들어 과제 자료 정리 스킬은 “파일 찾기 → 과목 판단 → 과목별 폴더로 이동 → 결과 확인”이라는 순서를 저장한다. 이번 주 파일명, 파일 수와 현재 폴더는 저장하지 않고 매번 다시 읽는다.":
    "스킬은 제목과 호출 표현, 반복 절차, 동적 입력, 판단 규칙, 검증 규칙, 허용 기능 목록과 버전 상태로 구성된다. 호출 표현은 사용자의 명령과 저장된 스킬을 연결하기 위해 등록한 대표 문장이나 핵심 표현이다. 예를 들어 과제 자료 정리 스킬은 “파일 찾기 → 과목 판단 → 과목별 폴더로 이동 → 결과 확인”이라는 순서를 저장한다. 이번 주 파일명, 파일 수와 현재 폴더는 저장하지 않고 매번 다시 읽는다.",

    "프로그램은 Python 기반 Windows 응용 프로그램으로 구현하였다. 개발 PC는 Windows 11 Home, AMD Ryzen 5 9500F 6코어 12스레드, 메모리 15.4GB, NVIDIA GeForce RTX 5060 Ti로 구성하였고 주 화면은 2560×1440 해상도를 사용하였다. 스킬 카탈로그와 사용 기록은 한 개의 파일로 자료를 관리하는 로컬 데이터베이스 SQLite에 저장한다. 실험 관측값은 한 줄에 한 건의 JSON 자료를 기록하는 JSONL 원장에 먼저 추가하고, 일정이 끝난 뒤 분석용 JSON 파일로 내보낸다. 각 결과 근거 파일은 SHA-256 해시 함수로 계산한 값과 관측값을 연결하여 내용 변경 여부를 확인한다.":
    "프로그램은 Python 기반 Windows 응용 프로그램으로 구현하였다. 개발 PC는 Windows 11 Home, AMD Ryzen 5 9500F 6코어 12스레드, 메모리 15.4GB, NVIDIA GeForce RTX 5060 Ti로 구성하였고 주 화면은 2560×1440 해상도를 사용하였다. 스킬 카탈로그와 사용 기록은 한 개의 파일로 자료를 관리하는 로컬 데이터베이스 SQLite에 저장한다. JSON(JavaScript Object Notation)은 항목 이름과 값을 짝지어 기록하는 자료 형식이고, JSONL(JSON Lines)은 JSON 자료를 한 줄에 한 건씩 이어서 저장하는 형식이다. 실험 관측값은 JSONL 원장에 먼저 추가하고, 일정이 끝난 뒤 분석용 JSON 파일로 내보낸다. 각 결과 근거 파일은 SHA-256 해시 함수로 계산한 값과 관측값을 연결하여 내용 변경 여부를 확인한다.",

    "실험은 같은 작업·반복 번호 안에서 네 조건을 모두 수행하는 완전 대응 블록 설계로 구성하였다. 완전 대응 블록은 같은 작업을 모든 조건에서 실행하고 결과를 서로 짝지어 비교하는 묶음이다. 계획기에 제공되는 스킬 정보의 형태를 독립변수로 두고 SK0, SK1, SK2와 SK3의 네 수준을 사용하였다. 측정 결과인 종속변수는 독립 검증을 통과한 성공 여부, 실행 시간, 언어 모델 호출 수, 토큰 사용량과 사용자 확인 횟수다. 모델 식별자와 설정, 기능 목록, 작업 자료와 초기 상태는 블록 안에서 같게 유지하였다.":
    "실험은 같은 작업·반복 번호 안에서 네 조건을 모두 수행하는 완전 대응 블록 설계로 구성하였다. 완전 대응 블록은 같은 작업을 모든 조건에서 실행하고 결과를 서로 짝지어 비교하는 묶음이다. 계획기에 제공되는 스킬 정보의 형태를 원인으로 조절하는 독립변수로 두고, 측정되는 결과인 종속변수는 독립 검증을 통과한 성공 여부, 실행 시간, 언어 모델 호출 수, 토큰 사용량과 사용자 확인 횟수로 정하였다. 사용자 확인 횟수는 실행 중 승인이나 추가 정보가 필요해 사용자가 응답한 횟수다. 모델 식별자와 설정, 기능 목록, 작업 자료와 초기 상태는 블록 안에서 같게 유지하였다.",

    "Wilson 95% 신뢰구간, 정확 McNemar 검정, Holm 다중비교 보정":
    "Wilson 95% 신뢰구간(소표본 성공률의 범위), 정확 McNemar 검정(짝지은 성공·실패 비교), Holm 보정(여러 비교의 우연한 오류 조정)",
    "단순 프롬프트 저장 효과":
    "일반 문장 지침 저장 효과",

    "SK3의 성공률은 SK0보다 0.267, SK1과 SK2보다 각각 0.133 높았다. 평균 실행 시간은 SK0보다 34.2%, SK1보다 33.6%, SK2보다 52.0% 짧았다. 평균 토큰 수는 각 조건보다 16.6%, 26.6%, 44.8% 적었다. 반면 SK3의 사용자 확인 횟수는 평균 1.0회로 가장 많았다. 실행 비용 감소와 사용자 확인 부담이 함께 나타났다.":
    "SK3의 성공률은 SK0보다 0.267, SK1과 SK2보다 각각 0.133 높았다. 평균 실행 시간은 SK0보다 34.2%, SK1보다 33.6%, SK2보다 52.0% 짧았다. 평균 토큰 수는 각 조건보다 16.6%, 26.5%, 44.8% 적었다. 반면 SK3의 사용자 확인 횟수는 평균 1.0회로 가장 많았다. 실행 비용 감소와 사용자 확인 부담이 함께 나타났다.",
}


def paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//*[local-name()='t']/text()"))


def remove_line_segments(paragraph: etree._Element) -> None:
    for item in paragraph.xpath("./*[local-name()='linesegarray']"):
        paragraph.remove(item)


def replace_paragraph_text(root: etree._Element, old: str, new: str) -> int:
    matches = [p for p in root.xpath("//*[local-name()='p']") if paragraph_text(p) == old]
    if len(matches) != 1:
        raise RuntimeError(f"교체 대상을 정확히 하나 찾지 못했습니다({len(matches)}): {old[:50]}")
    paragraph = matches[0]
    text_nodes = paragraph.xpath(".//*[local-name()='t']")
    if not text_nodes:
        raise RuntimeError(f"텍스트 노드가 없습니다: {old[:50]}")
    text_nodes[0].text = new
    for node in text_nodes[1:]:
        node.text = ""
    remove_line_segments(paragraph)
    return 1


def paragraph_texts(xml_bytes: bytes) -> list[str]:
    root = etree.fromstring(xml_bytes)
    return [paragraph_text(p) for p in root.xpath("//*[local-name()='p']")]


def patch_section(xml_bytes: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=False)
    root = etree.fromstring(xml_bytes, parser)
    before = [paragraph_text(p) for p in root.xpath("//*[local-name()='p']")]
    if any("초록" in text for text in before):
        raise RuntimeError("기준 문서에 초록이 발견되어 작업을 중단했습니다.")

    for old, new in REPLACEMENTS.items():
        replace_paragraph_text(root, old, new)

    after = [paragraph_text(p) for p in root.xpath("//*[local-name()='p']")]
    if any("초록" in text for text in after):
        raise RuntimeError("수정 결과에 초록이 추가되었습니다.")
    for old, new in REPLACEMENTS.items():
        if old in after or after.count(new) != 1:
            raise RuntimeError(f"교체 결과 검증 실패: {new[:50]}")
    declaration_end = xml_bytes.find(b"?>")
    if declaration_end < 0:
        raise RuntimeError("section0.xml의 XML 선언을 찾지 못했습니다.")
    original_declaration = xml_bytes[: declaration_end + 2]
    serialized_body = etree.tostring(root, encoding="utf-8", xml_declaration=False)
    return original_declaration + serialized_body


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(SOURCE, "r") as source_zip:
        infos = source_zip.infolist()
        original_entries = {info.filename: source_zip.read(info.filename) for info in infos}

    before_paragraphs = paragraph_texts(original_entries[SECTION])
    patched_section = patch_section(original_entries[SECTION])
    after_paragraphs = paragraph_texts(patched_section)

    if len(before_paragraphs) != len(after_paragraphs):
        raise RuntimeError("문단 수가 바뀌었습니다.")
    changed_indices = [
        index
        for index, (old, new) in enumerate(zip(before_paragraphs, after_paragraphs))
        if old != new
    ]
    if any(index < 93 for index in changed_indices):
        raise RuntimeError(f"표지·차례 영역이 변경되었습니다: {changed_indices}")

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
    changed_entries = [
        name for name in original_entries if original_entries[name] != result_entries[name]
    ]
    if changed_entries != [SECTION]:
        raise RuntimeError(f"본문 이외의 내부 파일이 변경되었습니다: {changed_entries}")

    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest().upper()
    print(f"output={OUTPUT}")
    print(f"changed_entries={changed_entries}")
    print(f"changed_paragraph_indices={changed_indices}")
    print(f"paragraph_count={len(after_paragraphs)}")
    print("abstract_present=False")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
