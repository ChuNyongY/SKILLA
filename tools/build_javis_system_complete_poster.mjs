import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:\\Users\\YongE\\Desktop\\JAVIS";
const skillDir = "C:\\Users\\YongE\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.1025.11240\\skills\\presentations";
const runtimePython = "C:\\Users\\YongE\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const buildDir = path.join(workspaceDir, ".build", "javis-system-complete-poster");
const outputDir = path.join(workspaceDir, "output");
const finalPptx = path.join(outputDir, "JAVIS_졸업작품_포스터_시스템강조_종합완성본.pptx");

const W = 3179;
const H = 4494;
const FONT = "Malgun Gothic";
const PURPLE = "#684A7B";
const PURPLE_DARK = "#422D51";
const PURPLE_LIGHT = "#F1ECF4";
const NAVY = "#142A4A";
const BLUE = "#2E6EB5";
const BLUE_LIGHT = "#EAF2FB";
const TEAL = "#138B7B";
const TEAL_LIGHT = "#E5F5F1";
const GOLD = "#D89417";
const GOLD_LIGHT = "#FFF4DC";
const RED = "#C64F58";
const INK = "#202737";
const MUTED = "#5B6472";
const LINE = "#D2CBD8";
const WHITE = "#FFFFFF";
const BG = "#F7F5F8";

function rect(slide, x, y, w, h, fill, line = "none", rounded = false) {
  return slide.shapes.add({
    geometry: rounded ? "roundRect" : "rect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: line === "none" ? { style: "solid", fill: "none", width: 0 } : { style: "solid", fill: line, width: 2 },
  });
}

function textbox(slide, text, x, y, w, h, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: style.fill ?? "none",
    line: style.line ?? { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: FONT,
    fontSize: style.fontSizePt ?? 22,
    bold: style.bold ?? false,
    color: style.color ?? INK,
    alignment: style.align ?? "left",
    verticalAlignment: style.valign ?? "top",
  };
  return shape;
}

function roundLabel(slide, text, x, y, w, h, fill, color = WHITE, fontSize = 21, line = "none") {
  const shape = rect(slide, x, y, w, h, fill, line, true);
  shape.text = text;
  shape.text.style = { typeface: FONT, fontSize, bold: true, color, alignment: "center", verticalAlignment: "middle" };
  return shape;
}

function circle(slide, text, x, y, size, fill, color = WHITE, fontSize = 20) {
  const shape = slide.shapes.add({
    geometry: "ellipse",
    position: { left: x, top: y, width: size, height: size },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = { typeface: FONT, fontSize, bold: true, color, alignment: "center", verticalAlignment: "middle" };
  return shape;
}

function chevron(slide, x, y, w, h, fill = PURPLE) {
  return slide.shapes.add({
    geometry: "chevron",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function section(slide, number, title, x, y, w, h, accent = PURPLE) {
  rect(slide, x, y, w, h, WHITE, LINE, true);
  rect(slide, x, y, w, 76, accent, "none", true);
  rect(slide, x, y + 59, w, 17, accent);
  roundLabel(slide, String(number).padStart(2, "0"), x + 18, y + 10, 68, 55, WHITE, accent, 19);
  textbox(slide, title, x + 104, y + 8, w - 130, 58, { fontSizePt: 29, bold: true, color: WHITE, valign: "middle" });
  return { x: x + 28, y: y + 98, w: w - 56, h: h - 118 };
}

function metric(slide, value, label, x, y, w, color) {
  rect(slide, x, y, w, 126, WHITE, color, true);
  textbox(slide, value, x + 10, y + 12, w - 20, 58, { fontSizePt: 32, bold: true, color, align: "center", valign: "middle" });
  textbox(slide, label, x + 10, y + 74, w - 20, 34, { fontSizePt: 16.5, color: MUTED, align: "center", valign: "middle" });
}

function scenario(slide, label, command, result, x, y, w, accent, pale) {
  rect(slide, x, y, w, 322, WHITE, accent, true);
  roundLabel(slide, label, x + 24, y + 22, 200, 54, pale, accent, 20, accent);
  textbox(slide, command, x + 28, y + 92, w - 56, 64, { fontSizePt: 25, bold: true, color: NAVY, align: "center", valign: "middle" });
  rect(slide, x + 34, y + 173, w - 68, 2, LINE);
  textbox(slide, result, x + 30, y + 196, w - 60, 96, { fontSizePt: 18.5, color: INK, align: "center", valign: "middle" });
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(buildDir, { recursive: true });
  await fs.mkdir(outputDir, { recursive: true });
  const { applyPresentationChartFont } = await import(pathToFileURL(path.join(skillDir, "container_tools", "artifact_tool_utils.mjs")).href);
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });
  const slide = presentation.slides.add();
  slide.background.fill = BG;

  // Header
  rect(slide, 0, 0, W, 455, PURPLE_DARK);
  rect(slide, 0, 435, W, 20, TEAL);
  textbox(slide, "Windows PC 반복 작업을 위한", 180, 54, W - 360, 72, { fontSizePt: 36, bold: true, color: "#E9DFF0", align: "center", valign: "middle" });
  textbox(slide, "스킬 생성·재사용·개정형 AI 에이전트 JAVIS", 150, 118, W - 300, 112, { fontSizePt: 58, bold: true, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "반복해서 겪은 PC 사용 불편을 직접 해결하고, 같은 작업 방법을 다음 실행에 다시 쓰는 개인용 Windows 에이전트", 220, 246, W - 440, 58, { fontSizePt: 24, color: "#F0EAF3", align: "center", valign: "middle" });
  roundLabel(slide, "완성된 연구용 시제품   ·   음성·텍스트 명령   ·   독립 결과 검증   ·   스킬 버전 관리", 460, 335, W - 920, 60, PURPLE, WHITE, 21, "#896B98");

  const margin = 112;
  const cw = W - margin * 2;
  const gap = 38;

  // 01
  const s1 = section(slide, 1, "연구 배경과 목적: 내가 실제로 불편했던 일을 줄이기 위해 만들었다", margin, 500, cw, 540, PURPLE);
  const left = 1760;
  textbox(slide, "매번 같은 설정과 판단을 반복했다", s1.x + 6, s1.y + 4, left - 20, 52, { fontSizePt: 30, bold: true, color: NAVY, valign: "middle" });
  textbox(slide, "발로란트를 시작할 때 게임 실행, DPI 800 설정, 음량 80 조절을 따로 했다. 소리가 크면 설정 창을 다시 열었고, 과제 파일도 같은 기준으로 매번 분류했다. 기존 AI에게 맡겨도 작업 순서와 예외 처리를 요청할 때마다 다시 설명해야 했다.", s1.x + 6, s1.y + 68, left - 35, 124, { fontSizePt: 21.5, color: INK });
  const smallW = (left - 60) / 3;
  const pains = [
    ["게임 시작", "게임·DPI·음량을\n각각 따로 조작"],
    ["소리 조절", "설정 창과 출력 장치를\n다시 찾아 변경"],
    ["파일 정리", "같은 분류 기준을\n매번 다시 판단"],
  ];
  pains.forEach((p, i) => {
    rect(slide, s1.x + 6 + i * (smallW + 20), s1.y + 222, smallW, 134, i === 1 ? GOLD_LIGHT : PURPLE_LIGHT, i === 1 ? GOLD : LINE, true);
    textbox(slide, p[0], s1.x + 20 + i * (smallW + 20), s1.y + 238, smallW - 28, 36, { fontSizePt: 20, bold: true, color: i === 1 ? GOLD : PURPLE_DARK, align: "center" });
    textbox(slide, p[1], s1.x + 20 + i * (smallW + 20), s1.y + 282, smallW - 28, 58, { fontSizePt: 17.5, color: MUTED, align: "center", valign: "middle" });
  });
  chevron(slide, s1.x + left + 12, s1.y + 148, 90, 70, TEAL);
  rect(slide, s1.x + left + 130, s1.y + 10, s1.w - left - 130, 348, TEAL_LIGHT, TEAL, true);
  textbox(slide, "연구 목적", s1.x + left + 165, s1.y + 34, s1.w - left - 200, 46, { fontSizePt: 27, bold: true, color: TEAL, align: "center" });
  textbox(slide, "반복되는 작업 순서와 판단 기준을\n스킬로 저장한다.\n\n실행할 때는 현재 PC 상태를 다시 읽고,\n완료 결과를 독립적으로 확인한다.\n\n실패 기록은 다음 스킬 버전의 개선 근거로 사용한다.", s1.x + left + 165, s1.y + 98, s1.w - left - 200, 220, { fontSizePt: 21, bold: true, color: NAVY, align: "center", valign: "middle" });

  // 02
  const s2 = section(slide, 2, "완성한 시스템: 요청 이해부터 스킬 개정까지 한 흐름으로 연결했다", margin, 1085, cw, 690, PURPLE);
  const flow = [
    ["사용자 요청", "음성·텍스트"], ["의도 판정", "명령 대상 확인"], ["스킬 검색", "검증 버전 선택"],
    ["계획 생성", "절차와 기능 결합"], ["권한 판정", "위험도·승인"], ["PC 실행", "등록 기능만 사용"],
    ["결과 검증", "실제 상태 재확인"], ["기록·개정", "다음 버전 후보"],
  ];
  const flowGap = 26;
  const flowW = (s2.w - flowGap * 7) / 8;
  flow.forEach((f, i) => {
    const x = s2.x + i * (flowW + flowGap);
    rect(slide, x, s2.y + 18, flowW, 176, i === 6 ? TEAL_LIGHT : PURPLE_LIGHT, i === 6 ? TEAL : PURPLE, true);
    circle(slide, String(i + 1), x + 18, s2.y + 34, 46, i === 6 ? TEAL : PURPLE, WHITE, 18);
    textbox(slide, f[0], x + 18, s2.y + 90, flowW - 36, 38, { fontSizePt: 19, bold: true, color: NAVY, align: "center" });
    textbox(slide, f[1], x + 14, s2.y + 134, flowW - 28, 28, { fontSizePt: 15.5, color: MUTED, align: "center" });
    if (i < flow.length - 1) chevron(slide, x + flowW + 6, s2.y + 86, 18, 38, PURPLE);
  });
  textbox(slide, "핵심 모듈", s2.x, s2.y + 238, 190, 44, { fontSizePt: 24, bold: true, color: NAVY, valign: "middle" });
  const modules = [
    ["요청·계획기", "NIM 언어 모델이 구조화된 계획을 만들며 등록되지 않은 기능은 사용할 수 없다."],
    ["스킬 관리", "초안·검증·폐기 상태와 버전을 관리하고, 검증된 스킬만 새 요청에 제공한다."],
    ["안전 실행기", "위험도를 R0부터 R4로 판정하고 필요한 경우 정확한 대상과 인자에 승인을 결합한다."],
    ["독립 검증기", "실행기의 성공 문구를 믿지 않고 파일, 프로세스, 창과 설정 값을 다시 읽는다."],
  ];
  const modW = (s2.w - 54) / 4;
  modules.forEach((m, i) => {
    const x = s2.x + i * (modW + 18);
    rect(slide, x, s2.y + 300, modW, 188, i === 3 ? TEAL_LIGHT : BLUE_LIGHT, i === 3 ? TEAL : BLUE, true);
    textbox(slide, m[0], x + 18, s2.y + 318, modW - 36, 40, { fontSizePt: 21, bold: true, color: i === 3 ? TEAL : BLUE, align: "center" });
    textbox(slide, m[1], x + 20, s2.y + 372, modW - 40, 92, { fontSizePt: 16.5, color: INK, align: "center", valign: "middle" });
  });
  roundLabel(slide, "LLM은 계획을 제안하고, 실행 권한과 성공 판정은 결정 규칙과 Windows 상태 검사가 맡는다.", s2.x + 240, s2.y + 518, s2.w - 480, 52, PURPLE_DARK, WHITE, 20);

  // 03
  const s3 = section(slide, 3, "실제 사용 장면: 사용자는 한 문장만 말하고 스킬이 작업을 끝낸다", margin, 1820, cw, 690, PURPLE);
  const scGap = 32;
  const scW = (s3.w - scGap * 2) / 3;
  scenario(slide, "게임 준비 스킬", "“자비스, 발로란트 실행”", "발로란트를 실행하고 Razer Synapse의 게임용 DPI 800 프로필을 적용한다. Windows 음량을 80으로 맞춘 뒤 실제 값을 다시 확인한다.", s3.x, s3.y + 10, scW, BLUE, BLUE_LIGHT);
  scenario(slide, "즉시 음량 스킬", "“아, 시끄러워”", "한국어 음성을 인식해 현재 출력 장치를 확인한다. 음량을 50으로 변경하고 Windows에서 읽은 값으로 완료 여부를 판정한다.", s3.x + scW + scGap, s3.y + 10, scW, GOLD, GOLD_LIGHT);
  scenario(slide, "과제 정리 스킬", "“이번 주 과제 자료 정리해 줘”", "저장된 분류 절차를 재사용한다. 이번 실행의 파일명과 내용을 새로 읽고 과목별 폴더로 이동한 뒤 누락과 잘못된 이동을 검사한다.", s3.x + (scW + scGap) * 2, s3.y + 10, scW, TEAL, TEAL_LIGHT);
  textbox(slide, "스킬은 고정된 파일명이나 볼륨 값을 외워 두는 매크로가 아니다. 반복되는 방법을 저장하고, 매번 달라지는 입력은 실행 직전에 다시 확인한다.", s3.x + 150, s3.y + 370, s3.w - 300, 72, { fontSizePt: 22, bold: true, color: PURPLE_DARK, align: "center", valign: "middle" });
  const mini = [
    ["시스템 정보", "운영체제·버전·구조·컴퓨터 이름 확인"],
    ["PDF와 폴더", "정확한 문서·경로·새 창 상태 확인"],
    ["파일 작업", "목록·내용·이동 결과를 독립 검사"],
    ["실행 기록", "시간·호출·토큰·사용자 확인 횟수 저장"],
  ];
  const miniW = (s3.w - 54) / 4;
  mini.forEach((m, i) => {
    rect(slide, s3.x + i * (miniW + 18), s3.y + 470, miniW, 92, WHITE, LINE, true);
    textbox(slide, m[0], s3.x + 14 + i * (miniW + 18), s3.y + 482, miniW - 28, 30, { fontSizePt: 18, bold: true, color: BLUE, align: "center" });
    textbox(slide, m[1], s3.x + 14 + i * (miniW + 18), s3.y + 518, miniW - 28, 46, { fontSizePt: 15.5, color: MUTED, align: "center", valign: "middle" });
  });

  // 04 & 05
  const half = (cw - gap) / 2;
  const s4 = section(slide, 4, "스킬의 생성·재사용·개정", margin, 2555, half, 700, PURPLE);
  const lifecycle = [
    ["생성", "성공한 실행 기록에서 작업 순서와 확인 규칙을 뽑아 초안으로 저장"],
    ["검토", "허용 기능과 개인정보를 검사하고 사람이 승인한 버전만 활성화"],
    ["재사용", "새 요청과 가장 관련 있는 검증 스킬을 찾아 계획기에 제공"],
    ["검증", "각 단계가 끝날 때 실제 Windows 상태로 성공 여부 확인"],
    ["개정", "반복 실패 원인을 반영한 새 버전을 만들고 기존 버전과 비교"],
  ];
  lifecycle.forEach((l, i) => {
    const y = s4.y + i * 95;
    circle(slide, String(i + 1), s4.x, y + 10, 54, i === 4 ? TEAL : PURPLE, WHITE, 19);
    textbox(slide, l[0], s4.x + 76, y + 4, 150, 36, { fontSizePt: 21, bold: true, color: i === 4 ? TEAL : PURPLE_DARK });
    textbox(slide, l[1], s4.x + 226, y, s4.w - 236, 60, { fontSizePt: 17, color: INK, valign: "middle" });
    if (i < 4) rect(slide, s4.x + 25, y + 67, 4, 26, LINE);
  });
  roundLabel(slide, "새 스킬은 기존 권한을 넓히지 않으며 검토 전에는 실행되지 않는다.", s4.x + 80, s4.y + 500, s4.w - 160, 66, TEAL_LIGHT, TEAL, 19, TEAL);

  const s5 = section(slide, 5, "기존 AI 에이전트와 다른 점", margin + half + gap, 2555, half, 700, PURPLE);
  const c1 = 300;
  const c2 = 440;
  const c3 = s5.w - c1 - c2;
  rect(slide, s5.x, s5.y, s5.w, 56, PURPLE_DARK, "none", true);
  textbox(slide, "비교 기준", s5.x, s5.y + 4, c1, 46, { fontSizePt: 18, bold: true, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "일반 PC 에이전트", s5.x + c1, s5.y + 4, c2, 46, { fontSizePt: 18, bold: true, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "JAVIS", s5.x + c1 + c2, s5.y + 4, c3, 46, { fontSizePt: 18, bold: true, color: WHITE, align: "center", valign: "middle" });
  const compare = [
    ["반복 작업", "요청마다 계획을 새로 생성", "검증된 스킬을 검색해 절차 재사용"],
    ["실행 권한", "모델이 선택한 도구 범위에 의존", "등록 기능과 스킬 허용 목록으로 제한"],
    ["위험 작업", "단순 확인 또는 고정 거부 목록", "위험도 판정과 대상·인자에 결합된 승인"],
    ["완료 판단", "도구가 보낸 성공 응답에 의존", "파일·프로세스·설정 값을 다시 읽음"],
    ["실패 이후", "다음 요청에 개선 내용이 남지 않음", "실패 근거로 개정 후보 생성·비교"],
  ];
  compare.forEach((r, i) => {
    const y = s5.y + 68 + i * 82;
    rect(slide, s5.x, y, s5.w, 72, i % 2 === 0 ? PURPLE_LIGHT : WHITE, LINE, true);
    textbox(slide, r[0], s5.x + 8, y + 8, c1 - 16, 54, { fontSizePt: 17.5, bold: true, color: NAVY, align: "center", valign: "middle" });
    textbox(slide, r[1], s5.x + c1 + 10, y + 8, c2 - 20, 54, { fontSizePt: 15.5, color: MUTED, align: "center", valign: "middle" });
    textbox(slide, r[2], s5.x + c1 + c2 + 10, y + 8, c3 - 20, 54, { fontSizePt: 15.5, bold: true, color: TEAL, align: "center", valign: "middle" });
  });
  const mW = (s5.w - 36) / 3;
  metric(slide, "1,091", "자동시험 통과", s5.x, s5.y + 500, mW, PURPLE);
  metric(slide, "13", "등록 기능 조립", s5.x + mW + 18, s5.y + 500, mW, BLUE);
  metric(slide, "0.1.9", "연구용 시제품 버전", s5.x + (mW + 18) * 2, s5.y + 500, mW, TEAL);

  // 06
  const s6 = section(slide, 6, "연구 질문과 보조 실험: 만든 시스템의 효과를 같은 조건에서 확인했다", margin, 3300, cw, 785, PURPLE);
  const left6 = 1160;
  textbox(slide, "연구 질문", s6.x, s6.y + 4, 220, 44, { fontSizePt: 25, bold: true, color: NAVY });
  textbox(slide, "1. 스킬을 재사용하면 작업 성공률과 실행 비용이 달라지는가?\n2. 최초 스킬보다 실패 기록을 반영한 개정 스킬이 나은가?\n3. 어떤 반복 작업에서 스킬의 효과가 크게 나타나는가?", s6.x, s6.y + 60, left6 - 30, 132, { fontSizePt: 19.5, color: INK });
  textbox(slide, "실험 설계", s6.x, s6.y + 218, 220, 44, { fontSizePt: 25, bold: true, color: NAVY });
  textbox(slide, "같은 모델·기능·초기 상태에서 스킬 정보만 변경했다.\n5개 작업 × 3회 반복 × 4조건 = 60개 관측\nSK0 스킬 없음  /  SK1 일반 지침  /  SK2 최초 스킬  /  SK3 개정 스킬", s6.x, s6.y + 270, left6 - 30, 126, { fontSizePt: 18, color: INK });
  roundLabel(slide, "성공은 모델의 답변이 아니라 독립 검증기가 읽은 실제 Windows 상태로 판정", s6.x + 10, s6.y + 426, left6 - 50, 72, TEAL_LIGHT, TEAL, 18.5, TEAL);

  const chartX = s6.x + left6 + 50;
  const chartW = 900;
  textbox(slide, "조건별 작업 성공률", chartX, s6.y + 4, chartW, 44, { fontSizePt: 24, bold: true, color: NAVY, align: "center" });
  const chart = slide.charts.add("bar", {
    position: { left: chartX, top: s6.y + 56, width: chartW, height: 360 },
    categories: ["SK0", "SK1", "SK2", "SK3"],
    series: [{ name: "성공률", values: [66.7, 80.0, 80.0, 93.3], fill: PURPLE }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { minimumScale: 0, maximumScale: 100, majorUnit: 20, majorGridlines: { style: "solid", fill: LINE, width: 1 } },
    xAxis: {},
  });
  applyPresentationChartFont(chart, { fontFamily: FONT });

  const resX = chartX + chartW + 70;
  const resW = s6.w - left6 - 1020;
  textbox(slide, "확인 실험 결과", resX, s6.y + 4, resW, 44, { fontSizePt: 24, bold: true, color: NAVY, align: "center" });
  metric(slide, "14 / 15", "개정 스킬 성공", resX, s6.y + 64, resW, TEAL);
  metric(slide, "12.367초", "평균 실행 시간", resX, s6.y + 208, resW, BLUE);
  metric(slide, "3,135.7", "평균 토큰", resX, s6.y + 352, resW, PURPLE);
  textbox(slide, "SK0 대비 실행 시간 34.2% 감소, 토큰 16.6% 감소", chartX, s6.y + 438, chartW, 44, { fontSizePt: 20, bold: true, color: TEAL, align: "center" });
  textbox(slide, "표본이 작아 성공률 차이는 통계적으로 확정하지 않았지만, 복수 파일을 판단하고 이동하는 작업에서 개정 스킬의 이점이 가장 뚜렷했다.", chartX, s6.y + 500, s6.w - left6 - 60, 64, { fontSizePt: 18.5, color: MUTED, align: "center", valign: "middle" });

  // 07
  const s7 = section(slide, 7, "결론: 작품의 중심은 실험 수치가 아니라 반복 불편을 해결한 완성된 시스템이다", margin, 4130, cw, 255, TEAL);
  textbox(slide, "JAVIS는 사용자의 한 문장을 실제 PC 작업으로 연결하고, 반복되는 방법을 스킬로 축적한다. 매 실행에서 현재 상태를 다시 확인하고 결과를 독립 검증하며, 실패 기록을 다음 버전의 개선 근거로 남긴다.", s7.x + 10, s7.y + 2, s7.w - 20, 70, { fontSizePt: 22, bold: true, color: NAVY, align: "center", valign: "middle" });
  roundLabel(slide, "내가 불편해서 만든 기능이 한 번의 자동화로 끝나지 않고, 사용할수록 작업 방법이 쌓이는 개인용 Windows 에이전트가 되었다.", s7.x + 180, s7.y + 88, s7.w - 360, 54, PURPLE_DARK, WHITE, 20.5);

  // References/footer
  textbox(slide, "관련 방법: ReAct · Toolformer · Reflexion · Voyager · OSWorld · AgentBench    |    구현 근거: JAVIS 0.1.9, 자동시험 1,091건 통과, 13개 기능 조립    |    확인 실험: 15개 완전 대응 블록, 60개 관측", 130, 4406, W - 260, 40, { fontSizePt: 14.5, color: MUTED, align: "center", valign: "middle" });
  rect(slide, 0, 4470, W, 24, PURPLE_DARK);

  const preview = await presentation.export({ slide, format: "png", scale: 0.45 });
  await writeBlob(path.join(buildDir, "poster-preview.png"), preview);

  const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools", "artifact_tool_utils.mjs")).href);
  const candidatePath = path.join(buildDir, "candidate.pptx");
  await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
  await finalizePresentation({
    workspaceDir,
    candidatePath,
    finalPath: finalPptx,
    pythonExecutable: runtimePython,
    integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: ["--expected-slide-size-emu", `${W * 9525},${H * 9525}`, "--validate-heading-fit"],
    explicitTotalSlideCount: 1,
    requiredNativeTableOwnerSlides: [],
    requiredNativeChartOwnerSlides: [1],
    materializeLiteralChartWorkbooks: true,
    fontPolicy: { basis: "design", families: [FONT] },
    verifyArtifactToolImport: true,
    receiptPath: path.join(buildDir, "poster.validation.json"),
  });
  console.log(finalPptx);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
