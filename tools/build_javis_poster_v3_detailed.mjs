import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "file:///C:/Users/YongE/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const workspaceDir = "C:\\Users\\YongE\\Desktop\\JAVIS";
const skillDir = "C:\\Users\\YongE\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.1025.11240\\skills\\presentations";
const runtimePython = "C:\\Users\\YongE\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const buildDir = path.join(workspaceDir, ".build", "javis-poster-v3-detailed");
const outputDir = path.join(workspaceDir, "output");
const finalPptx = path.join(outputDir, "JAVIS_졸업작품_포스터_실행흐름_번호제목_일렬정렬본.pptx");
const TEXT_SCALE = 1.32;

const W = 3179;
const H = 4494;
const FONT = "Malgun Gothic";
const PURPLE = "#12304A";
const DARK = "#0B1F33";
const LIGHT = "#EDF3F6";
const NAVY = "#0B1F33";
const BLUE = "#2878A8";
const BLUE_LIGHT = "#E8F3F8";
const TEAL = "#0F766E";
const TEAL_LIGHT = "#E5F4F1";
const GOLD = "#D97706";
const GOLD_LIGHT = "#FFF2D8";
const RED = "#BD4D57";
const RED_LIGHT = "#FBE9EB";
const INK = "#17212B";
const MUTED = "#4B5C68";
const LINE = "#C7D2D9";
const WHITE = "#FFFFFF";
const BG = "#F7F9FA";

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
    fontSize: Math.round((style.fontSizePt ?? 30) * TEXT_SCALE),
    bold: style.bold ?? false,
    color: style.color ?? INK,
    alignment: style.align ?? "left",
    verticalAlignment: style.valign ?? "top",
  };
  return shape;
}

function pill(slide, text, x, y, w, h, fill, color = WHITE, fontSize = 30, line = "none") {
  const p = rect(slide, x, y, w, h, fill, line, true);
  p.text = text;
  p.text.style = { typeface: FONT, fontSize: Math.round(fontSize * TEXT_SCALE), bold: true, color, alignment: "center", verticalAlignment: "middle" };
  return p;
}

function circle(slide, text, x, y, size, fill, fontSize = 26) {
  const c = slide.shapes.add({
    geometry: "ellipse",
    position: { left: x, top: y, width: size, height: size },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
  c.text = text;
  c.text.style = { typeface: FONT, fontSize: Math.round(fontSize * 1.05), bold: true, color: WHITE, alignment: "center", verticalAlignment: "middle" };
  return c;
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
  rect(slide, x, y, w, 96, accent, "none", true);
  rect(slide, x, y + 76, w, 20, accent);
  pill(slide, String(number).padStart(2, "0"), x + 20, y + 13, 86, 68, WHITE, accent, 25);
  textbox(slide, title, x + 132, y + 8, w - 156, 74, { fontSizePt: 44, bold: true, color: WHITE, valign: "middle" });
  return { x: x + 34, y: y + 124, w: w - 68, h: h - 150 };
}

function infoCard(slide, title, body, x, y, w, h, color, pale) {
  rect(slide, x, y, w, h, pale, color, true);
  textbox(slide, title, x + 28, y + 24, w - 56, 56, { fontSizePt: 34, bold: true, color, align: "center", valign: "middle" });
  textbox(slide, body, x + 32, y + 98, w - 64, h - 124, { fontSizePt: 30, color: INK, align: "center", valign: "middle" });
}

function scenarioCard(slide, title, command, result, x, y, w, color, pale) {
  rect(slide, x, y, w, 356, WHITE, color, true);
  pill(slide, title, x + 26, y + 22, w - 52, 62, pale, color, 30, color);
  textbox(slide, command, x + 30, y + 102, w - 60, 64, { fontSizePt: 34, bold: true, color: NAVY, align: "center", valign: "middle" });
  rect(slide, x + 48, y + 188, w - 96, 3, LINE);
  textbox(slide, result, x + 34, y + 212, w - 68, 112, { fontSizePt: 29, color: INK, align: "center", valign: "middle" });
}

function conditionCard(slide, code, title, body, x, y, w, color, pale) {
  rect(slide, x, y, w, 210, pale, color, true);
  pill(slide, code, x + 18, y + 18, 118, 58, color, WHITE, 30);
  textbox(slide, title, x + 154, y + 18, w - 172, 58, { fontSizePt: 32, bold: true, color, valign: "middle" });
  textbox(slide, body, x + 24, y + 94, w - 48, 88, { fontSizePt: 28, color: INK, align: "center", valign: "middle" });
}

function metric(slide, value, label, detail, x, y, w, color, pale) {
  rect(slide, x, y, w, 214, pale, color, true);
  textbox(slide, value, x + 20, y + 18, w - 40, 74, { fontSizePt: 48, bold: true, color, align: "center", valign: "middle" });
  textbox(slide, label, x + 20, y + 98, w - 40, 42, { fontSizePt: 30, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, detail, x + 22, y + 150, w - 44, 40, { fontSizePt: 28, color: MUTED, align: "center", valign: "middle" });
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(buildDir, { recursive: true });
  await fs.mkdir(outputDir, { recursive: true });
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });
  const slide = presentation.slides.add();
  slide.background.fill = BG;

  rect(slide, 0, 0, W, 400, DARK);
  rect(slide, 0, 380, W, 20, TEAL);
  textbox(slide, "Windows PC 반복 작업을 위한", 170, 36, W - 340, 66, { fontSizePt: 46, bold: true, color: "#DDE8EE", align: "center", valign: "middle" });
  textbox(slide, "스킬 생성·재사용·개정형 AI 에이전트 JAVIS", 120, 103, W - 240, 116, { fontSizePt: 72, bold: true, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "사용자가 반복해서 설명하던 작업 방법을 스킬로 저장하고, 실행 뒤 실제 PC 상태까지 확인한다", 180, 236, W - 360, 64, { fontSizePt: 34, color: WHITE, align: "center", valign: "middle" });
  pill(slide, "요청 이해  ·  스킬 재사용  ·  안전 확인  ·  PC 실행  ·  결과 검증  ·  실패 기반 개정", 360, 318, W - 720, 56, TEAL, WHITE, 29, "#4AA69D");

  const margin = 108;
  const cw = W - margin * 2;
  const gap = 38;

  const s1 = section(slide, 1, "문제에서 연구 질문까지", margin, 440, cw, 570, DARK);
  const cardGap = 30;
  const cardW = (s1.w - cardGap * 2) / 3;
  infoCard(slide, "출발점: 내가 겪은 불편", "게임·과제·논문 작업을 할 때 같은 설정과 정리 기준을 매번 다시 설명하고 직접 확인해야 했다.", s1.x, s1.y + 4, cardW, 260, TEAL, TEAL_LIGHT);
  infoCard(slide, "기존 방식의 문제", "고정 매크로는 화면이 바뀌면 깨지고, 일반 에이전트는 매번 새 계획을 만든다. 도구의 성공 응답도 실제 완료를 보장하지 않는다.", s1.x + cardW + cardGap, s1.y + 4, cardW, 260, NAVY, LIGHT);
  infoCard(slide, "연구 질문", "검증된 스킬의 재사용과 실패 기반 개정이 같은 언어 모델의 성공률·시간·토큰에 어떤 영향을 주는가?", s1.x + (cardW + cardGap) * 2, s1.y + 4, cardW, 260, GOLD, GOLD_LIGHT);
  pill(slide, "스킬 = 재사용 절차 + 바뀌는 값의 입력 규칙 + 허용 도구·권한 + 성공 판정 + 버전 기록", s1.x + 120, s1.y + 296, s1.w - 240, 94, DARK, WHITE, 31);

  const s2 = section(slide, 2, "JAVIS의 실행 흐름", margin, 1045, cw, 730, DARK);
  const flow = [
    ["사용자 요청", "음성·텍스트"], ["의도 확인", "명령 대상 확인"], ["스킬 검색", "검증 버전 선택"],
    ["계획 생성", "작업 순서 구성"], ["위험도·승인", "기존 안전 실행 기반"], ["PC 실행", "등록 기능만 사용"],
    ["결과 검증", "실제 상태 재확인"],
  ];
  const fwGap = 32;
  const fw = (s2.w - fwGap * 6) / 7;
  flow.forEach((f, i) => {
    const x = s2.x + i * (fw + fwGap);
    rect(slide, x, s2.y + 6, fw, 190, i === 4 ? GOLD_LIGHT : i === 6 ? TEAL_LIGHT : LIGHT, i === 4 ? GOLD : i === 6 ? TEAL : PURPLE, true);
    circle(slide, String(i + 1), x + 22, s2.y + 48, 52, i === 4 ? GOLD : i === 6 ? TEAL : PURPLE, 22);
    textbox(slide, f[0], x + 86, s2.y + 44, fw - 104, 60, { fontSizePt: 28, bold: true, color: NAVY, align: "left", valign: "middle" });
    textbox(slide, f[1], x + 18, s2.y + 116, fw - 36, 48, { fontSizePt: 26, color: MUTED, align: "center", valign: "middle" });
    if (i < 6) chevron(slide, x + fw + 7, s2.y + 84, 18, 34, PURPLE);
  });

  textbox(slide, "왜 위험도와 승인을 확인하는가?", s2.x, s2.y + 230, 760, 48, { fontSizePt: 34, bold: true, color: GOLD });
  textbox(slide, "파일 이동·앱 실행처럼 PC 상태를 바꾸므로 대상과 영향 범위를 먼저 확인한다. 기존 안전 실행 구조의 Policy Engine을 사용한다.", s2.x + 760, s2.y + 218, s2.w - 790, 76, { fontSizePt: 29, color: INK, valign: "middle" });
  const riskW = (s2.w - 72) / 4;
  const risks = [
    ["R0·R1", "자동 실행", "읽기와 낮은 위험 작업", TEAL, TEAL_LIGHT],
    ["R2", "사용자 확인", "미리 보기 뒤 실행", BLUE, BLUE_LIGHT],
    ["R3·R4", "강한 승인", "민감하거나 큰 영향 작업", GOLD, GOLD_LIGHT],
    ["DENY", "실행 거부", "형식 오류·미등록 기능", RED, RED_LIGHT],
  ];
  risks.forEach((r, i) => {
    const x = s2.x + i * (riskW + 24);
    rect(slide, x, s2.y + 310, riskW, 140, r[4], r[3], true);
    pill(slide, r[0], x + 18, s2.y + 326, 130, 48, r[3], WHITE, 26);
    textbox(slide, r[1], x + 166, s2.y + 326, riskW - 184, 46, { fontSizePt: 28, bold: true, color: r[3], valign: "middle" });
    textbox(slide, r[2], x + 20, s2.y + 386, riskW - 40, 36, { fontSizePt: 26, color: INK, align: "center" });
  });
  const lowerY = s2.y + 482;
  pill(slide, "검증 성공", s2.x + 140, lowerY, 320, 62, TEAL_LIGHT, TEAL, 30, TEAL);
  chevron(slide, s2.x + 490, lowerY + 10, 60, 42, TEAL);
  pill(slide, "실행 기록 저장", s2.x + 580, lowerY, 420, 62, TEAL, WHITE, 30);
  chevron(slide, s2.x + 1030, lowerY + 10, 60, 42, TEAL);
  pill(slide, "다음 요청에서 스킬 재사용", s2.x + 1120, lowerY, 600, 62, TEAL_LIGHT, TEAL, 30, TEAL);
  pill(slide, "검증 실패", s2.x + 1840, lowerY, 320, 62, RED_LIGHT, RED, 30, RED);
  chevron(slide, s2.x + 2190, lowerY + 10, 60, 42, RED);
  pill(slide, "제한 재계획·중단", s2.x + 2280, lowerY, 470, 62, RED, WHITE, 30);
  textbox(slide, "실패 근거는 기존 스킬을 덮어쓰지 않고 새 개정 후보를 만드는 데 사용한다.", s2.x + 400, s2.y + 566, s2.w - 800, 48, { fontSizePt: 30, bold: true, color: PURPLE, align: "center" });

  const s3 = section(slide, 3, "한 문장 요청이 실제 작업이 되는 예", margin, 1810, cw, 600, DARK);
  const scGap = 34;
  const scW = (s3.w - scGap * 2) / 3;
  scenarioCard(slide, "과제 파일 정리", "“이번 주 과제 자료 정리해 줘”", "파일명과 내용을 확인해 과목별 폴더로 옮긴다. 작업 후 누락과 잘못된 분류를 다시 검사한다.", s3.x, s3.y + 4, scW, TEAL, TEAL_LIGHT);
  scenarioCard(slide, "논문 PDF 열기", "“스킬 관련 논문 열어 줘”", "허용 폴더에서 후보를 찾고 경로를 확인한다. 등록된 PDF 프로그램으로 연 뒤 새 창과 파일을 확인한다.", s3.x + scW + scGap, s3.y + 4, scW, BLUE, BLUE_LIGHT);
  scenarioCard(slide, "게임 모드 준비", "“자비스, 게임 모드 준비해”", "게임을 실행하고 마우스 DPI 800과 Windows 음량 80을 적용한다. 마지막에 실제 설정값을 다시 읽는다.", s3.x + (scW + scGap) * 2, s3.y + 4, scW, GOLD, GOLD_LIGHT);
  pill(slide, "고정 매크로와 달리 파일명·경로·장치 상태는 매번 다시 읽고, 반복되는 판단 방법만 스킬에서 재사용한다.", s3.x + 110, s3.y + 390, s3.w - 220, 70, DARK, WHITE, 31);

  const half = (cw - gap) / 2;
  const s4 = section(slide, 4, "스킬 생성·재사용·개정", margin, 2445, half, 690, DARK);
  const life = [
    ["생성", "성공한 실행의 순서·판단·완료 확인을 초안으로 저장"],
    ["검토", "허용 기능과 개인정보를 검사한 뒤 승인 버전만 활성화"],
    ["재사용", "새 요청과 가까운 검증 스킬을 계획기에 제공"],
    ["검증", "각 단계가 끝날 때 실제 Windows 상태를 다시 확인"],
    ["개정", "반복 실패를 반영한 새 버전을 이전 버전과 비교"],
  ];
  life.forEach((l, i) => {
    const y = s4.y + i * 94;
    circle(slide, String(i + 1), s4.x, y + 8, 56, i === 4 ? TEAL : PURPLE, 24);
    textbox(slide, l[0], s4.x + 78, y + 8, 170, 44, { fontSizePt: 30, bold: true, color: i === 4 ? TEAL : PURPLE });
    textbox(slide, l[1], s4.x + 250, y, s4.w - 260, 64, { fontSizePt: 28, color: INK, valign: "middle" });
  });
  pill(slide, "ReAct=계획·도구 반복  Toolformer=도구 호출 구조\nReflexion=실패 피드백  Voyager=스킬 저장소", s4.x + 24, s4.y + 486, s4.w - 48, 78, TEAL_LIGHT, TEAL, 23, TEAL);

  const s5 = section(slide, 5, "매크로·일반 에이전트와 차이", margin + half + gap, 2445, half, 690, DARK);
  const rows = [
    ["작업 방법", "고정 동작 또는 새 계획", "검증된 방법을 재사용"],
    ["상태 변화", "화면·경로 변경에 취약", "현재 값을 다시 읽어 적용"],
    ["완료 판단", "클릭·도구 응답으로 종료", "실제 파일·창·설정 재확인"],
    ["실패 이후", "실패 기록을 재사용하지 않음", "개정 후보를 만들고 비교"],
  ];
  rect(slide, s5.x, s5.y, s5.w, 66, DARK, "none", true);
  textbox(slide, "비교", s5.x, s5.y + 6, 290, 50, { fontSizePt: 28, bold: true, color: WHITE, align: "center" });
  textbox(slide, "매크로·일반 에이전트", s5.x + 290, s5.y + 6, 450, 50, { fontSizePt: 26, bold: true, color: WHITE, align: "center" });
  textbox(slide, "JAVIS", s5.x + 740, s5.y + 6, s5.w - 740, 50, { fontSizePt: 28, bold: true, color: WHITE, align: "center" });
  rows.forEach((r, i) => {
    const y = s5.y + 78 + i * 98;
    rect(slide, s5.x, y, s5.w, 86, i % 2 === 0 ? LIGHT : WHITE, LINE, true);
    textbox(slide, r[0], s5.x + 10, y + 10, 270, 62, { fontSizePt: 28, bold: true, color: NAVY, align: "center", valign: "middle" });
    textbox(slide, r[1], s5.x + 300, y + 10, 430, 62, { fontSizePt: 28, color: MUTED, align: "center", valign: "middle" });
    textbox(slide, r[2], s5.x + 750, y + 10, s5.w - 770, 62, { fontSizePt: 28, bold: true, color: TEAL, align: "center", valign: "middle" });
  });
  pill(slide, "1,091개 자동시험 통과", s5.x, s5.y + 488, 430, 70, LIGHT, NAVY, 28, NAVY);
  pill(slide, "13개 실행 기능 등록", s5.x + 452, s5.y + 488, 390, 70, BLUE_LIGHT, BLUE, 27, BLUE);
  pill(slide, "JAVIS 0.1.9 시제품", s5.x + 864, s5.y + 488, s5.w - 864, 70, TEAL_LIGHT, TEAL, 27, TEAL);

  const s6 = section(slide, 6, "실험 환경·방법·결과", margin, 3170, cw, 940, DARK);
  const condGap = 24;
  const condW = (s6.w - condGap * 3) / 4;
  conditionCard(slide, "SK0", "스킬 없음", "매번 절차를 새로 계획", s6.x, s6.y + 2, condW, MUTED, "#F1F2F4");
  conditionCard(slide, "SK1", "일반 지침", "절차만 문장으로 제공", s6.x + condW + condGap, s6.y + 2, condW, BLUE, BLUE_LIGHT);
  conditionCard(slide, "SK2", "최초 스킬", "입력·판단·완료 규칙 포함", s6.x + (condW + condGap) * 2, s6.y + 2, condW, NAVY, LIGHT);
  conditionCard(slide, "SK3", "개정 스킬", "반복 실패와 보완 규칙 반영", s6.x + (condW + condGap) * 3, s6.y + 2, condW, TEAL, TEAL_LIGHT);

  const envGap = 24;
  const envW = (s6.w - envGap * 3) / 4;
  const envs = [
    ["실행 환경", "Windows 11 PC 1대 · JAVIS 0.1.9", TEAL, TEAL_LIGHT],
    ["통제 조건", "같은 NIM 모델·설정·도구 목록", BLUE, BLUE_LIGHT],
    ["초기 상태", "매회 새 폴더 생성 · SHA-256 일치", NAVY, LIGHT],
    ["재현 식별자", "developer10 · seed 2026102001", GOLD, GOLD_LIGHT],
  ];
  envs.forEach((e, i) => {
    const x = s6.x + i * (envW + envGap);
    rect(slide, x, s6.y + 232, envW, 120, e[3], e[2], true);
    textbox(slide, e[0], x + 18, s6.y + 242, envW - 36, 38, { fontSizePt: 29, bold: true, color: e[2], align: "center" });
    textbox(slide, e[1], x + 18, s6.y + 286, envW - 36, 44, { fontSizePt: 27, color: INK, align: "center", valign: "middle" });
  });

  pill(slide, "실험 규모", s6.x, s6.y + 374, 220, 56, DARK, WHITE, 28);
  textbox(slide, "5개 작업 × 3회 반복 × 4조건 = 15개 대응 블록, 60회 실행", s6.x + 244, s6.y + 370, 1220, 64, { fontSizePt: 29, bold: true, color: NAVY, valign: "middle" });
  pill(slide, "성공 판정", s6.x + 1510, s6.y + 374, 220, 56, DARK, WHITE, 28);
  textbox(slide, "실제 파일·폴더·창 상태를 독립 검증기가 확인", s6.x + 1754, s6.y + 370, s6.w - 1754, 64, { fontSizePt: 29, bold: true, color: NAVY, valign: "middle" });
  textbox(slide, "재현: 매 조건 전 초기 상태 복원 · seed로 순서 섞기 · 실패 포함 · 결과 근거 60개를 SHA-256으로 연결\n계산: 성공률=성공÷15 · 평균 토큰=Σ(입력+출력)÷15 · 절감률=(기준-SK3)÷기준×100", s6.x + 70, s6.y + 438, s6.w - 140, 86, { fontSizePt: 25, color: INK, align: "center", valign: "middle" });

  const mGap = 34;
  const mW = (s6.w - mGap * 2) / 3;
  metric(slide, "14 / 15", "SK3 성공", "SK0는 10 / 15", s6.x, s6.y + 520, mW, TEAL, TEAL_LIGHT);
  metric(slide, "12.367초", "SK3 평균 시간", "SK0 대비 34.2% 감소", s6.x + mW + mGap, s6.y + 520, mW, BLUE, BLUE_LIGHT);
  metric(slide, "3,135.7", "SK3 평균 토큰", "입력 토큰과 출력 토큰의 합", s6.x + (mW + mGap) * 2, s6.y + 520, mW, NAVY, LIGHT);
  pill(slide, "토큰 절감", s6.x, s6.y + 748, 230, 62, NAVY, WHITE, 28);
  textbox(slide, "SK0 623.8토큰(16.6%) · SK1 1,133.2토큰(26.5%) · SK2 2,545.2토큰(44.8%) 절감", s6.x + 250, s6.y + 742, 1680, 70, { fontSizePt: 26, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, "Holm 보정 p≥0.375, 유의하지 않음\nSK3 사용자 확인 평균 1.0회", s6.x + 1970, s6.y + 738, s6.w - 1970, 78, { fontSizePt: 23, bold: true, color: RED, align: "center", valign: "middle" });

  const s7 = section(slide, 7, "결론과 연구 기여", margin, 4120, cw, 300, TEAL);
  textbox(slide, "JAVIS는 반복 작업을 ‘고정 클릭’이 아니라 ‘현재 상태를 다시 확인하는 검증 스킬’로 저장한다.", s7.x + 60, s7.y - 2, s7.w - 120, 64, { fontSizePt: 34, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, "개인적 불편에서 출발해 스킬 생성·검토·재사용·독립 검증·실패 기반 개정을 하나의 Windows 시제품으로 구현했다. 자체 실험은 구현 가능성과 비용 감소 가능성을 확인했으며, 일반화에는 다수 사용자 실험이 더 필요하다.", s7.x + 60, s7.y + 72, s7.w - 120, 86, { fontSizePt: 27, color: INK, align: "center", valign: "middle" });

  textbox(slide, "방법론: ReAct·Toolformer·Reflexion·Voyager  |  평가 참고: OSWorld·AgentBench  |  구현: JAVIS 0.1.9·자동시험 1,091개·등록 기능 13개  |  실험: 15개 대응 블록·60회", 140, 4420, W - 280, 44, { fontSizePt: 21, color: MUTED, align: "center", valign: "middle" });
  rect(slide, 0, 4470, W, 24, DARK);

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
    requiredNativeChartOwnerSlides: [],
    materializeLiteralChartWorkbooks: true,
    fontPolicy: { basis: "design", families: [FONT] },
    verifyArtifactToolImport: true,
    receiptPath: path.join(buildDir, "poster-v10.validation.json"),
  });
  console.log(finalPptx);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
