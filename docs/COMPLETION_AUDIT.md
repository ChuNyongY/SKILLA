# 원 계획서 대비 완료 감사

최종 갱신: 2026-10-19

## 2026-10-20 최종 통합 감사

- 전체 자동시험을 다시 실행하여 1,091개 통과·5개 건너뜀을 확인했다. 제품 소스와 시험의 Ruff 검사는
  통과했고, strict mypy는 151개 소스 파일에서 오류가 없었다.
- 절대 경로로 source doctor 15/15, Credential Manager 기반 사전점검 3/3, 13개 기능 서비스 조립
  `ready=true`, `capture_running=false`, `host_state=CREATED`를 다시 확인했다.
- 설치된 `0.1.9` 패키지는 manifest 1,826개 파일을 모두 검증했고 시작 메뉴 등록 상태는
  `ALREADY_REGISTERED`였다. 설치본 `JAVIS.exe smoke-system-info`도
  `SUCCEEDED/ALL_ACTIONS_VERIFIED`로 끝났다.
- 연결된 주 화면은 `DISPLAY1` 2560×1440이며 저장된 대상과 일치했다. 현재 NIM 자격 증명은
  값 노출 없이 존재 여부만 확인했고 제품 사전점검을 통과했다.
- 확인 실험 묶음은 15개 완전 대응 블록·60개 관측이며, 60개 결과 근거 파일과 observations·report의
  SHA-256이 manifest와 모두 일치했다. 분석기를 다시 실행해 SK0 10/15, SK1 12/15, SK2 12/15,
  SK3 14/15와 Holm 보정 p값 0.375·1.000·1.000을 재현했다.
- 졸업논문 초안, 관련 논문 방법론 정리본과 13장 최종 발표본이 존재하고 텍스트 자리표시자나 이전
  `153개 파일` 표기는 없다. 발표본의 패키지·레이아웃·글꼴·편집 가능한 성공률 차트 검증을 통과했다.
- 공개 배포용 코드 서명과 외부 참가자 일반화 실험은 완료 범위가 아니다. 이 제한을 논문과 발표본에
  명시했으며, 로컬 시연·제출용 프로그램 완성과 자체 확인 실험 완료를 보편적 성능 우월성으로
  표현하지 않는다.

## 2026-10-19 0.1.9 스킬 검토 창 감사

- 기존 텍스트 명령 창에서 스킬 검토 창을 열 때 두 번째 `Tk` 루트와 중첩 실행 루프를 만들던
  결함을 같은 루트의 `Toplevel` 보조 창으로 수정했다. 실제 Windows 화면에서
  `[신규] Windows 시스템 정보 조회 (v1)`이 표시되고, 저장소 조회에서도 같은 ID·버전·DRAFT
  상태임을 독립적으로 확인했다.
- 초안이 없을 때는 빈 화면 대신 실행 기록을 `스킬 후보 검토`에서 초안으로 만드는 절차를
  안내하도록 회귀 시험을 추가했다.
- 전체 1,096개 시험 중 1,091개 통과·환경 의존 5개 건너뜀, Ruff, strict mypy 151 files가
  통과했다. 0.1.9 r1 package는 1,826개 manifest 항목, 사전점검 3/3, 13-capability service
  `CREATED`, `capture_running=false`를 통과했다.
- Setup 실제 설치 결과는 `SUCCESS/code=0`이며 시작 메뉴 대상은 설치된 0.1.9다. 설치본의
  `smoke-system-info`는 `SUCCEEDED/ALL_ACTIONS_VERIFIED`, 화면 열거는 주 화면 `DISPLAY1`
  2560×1440을 반환했다.
- Setup SHA-256은 `d7fe1397a9cf9bcd9bb3dbee93dea04cafda6b48e0bf32d16e6d939f01a76f8e`,
  wheel은 `a0c96269c272945cb475851fd2b7d0fd4ad1cfd2f578f3dade78f2277da50c8b`,
  package manifest는 `93c3f99737c35aa943ede07b281969a71193d5ec754a10a8b3de119f1b0c8a27`다.
  패키지의 `NIM.txt`는 0건이며 release audit의 manifest·Setup hash는 PASS다.
- console/tray/Setup 세 파일은 모두 `NotSigned`라 서명 항목은 예상대로 FAIL이다. 따라서
  로컬 시연용 설치본 검증 완료를 공개 배포용 코드 서명 완료로 과장하지 않는다.

## 2026-10-19 0.1.8 결함 수정 감사

- 앱 버전과 사용자 상태 형식을 분리하고, 현재 설치 버전의 SQLite 데이터는 SQLite 백업 API로
  `state/v1`에 이관한다. 기존 목적 파일은 덮어쓰지 않으며 심볼릭 링크·재분석 지점은 거부한다.
- 검증 완료 결과만 화면 표시 저장소에 들어가며, 시스템 정보의 허용 항목과 파일 개수 외의
  관측 데이터는 고정 성공 문구로 축약한다.
- 텍스트 명령·스킬 후보 검토 화면의 상태 문구와 초안 생성 피드백을 한국어 중심으로 수정했다.
- 0.1.8이 직전 0.1.7 상태를 찾는 실제 업그레이드 경로를 시험과 설치본 양쪽에서 검증했다.
  초안 `12f0715a-1a19-4fd4-a15d-90b89ca3a028`의 키, 버전 1, DRAFT 상태가 유지됐다.
- 전체 1,095개 시험 중 1,090개가 통과하고 환경 의존 시험 5개가 건너뛰어졌으며, Ruff와 strict
  mypy 151 source files가 통과했다. 별도 가상환경 wheel 설치, 버전·신규 결과 저장소 import,
  CLI 도움말도 통과했다.
- 최종 1,826-entry r2 package manifest와 Setup sidecar hash는 PASS다. Setup 실제 설치는 exit 0,
  설치본 사전점검 3/3, 13-capability service `CREATED`, `capture_running=false`, 실제 텍스트 명령 창
  생성·정상 종료를 통과했다. Setup SHA-256은
  `023b73d46b98b643f5555111091afed6346951213a3a2670fd77b6d9a9e65fb7`이다.
- package·wheel·Setup에서 `NIM.txt`와 실제 키 일치는 0건이다. console/tray/Setup은 모두
  `NotSigned`라서 로컬 시연·제출용 검증 완료와 공개 서명 배포 완료는 구분한다.

## 2026-10-18 첫 실행 설정·0.1.7 감사

- NIM 자격 증명이 `ABSENT`이면 마스킹된 로컬 초기 설정 창을 열고 Windows 자격 증명 관리자 저장과
  재읽기 검증을 통과한 뒤에만 기존 제품 시작 경로로 들어간다. 취소·저장 실패·예외·허위 성공 뒤
  재검증 실패는 제품 실행과 사전점검을 호출하지 않는다.
- 비밀값은 `SecretStr`로만 저장기에 전달하고 창 입력값을 즉시 비운다. 저장기나 UI 예외에 키·사용자
  경로가 포함돼도 고정 문구 외의 값은 표시하지 않는 시험을 추가했다.
- 전체 시험 **1,085 passed, 4 skipped**, Ruff와 strict mypy 150 files를 통과했다. 0.1.7 wheel은
  새 가상환경 설치·version import·CLI 도움말을 통과했다.
- 0.1.7 실제 설치는 `SUCCESS`, 재설치는 `ALREADY_VERIFIED`였고 설치본 manifest 1,826개,
  사전점검 3/3, 13개 기능 서비스 조립과 마이크 미개방을 재검증했다. 시작 메뉴 링크의 실제 실행으로
  `JAVIS 텍스트 명령` 창을 확인하고 정상 종료했다.
- 최종 r2 Setup SHA-256은
  `a9003f4465f838b32540827ccb21e91a509e46e54ecbfdf6c94a0cd6de980228`, package manifest는
  `e4cc23da0bd5e511a10401602f55722e119d52aa28c965cd11271fa48aaadf16`, 두 실행 파일은 각각
  `815c7a5af68ae43b8770c690e5cf24590b277113415121629c0578354b63ef84`,
  `88ff9db277f3e108715227add9b861dbfe7925f3b1e318c120abddb67cc7466d`다. package의 민감한
  파일명과 실제 키 byte 일치 검색은 0건이다.
- release audit은 manifest·Setup hash PASS, 세 서명 `SIGNATURE_INVALID`이며 실제 파일도 모두
  `NotSigned`다. 사용 가능한 현재 사용자 코드 서명 인증서가 0개이므로 공개 배포 완료라고 표시하지
  않는다.
- 이 감사는 기존 자격 증명이 있는 실제 시작 경로와 초기 설정 로직의 자동시험을 증명한다. 실제
  자격 증명을 삭제해 첫 실행 창을 다시 띄우지는 않았으므로 사용자 비밀 상태를 검증 때문에 변경하지
  않았다.

## 2026-10-18 시작 실패 가시성 감사

- 스킬 중심 연구 제품임에도 기본 텍스트 UI에서 스킬 catalog와 후보 trace를 열 수 없던 접근성
  결함을 수정했다. 0.1.6 기본 창은 `스킬 관리`, `스킬 후보 검토`, `작업 화면 선택`을 같은 두 번째
  버튼 행에 제공하고 tray와 동일한 객체·workflow를 호출한다. 실패 문구는 고정값만 사용한다.

- 더블클릭 경로가 주 UI 생성 전에 Credential Manager, 제품 구성과 필수 구성 요소를 확인한다.
  누락·손상·예상하지 못한 실패는 고정 한국어 안내와 안정적인 비정상 종료 코드로 끝나므로 이전처럼
  windowed 프로세스가 설명 없이 닫히는 경로를 제거했다.
- 개인 정보 최소화 시험은 실제 예외에 API 키 형태와 사용자 경로가 포함돼도 오류 창에 전달되지 않음을
  확인한다. 제품 실행기는 사전점검을 통과한 경우에만 호출되고, 성공 시에는 오류 창이 표시되지 않는다.
- 첫 0.1.4 실제 설치에서 과거 `primary` 좌표와 현재 좌표가 달라 시작이 차단되는 결함을 발견했다.
  `primary` 모드는 현재 주 화면 descriptor를 원자적으로 갱신하고, 명시적 `device` 모드는 계속
  fail-closed하도록 수정한 0.1.5를 새 배포물로 만들었다.
- 최종 0.1.6 one-folder 1,826개 파일은 manifest `VERIFIED`, 사전점검 3/3, 13개 기능 서비스 조립과
  마이크 미개방을 통과했다. Setup 최초 설치 `SUCCESS`, 재설치 `ALREADY_VERIFIED`, 0.1.6 시작 메뉴
  target·빈 인자·작업 폴더와 실제 텍스트 명령 창 생성·정상 종료를 확인했다.
- 전체 시험은 1,078 passed, 4 skipped이며 Ruff와 strict mypy 150 files를 통과했다. wheel도 별도
  가상환경에서 설치·핵심 모듈 import·CLI 도움말을 통과했다. 최종 Setup SHA-256은
  `5f90c3cd579db2797ab8d1d5ea062810b78ec1ef63737c98dc248c007888f091`이다.
- 0.1.6 창에 실제 한국어 명령을 다시 입력하는 마지막 UI 반복은 사용자가 물리적 Escape로 화면 조작을
  중단해 수행하지 않았다. 같은 NIM→정책→실행→검증→trace 경로의 설치본 E2E는 0.1.3에서 통과했고,
  0.1.6에는 시작·회귀·서비스 조립 근거가 있으나 이를 0.1.6 UI E2E로 과장하지 않는다.
- 0.1.6 release audit은 manifest·Setup hash PASS, 세 Authenticode signature FAIL이다. 현재 사용자
  저장소의 사용 가능한 code-signing 인증서가 0개이므로 공개 배포 완료는 외부 인증서가 생기기 전까지
  증명할 수 없다. 실제 다중 모니터는 두 번째 화면이 없고, 한국어 호출어 최종 검증은 새 음성 자료와
  장치 사용 동의가 필요하므로 자동시험으로 대체하지 않는다.

## 2026-10-17 제품 완성도 감사

- 사용자 설계도의 핵심인 스킬 검색·재사용·실행 기록·개정 구조를 유지하면서, 실제 제품 사용에
  필요한 텍스트 명령 창과 작업 화면 선택을 제품 조립 경로에 추가했다. 텍스트와 음성은 같은
  planner·정책·executor·verifier·skill trace를 사용하지만, 기본 더블클릭 경로는 마이크를 열지 않는다.
- 실제 NIM 텍스트 명령에서 `system.info.read` 실행과 독립 검증, 스킬 실행 기록까지 완료했다.
  one-folder와 격리 설치 폴더를 각각 작업 위치로 둔 배포용 EXE의 실제 `JAVIS 텍스트 명령` 창
  생성, 현재 `DISPLAY1` 열거·선택, 13-capability 제품 서비스 조립을 각각 실행해 확인했다.
- 설치된 0.1.3 기본 텍스트 창의 `작업 화면 선택` 버튼을 실제 화면에서 확인하고 클릭해 주 화면,
  정확한 DISPLAY1, 전면 창 추적 선택지가 표시되는 것을 확인했다. 저장하지 않고 취소했으며
  시험 창을 모두 닫아 사용자 설정을 변경하지 않았다.
- 설치본 시작 메뉴부터 실제 한국어 텍스트 입력, NIM 계획, `system.info.read`, 독립 검증, 완료 화면,
  스킬 후보 trace 저장까지 한 번의 실제 제품 동선으로 통과했다. 외부 감사 원장 5개 record의
  hash chain도 직접 검증했다. 이는 이전의 소스 직접 호출 smoke보다 강한 설치본 E2E 근거다.
- 전체 자동시험은 1,068 passed, 4 skipped이고 제품 소스·시험 Ruff 및 strict mypy 149 files를
  통과했다. 4개 skip은 실행 환경 또는 선택 의존성이 있는 시험으로 실패를 성공으로 바꾸지 않았다.
- 0.1.3 r1 one-folder 1,826개 파일과 설치본 manifest가 모두 `VERIFIED`다. 실제 현재 사용자
  위치의 최초 설치는 `SUCCESS/code=0`, 동일 Setup 재설치는 `ALREADY_VERIFIED/code=0`이고
  설치본의 화면 열거와 Credential 기반 제품 서비스 검사도 exit 0이었다. 기존 0.1.0~0.1.2는
  덮지 않았다.
- 설치기가 만든 현재 사용자 시작 메뉴 링크는 설치된 0.1.3의 windowed 실행 파일, 빈 인자, 정확한
  작업 폴더·설명·아이콘을 다시 읽어 검증했다. 동일 부모 아래의 정확한 이전 버전 링크만 갱신하고
  외부 링크는 거부한다. 실제 연속 업그레이드 뒤 링크를 실행해 0.1.3 hash의 새 process와
  `JAVIS 텍스트 명령` 창을 확인했으며, 다른 대상의 기존 링크는 덮거나 제거하지 않는 시험도 통과했다.
  package와 wheel의 API key 형태 검색은 0건이다.
- 기능 완성 관점에서 텍스트 기반 로컬 스킬 에이전트는 시연 가능한 상태다. 다만 실행 파일 세 개가
  `NotSigned`이고, 현재 PC가 단일 화면이므로 실제 다중 화면 이동 시험은 없으며, 음성 호출어 모델은
  기존 실제 pilot 기준을 통과하지 못했다. 따라서 로컬 텍스트 시연 가능과 공개 배포·음성 완성을
  구분한다.

## 2026-10-17 발표 산출물 감사

- 스킬 중심 연구 목표와 32블록·128관측 결과를 13장 졸업발표 자료에 반영했다.
  표시한 조건별 성공 수, 시간·호출·토큰 감소율, Holm 보정 p값을 최신
  `report.json`과 다시 계산해 일치함을 확인했다.
- 최종 PPTX는 13장·1개 수정 가능 차트와 내장 workbook 자료를 포함하며, package·layout·font·
  first-party import·native chart 검사를 통과했다. 모든 장을 렌더링하고 수정 장을
  확대 검토해 잘림·겹침·낮은 대비를 수정했다. PPTX SHA-256은
  `3572f3d3446efa147fb829729fe07274ab5f52fd42ab2025dab880c17f108358`이다.
- 기존 권한·위험도 중심 교수님 정리본을 스킬 재사용·개정 중심으로 다시 써서
  발표자료·연구계획·실제 결과 사이의 목적 불일치를 제거했다. 단일 개발자 예비실험,
  실제 참가자 부재, 미서명 배포물은 미완료 사항으로 유지했다.
- 실제 참가자 자료는 없지만, 운영안은 현재 코드의 `SK0~SK3` 일정·관측·분석 계약과 일치하도록
  수정했다. 연구윤리 적용 확인, 자발적 동의, 무작위 ID, 개인정보 비수집, 가역적·격리 실행,
  중단·철회·폐기 규칙을 자료 수집 전 필수 조건으로 고정했다.
- 참가자 문서 초안 세 종을 추가했지만, `[확정 필요]` 항목과 연구윤리 확인이 남아 있으므로
  참가자 실험 준비 완료나 실험 완료로 판정하지 않는다. 동의 원본에 개인 식별자가 포함되는 경우
  실험 관측과 분리 보관하는 경계를 명시했다.

## 2026-10-16 스킬 연구·배포 갱신

- 연구 중심을 스킬 생성·검색·재사용·실행 기록·개정으로 고정한 뒤 파일 분류·PDF 열기·폴더 목록,
  확장자별 파일 정리와 Explorer 폴더 열기에서 SK0~SK3 완전 대응 32블록·128관측을 수집했다.
  SK0 26/32, SK1 24/32, SK2 30/32, SK3 32/32 성공했다. SK3 대 SK1의 Holm 보정 p값은
  0.0234375지만 SK0 비교는 0.0625, SK2 비교는 0.5다. 이는 개발자 파일럿이며 사용자 연구나
  일반적 우월성의 증거가 아니다.
- 폴더 목록 최초 실행의 모델 출력 한도 기록 불일치를 발견해 원본과 통합 묶음을 무효 보관하고,
  정확한 1,000-token 구성 hash로 3블록을 다시 수집했다. 무효 자료는 현재 통합 분석에 포함하지
  않으며, 다섯 작업의 유효 관측 128개만 사용한다.
- 최신 전체 회귀는 1,040 collected, 1,037 passed, 3 skipped다. 제품 소스·시험·열 개 검증 도구는
  Ruff clean이고 strict mypy는 155 source files에서 통과했다.
- 최신 소스 doctor 15/15, Credential preflight 3/3, 13-capability service `CREATED`와
  `capture_running=false`를 재확인했다. 안전 평가는 8 PASS / 7 NOT_RUN이며 snapshot VM과
  interactive actual 근거가 남아 `all_required_evidence_complete=false`다.
- 같은 소스에서 S01 Chrome, S02 음량·복원, S03 메모리/PDF/Edge, Explorer exact-folder,
  Settings display/sound/network/bluetooth와 tray actual reversible smoke를 다시 통과하고 각 창을
  정리했다. 이는 현재 host 기능 근거이며 VM 50셀·참가자 연구의 대체 증거는 아니다.
- 최신 package의 1,826-entry manifest는 source verifier에서 `VERIFIED`됐고 새 wheel은 깨끗한
  가상환경 설치·핵심 import·CLI를 통과했다. 설치 결과 영수증을 추가한 r5 Setup은 격리 최초 설치,
  source·설치본 manifest, frozen doctor 필수 항목, Credential preflight, 서비스 조립, 외부 state와
  재설치 `ALREADY_VERIFIED`를 통과했다. 손상 설치 부정 시험은 `FAILED/code=13`과 비덮어쓰기를
  확인했다. 직전 r3의 Code Integrity 차단은 r5에서 재현되지 않았고 현재 one-folder 직접 verifier도
  통과했다. package와 Setup hash 감사도 통과했지만 세 실행 파일은 `NotSigned`이므로 공개 배포는
  완료가 아니다.
- 아래 2026-10-07 표와 수치는 원 계획의 안전 하네스 감사 기록이다. 최신 스킬 연구와 배포 수치는
  `docs/STATUS.md`, `docs/SKILL_RESEARCH_PLAN.md`와 `docs/COMBINED_SKILL_STUDY_20261016.md`를
  기준으로 한다.

## 2026-10-07 음성·사용자 검증 갱신

- 전체 회귀는 **829 collected, 826 passed, 3 skipped**, line coverage 83%, Ruff clean,
  mypy strict 126 source files다.
  소스 실행 기준 doctor 15/15, Credential preflight 3/3, 13-capability service `CREATED`와
  `capture_running=false`를 재확인했다.
- 실제 기본 마이크에서 frame과 음성 energy가 들어오는 것은 확인했지만 공식 영어
  `hey_jarvis_v0.1`은 한국어식·영어식 발화를 모두 감지하지 못했다. 실패 지점은 마이크나 STT보다
  호출어 모델이다.
- 동의·SHA-256이 결합된 로컬 WAV만 읽는 FAR/FRR 평가기와 CLI를 추가했다. 추론 실패를 분모에서
  빼지 않고 양성 표본은 FN, 비호출어 표본은 FP로 보수적으로 계산한다.
- 자료 형식 1.1은 거리·소음·비식별 세션 조건을 기록하고 각 조건의 양성·비호출어 균형을 강제하며,
  전체 수치와 같은 실패 산입 원칙으로 조건별 FAR/FRR을 낸다. 1.0 자료는 미지정 조건으로 읽는다.
- 별도 보정 corpus에서 FAR 상한을 먼저 만족시키고 FRR·FAR·높은 임계값 순으로 0.50~0.99 중 하나를
  고정하는 offline calibration CLI를 추가했다. 가능한 후보가 없으면 임계값을 만들지 않는다.
- 사용자 동의 아래 실제 4표본 pilot을 수집했다. WAV 형식·길이·hash·protected ACL·nonzero
  신호·clipping 0이 모두 확인됐지만, 공식 영어 모델의 임계값 0.5 결과는 TP 0/TN 2/FP 0/FN 2,
  FAR 0.0/FRR 1.0이었다. 따라서 실제 수집·평가 경로는 직접 입증됐지만 현재 모델은 이번 pilot
  조건에서 기준 미달이다. 표본 수가 너무 작으므로 논문 성능 결론에는 쓰지 않는다.
- `wakeword-forge` 계열 후보용 RepCNN 어댑터와 별도 평가 CLI를 추가했다. 해시·크기·ONNX 입출력,
  3초 창과 400 ms hop을 검증하지만 제품 기본 경로에는 연결하지 않았다. 공개 `okay-hermes`의 무음
  점수 `0.624035120`과 합성 CLI FAR 0/FRR 1은 연결 증거일 뿐 한국어 성능 근거가 아니다.
- 실제 고정 한국어 TTS 스피커 재생과 Windows Hello `VERIFIED`는 PASS했다. TTS 사용자 평가는
  3/5이며 번역기 같은 말투를 개선해야 한다. 실제 동의 한국어 corpus와 맞춤 `Jarvis` 모델은 없다.

## 2026-10-06 재검증

- Chrome 자동 업데이트로 등록 SHA-256이 달라진 상태를 발견해 Google Authenticode 발행자를 다시 확인하고 `config/apps.json`을 현재 해시로 갱신했다.
- 최신 Chrome은 인자 없는 재실행에서 새 창을 만들지 않을 수 있으므로, 앱 등록부가 허용하는 고정 `--new-window` 하나만 `process.launch`가 전달하도록 계약을 확장했다. 임의 LLM 인자는 계속 거부한다. 실제 S01에서 새 PID/HWND 확인과 정확한 창 정리가 PASS했고, Explorer와 S03 PDF→Edge 가역 시험도 PASS했다.
- 전체 회귀는 **766 passed, 3 skipped, line coverage 83%**, Ruff clean, mypy strict 123 source files다. 소스 실행 기준 doctor 15/15, Credential `PRESENT`, preflight 3/3, 13-capability service `CREATED`를 재확인했다.
- pywin32가 frozen 환경에서 예상 밖 예외를 반환할 때 고정 target을 Windows `CredReadW`로 읽는 제한된 대체 경로를 추가했다. 실제 frozen `JAVIS.exe`에서 Credential `PRESENT`, preflight 3/3, 13-capability service `CREATED`, capture 미실행을 직접 재현했다.
- 새 wheel SHA-256은 `86256abc55e715f9d6748bb3dd385030f95d989a8e599d99973bcee3f4a937c9`다. one-folder manifest 1,826개 항목은 exact verify를 통과했고 manifest SHA-256은 `4127ddbac7d2fee49d6d392031c4f7dac8766d343820d9ec1931ef31ea402abc`다. Setup SHA-256은 `3690062f16e7172fb96e372f603d736f2e2fe81323f3cbb55176070b17c70c22`이며 sidecar와 일치한다. console/tray/Setup은 모두 `NotSigned`다.
- PowerShell 스크립트가 시스템 정책에 차단되는데도 IExpress가 0을 반환하는 설치 결함을 발견했다. 정책 우회 없이 Windows `cmd`·`certutil`·`tar`와 staged `JAVIS.exe verify-package`를 사용하는 설치 진입부로 교체했다. 깨끗한 `%LOCALAPPDATA%\JAVIS-PC\0.1.0`에 실제 Setup 최초 설치 PASS, 11.5초 내 정상 종료, 설치 manifest와 source manifest 일치, Credential preflight 3/3, 13-capability service `CREATED`, autostart `ABSENT`를 확인했다.
- benchmark ledger는 completed 70, ready 0, snapshot VM environment unavailable 50, runner unavailable 0으로 재검증됐다. safe evaluation은 8 PASS / 7 NOT_RUN이다.
- snapshot VM 전용 exact-cell 요청 50개를 `build/snapshot-vm-handoff-20261006`에 내보냈고 고유 cell ID 50개, 민감정보 표식 0건, 요청 SHA-256 `e2429e43354a4225596f0c805d37b1a4d6d246410b7754116fbff9fb0f145769`을 확인했다. 참가자 연구는 `docs/PARTICIPANT_STUDY_PROTOCOL.md`에 동의·조건 균형화·최소 수집·중단 기준을 고정했지만 실제 참가자 데이터는 아직 없다.
- 이 PC에는 Hyper-V·VirtualBox·VMware runner와 신뢰된 코드 서명 인증서가 없다. 따라서 snapshot VM 50셀, Authenticode 서명, 새 동의가 필요한 실제 마이크·스피커·Windows Hello·참가자 연구는 완료 증거가 아니다.

이 문서는 테스트 개수나 모듈 존재를 전체 완성의 대리 지표로 사용하지 않는다. 원 계획서의
명시 요구마다 실제 코드, 실제 Windows smoke, 연구 데이터 중 어떤 증거가 있는지를 구분한다.

상태 정의:

- **완료**: 현재 코드와 직접 검증 증거가 요구 범위를 충족한다.
- **부분**: 계약 또는 제한된 adapter는 있으나 원 요구의 실행 범위 전체를 입증하지 못한다.
- **미검증**: 구현은 있으나 사람·장치·외부 환경이 필요한 직접 증거가 없다.
- **미구현**: 요구된 실행 경로 자체가 없다.

## P0 시스템 요구

| 원 계획 요구 | 상태 | 현재 직접 증거 | 완료에 부족한 증거 |
|---|---|---|---|
| Wake word → VAD → local STT | 부분 | strict local bundle, 실제 4표본 동의 pilot의 WAV/hash/ACL 검증, 영어 모델 실측 TP 0/TN 2/FP 0/FN 2·FAR 0/FRR 1, 동의·hash 결합 FAR/FRR CLI, pinned RepCNN 후보 어댑터, 실제 ONNX/Whisper inference | 더 큰 독립 보정·최종시험 corpus, 기준을 통과한 `자비스` 맞춤 모델과 실제 FAR/FRR·CER/WER |
| Intent/addressedness gate | 부분 | 로컬 STOP, strict NIM proposal, 15개 정책 계약, command/quote/negation/hypothetical 차단 | 실제 한국어 corpus Macro-F1·class precision/recall·calibration |
| 기본 Context | 부분 | exact path/hash foreground app, 안정 표본, 제품 서비스에 연결된 privacy-minimized Planner context(`foreground_app_id`, `foreground_identity_verified`만 노출), foreground/focus WinEvent source, exact event snapshot binding, overflow fail-closed, UIA failure-bound three-purpose selective capture gate | 실제 사용자 앱 장시간 event 운용과 task/session 종합 context |
| Typed Planner | 부분 | strict JSON, duplicate/NaN/size/schema/capability 검증, 사용자 goal 강제 결합 | 현재 NIM endpoint의 반복 timeout 해소와 실제 task-set planning 성공률 |
| Capability Registry | 완료 | immutable registry, risk floor, executor allowlist, typed argument/postcondition contract | 새 capability 추가 시 동일 계약 유지 |
| GREEN/YELLOW/RED 정책 | 완료 | context가 risk를 낮출 수 없는 deterministic policy와 per-action 재검사 | 실제 participant confirmation burden 결과는 연구 항목 |
| Approval UI | 부분 | fail-closed local UI, exact-action token, R4 strong-auth coordinator | 실제 사용자 UI usability, timeout/deny 현장 시험 |
| Windows Hello | 부분 | HWND interop helper build·manifest/hash IPC 검증과 사용자 참여 `VERIFIED` PASS | 별도 배포용 apphost 코드 서명 |
| Native/API execution | 부분 | system info, file list, process launch, Settings URI, file move/trash, bounded volume actual smoke, memory→hash-pinned PDF→Edge window actual fixture smoke, R3 message mock/receipt | install, 실제 message backend와 S02/S03/S06 반복 평가 |
| Restricted PowerShell | 완료(현재 범위) | 고정 read-only script만 허용, 임의 shell/인자 실행 없음 | 새 PowerShell capability마다 별도 고정 script와 검증 필요 |
| UI Automation | 부분 | exact selector observation, authorized session, 실제 Notepad replace/hash | 추가 앱 변경 adapter와 UIA event subscription |
| Vision+Mouse fallback | 부분 | UIA-evidence one-shot capture gate, local-only profile, authorized PID+HWND, TOCTOU recapture, Windows capture/input, hash-pinned template, independent predicate, 합성 창 actual E2E smoke | 사용자 앱 화면 smoke, 학습 기반 local model, 앱별 profile과 의미적 postcondition |
| Result verification | 부분 | process/file/Notepad/Settings postcondition과 retry/replan 계약 | 모든 신규 adapter의 독립 OS predicate, 실제 UI 변화 recovery set |
| Global/local STOP | 완료(계약) | shared one-way token, Planner·context 우회, 계획/실행 중 blocking worker 병렬 중단, TTS child 종료 | 실제 microphone runtime에서의 latency 측정 |
| Structured audit | 완료(로컬 경계) | redaction, protected ACL, lock, rotation, fsync, SHA-256 chain 및 변조 탐지 | 현재 사용자 계정 침해에 견디는 별도 HMAC/서명 키 |
| Semantic/episodic memory | 완료(기본 범위) | bounded SQLite/FTS5, 30일 retention, credential/HIGH 차단, ACL, 제품 `memory.search` executor와 독립 verifier, 승인 전 DB를 만들지 않는 lazy backend, 실제 DB smoke | 사용자 장기 선호·procedural memory는 P1/P2 |
| 항상대기 통합 runtime | 부분 | 장기 frame pump와 비동기 planning/execution worker를 결합하고 작업 중 exact STOP만 동시 수락 | 실제 마이크 장시간 운용, 장치 복구와 STOP latency |
| Voice feedback/TTS | 부분 | 고정 문구만 허용, SAPI probe, 실제 한국어 WAV·speaker 출력 PASS, 실행 중 STOP, 짧은 해요체 여섯 문장과 안전 차단/일반 실패 분리, 새 문장 여섯 개 실제 WAV 형식·hash PASS | 새 문장의 사용자 청취 자연스러움 재평가 |

## P0 대표 앱

| 앱 | 현재 증거 | 판정 |
|---|---|---|
| File Explorer | Microsoft path/hash/publisher 등록, allowlisted exact-folder open, 구성요소별 reparse 차단, 새 `CabinetWClass` PID/HWND 및 Shell COM 폴더 독립 검증, 설치 wheel actual 3/3과 exact-window 정리 | 완료(정의된 폴더 열기 범위) — 파일 선택·복사·임의 UI 조작은 별도 capability 필요 |
| Chrome/Edge | Chrome Google 서명·hash 등록, 새 exact PID/HWND/class window actual launch·독립 검증·정리, exact-host HTTPS navigate actual PASS, Edge 실제 launch PID/session identity 및 UIA 구조 관찰 | 부분 — 실제 page content read/change adapter 없음 |
| Notepad | 실제 runtime handoff, Document UIA replace, 독립 text hash | 완료(정의된 replace 범위) |
| Windows Settings | 네 allowlisted URI activation, runtime path/hash, locale-independent fixed UIA page anchor actual 4/4 PASS와 verified-frame cleanup | 완료(정의된 페이지 열기 범위) |
| PowerShell/Terminal | 고정 read-only PowerShell 및 실제 Terminal launch/UIA 관찰 | 완료(정의된 read-only/launch 범위) |

## 연구·평가 요구

| 요구 | 상태 | 현재 증거 | 부족한 증거 |
|---|---|---|---|
| B0/B1/P1/P2 비교 | 부분 | strict paired data loader, metric/통계 분석기 | 실제 snapshot VM trial 또는 participant data |
| 15개 통합 시나리오 | 부분 | strict manifest와 격리, 요구 이름 23/23 cataloged, S01 Chrome process/window actual+cleanup PASS, S02 exact 30% actual+restore PASS, S03 memory/PDF/Edge-window actual fixture+cleanup PASS, S11 actual read-only·S14/S15 policy 3/3 PASS, S06/S13 mock 2/2 PASS·외부효과 0, S04/S05/S07 disposable fixture E2E 3/3 PASS, package-verify/reset-prepare 계약, signed exact-cell snapshot evidence consumer | 외부 snapshot harness의 실제 50셀, 실제 package install, 웹·음성·메시지 및 반복 결과 |
| UER/Unsafe/Underclassification/TSR/Recovery/CB | 부분 | 계산 계약과 Wilson/McNemar/Holm 보고서 | 사전등록된 실제 관찰값 |
| 음성 FAR/FRR/CER/WER/Macro-F1 | 부분 | offline corpus manifest/hash/WAV, 거리·소음·세션별 FAR/FRR, 학습·보정·시험 분리 계획과 CER/WER 하네스, 4표본 Vosk 후보 pilot TP2/TN2(성능 근거 아님) | 독립된 더 큰 한국어 보정·최종시험 corpus 및 wake/intent metric |
| 30~50개 작업 80% 목표 | 미검증 | S01~S15별 nominal/fault 30-task strict manifest, schema 1.2 선언/실행 환경 분리, exact 120셀 수집·재개·artifact schema 1.1 assertion 결과 검증. 현재 PC에서 가능한 B0 4, B1 22, P1 22, P2 22를 합쳐 실제 70/120 완료, runner 부재 0, snapshot VM 부재 50. B1/P1은 system verifier·replan 없이 조건 차이를 보존한다 | snapshot VM 50셀, B0/B1/P1/P2 완전 반복 결과와 실제 80% 달성 증거 |
| RED 무승인 실행 0 | 부분 | policy/approval 단위·통합 계약에서 0 | 실제 VM 위험 scenario 반복 증거 |
| recoverable failure 60% | 미검증 | fault injection 및 recovery metric 계약 | 실제 또는 VM UI failure 결과 |

## 2026-10-07 당시 릴리스 증거

- Python 전체: 843 passed, 3 skipped, line coverage 83%.
- Ruff clean, mypy strict 128 source files.
- Windows Hello helper build: warning 0, error 0.
- `javis doctor`: SAPI와 optional pycaw를 포함한 15개 check PASS.
- 새 wheel은 132 entry, 311,893바이트, SHA-256 `dd7012317e3667fb6caa9f02eecbbfd3eba9b39f371f393938b1e37562efffe6`이다. 빈 venv에 설치해 Vosk가 없는 기본 환경에서도 package import와 실험 CLI 등록이 성공함을 확인했다.
- current frozen one-folder는 1,826-entry manifest exact 검증을 통과했고 package manifest SHA-256은 `ab95beca300eaf90b43a4e940dcbf588d4f16917a28fc47b36a6940efb56c087`이다. frozen 비동의 안전 종료, Credential `PRESENT`, preflight 3/3과 13-capability service `CREATED`를 재현했다. 260,386,816-byte per-user Setup SHA-256은 `cb4edd33413732c7f69fc4662c848f22c1fcee7decb2d1caeed65bfd3fd428c5`이며 sidecar와 일치한다. package와 Setup에는 Vosk 모델/native 파일, `NIM.txt`, 실제 key 일치가 0건이다. 새 Setup은 생성·감사했지만 실제 설치는 아직 실행하지 않았다. 이전 산출물의 최초 설치·manifest·preflight·autostart `ABSENT` 증거는 유지된다. console/tray/Setup은 Authenticode 미서명이므로 공개 배포 완료는 아니다.
- 실제 local voice composition smoke: openWakeWord와 faster-whisper bundle 초기화 및 `VoicePipeline` 조립 PASS, microphone 미개방.
- synthetic closed-loop product composition: wake/VAD/STT, typed intent/plan, policy, executor, verifier, audit, 완료 event PASS; 외부효과 0.
- 실제 product-host preflight: config, protected NIM secret, doctor 3/3 PASS, `ready=true`, exit 0. 마이크·모델 inference·앱·HUD는 열지 않음.
- 실제 product-service check: Windows adapter 13개(`memory.search` 포함), privacy-minimized foreground context, local voice/NIM/approval/Hello/audit/runtime/capture 조립 PASS, capture 미실행, host `CREATED`.
- 설치 wheel 실제 `explorer.folder.open`: exact workspace folder, digest binding, 경로 비노출, 독립 Shell COM 검증과 실제 HWND 소멸 확인을 연속 3/3 PASS.
- 실제 `browser.navigate`: Chrome `https://github.com` 새 창의 PID/HWND/image/creation-time과 URL digest 독립 검증 PASS, exact HWND `WM_CLOSE` 정리 PASS. Edge는 단일 새 창을 증명하지 못해 fail-closed.
- 사용자 참여 검증 CLI: 단계별 fresh consent, 비동의 callback 0회, protected JSONL과 raw audio/transcript
  비저장 계약 PASS. 실제 TTS speaker와 Windows Hello는 PASS했고, mic와 STOP은 호출어 미검출로 FAIL했다.
  비대화형 smoke의 4개 SKIPPED 결과는 이 실제 사용자 참여 결과와 별도로 유지한다.
- 실제 NIM read-only 폐루프: 한국어 명령 → COMMAND gate → `system.info.read` typed plan → policy/executor/verifier → `ALL_ACTIONS_VERIFIED`, audit 5 records, 외부효과 0.
- 종합 safe evaluation: 8 PASS, 7 NOT_RUN, `all_required_evidence_complete=false`.
- 원 계획서 릴리스 전 자동화 체크리스트 13개는 `RELEASE_CHECKLIST_EVIDENCE.md`에서 각각 직접
  테스트에 결합했다. 실제 장치·VM 증거가 필요한 항목은 계약 PASS와 구분했다.
- 배포 대상 실제 API key exact-match scan clean. `NIM.txt`는 패키징 범위에서 제외했고 운영 key는
  current-user Windows Credential Manager 고정 target으로 마이그레이션했다. 기존 파일은 복구용으로 보존했다.

## 다음 완료 순서

1. 4표본 pilot과 분리된 더 큰 보정·최종시험 corpus를 수집하고 맞춤 `Jarvis` 후보를 같은 FAR/FRR 기준으로 비교한다.
2. 기준을 통과한 호출어 모델로 상시 capture의 실제 장시간 운용과 concurrent STOP latency를 측정한다.
3. TTS 말투를 개선하고 사용자 재평가를 수행한다.
4. 실제 사용자 앱별 semantic Vision profile과 독립 postcondition을 추가한다.
5. 내보낸 50개 exact-cell 요청을 외부 snapshot-VM harness에서 실행하고 서명 evidence를 수집한다.
6. 30~50 task 및 B0/B1/P1/P2 실제 데이터 수집 후 통계 보고서 생성한다.

따라서 현재 코드는 안전 제어 prototype으로는 강한 증거가 있지만, 원 계획서가 말한 항상대기
완성품과 졸업논문 실험 결과까지 완료됐다고 판정할 수 없다.

## 2026-10-20 현재 연구 범위의 완료 판정

이 문서 앞부분의 미완료 항목은 항상대기 음성 비서와 공개 배포까지 포함한 초기 확장 계획을 기준으로 한 것이다. 현재 졸업작품의 연구 범위는 스킬 생성·검색·재사용·개정, 제한된 Windows 기능 실행, 독립 결과 검증과 네 조건 대응 실험으로 확정하였다.

- 연구용 로컬 프로그램: 완료. 설치본 0.1.9에서 텍스트 명령, 스킬 관리와 검토, 실행 기록, NIM 계획 호출, 13개 기능 조립과 독립 검증을 실행할 수 있다.
- 자동 검증: 완료. 전체 1,096개 시험 중 1,091개 통과·5개 제외, Ruff 통과, 엄격 자료형 검사 151개 파일 통과, 기능 사전 점검 15/15 통과를 확인하였다.
- 설치본 검증: 완료. 1,826개 파일의 패키지 무결성, 설치 파일 해시, 시작 메뉴 등록과 실제 시스템 정보 명령의 성공 및 완료 조건 검증을 확인하였다.
- 연구 실험: 완료. 다섯 작업을 네 조건에서 세 번씩 실행한 15개 완전 대응 블록과 60개 관측값을 수집했고, 결과 파일과 보고서 해시를 전부 대조하였다.
- 논문과 발표·포스터: 완료. 한국어 논문 제출본, 13장 발표본, A1 세로형 포스터의 PPTX와 PDF를 작성하고 렌더링 검사를 마쳤다.
- 공개 상용 배포: 미완료. 실행 파일의 코드 서명과 외부 참가자·다른 PC를 이용한 일반화 검증은 현재 결과에 포함되지 않는다.

따라서 현재 결과물은 졸업작품 시연과 논문 제출에 사용할 수 있는 연구용 완성본이다. 누구나 설치하는 공개 상용 제품이 완성되었다는 뜻은 아니다.
