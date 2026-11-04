import fs from "node:fs/promises";
import path from "node:path";

import { Presentation, PresentationFile } from "@oai/artifact-tool";

const ROOT = path.resolve(".");
const OUT = path.join(ROOT, "output");
const PREVIEW = path.join(ROOT, ".poster-rebuild", "previews");
const UI = path.join(OUT, "ui_actual");

const C = {
  navy: "#071B2D",
  blue: "#1368CE",
  cyan: "#19C6D7",
  teal: "#0E8C80",
  mint: "#56E3B5",
  orange: "#F39A27",
  red: "#D94747",
  ink: "#17283A",
  gray: "#5F7181",
  line: "#B9CEDB",
  white: "#FFFFFF",
  pale: "#EAF4FA",
  pale2: "#E7F8F4",
  yellow: "#FFF3D7",
  redp: "#FDEBEC",
  bg: "#F3F7FA",
};

function helpers(slide) {
  const box = (x, y, w, h, fill = C.white, stroke = C.line, geometry = "roundRect") => {
    const shape = slide.shapes.add({
      geometry,
      position: { left: x, top: y, width: w, height: h },
      fill,
      line: { style: "solid", fill: stroke, width: 1.5 },
    });
    if (["rect", "roundRect", "textbox"].includes(geometry)) {
      shape.borderRadius = "rounded-lg";
    }
    return shape;
  };
  const txt = (value, x, y, w, h, size = 22, color = C.ink, bold = false, align = "left") => {
    const shape = slide.shapes.add({
      geometry: "textbox",
      position: { left: x, top: y, width: w, height: h },
      fill: "none",
      line: { style: "solid", fill: "none", width: 0 },
    });
    shape.text = value;
    shape.text.style = {
      fontFamily: "Noto Sans KR",
      fontSize: size,
      color,
      bold,
      alignment: align,
      verticalAlignment: "middle",
      wrap: true,
    };
    return shape;
  };
  const section = (n, title, y) => {
    box(42, y, 1316, 54, C.navy, C.navy, "rect");
    txt(String(n).padStart(2, "0"), 58, y, 58, 54, 23, C.cyan, true, "center");
    txt(title, 126, y, 1190, 54, 26, C.white, true);
  };
  const arrow = (x, y, w = 44, color = C.blue) => txt("➜", x, y, w, 42, 29, color, true, "center");
  const node = (title, sub, x, y, w, h, fill = C.white, stroke = C.blue) => {
    box(x, y, w, h, fill, stroke);
    txt(title, x + 10, y + 7, w - 20, 32, 19, C.ink, true, "center");
    txt(sub, x + 10, y + 39, w - 20, h - 44, 14, C.gray, false, "center");
  };
  const pill = (value, x, y, w, fill = C.pale, color = C.blue) => {
    box(x, y, w, 34, fill, fill);
    txt(value, x + 8, y + 1, w - 16, 31, 14, color, true, "center");
  };
  return { box, txt, section, arrow, node, pill };
}

function header(slide, H, subtitle) {
  const { box, txt } = H;
  box(0, 0, 1400, 186, C.navy, C.navy, "rect");
  txt("SKILLA", 54, 18, 300, 78, 56, C.white, true);
  txt("스킬 로컬 기반 AI 에이전트", 360, 23, 980, 65, 34, C.white, true, "right");
  txt(subtitle, 55, 96, 1290, 44, 22, "#D1E8F4");
  txt("SKILL-BASED LOCAL AI AGENT  ·  실제 구현과 자체 검증", 55, 145, 1050, 24, 14, C.cyan, true);
}

function addImage(slide, blob, alt, x, y, w, h) {
  slide.images.add({
    blob,
    contentType: "image/png",
    alt,
    fit: "contain",
    position: { left: x, top: y, width: w, height: h },
  });
}

function pageOne(slide, images) {
  const H = helpers(slide);
  const { box, txt, section, arrow, node, pill } = H;
  header(slide, H, "사용자가 불편했던 반복 작업을 저장하고, 다음 실행에서 다시 쓰는 Windows 프로그램");

  section(1, "문제 → 해결: 왜 만들었는가", 212);
  box(42, 280, 624, 238, "#FFF9F9", C.red);
  txt("기존 AI 에이전트", 66, 294, 560, 34, 25, C.red, true);
  txt(
    "• 같은 작업도 매번 계획을 새로 생성\n• 파일·폴더·예외를 처음부터 다시 판단\n• 성공·실패 경험이 다음 실행에 남지 않음\n• 반복할수록 시간·호출·토큰이 계속 누적",
    66,
    338,
    560,
    154,
    20,
  );
  arrow(676, 368, 46, C.orange);
  box(734, 280, 624, 238, C.pale2, C.teal);
  txt("SKILLA의 해결", 758, 294, 560, 34, 25, C.teal, true);
  txt(
    "• 반복 절차를 ‘스킬’로 저장\n• 실행 때 달라지는 파일명·상태만 다시 확인\n• 실제 PC 상태로 성공 여부를 별도 검증\n• 실패 기록은 자동 반영하지 않고 개정 초안으로 검토",
    758,
    338,
    560,
    154,
    20,
  );
  txt(
    "스킬 = 작업 순서 + 판단 기준 + 완료 확인 방법   |   로컬 = 사용자 PC 안에서 스킬·실행 기록 관리",
    42,
    526,
    1316,
    42,
    17,
    C.ink,
    true,
    "center",
  );

  section(2, "전체 실행 구조 — 요청부터 결과 확인과 개정까지", 586);
  const flowY = 660;
  const xs = [50, 222, 394, 566, 738, 910, 1082, 1254];
  const widths = [132, 132, 132, 132, 132, 132, 132, 104];
  const titles = ["사용자 요청", "의도 확인", "스킬 검색", "계획 생성", "안전 확인", "PC 실행", "결과 검증", "기록"];
  const subs = ["음성·텍스트", "명령 대상", "승인 버전", "순서 구성", "필요 시 승인", "등록 기능", "실제 상태", "성공·실패"];
  for (let i = 0; i < titles.length; i += 1) {
    node(titles[i], subs[i], xs[i], flowY, widths[i], 94, i === 6 ? C.pale2 : C.white, i === 6 ? C.teal : C.blue);
    if (i < titles.length - 1) arrow(xs[i] + widths[i] + 2, flowY + 26, 34, i >= 5 ? C.teal : C.blue);
  }
  box(186, 788, 1028, 104, C.yellow, C.orange);
  txt("반복 실패·예외 발생", 206, 800, 250, 30, 20, C.orange, true);
  arrow(466, 800, 44, C.orange);
  txt("개정 스킬 초안 생성", 520, 800, 250, 30, 20, C.ink, true);
  arrow(778, 800, 44, C.orange);
  txt("사용자 승인 전까지 실행에 사용하지 않음", 830, 797, 360, 38, 18, C.red, true);
  txt("일반 질문·일회성 요청은 스킬로 저장하지 않고 일반 처리", 206, 848, 984, 28, 17, C.gray, false, "center");

  section(3, "구체적인 사용 예시 — 저장할 것과 매번 확인할 것을 구분", 916);
  box(42, 980, 646, 208, C.white, C.blue);
  pill("예시 A", 62, 996, 100, C.pale, C.blue);
  txt("과제 자료 정리", 176, 992, 480, 40, 24, C.blue, true);
  txt("저장: 파일 찾기 → 과목 판단 → 폴더 이동 → 결과 확인", 64, 1042, 596, 34, 18, C.teal, true);
  txt("매번 확인: 이번 주 파일명·개수·내용·예외 파일", 64, 1082, 596, 34, 18, C.orange, true);
  txt("검증: 이동 전후 파일 수 일치, 원본 누락 없음", 64, 1122, 596, 34, 18, C.ink, true);
  box(712, 980, 646, 208, C.white, C.teal);
  pill("예시 B", 732, 996, 100, C.pale2, C.teal);
  txt("PC 작업 모드 준비", 846, 992, 480, 40, 24, C.teal, true);
  txt("저장: 앱 실행 → 장치 설정 → 창 배치 → 결과 확인", 734, 1042, 596, 34, 18, C.teal, true);
  txt("매번 확인: 현재 앱·장치 상태·사용자 지정 값", 734, 1082, 596, 34, 18, C.orange, true);
  txt("검증: 대상 앱 실행, 설정 값과 창 상태 재확인", 734, 1122, 596, 34, 18, C.ink, true);

  section(4, "실제로 구현된 화면 — 같은 코드로 상태와 기록을 표시", 1214);
  const imgY = 1282;
  const imgW = 412;
  const imgH = 304;
  txt("대기·최근 완료 상태", 42, 1252, imgW, 28, 18, C.blue, true, "center");
  txt("안전 실행 상태", 494, 1252, imgW, 28, 18, C.teal, true, "center");
  txt("독립 검증 결과", 946, 1252, imgW, 28, 18, C.teal, true, "center");
  addImage(slide, images.idle, "실제 구현된 SKILLA 대기 화면", 42, imgY, imgW, imgH);
  addImage(slide, images.executing, "실제 구현된 SKILLA 실행 화면", 494, imgY, imgW, imgH);
  addImage(slide, images.result, "실제 구현된 SKILLA 결과 검증 화면", 946, imgY, imgW, imgH);
  box(42, 1608, 1316, 176, C.navy, C.navy);
  txt("핵심 구현", 64, 1624, 180, 34, 23, C.cyan, true);
  txt(
    "① 음성·텍스트 요청  ② 승인된 스킬 검색  ③ 등록된 기능만 실행  ④ 실제 PC 상태 재확인  ⑤ 실행 기록 기반 개정 초안",
    252,
    1618,
    1072,
    48,
    20,
    C.white,
    true,
  );
  txt(
    "안 되는 것을 된다고 표시하지 않음  ·  검증되지 않은 결과는 결과 창에 표시하지 않음  ·  스킬 개정은 사용자 승인 후 반영",
    64,
    1680,
    1270,
    54,
    18,
    "#D2E7F2",
    true,
    "center",
  );
  txt("그림 1. SKILLA 문제 해결 구조와 실제 구현 화면", 42, 1804, 1316, 28, 15, C.gray, false, "center");
  txt("※ 2쪽에서 사용 모델, 실험 환경, 평가 기준과 한계를 설명", 42, 1850, 1316, 44, 19, C.orange, true, "center");
}

function pageTwo(slide, images) {
  const H = helpers(slide);
  const { box, txt, section, pill } = H;
  box(0, 0, 1400, 186, C.navy, C.navy, "rect");
  txt("SKILLA  |  모델·실험·검증 부록", 54, 20, 1290, 68, 42, C.white, true);
  txt(
    "어떤 모델을 사용했고, 어떤 환경에서 무엇을 측정했는가",
    55,
    94,
    1290,
    42,
    22,
    "#D1E8F4",
  );
  txt(
    "구성·수치·한계를 코드와 실행 기록으로 확인",
    55,
    145,
    1050,
    24,
    14,
    C.cyan,
    true,
  );

  section(5, "실제 사용 모델과 역할", 212);
  const cards = [
    ["LLM", "z-ai/glm-5.3-flash", "요청 의도 분류 · 기본 계획 · 사용자가 요청한 스킬 초안", C.blue],
    ["STT", "faster-whisper-small", "한국어 음성을 문자 명령으로 변환", C.teal],
    ["TTS", "Edge Neural TTS", "ko-KR-SunHiNeural 음성으로 상태·결과 안내", C.orange],
  ];
  cards.forEach((item, index) => {
    const x = 42 + index * 448;
    box(x, 280, 420, 192, index === 1 ? C.pale2 : C.white, item[3]);
    pill(item[0], x + 20, 298, 88, index === 1 ? "#D4F5EC" : C.pale, item[3]);
    txt(item[1], x + 20, 342, 380, 42, 22, C.ink, true);
    txt(item[2], x + 20, 392, 380, 62, 17, C.gray);
  });
  txt(
    "LLM = 문장을 이해하고 순서를 만드는 언어 모델  |  STT = 음성을 글자로 변환  |  TTS = 글자를 음성으로 읽음",
    42,
    486,
    1316,
    42,
    16,
    C.ink,
    true,
    "center",
  );

  section(6, "재현 가능한 자체실험 환경", 548);
  box(42, 616, 612, 252, C.white, C.blue);
  txt("실험 PC", 64, 630, 200, 34, 23, C.blue, true);
  txt(
    "• Windows 11 Home 10.0.26300\n• AMD Ryzen 5 9500F 6-Core\n• RAM 15.4 GB\n• NVIDIA GeForce RTX 5060 Ti",
    64,
    676,
    560,
    160,
    19,
  );
  box(678, 616, 680, 252, C.pale2, C.teal);
  txt("재현 조건", 700, 630, 200, 34, 23, C.teal, true);
  txt(
    "• 작업 5종 × 3회 × 조건 4종 = 60개 관측\n• seed 2026102001, 실행 묶음 developer10\n• 매 실행 전 같은 초기 파일 묶음 생성\n• 초기 상태 SHA-256 불일치 시 수집 거부\n• 실패·계획 오류·예산 초과도 제외하지 않음",
    700,
    672,
    630,
    174,
    18,
  );

  section(7, "비교 조건과 평가 기준", 892);
  const conditionText = [
    ["SK0", "스킬 없음"],
    ["SK1", "일반 지침"],
    ["SK2", "최초 스킬"],
    ["SK3", "실패 반영 개정 스킬"],
  ];
  conditionText.forEach((item, index) => {
    const x = 42 + index * 329;
    box(x, 960, 304, 84, index === 3 ? C.pale2 : C.white, index === 3 ? C.teal : C.line);
    txt(item[0], x + 12, 974, 70, 52, 25, index === 3 ? C.teal : C.blue, true, "center");
    txt(item[1], x + 84, 974, 204, 52, 18, C.ink, true, "center");
  });
  box(42, 1064, 1316, 104, C.yellow, C.orange);
  txt(
    "성공률: 독립 검증 통과 비율  |  시간: 요청 시작~검증 완료  |  호출 수: LLM 사용 횟수  |  토큰: 입력+출력  |  확인: 사용자 개입 횟수",
    62,
    1074,
    1276,
    44,
    17,
    C.ink,
    true,
    "center",
  );
  txt(
    "성공 여부는 AI의 ‘완료했습니다’ 문장이 아니라 파일·창·폴더의 실제 상태로 판정",
    62,
    1120,
    1276,
    34,
    18,
    C.red,
    true,
    "center",
  );

  section(8, "자체실험 결과와 해석", 1192);
  const cols = [42, 188, 390, 602, 814, 1034];
  const widths = [146, 202, 212, 212, 220, 324];
  ["조건", "성공", "평균 시간", "평균 호출", "평균 토큰", "해석"].forEach((value, index) => {
    box(cols[index], 1260, widths[index], 48, C.navy, C.navy, "rect");
    txt(value, cols[index] + 4, 1262, widths[index] - 8, 42, 17, C.white, true, "center");
  });
  const rows = [
    ["SK0", "10/15", "18.783초", "2.200", "3,759.5", "스킬 없음"],
    ["SK1", "12/15", "18.614초", "2.467", "4,268.9", "일반 지침"],
    ["SK2", "12/15", "25.742초", "3.000", "5,680.9", "최초 스킬"],
    ["SK3", "14/15", "12.367초", "1.867", "3,135.7", "가장 높은 성공·낮은 평균 비용"],
  ];
  rows.forEach((row, r) => {
    const y = 1308 + r * 52;
    row.forEach((value, index) => {
      const best = r === 3;
      box(cols[index], y, widths[index], 52, best ? C.pale2 : C.white, best ? C.teal : C.line, "rect");
      txt(value, cols[index] + 4, y + 2, widths[index] - 8, 46, index === 5 ? 15 : 17, best ? C.teal : C.ink, best, "center");
    });
  });
  txt(
    "SK3 대 SK0: 평균 시간 34.2% 감소, 평균 토큰 16.6% 감소  ·  복잡한 파일 정리에서 차이가 주로 관측",
    42,
    1528,
    1316,
    38,
    18,
    C.teal,
    true,
    "center",
  );

  section(9, "스킬 검토와 개정 후보 화면 — 기록을 사람이 확인", 1590);
  txt("스킬 내용·허용 기능 검토", 42, 1646, 640, 28, 18, C.blue, true, "center");
  txt("실패·예외 근거와 개정 대상 검토", 718, 1646, 640, 28, 18, C.orange, true, "center");
  addImage(slide, images.skills, "실제 구현된 SKILLA 스킬 관리 화면", 42, 1676, 640, 225);
  addImage(slide, images.review, "실제 구현된 SKILLA 개정 후보 검토 화면", 718, 1676, 640, 225);
  box(42, 1906, 1316, 54, C.redp, C.red);
  txt(
    "한계: 개발 PC 1대·15개 블록의 소규모 자체실험이며, Holm 보정 뒤 성공률 차이는 통계적으로 유의하지 않음",
    56,
    1912,
    1288,
    40,
    16,
    C.red,
    true,
    "center",
  );
}

async function imageBytes(file) {
  const data = await fs.readFile(file);
  return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
}

async function main() {
  await fs.mkdir(OUT, { recursive: true });
  await fs.mkdir(PREVIEW, { recursive: true });
  const images = {
    idle: await imageBytes(path.join(UI, "SKILLA_실제구현_대기중.png")),
    executing: await imageBytes(path.join(UI, "SKILLA_실제구현_실행중.png")),
    result: await imageBytes(path.join(UI, "SKILLA_실제구현_결과검증.png")),
    skills: await imageBytes(path.join(UI, "SKILLA_실제구현_스킬관리.png")),
    review: await imageBytes(path.join(UI, "SKILLA_실제구현_개정후보검토.png")),
  };
  const deck = Presentation.create({ slideSize: { width: 1400, height: 1980 } });
  const first = deck.slides.add();
  first.background.fill = C.bg;
  pageOne(first, images);
  const second = deck.slides.add();
  second.background.fill = C.bg;
  pageTwo(second, images);

  const filename = "SKILLA_졸업작품_포스터_실제구현_종합본.pptx";
  await (await PresentationFile.exportPptx(deck)).save(path.join(OUT, filename));
  for (const [index, slide] of [first, second].entries()) {
    const png = await deck.export({ slide, format: "png", scale: 0.65 });
    await fs.writeFile(
      path.join(PREVIEW, `actual-poster-${index + 1}.png`),
      new Uint8Array(await png.arrayBuffer()),
    );
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(
      path.join(PREVIEW, `actual-poster-${index + 1}.layout.json`),
      new Uint8Array(await layout.arrayBuffer()),
    );
  }
  console.log(path.join(OUT, filename));
}

await main();
