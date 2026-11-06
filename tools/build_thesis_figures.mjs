import fs from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const root = "C:\\Users\\YongE\\Desktop\\SKILLA";
const out = path.join(root, "output", "figures");
const purple = "#705781";
const purpleLight = "#EEE9F2";
const teal = "#4D8B88";
const blue = "#4F6E9A";
const ink = "#24212A";
const gray = "#6B6670";
const line = "#CFC7D5";

const esc = (s) => s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

function base(title, subtitle = "") {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
  <rect width="1600" height="900" fill="#FFFFFF"/>
  <rect x="0" y="0" width="1600" height="118" fill="${purple}"/>
  <text x="800" y="58" font-family="Malgun Gothic, sans-serif" font-size="42" font-weight="700" fill="#FFFFFF" text-anchor="middle">${esc(title)}</text>
  <text x="800" y="94" font-family="Malgun Gothic, sans-serif" font-size="21" fill="#EEE8F2" text-anchor="middle">${esc(subtitle)}</text>`;
}

function text(x, y, value, size = 26, weight = 400, fill = ink, anchor = "middle") {
  return `<text x="${x}" y="${y}" font-family="Malgun Gothic, sans-serif" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}">${esc(value)}</text>`;
}

function box(x, y, w, h, label, fill = purpleLight, stroke = purple, size = 25) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="18" fill="${fill}" stroke="${stroke}" stroke-width="3"/>${text(x + w / 2, y + h / 2 + 9, label, size, 700, ink)}`;
}

function arrow(x1, y1, x2, y2, color = purple) {
  return `<line x1="${x1}" y1="${y1}" x2="${x2 - 14}" y2="${y2}" stroke="${color}" stroke-width="7" stroke-linecap="round"/>
  <polygon points="${x2},${y2} ${x2 - 24},${y2 - 15} ${x2 - 24},${y2 + 15}" fill="${color}"/>`;
}

async function save(name, svg) {
  await sharp(Buffer.from(svg)).png().toFile(path.join(out, name));
}

async function main() {
  await fs.mkdir(out, { recursive: true });

  let svg = base("SKILLA의 전체 실행 흐름", "요청 이해부터 독립 검증과 스킬 개정 후보 생성까지");
  const labels = ["사용자 요청", "요청 분석", "스킬 검색", "계획 생성", "권한 검사", "기능 실행", "결과 검증", "실행 기록"];
  labels.forEach((label, i) => {
    const x = 55 + i * 190;
    svg += box(x, 245, 155, 116, label, i === 6 ? "#E4F1EF" : purpleLight, i === 6 ? teal : purple, 22);
    if (i < labels.length - 1) svg += arrow(x + 158, 303, x + 188, 303);
  });
  svg += `<path d="M 1400 410 C 1400 545 1110 545 1110 650" fill="none" stroke="${teal}" stroke-width="7"/>
  <polygon points="1110,670 1094,642 1126,642" fill="${teal}"/>`;
  svg += box(820, 670, 580, 118, "실패 근거로 개정 후보 생성  DRAFT", "#E4F1EF", teal, 25);
  svg += text(800, 470, "검증된 스킬만 계획기에 제공하고, 허용 기능 밖의 행동은 차단한다", 28, 700, purple);
  svg += text(800, 525, "실행 성공 응답과 별도로 실제 파일·프로세스·창 상태를 다시 확인한다", 26, 400, gray);
  svg += text(800, 840, "개정 후보는 기존 스킬을 자동으로 덮어쓰지 않으며 검토 후 활성화된다", 25, 700, teal);
  svg += `</svg>`;
  await save("skilla_system_flow.png", svg);

  svg = base("스킬에 저장하는 정보", "반복되는 방법과 실행마다 바뀌는 값을 분리한다");
  svg += `<rect x="90" y="185" width="650" height="585" rx="22" fill="#F6F3F8" stroke="${purple}" stroke-width="4"/>
  <rect x="860" y="185" width="650" height="585" rx="22" fill="#F2F7F7" stroke="${teal}" stroke-width="4"/>`;
  svg += text(415, 250, "스킬에 저장", 34, 700, purple);
  svg += text(1185, 250, "실행할 때 다시 확인", 34, 700, teal);
  const left = ["반복되는 작업 순서", "분류와 판단 기준", "허용 기능 목록", "완료 확인 방법", "스킬 ID와 버전 상태"];
  const right = ["현재 파일명과 파일 수", "실제 경로와 폴더 상태", "열린 프로그램과 창 상태", "예외 상황과 동적 입력", "이번 실행의 결과 근거"];
  left.forEach((v, i) => { svg += box(165, 310 + i * 86, 500, 62, v, "#FFFFFF", line, 23); });
  right.forEach((v, i) => { svg += box(935, 310 + i * 86, 500, 62, v, "#FFFFFF", line, 23); });
  svg += arrow(745, 475, 850, 475, blue);
  svg += text(800, 820, "바뀌는 값은 입력으로 두고 반복되는 방법만 재사용한다", 30, 700, blue);
  svg += `</svg>`;
  await save("skilla_skill_structure.png", svg);

  svg = base("네 조건 완전 대응 블록 실험", "같은 작업과 반복 번호 안에서 스킬 제공 방식만 바꾼다");
  const conds = [
    ["SK0", "스킬 없음", "#F0F0F0", "#777777"],
    ["SK1", "일반 지침", "#EEF3F8", blue],
    ["SK2", "최초 스킬", purpleLight, purple],
    ["SK3", "개정 스킬", "#E4F1EF", teal],
  ];
  conds.forEach((c, i) => {
    const x = 110 + i * 375;
    svg += `<rect x="${x}" y="235" width="300" height="240" rx="22" fill="${c[2]}" stroke="${c[3]}" stroke-width="4"/>`;
    svg += text(x + 150, 315, c[0], 44, 700, c[3]);
    svg += text(x + 150, 382, c[1], 29, 700, ink);
    svg += text(x + 150, 432, "동일 작업·동일 초기 상태", 20, 400, gray);
  });
  svg += `<line x1="260" y1="545" x2="1340" y2="545" stroke="${line}" stroke-width="5"/>
  <line x1="260" y1="545" x2="260" y2="600" stroke="${line}" stroke-width="5"/>
  <line x1="635" y1="545" x2="635" y2="600" stroke="${line}" stroke-width="5"/>
  <line x1="1010" y1="545" x2="1010" y2="600" stroke="${line}" stroke-width="5"/>
  <line x1="1340" y1="545" x2="1340" y2="600" stroke="${line}" stroke-width="5"/>`;
  svg += box(405, 615, 790, 120, "독립 검증기가 실제 Windows 상태로 성공 여부 판정", "#FFFFFF", purple, 27);
  svg += text(800, 800, "측정: 성공률  실행 시간  LLM 호출 수  토큰 사용량  사용자 확인 횟수", 27, 700, purple);
  svg += text(800, 850, "모델 설정·기능 목록·초기 자료·완료 판정 기준은 블록 안에서 고정", 23, 400, gray);
  svg += `</svg>`;
  await save("skilla_experiment_design.png", svg);

  console.log(out);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
