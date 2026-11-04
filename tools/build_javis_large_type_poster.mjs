import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:\\Users\\YongE\\Desktop\\JAVIS";
const skillDir = "C:\\Users\\YongE\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.1025.11240\\skills\\presentations";
const runtimePython = "C:\\Users\\YongE\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const buildDir = path.join(workspaceDir, ".build", "javis-large-type-poster");
const outputDir = path.join(workspaceDir, "output");
const finalPptx = path.join(outputDir, "JAVIS_졸업작품_포스터_대형글자_최종본_v2.pptx");

const W = 3179;
const H = 4494;
const FONT = "Malgun Gothic";
const PURPLE = "#674979";
const DARK = "#3E2A4A";
const LIGHT = "#F1ECF4";
const NAVY = "#142A49";
const BLUE = "#2B6DB2";
const BLUE_LIGHT = "#EAF2FB";
const TEAL = "#138B7B";
const TEAL_LIGHT = "#E6F5F1";
const GOLD = "#C98208";
const GOLD_LIGHT = "#FFF3D9";
const INK = "#202736";
const MUTED = "#566170";
const LINE = "#CFC7D5";
const WHITE = "#FFFFFF";
const BG = "#F8F6F9";

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
    fontSize: style.fontSizePt ?? 28,
    bold: style.bold ?? false,
    color: style.color ?? INK,
    alignment: style.align ?? "left",
    verticalAlignment: style.valign ?? "top",
  };
  return shape;
}

function pill(slide, text, x, y, w, h, fill, color = WHITE, fontSize = 28, line = "none") {
  const p = rect(slide, x, y, w, h, fill, line, true);
  p.text = text;
  p.text.style = { typeface: FONT, fontSize, bold: true, color, alignment: "center", verticalAlignment: "middle" };
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
  c.text.style = { typeface: FONT, fontSize, bold: true, color: WHITE, alignment: "center", verticalAlignment: "middle" };
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
  rect(slide, x, y, w, 94, accent, "none", true);
  rect(slide, x, y + 75, w, 19, accent);
  pill(slide, String(number).padStart(2, "0"), x + 20, y + 13, 84, 66, WHITE, accent, 24);
  textbox(slide, title, x + 126, y + 10, w - 150, 70, { fontSizePt: 40, bold: true, color: WHITE, valign: "middle" });
  return { x: x + 34, y: y + 122, w: w - 68, h: h - 148 };
}

function scenarioCard(slide, title, command, result, x, y, w, color, pale) {
  rect(slide, x, y, w, 390, WHITE, color, true);
  pill(slide, title, x + 28, y + 24, w - 56, 64, pale, color, 29, color);
  textbox(slide, command, x + 34, y + 112, w - 68, 72, { fontSizePt: 34, bold: true, color: NAVY, align: "center", valign: "middle" });
  rect(slide, x + 50, y + 204, w - 100, 3, LINE);
  textbox(slide, result, x + 36, y + 230, w - 72, 126, { fontSizePt: 28, color: INK, align: "center", valign: "middle" });
}

function metric(slide, value, label, detail, x, y, w, color, pale) {
  rect(slide, x, y, w, 260, pale, color, true);
  textbox(slide, value, x + 20, y + 24, w - 40, 90, { fontSizePt: 52, bold: true, color, align: "center", valign: "middle" });
  textbox(slide, label, x + 20, y + 126, w - 40, 48, { fontSizePt: 30, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, detail, x + 24, y + 186, w - 48, 50, { fontSizePt: 28, color: MUTED, align: "center", valign: "middle" });
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

  rect(slide, 0, 0, W, 440, DARK);
  rect(slide, 0, 420, W, 20, TEAL);
  textbox(slide, "Windows PC 반복 작업을 위한", 180, 45, W - 360, 72, { fontSizePt: 42, bold: true, color: "#E8DDED", align: "center", valign: "middle" });
  textbox(slide, "스킬 생성·재사용·개정형 AI 에이전트 JAVIS", 120, 116, W - 240, 120, { fontSizePt: 68, bold: true, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "반복해서 겪은 PC 사용 불편을 직접 해결하고 작업 방법을 다음 실행에도 다시 쓰는 Windows 에이전트", 210, 260, W - 420, 64, { fontSizePt: 30, color: WHITE, align: "center", valign: "middle" });
  pill(slide, "완성된 연구용 시제품   음성·텍스트 명령   독립 결과 검증   스킬 버전 관리", 450, 344, W - 900, 58, PURPLE, WHITE, 26, "#8C6D9B");

  const margin = 110;
  const cw = W - margin * 2;
  const gap = 40;

  const s1 = section(slide, 1, "연구 배경과 목적", margin, 490, cw, 520, PURPLE);
  textbox(slide, "같은 PC 작업을 반복할 때마다 설정과 판단을 처음부터 다시 해야 했다.", s1.x, s1.y, 1780, 72, { fontSizePt: 36, bold: true, color: NAVY, valign: "middle" });
  textbox(slide, "게임을 시작할 때 여러 프로그램의 설정을 따로 맞췄고, 과제 파일과 논문 자료도 매번 같은 기준으로 다시 찾고 정리했다. 기존 AI 에이전트는 이전 작업의 절차와 실패 원인을 다음 실행에 충분히 활용하지 못했다.", s1.x, s1.y + 94, 1780, 146, { fontSizePt: 28, color: INK });
  chevron(slide, s1.x + 1810, s1.y + 120, 88, 72, TEAL);
  rect(slide, s1.x + 1930, s1.y, s1.w - 1930, 270, TEAL_LIGHT, TEAL, true);
  textbox(slide, "연구 목적", s1.x + 1970, s1.y + 26, s1.w - 2010, 56, { fontSizePt: 34, bold: true, color: TEAL, align: "center" });
  textbox(slide, "반복되는 작업 방법을 스킬로 저장한다.\n실행할 때 현재 PC 상태를 다시 확인한다.\n실패 기록을 다음 버전의 개선에 사용한다.", s1.x + 1970, s1.y + 102, s1.w - 2010, 132, { fontSizePt: 28, bold: true, color: NAVY, align: "center", valign: "middle" });

  const s2 = section(slide, 2, "JAVIS의 전체 실행 구조", margin, 1050, cw, 650, PURPLE);
  const flow = [
    ["요청 이해", "음성·텍스트"],
    ["스킬 검색", "검증 버전 선택"],
    ["계획 생성", "절차와 기능 결합"],
    ["권한 판정", "위험도와 승인"],
    ["PC 실행", "등록 기능 사용"],
    ["결과 검증", "실제 상태 확인"],
    ["기록·개정", "다음 버전 생성"],
  ];
  const flowGap = 30;
  const flowW = (s2.w - flowGap * 6) / 7;
  flow.forEach((f, i) => {
    const x = s2.x + i * (flowW + flowGap);
    rect(slide, x, s2.y + 10, flowW, 206, i === 5 ? TEAL_LIGHT : LIGHT, i === 5 ? TEAL : PURPLE, true);
    circle(slide, String(i + 1), x + 20, s2.y + 28, 58, i === 5 ? TEAL : PURPLE, 24);
    textbox(slide, f[0], x + 18, s2.y + 100, flowW - 36, 48, { fontSizePt: 28, bold: true, color: NAVY, align: "center" });
    textbox(slide, f[1], x + 16, s2.y + 152, flowW - 32, 44, { fontSizePt: 28, color: MUTED, align: "center" });
    if (i < flow.length - 1) chevron(slide, x + flowW + 7, s2.y + 92, 17, 40, PURPLE);
  });
  const modW = (s2.w - 60) / 4;
  const mods = [
    ["요청·계획기", "언어 모델이 정해진 형식으로 실행 계획을 만든다."],
    ["스킬 관리", "검증된 스킬만 검색하고 버전과 실행 기록을 관리한다."],
    ["안전 실행기", "등록된 기능과 승인 범위 안에서 Windows 작업을 수행한다."],
    ["독립 검증기", "파일, 프로세스와 설정 값을 다시 읽어 완료를 판정한다."],
  ];
  mods.forEach((m, i) => {
    const x = s2.x + i * (modW + 20);
    rect(slide, x, s2.y + 270, modW, 172, i === 3 ? TEAL_LIGHT : BLUE_LIGHT, i === 3 ? TEAL : BLUE, true);
    textbox(slide, m[0], x + 18, s2.y + 288, modW - 36, 44, { fontSizePt: 30, bold: true, color: i === 3 ? TEAL : BLUE, align: "center" });
    textbox(slide, m[1], x + 22, s2.y + 340, modW - 44, 84, { fontSizePt: 28, color: INK, align: "center", valign: "middle" });
  });
  pill(slide, "언어 모델은 계획을 제안하고, 실행 권한과 성공 판정은 규칙과 Windows 상태 검사가 맡는다.", s2.x + 250, s2.y + 474, s2.w - 500, 58, DARK, WHITE, 28);

  const s3 = section(slide, 3, "대표 사용 사례", margin, 1740, cw, 690, PURPLE);
  const scGap = 36;
  const scW = (s3.w - scGap * 2) / 3;
  scenarioCard(slide, "과제 파일 정리", "“이번 주 과제 자료 정리해 줘”", "이번 실행의 파일명과 내용을 확인한다. 저장된 분류 기준으로 과목별 폴더에 이동하고 누락과 잘못된 이동을 검사한다.", s3.x, s3.y + 8, scW, TEAL, TEAL_LIGHT);
  scenarioCard(slide, "논문 PDF 열기", "“스킬 관련 논문 열어 줘”", "허용된 폴더에서 후보를 찾는다. 정확한 파일을 선택하고 해시와 경로를 확인한 뒤 등록된 PDF 프로그램으로 연다.", s3.x + scW + scGap, s3.y + 8, scW, BLUE, BLUE_LIGHT);
  scenarioCard(slide, "발로란트 준비", "“자비스, 발로란트 실행”", "게임을 실행하고 Razer Synapse의 DPI 800 프로필을 적용한다. Windows 음량을 80으로 맞춘 뒤 실제 값을 다시 확인한다.", s3.x + (scW + scGap) * 2, s3.y + 8, scW, GOLD, GOLD_LIGHT);
  textbox(slide, "스킬은 반복되는 작업 순서와 판단 기준을 저장한다. 파일명, 경로와 장치 상태처럼 바뀌는 값은 실행할 때마다 다시 확인한다.", s3.x + 180, s3.y + 438, s3.w - 360, 88, { fontSizePt: 30, bold: true, color: PURPLE, align: "center", valign: "middle" });

  const half = (cw - gap) / 2;
  const s4 = section(slide, 4, "스킬의 생성·재사용·개정", margin, 2470, half, 720, PURPLE);
  const life = [
    ["생성", "성공한 실행에서 작업 순서와 확인 방법을 스킬 초안으로 저장"],
    ["검토", "허용 기능과 개인정보를 검사하고 사람이 승인한 버전만 활성화"],
    ["재사용", "새 요청과 가장 관련 있는 검증 스킬을 찾아 계획기에 제공"],
    ["검증", "각 단계가 끝날 때 실제 Windows 상태로 성공 여부 확인"],
    ["개정", "반복 실패 원인을 반영한 새 버전을 만들고 기존 버전과 비교"],
  ];
  life.forEach((l, i) => {
    const y = s4.y + i * 100;
    circle(slide, String(i + 1), s4.x, y + 10, 58, i === 4 ? TEAL : PURPLE, 24);
    textbox(slide, l[0], s4.x + 82, y + 8, 180, 48, { fontSizePt: 30, bold: true, color: i === 4 ? TEAL : PURPLE });
    textbox(slide, l[1], s4.x + 270, y, s4.w - 280, 72, { fontSizePt: 28, color: INK, valign: "middle" });
  });
  pill(slide, "검토 전 스킬은 실행되지 않으며 기존 권한을 자동으로 넓히지 않는다.", s4.x + 60, s4.y + 520, s4.w - 120, 66, TEAL_LIGHT, TEAL, 27, TEAL);

  const s5 = section(slide, 5, "기존 AI 에이전트와 다른 점", margin + half + gap, 2470, half, 720, PURPLE);
  const rows = [
    ["반복 작업", "매번 새 계획", "검증 스킬 재사용"],
    ["실행 권한", "모델의 도구 선택", "등록 기능과 허용 목록"],
    ["완료 판단", "도구의 성공 응답", "실제 PC 상태 재확인"],
    ["실패 이후", "다음 요청에 남지 않음", "개정 후보 생성·비교"],
  ];
  rect(slide, s5.x, s5.y, s5.w, 70, DARK, "none", true);
  textbox(slide, "비교", s5.x, s5.y + 8, 300, 52, { fontSizePt: 28, bold: true, color: WHITE, align: "center" });
  textbox(slide, "일반 PC 에이전트", s5.x + 300, s5.y + 8, 460, 52, { fontSizePt: 28, bold: true, color: WHITE, align: "center" });
  textbox(slide, "JAVIS", s5.x + 760, s5.y + 8, s5.w - 760, 52, { fontSizePt: 28, bold: true, color: WHITE, align: "center" });
  rows.forEach((r, i) => {
    const y = s5.y + 84 + i * 102;
    rect(slide, s5.x, y, s5.w, 90, i % 2 === 0 ? LIGHT : WHITE, LINE, true);
    textbox(slide, r[0], s5.x + 12, y + 12, 276, 62, { fontSizePt: 28, bold: true, color: NAVY, align: "center", valign: "middle" });
    textbox(slide, r[1], s5.x + 310, y + 12, 440, 62, { fontSizePt: 28, color: MUTED, align: "center", valign: "middle" });
    textbox(slide, r[2], s5.x + 772, y + 12, s5.w - 792, 62, { fontSizePt: 28, bold: true, color: TEAL, align: "center", valign: "middle" });
  });
  const tagW = (s5.w - 36) / 3;
  pill(slide, "1,091\n자동시험 통과", s5.x, s5.y + 520, tagW, 94, LIGHT, PURPLE, 28, PURPLE);
  pill(slide, "13개\n등록 기능", s5.x + tagW + 18, s5.y + 520, tagW, 94, BLUE_LIGHT, BLUE, 28, BLUE);
  pill(slide, "0.1.9\n시제품 버전", s5.x + (tagW + 18) * 2, s5.y + 520, tagW, 94, TEAL_LIGHT, TEAL, 28, TEAL);

  const s6 = section(slide, 6, "보조 실험 결과", margin, 3230, cw, 700, PURPLE);
  textbox(slide, "같은 모델, 같은 기능, 같은 초기 상태에서 스킬 정보만 바꿨다.", s6.x + 80, s6.y, s6.w - 160, 68, { fontSizePt: 34, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, "5개 작업을 세 번씩 반복하고 네 조건을 비교해 총 60개 실행을 기록했다. 성공 여부는 모델의 답변이 아니라 독립 검증기가 읽은 실제 Windows 상태로 판정했다.", s6.x + 100, s6.y + 80, s6.w - 200, 98, { fontSizePt: 28, color: INK, align: "center", valign: "middle" });
  const metricGap = 42;
  const metricW = (s6.w - metricGap * 2) / 3;
  metric(slide, "14 / 15", "개정 스킬 성공", "SK0는 10 / 15", s6.x, s6.y + 214, metricW, TEAL, TEAL_LIGHT);
  metric(slide, "34.2%", "평균 시간 감소", "18.783초에서 12.367초", s6.x + metricW + metricGap, s6.y + 214, metricW, BLUE, BLUE_LIGHT);
  metric(slide, "16.6%", "평균 토큰 감소", "3,759.5에서 3,135.7", s6.x + (metricW + metricGap) * 2, s6.y + 214, metricW, PURPLE, LIGHT);
  pill(slide, "실험은 작품의 효과를 확인하는 보조 근거이며, 작품의 중심은 스킬을 만들고 다시 쓰며 개선하는 완성된 시스템이다.", s6.x + 160, s6.y + 508, s6.w - 320, 68, DARK, WHITE, 28);

  const s7 = section(slide, 7, "결론", margin, 3970, cw, 350, TEAL);
  textbox(slide, "JAVIS는 사용자의 요청을 실제 PC 작업으로 실행하고, 반복되는 방법을 스킬로 저장한다.", s7.x + 80, s7.y, s7.w - 160, 62, { fontSizePt: 34, bold: true, color: NAVY, align: "center", valign: "middle" });
  textbox(slide, "매 실행에서 현재 상태를 다시 확인하고 결과를 독립적으로 검증한다. 실패 기록은 다음 스킬 버전의 개선 근거가 된다. 사용자는 같은 작업을 다시 설명하지 않고 한 문장으로 실행할 수 있다.", s7.x + 100, s7.y + 82, s7.w - 200, 92, { fontSizePt: 28, color: INK, align: "center", valign: "middle" });
  pill(slide, "개인의 반복 불편을 해결한 기능이 사용할수록 작업 방법이 쌓이는 Windows 에이전트로 확장되었다.", s7.x + 220, s7.y + 196, s7.w - 440, 62, PURPLE, WHITE, 28);

  textbox(slide, "관련 방법: ReAct, Toolformer, Reflexion, Voyager, OSWorld, AgentBench   구현 자료: JAVIS 0.1.9, 자동시험 1,091건, 등록 기능 13개   확인 실험: 15개 대응 블록, 60개 실행", 150, 4360, W - 300, 58, { fontSizePt: 22, color: MUTED, align: "center", valign: "middle" });
  rect(slide, 0, 4468, W, 26, DARK);

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
    receiptPath: path.join(buildDir, "poster-v2.validation.json"),
  });
  console.log(finalPptx);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
