import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:\\Users\\YongE\\Desktop\\JAVIS";
const SKILL_DIR = "C:\\Users\\YongE\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.1025.11240\\skills\\presentations";
const RUNTIME_PYTHON = "C:\\Users\\YongE\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const buildDir = path.join(workspaceDir, ".build", "javis-poster");
const outputDir = path.join(workspaceDir, "output");
const FINAL_PPTX = path.join(outputDir, "JAVIS_졸업작품_포스터_예시반영본.pptx");
const FONT = "Malgun Gothic";
const W = 3179;
const H = 4494;
const PURPLE = "#705781";
const PURPLE_DARK = "#4F3B60";
const PURPLE_LIGHT = "#EEE9F2";
const INK = "#26232A";
const MUTED = "#5E5963";
const GRID = "#D7D0DC";
const WHITE = "#FFFFFF";
const BLUE = "#4F6E9A";
const TEAL = "#4D8B88";

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

function rect(slide, x, y, w, h, fill, line = "none") {
  return slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: line === "none" ? { style: "solid", fill: "none", width: 0 } : { style: "solid", fill: line, width: 2 },
  });
}

function section(slide, number, title, x, y, w, h) {
  rect(slide, x, y, w, 78, PURPLE);
  textbox(slide, String(number).padStart(2, "0"), x + 20, y + 10, 100, 58,
    { fontSizePt: 28, bold: true, color: WHITE, valign: "middle" });
  textbox(slide, title, x + 118, y + 9, w - 138, 60,
    { fontSizePt: 29, bold: true, color: WHITE, valign: "middle" });
  rect(slide, x, y + 78, w, h - 78, WHITE, GRID);
  return { x: x + 32, y: y + 104, w: w - 64, h: h - 130 };
}

function processBox(slide, label, x, y, w, h, color = PURPLE_LIGHT) {
  const s = slide.shapes.add({
    geometry: "roundRect",
    position: { left: x, top: y, width: w, height: h },
    fill: color,
    line: { style: "solid", fill: PURPLE, width: 2 },
    borderRadius: "rounded-lg",
  });
  s.text = label;
  s.text.style = { typeface: FONT, fontSize: 19, bold: true, color: PURPLE_DARK,
    alignment: "center", verticalAlignment: "middle" };
  return s;
}

function chevron(slide, x, y, w, h) {
  return slide.shapes.add({
    geometry: "chevron",
    position: { left: x, top: y, width: w, height: h },
    fill: PURPLE,
    line: { style: "solid", fill: "none", width: 0 },
  });
}

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

async function main() {
  await fs.mkdir(buildDir, { recursive: true });
  await fs.mkdir(outputDir, { recursive: true });
  const { applyPresentationChartFont } = await import(pathToFileURL(
    path.join(SKILL_DIR, "container_tools", "artifact_tool_utils.mjs")
  ).href);
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });
  const slide = presentation.slides.add();
  slide.background.fill = WHITE;

  rect(slide, 0, 0, W, 430, PURPLE);
  textbox(slide, "Windows PC 반복 작업을 위한\n스킬 생성·재사용·개정형 AI 에이전트", 190, 68, W - 380, 210,
    { fontSizePt: 54, bold: true, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "JAVIS  |  졸업작품 및 졸업논문 연구", 190, 292, W - 380, 56,
    { fontSizePt: 24, color: WHITE, align: "center", valign: "middle" });
  textbox(slide, "동일한 언어 모델에서 스킬 재사용과 개정이 실행 성능에 미치는 영향", 190, 354, W - 380, 48,
    { fontSizePt: 20, color: "#E8DFED", align: "center", valign: "middle" });

  const margin = 130;
  const gap = 46;
  const col = (W - margin * 2 - gap * 2) / 3;
  const x1 = margin;
  const x2 = margin + col + gap;
  const x3 = margin + (col + gap) * 2;

  const s1 = section(slide, 1, "연구 배경과 목적", x1, 505, col, 770);
  textbox(slide,
    "같은 PC 작업을 반복해도 기존 에이전트는 매번 계획을 다시 만든다. 호출 수와 토큰이 누적되고, 이전 실패에서 확인한 예외 처리 방법도 남지 않는다.\n\nJAVIS는 반복되는 절차와 판단 기준을 스킬로 저장한다. 파일명과 경로처럼 바뀌는 값은 실행 직전에 다시 확인한다.\n\n연구 목적\n스킬의 재사용과 개정이 성공률, 실행 시간, 호출 수와 토큰 사용량에 주는 영향을 같은 모델과 같은 초기 상태에서 비교한다.",
    s1.x, s1.y, s1.w, s1.h, { fontSizePt: 20, color: INK });

  const s2 = section(slide, 2, "프로그램 실행 과정", x2, 505, col * 2 + gap, 770);
  const py = s2.y + 36;
  const bw = 235;
  const bh = 108;
  const labels = ["요청 분석", "스킬 검색", "계획 생성", "권한 검사", "기능 실행", "결과 검증", "실행 기록"];
  labels.forEach((label, i) => {
    const bx = s2.x + i * (bw + 38);
    processBox(slide, label, bx, py, bw, bh, i === 6 ? "#E2F0EE" : PURPLE_LIGHT);
    if (i < labels.length - 1) chevron(slide, bx + bw + 8, py + 34, 24, 40);
  });
  textbox(slide,
    "검증된 스킬만 계획기에 제공한다. 스킬이 허용하지 않은 기능은 실행하지 않는다. 실행기의 성공 응답과 별도로 검증기가 파일, 프로세스와 창 상태를 다시 읽어 완료 여부를 판단한다.",
    s2.x, py + 165, s2.w, 180, { fontSizePt: 21, color: INK, align: "center" });
  rect(slide, s2.x + 95, py + 385, s2.w - 190, 2, GRID);
  textbox(slide, "실패 기록은 기존 스킬을 자동으로 덮어쓰지 않는다. 새 개정안은 초안으로 저장하고 검토 후 활성화한다.",
    s2.x + 80, py + 420, s2.w - 160, 120, { fontSizePt: 22, bold: true, color: PURPLE_DARK, align: "center" });

  const s3 = section(slide, 3, "스킬이 저장하는 정보", x1, 1328, col, 760);
  textbox(slide,
    "저장하는 것\n• 반복되는 작업 순서\n• 분류와 판단 기준\n• 허용 기능 목록\n• 완료 확인 방법\n\n매번 새로 확인하는 것\n• 현재 파일명과 파일 수\n• 실제 경로와 창 상태\n• 예외 상황\n\n핵심 원칙\n바뀌는 값은 입력으로 두고, 반복되는 방법만 스킬로 저장한다.",
    s3.x, s3.y, s3.w, s3.h, { fontSizePt: 20 });

  const s4 = section(slide, 4, "연구 질문과 실험 조건", x2, 1328, col, 760);
  textbox(slide,
    "연구 질문\n1. 스킬 제공 시 성공률이 달라지는가\n2. 실행 시간과 호출 비용이 줄어드는가\n3. 개정 스킬이 최초 스킬보다 나은가\n4. 작업 유형에 따라 효과가 다른가\n\n비교 조건\nSK0  스킬 없음\nSK1  일반 지침\nSK2  최초 스킬\nSK3  개정 스킬\n\n동일 작업과 반복 번호 안에서 네 조건을 모두 수행하는 완전 대응 블록 설계를 사용했다.",
    s4.x, s4.y, s4.w, s4.h, { fontSizePt: 19.5 });

  const s5 = section(slide, 5, "평가 작업과 측정 지표", x3, 1328, col, 760);
  textbox(slide,
    "평가 작업\n• 과제 파일 정리\n• 논문 PDF 열기\n• 폴더 파일 목록 확인\n• 확장자별 파일 정리\n• Explorer 폴더 열기\n\n주 지표\n독립 검증을 통과한 작업 성공 여부\n\n보조 지표\n실행 시간, 언어 모델 호출 수, 토큰 사용량, 사용자 확인 횟수\n\n성공률은 Wilson 95% 신뢰구간과 정확 McNemar 검정으로 비교했다.",
    s5.x, s5.y, s5.w, s5.h, { fontSizePt: 19.5 });

  const s6 = section(slide, 6, "확인 실험 결과", x1, 2142, col * 2 + gap, 1050);
  const resultChart = slide.charts.add("bar", {
    position: { left: s6.x + 30, top: s6.y + 20, width: s6.w - 60, height: 480 },
    categories: ["SK0", "SK1", "SK2", "SK3"],
    series: [{ name: "성공 횟수", values: [10, 12, 12, 14], fill: PURPLE }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { minimumScale: 0, maximumScale: 15, majorUnit: 3,
      majorGridlines: { style: "solid", fill: GRID, width: 1 } },
    xAxis: {},
  });
  applyPresentationChartFont(resultChart, { fontFamily: FONT });
  textbox(slide, "15회 중 성공 횟수", s6.x + 40, s6.y + 490, s6.w - 80, 48,
    { fontSizePt: 18, color: MUTED, align: "center" });
  textbox(slide,
    "SK3 평균 실행 시간 12.367초\nSK0보다 34.2%, SK1보다 33.6%, SK2보다 52.0% 짧았다.\n\nSK3의 평균 토큰 수도 가장 적었다. 그러나 성공률 차이는 Holm 보정 뒤 유의수준 0.05에서 통계적으로 유의하지 않았다.",
    s6.x + 40, s6.y + 570, s6.w - 80, 280, { fontSizePt: 22, bold: false, align: "center" });

  const s7 = section(slide, 7, "결과 해석", x3, 2142, col, 1050);
  textbox(slide,
    "차이가 크게 나타난 작업\n여러 파일을 분류하고 이동하는 작업\n\n차이가 거의 없었던 작업\n폴더 목록 조회와 Explorer 폴더 열기\n\n해석\n스킬은 판단 단계가 반복되는 작업에서 계획 비용을 줄일 가능성을 보였다. 단순 작업에는 검색과 지침 제공의 추가 비용이 생길 수 있다.\n\n주의\n확인 실험은 한 대의 Windows PC에서 15개 블록으로 수행했다. 일반 사용자 전체의 성능으로 확대할 수 없다.",
    s7.x, s7.y, s7.w, s7.h, { fontSizePt: 20 });

  const s8 = section(slide, 8, "결론과 연구 의의", x1, 3246, col * 3 + gap * 2, 1010);
  const c1 = s8.x;
  const cw = (s8.w - 100) / 3;
  textbox(slide, "프로그램 구현", c1, s8.y + 20, cw, 58,
    { fontSizePt: 27, bold: true, color: PURPLE_DARK, align: "center" });
  textbox(slide,
    "스킬 생성, 검색, 재사용, 실행 기록, 개정 후보와 독립 검증을 하나의 Windows 실행 하네스로 연결했다. 실행 기능은 등록된 계약으로 제한했다.",
    c1 + 20, s8.y + 100, cw - 40, 360, { fontSizePt: 22, align: "center" });
  rect(slide, c1 + cw + 45, s8.y + 10, 2, 600, GRID);
  textbox(slide, "연구 방법", c1 + cw + 70, s8.y + 20, cw, 58,
    { fontSizePt: 27, bold: true, color: PURPLE_DARK, align: "center" });
  textbox(slide,
    "모델과 도구, 초기 상태를 고정하고 스킬 제공 방식만 바꾸었다. 성공은 언어 모델의 응답이 아니라 실제 운영체제 상태로 판정했다.",
    c1 + cw + 90, s8.y + 100, cw - 40, 360, { fontSizePt: 22, align: "center" });
  rect(slide, c1 + cw * 2 + 95, s8.y + 10, 2, 600, GRID);
  textbox(slide, "핵심 결론", c1 + cw * 2 + 120, s8.y + 20, cw, 58,
    { fontSizePt: 27, bold: true, color: PURPLE_DARK, align: "center" });
  textbox(slide,
    "개정 스킬은 복잡한 반복 작업에서 실행 비용을 줄일 가능성을 보였다. 표본이 작아 성공률 향상을 확정할 수 없으므로, 더 많은 사용자와 작업을 이용한 후속 검증이 필요하다.",
    c1 + cw * 2 + 140, s8.y + 100, cw - 40, 360, { fontSizePt: 22, align: "center" });
  rect(slide, s8.x + 80, s8.y + 650, s8.w - 160, 2, GRID);
  textbox(slide,
    "JAVIS의 차별점: 기능 수를 늘리는 개인 비서가 아니라, 반복 절차를 스킬로 저장하고 같은 조건에서 재사용·개정 효과를 검증하는 연구용 PC 에이전트",
    s8.x + 90, s8.y + 700, s8.w - 180, 150, { fontSizePt: 25, bold: true, color: PURPLE_DARK, align: "center", valign: "middle" });

  textbox(slide, "JAVIS 연구 포스터  |  2026년 10월", margin, 4338, W - margin * 2, 52,
    { fontSizePt: 16, color: MUTED, align: "center" });

  const preview = await presentation.export({ slide, format: "png", scale: 0.35 });
  await writeBlob(path.join(buildDir, "poster-preview.png"), preview);

  const { finalizePresentation } = await import(pathToFileURL(
    path.join(SKILL_DIR, "container_tools", "artifact_tool_utils.mjs")
  ).href);
  const candidatePath = path.join(buildDir, "candidate.pptx");
  await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
  const expectedSlideSizeEmu = `${W * 9525},${H * 9525}`;
  await finalizePresentation({
    workspaceDir,
    candidatePath,
    finalPath: FINAL_PPTX,
    pythonExecutable: RUNTIME_PYTHON,
    integrityValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(SKILL_DIR, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: ["--expected-slide-size-emu", expectedSlideSizeEmu, "--validate-heading-fit"],
    explicitTotalSlideCount: 1,
    requiredNativeTableOwnerSlides: [],
    requiredNativeChartOwnerSlides: [1],
    materializeLiteralChartWorkbooks: true,
    fontPolicy: { basis: "design", families: [FONT] },
    verifyArtifactToolImport: true,
    receiptPath: path.join(buildDir, "poster.validation.json"),
  });
  console.log(FINAL_PPTX);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
