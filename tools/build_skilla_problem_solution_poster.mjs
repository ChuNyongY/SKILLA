import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:\\Users\\YongE\\Desktop\\SKILLA";
const skillDir = "C:\\Users\\YongE\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.1025.11240\\skills\\presentations";
const runtimePython = "C:\\Users\\YongE\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const buildDir = path.join(workspaceDir, ".build", "skilla-problem-solution-poster");
const outputDir = path.join(workspaceDir, "output");
const finalPptx = path.join(outputDir, "SKILLA_졸업작품_포스터_사용자불편해결중심_최종본.pptx");

const W = 3179;
const H = 4494;
const FONT = "Malgun Gothic";
const NAVY = "#0B2344";
const NAVY_2 = "#12365F";
const BLUE = "#1676D2";
const CYAN = "#19B8C4";
const SKY = "#EAF5FF";
const MINT = "#E8F8F4";
const GREEN = "#16866F";
const AMBER = "#C97700";
const AMBER_BG = "#FFF4DF";
const RED = "#C94B52";
const INK = "#172235";
const MUTED = "#536273";
const LINE = "#CBD7E4";
const PANEL = "#F7FAFD";
const WHITE = "#FFFFFF";

function rect(slide, x, y, w, h, fill, line = "none", radius = false) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
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

function circleLabel(slide, label, x, y, size, fill, color = WHITE, fontSize = 24) {
  const c = slide.shapes.add({
    geometry: "ellipse",
    position: { left: x, top: y, width: size, height: size },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
  c.text = label;
  c.text.style = { typeface: FONT, fontSize, bold: true, color, alignment: "center", verticalAlignment: "middle" };
  return c;
}

function section(slide, number, title, x, y, w, h, accent = BLUE) {
  rect(slide, x, y, w, h, WHITE, LINE, true);
  rect(slide, x, y, w, 86, NAVY, "none", true);
  rect(slide, x, y + 68, w, 18, NAVY);
  circleLabel(slide, String(number).padStart(2, "0"), x + 24, y + 12, 60, accent, WHITE, 21);
  textbox(slide, title, x + 100, y + 10, w - 128, 64, { fontSizePt: 31, bold: true, color: WHITE, valign: "middle" });
  return { x: x + 34, y: y + 112, w: w - 68, h: h - 140 };
}

function pill(slide, text, x, y, w, h, fill, color = INK, line = "none", fontSize = 20) {
  const p = rect(slide, x, y, w, h, fill, line, true);
  p.text = text;
  p.text.style = { typeface: FONT, fontSize, bold: true, color, alignment: "center", verticalAlignment: "middle" };
  return p;
}

function arrow(slide, x, y, w, h, fill = BLUE) {
  return slide.shapes.add({
    geometry: "chevron",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

function stepCard(slide, n, title, detail, x, y, w, h, fill = SKY, border = BLUE) {
  rect(slide, x, y, w, h, fill, border, true);
  circleLabel(slide, String(n), x + 18, y + 18, 54, border, WHITE, 20);
  textbox(slide, title, x + 88, y + 18, w - 112, 48, { fontSizePt: 23, bold: true, color: NAVY, valign: "middle" });
  textbox(slide, detail, x + 26, y + 82, w - 52, h - 102, { fontSizePt: 18.5, color: MUTED, align: "center", valign: "middle" });
}

function statusRow(slide, status, title, detail, x, y, w, statusColor, statusBg) {
  rect(slide, x, y, w, 84, PANEL, LINE, true);
  pill(slide, status, x + 16, y + 14, 116, 56, statusBg, statusColor, "none", 18);
  textbox(slide, title, x + 154, y + 10, 330, 62, { fontSizePt: 21, bold: true, color: NAVY, valign: "middle" });
  textbox(slide, detail, x + 500, y + 10, w - 520, 62, { fontSizePt: 17.5, color: MUTED, valign: "middle" });
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(buildDir, { recursive: true });
  await fs.mkdir(outputDir, { recursive: true });
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });
  const slide = presentation.slides.add();
  slide.background.fill = "#F2F6FA";

  // Header
  rect(slide, 0, 0, W, 500, NAVY);
  rect(slide, 0, 480, W, 20, CYAN);
  textbox(slide, "SKILLA", 130, 72, 520, 110, { fontSizePt: 68, bold: true, color: CYAN, valign: "middle" });
  textbox(slide, "반복되는 PC 일을 기억하는\n스킬 기반 개인 에이전트", 650, 52, 2400, 210, { fontSizePt: 57, bold: true, color: WHITE, align: "left", valign: "middle" });
  textbox(slide, "내가 매일 겪던 작은 불편에서 시작해, 한 번 만든 작업 방법을 다음에도 다시 쓰도록 만들었다", 650, 282, 2320, 62, { fontSizePt: 25, color: "#D5E7F8", valign: "middle" });
  pill(slide, "졸업작품·졸업논문  |  Windows 11 로컬 실행  |  스킬 생성·재사용·검증·개정", 650, 374, 2320, 64, NAVY_2, WHITE, "#31597E", 21);

  const margin = 118;
  const contentW = W - margin * 2;
  const gap = 42;

  // 01: Personal pain point
  const s1 = section(slide, 1, "출발점은 거창한 기술이 아니라 내가 반복해서 겪던 불편이었다", margin, 560, contentW, 690, CYAN);
  textbox(slide, "“왜 같은 일을 매번 다시 눌러야 하지?”", s1.x + 8, s1.y + 2, 950, 68, { fontSizePt: 34, bold: true, color: BLUE, valign: "middle" });
  textbox(slide, "저는 발로란트를 켤 때마다 게임을 실행하고, Razer Synapse에서 DPI를 맞추고, Windows 소리를 조정했다.\n소리가 크면 다시 설정 창을 열었고, 파일 정리도 늘 비슷한 기준을 매번 설명했다.", s1.x + 8, s1.y + 80, 1730, 138, { fontSizePt: 23, color: INK });

  const cardY = s1.y + 255;
  const painW = 540;
  const painGap = 28;
  const painXs = [s1.x + 8, s1.x + 8 + painW + painGap, s1.x + 8 + (painW + painGap) * 2];
  const painData = [
    ["게임 시작", "게임 실행 → DPI 800 → 음량 80\n매번 세 곳을 따로 조작"],
    ["갑자기 시끄러울 때", "설정 창 찾기 → 출력 장치 확인 →\n음량 50으로 조정"],
    ["과제 자료 정리", "파일 확인 → 과목 판단 → 이동 →\n결과 확인을 매번 다시 판단"],
  ];
  painData.forEach((d, i) => {
    rect(slide, painXs[i], cardY, painW, 180, i === 1 ? AMBER_BG : PANEL, i === 1 ? "#E8B35D" : LINE, true);
    circleLabel(slide, String(i + 1), painXs[i] + 20, cardY + 22, 48, i === 1 ? AMBER : BLUE, WHITE, 19);
    textbox(slide, d[0], painXs[i] + 86, cardY + 16, painW - 108, 54, { fontSizePt: 23, bold: true, color: NAVY, valign: "middle" });
    textbox(slide, d[1], painXs[i] + 22, cardY + 82, painW - 44, 78, { fontSizePt: 18.5, color: MUTED, align: "center", valign: "middle" });
  });
  arrow(slide, s1.x + 1760, cardY + 55, 90, 70, CYAN);
  rect(slide, s1.x + 1880, s1.y + 34, s1.w - 1900, 430, MINT, GREEN, true);
  textbox(slide, "내가 세운 해결 원칙", s1.x + 1920, s1.y + 66, s1.w - 1980, 54, { fontSizePt: 27, bold: true, color: GREEN, align: "center" });
  textbox(slide, "바뀌는 값은\n실행할 때 다시 확인하고", s1.x + 1920, s1.y + 148, s1.w - 1980, 95, { fontSizePt: 24, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, "반복되는 작업 방법은\n스킬로 저장해 다시 쓴다", s1.x + 1920, s1.y + 270, s1.w - 1980, 110, { fontSizePt: 28, bold: true, color: GREEN, align: "center", valign: "middle" });

  // 02: Built system
  const s2 = section(slide, 2, "그래서 만든 것: 요청부터 결과 확인까지 이어지는 SKILLA 실행 구조", margin, 1295, contentW, 790, BLUE);
  const steps = [
    ["요청 이해", "사용자가 원하는\n작업과 조건 파악"],
    ["스킬 검색", "저장된 작업 방법이\n있는지 먼저 확인"],
    ["현재 상태 확인", "파일·장치·프로그램을\n실행 직전에 다시 읽음"],
    ["안전하게 실행", "등록된 기능과\n허용 범위 안에서 수행"],
    ["결과 검증", "말이 아니라 실제\nWindows 상태로 판정"],
    ["기록·개정", "실패 원인을 남기고\n다음 스킬 후보 생성"],
  ];
  const stepGap = 28;
  const stepW = (s2.w - stepGap * 5) / 6;
  steps.forEach((d, i) => {
    stepCard(slide, i + 1, d[0], d[1], s2.x + i * (stepW + stepGap), s2.y + 18, stepW, 218, i === 4 ? MINT : SKY, i === 4 ? GREEN : BLUE);
  });
  textbox(slide, "스킬이란?", s2.x + 12, s2.y + 290, 300, 54, { fontSizePt: 29, bold: true, color: NAVY, valign: "middle" });
  textbox(slide, "단순한 명령어가 아니라 작업 순서, 판단 기준, 허용 기능, 완료 확인 방법을 함께 저장한 ‘재사용 가능한 작업 방법’이다.", s2.x + 300, s2.y + 290, s2.w - 312, 58, { fontSizePt: 23, bold: true, color: BLUE, valign: "middle" });
  const keepW = (s2.w - 48) / 2;
  rect(slide, s2.x, s2.y + 390, keepW, 208, "#F0F5FB", LINE, true);
  textbox(slide, "스킬에 저장하는 것", s2.x + 30, s2.y + 414, keepW - 60, 45, { fontSizePt: 24, bold: true, color: NAVY, align: "center" });
  textbox(slide, "반복되는 순서  ·  판단 기준  ·  허용 기능  ·  결과 확인 방법", s2.x + 30, s2.y + 482, keepW - 60, 74, { fontSizePt: 21, color: INK, align: "center", valign: "middle" });
  rect(slide, s2.x + keepW + 48, s2.y + 390, keepW, 208, MINT, "#9BD5C8", true);
  textbox(slide, "실행할 때마다 다시 확인하는 것", s2.x + keepW + 78, s2.y + 414, keepW - 60, 45, { fontSizePt: 24, bold: true, color: GREEN, align: "center" });
  textbox(slide, "현재 파일명·개수  ·  실제 경로  ·  열린 프로그램  ·  장치 상태  ·  예외 상황", s2.x + keepW + 78, s2.y + 482, keepW - 60, 74, { fontSizePt: 21, color: INK, align: "center", valign: "middle" });

  // 03: Scenarios
  const s3 = section(slide, 3, "한 문장으로 달라지는 사용 장면", margin, 2130, contentW, 1030, CYAN);
  const rowY = [s3.y + 10, s3.y + 278, s3.y + 546];
  const scenarioNames = ["게임 준비", "조용히 하기", "반복 파일 작업"];
  const before = [
    "발로란트 실행\nSynapse 열기\nDPI 800 확인\n음량 80 조정",
    "설정 창 열기\n출력 장치 확인\n볼륨 슬라이더 조정",
    "파일을 하나씩 확인\n과목 분류 기준 판단\n폴더 이동 후 재확인",
  ];
  const phrases = ["“자비스, 발로란트 실행”", "“아, 시끄러워”", "“이번 주 과제 자료 정리해 줘”"];
  const after = [
    "발로란트 실행 스킬 호출\n게임용 음량 80 적용·확인\nSynapse의 800 DPI 프로필 연결",
    "현재 출력 장치를 읽고\nWindows 음량을 50으로 변경\n변경된 값을 다시 읽어 확인",
    "저장된 분류 절차를 재사용하고\n이번 주의 파일명·내용만 새로 확인\n이동 결과와 누락 파일을 검사",
  ];
  for (let i = 0; i < 3; i++) {
    const y = rowY[i];
    pill(slide, scenarioNames[i], s3.x, y + 78, 220, 76, i === 1 ? AMBER_BG : SKY, i === 1 ? AMBER : BLUE, i === 1 ? "#E4B664" : "#9CC7EF", 22);
    rect(slide, s3.x + 250, y, 690, 232, PANEL, LINE, true);
    textbox(slide, "이전", s3.x + 280, y + 20, 100, 40, { fontSizePt: 21, bold: true, color: MUTED });
    textbox(slide, before[i], s3.x + 280, y + 72, 620, 132, { fontSizePt: 18.5, color: INK, align: "center", valign: "middle" });
    arrow(slide, s3.x + 974, y + 82, 90, 68, CYAN);
    rect(slide, s3.x + 1092, y + 38, 620, 156, NAVY_2, "none", true);
    textbox(slide, phrases[i], s3.x + 1120, y + 52, 564, 128, { fontSizePt: 25, bold: true, color: WHITE, align: "center", valign: "middle" });
    arrow(slide, s3.x + 1745, y + 82, 90, 68, CYAN);
    rect(slide, s3.x + 1864, y, s3.w - 1864, 232, MINT, GREEN, true);
    textbox(slide, "SKILLA", s3.x + 1894, y + 20, 140, 40, { fontSizePt: 21, bold: true, color: GREEN });
    textbox(slide, after[i], s3.x + 1894, y + 66, s3.w - 1924, 146, { fontSizePt: 18.5, color: INK, align: "center", valign: "middle" });
  }
  textbox(slide, "핵심 변화: 사용자는 목표만 말하고, 반복되는 방법은 스킬이 기억한다.", s3.x + 200, s3.y + 824, s3.w - 400, 60, { fontSizePt: 27, bold: true, color: BLUE, align: "center", valign: "middle" });

  // 04: Difference and implementation
  const leftW = 1850;
  const rightW = contentW - leftW - gap;
  const s4 = section(slide, 4, "기존 PC 에이전트와 무엇이 다른가", margin, 3205, leftW, 640, BLUE);
  const col1 = 430;
  const col2 = 610;
  const col3 = s4.w - col1 - col2;
  const tx = s4.x;
  const ty = s4.y + 4;
  rect(slide, tx, ty, col1, 64, NAVY_2, "none", true);
  rect(slide, tx + col1, ty, col2, 64, "#E6EDF5", "none", true);
  rect(slide, tx + col1 + col2, ty, col3, 64, MINT, "none", true);
  textbox(slide, "비교 기준", tx, ty + 4, col1, 54, { fontSizePt: 20, bold: true, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "기존 방식", tx + col1, ty + 4, col2, 54, { fontSizePt: 20, bold: true, color: MUTED, align: "center", valign: "middle" });
  textbox(slide, "SKILLA", tx + col1 + col2, ty + 4, col3, 54, { fontSizePt: 20, bold: true, color: GREEN, align: "center", valign: "middle" });
  const compare = [
    ["계획", "요청할 때마다 처음부터 생성", "저장된 스킬을 먼저 찾아 재사용"],
    ["성공 판단", "기능 호출이 끝나면 성공으로 보기 쉬움", "실제 파일·프로세스·설정 값을 다시 읽음"],
    ["실패 이후", "다음 요청에 실패 원인이 남지 않음", "실행 기록으로 개정 후보를 만들고 검토 후 적용"],
    ["안전 범위", "모델이 선택한 도구에 크게 의존", "등록된 기능과 스킬의 허용 범위 안에서만 실행"],
  ];
  compare.forEach((r, i) => {
    const y = ty + 76 + i * 92;
    rect(slide, tx, y, s4.w, 82, i % 2 === 0 ? WHITE : PANEL, LINE, true);
    textbox(slide, r[0], tx + 10, y + 8, col1 - 20, 66, { fontSizePt: 20, bold: true, color: NAVY, align: "center", valign: "middle" });
    textbox(slide, r[1], tx + col1 + 20, y + 8, col2 - 40, 66, { fontSizePt: 18, color: MUTED, align: "center", valign: "middle" });
    textbox(slide, r[2], tx + col1 + col2 + 20, y + 8, col3 - 40, 66, { fontSizePt: 18, bold: true, color: GREEN, align: "center", valign: "middle" });
  });

  const s5 = section(slide, 5, "현재 구현된 범위", margin + leftW + gap, 3205, rightW, 640, CYAN);
  textbox(slide, "Windows 11 로컬 시제품", s5.x, s5.y, s5.w, 52, { fontSizePt: 25, bold: true, color: BLUE, align: "center" });
  const implemented = [
    "텍스트 명령과 작업 화면 선택",
    "스킬 저장·검색·버전 관리",
    "등록된 Windows 기능 실행",
    "독립적인 결과 재확인과 실행 기록",
    "실패 기록 기반 개정 후보 검토",
  ];
  implemented.forEach((t, i) => {
    circleLabel(slide, "✓", s5.x + 14, s5.y + 82 + i * 70, 44, GREEN, WHITE, 21);
    textbox(slide, t, s5.x + 76, s5.y + 78 + i * 70, s5.w - 90, 52, { fontSizePt: 18.5, color: INK, valign: "middle" });
  });
  pill(slide, "현재 범위: Windows와 선택한 프로그램", s5.x + 20, s5.y + 444, s5.w - 40, 62, SKY, BLUE, "#A7CFF3", 18);

  // 06: verified status + research role
  const s6 = section(slide, 6, "지금까지 확인한 것과 남은 과제", margin, 3890, leftW, 450, CYAN);
  statusRow(slide, "확인", "텍스트 명령", "시스템 정보 읽기와 결과 화면 출력", s6.x, s6.y, s6.w, GREEN, MINT);
  statusRow(slide, "확인", "Windows 음량", "설정 변경 뒤 실제 값을 다시 읽는 왕복 시험", s6.x, s6.y + 96, s6.w, GREEN, MINT);
  statusRow(slide, "연결", "게임 준비 스킬", "발로란트 실행 절차와 Synapse 800 DPI 프로필", s6.x, s6.y + 192, s6.w, BLUE, SKY);
  statusRow(slide, "보완 중", "한국어 음성 입력", "웹캠 마이크 선택과 깨우기 인식의 실사용 검증", s6.x, s6.y + 288, s6.w, AMBER, AMBER_BG);

  const s7 = section(slide, 7, "논문에서 다룰 연구", margin + leftW + gap, 3890, rightW, 450, BLUE);
  textbox(slide, "작품이 중심이고, 실험은 효과를 확인하는 보조 근거로 사용한다.", s7.x + 10, s7.y, s7.w - 20, 76, { fontSizePt: 22, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, "비교 조건\n스킬 없음  /  최초 스킬  /  개정 스킬\n\n확인 지표\n성공률  ·  실행 시간  ·  LLM 호출 수\n토큰 사용량  ·  사용자 재확인 횟수", s7.x + 20, s7.y + 94, s7.w - 40, 220, { fontSizePt: 18.5, color: INK, align: "center", valign: "middle" });

  // Footer conclusion
  rect(slide, 0, 4382, W, 112, NAVY);
  textbox(slide, "결론", 130, 4404, 160, 58, { fontSizePt: 27, bold: true, color: CYAN, valign: "middle" });
  textbox(slide, "SKILLA의 강점은 ‘무엇이든 하는 AI’가 아니라, 내가 자주 하는 PC 작업을 기억하고 다음에는 더 적은 조작으로 끝내게 만든다는 점이다.", 300, 4398, W - 430, 70, { fontSizePt: 24, bold: true, color: WHITE, align: "center", valign: "middle" });

  const preview = await presentation.export({ slide, format: "png", scale: 0.45 });
  await writeBlob(path.join(buildDir, "poster-preview.png"), preview);

  const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools", "artifact_tool_utils.mjs")).href);
  const candidatePath = path.join(buildDir, "candidate.pptx");
  await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
  const expectedSlideSizeEmu = `${W * 9525},${H * 9525}`;
  await finalizePresentation({
    workspaceDir,
    candidatePath,
    finalPath: finalPptx,
    pythonExecutable: runtimePython,
    integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: ["--expected-slide-size-emu", expectedSlideSizeEmu, "--validate-heading-fit"],
    explicitTotalSlideCount: 1,
    requiredNativeTableOwnerSlides: [],
    requiredNativeChartOwnerSlides: [],
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
