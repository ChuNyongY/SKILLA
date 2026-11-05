# 구현 상태

최종 갱신: 2026-10-20

## 2026-10-20 독립 확인 실험과 자동 업데이트 앱 검증

- 예시 논문의 반복측정 설계를 JAVIS 스킬 연구에 맞춰 적용해 결과 확인 전에 `developer10`, seed
  `2026102001`, 5작업×3블록×SK0~SK3의 60관측 계획을 고정하고 실행했다.
- 15개 완전 대응 블록에서 SK0 10/15, SK1 12/15, SK2 12/15, SK3 14/15 성공했다. SK3의
  평균 시간은 12,367 ms, 평균 호출은 1.867회, 평균 토큰은 3,135.7이었지만 평균 사용자 확인은
  1.0회로 가장 높았다. 세 exact McNemar 비교는 Holm 보정 뒤 모두 p>=0.375이므로 통계적
  우월성을 주장하지 않는다.
- 60개 evidence hash, observations/report hash와 manifest를 전부 대조했고 불일치 0건이었다.
  같은 인자로 다섯 runner를 재실행했을 때 원장·관측·보고서 15개 파일이 모두 불변이었다.
- Edge 자동 업데이트 해시 drift를 실험 사전점검에서 발견했다. 현재 실행 파일의 Microsoft
  Authenticode 서명과 새 SHA-256을 확인해 등록부를 갱신하고, PDF·Explorer 실험 runner도 제품과
  같은 `등록 경로 + 정확한 발행자 서명` 조건에서만 signed update를 허용하도록 수정했다.
- 전체 1,096개 회귀시험, 자격 증명 사전점검 3/3과 앱 등록부 유효 서명을 통과했다.

## 2026-10-19 0.1.9 스킬 검토 창 표시 수정

- 텍스트 명령 창에서 스킬 검토를 열 때 별도 `Tk` 실행 루프를 중첩하던 구조를 같은 실행 루프의
  `Toplevel` 보조 창으로 변경했다. 실제 로컬 초안이 있는데도 목록이 빈 화면처럼 보이던 현상을
  제거했다.
- 실제 0.1.7→`state/v1` 이관 초안을 사용해 `[신규] Windows 시스템 정보 조회 (v1)` 항목이
  스킬 검토 창에 표시되는 것을 Windows 화면 자동화와 데이터베이스 조회 두 경로로 확인했다.
- 검토 대기 초안이 정말 0개일 때는 빈 화면 대신 `스킬 후보 검토`에서 실행 기록을 초안으로
  만드는 방법을 안내한다.
- 전체 **1,096개 시험(1,091 통과, 5 건너뜀)**, Ruff, strict mypy 151 files를 통과했다.
  1,826개 파일의 0.1.9 r1 패키지는 manifest 검증, 자격 증명 사전점검 3/3, 13개 기능 서비스
  조립과 `capture_running=false`를 통과했다. 설치본의 읽기 전용 시스템 정보 smoke도
  `SUCCEEDED`와 `ALL_ACTIONS_VERIFIED`로 끝났다.
- 실제 Setup 설치는 `SUCCESS/code=0`이었고 시작 메뉴가 설치된 0.1.9를 가리킨다. 설치본
  카탈로그에서도 `read-windows-system-info` v1 DRAFT가 유지됐다. 현재 주 화면은
  `DISPLAY1` 2560×1440으로 정상 탐지됐다.
- Setup SHA-256은 `d7fe1397a9cf9bcd9bb3dbee93dea04cafda6b48e0bf32d16e6d939f01a76f8e`,
  wheel은 `a0c96269c272945cb475851fd2b7d0fd4ad1cfd2f578f3dade78f2277da50c8b`,
  package manifest는 `93c3f99737c35aa943ede07b281969a71193d5ec754a10a8b3de119f1b0c8a27`다.
  패키지의 `NIM.txt`는 0건이다. release audit은 manifest와 Setup hash를 통과했지만
  console/tray/Setup은 모두 `NotSigned`이므로 공개 서명 배포 완료와 구분한다.

## 2026-10-19 0.1.8 전면 결함 수정

- 설치본의 스킬·실행 기록 저장 경로를 앱 버전별 폴더에서 상태 형식별 공용 `state/v1` 폴더로
  변경했다. 첫 실행 때 0.1.7 데이터베이스와 감사·화면 선택 파일을 덮어쓰지 않고 이관하므로,
  업데이트 뒤 스킬 목록이 비어 보이던 결함을 제거했다.
- 텍스트 명령 화면에 독립 검증을 통과한 결과 영역을 추가했다. 시스템 정보는 운영체제,
  릴리스, 버전, 시스템 종류, 컴퓨터 이름만 한국어 표제로 표시하며 임의 관측값은 노출하지 않는다.
- 유휴 상태와 완료 상태가 동시에 표시되던 문구를 하나의 완료 상태로 정리했고, NIM 스킬 초안
  생성 완료를 별도 알림으로 보여준다. 실행 기록의 성공·검증 상태와 주요 기능명도 한국어로 표시한다.
- 전체 **1,095개 시험(1,090 통과, 5 건너뜀)**, Ruff, strict mypy 151 files를 통과했다. 1,826개
  파일의 0.1.8 r2 패키지는 manifest 검증, 자격 증명 사전점검 3/3, 13개 기능 서비스 조립,
  `capture_running=false`를 통과했다.
- 실제 Setup 설치 exit code 0 뒤 시작 메뉴가 설치된 0.1.8을 가리키고, 텍스트 명령 창 제목을
  실제로 확인한 뒤 정상 종료했다. 0.1.7의 `read-windows-system-info` 초안 ID와 DRAFT 상태가
  `state/v1`에 그대로 이관됨을 설치본 CLI로 확인했다.
- 최종 Setup SHA-256은 `023b73d46b98b643f5555111091afed6346951213a3a2670fd77b6d9a9e65fb7`,
  wheel은 `43c3f9aac2da2983aaf43fbddc70c1de4b1e360c3881b7412370c40656a57a65`다.
  패키지와 Setup의 `NIM.txt` 및 실제 키 일치는 0건이다. 세 실행 파일은 여전히 미서명이다.

## 2026-10-18 첫 실행 설정·0.1.7 최종 후보

- NIM 키가 없는 첫 실행에서 콘솔 명령을 요구하던 진입 장벽을 제거했다. 마스킹된 `JAVIS 초기 설정`
  창에서 키를 받아 기존 Windows 자격 증명 관리자에 저장하고, 저장 상태를 다시 읽어 `PRESENT`가
  확인된 경우에만 제품 사전점검과 주 창으로 진행한다. 취소는 조용히 종료하고 저장·화면 오류는
  고정 한국어 문구만 표시한다.
- API 키는 명령줄·로그·오류 문구에 넣지 않으며 저장 직후 입력 위젯의 값을 지운다. 작업자 token은
  초기 설정보다 먼저 분기한다. 저장 성공·취소·실패·예외 redaction·저장 후 재검증 실패를 자동시험으로
  고정했다.
- 전체 회귀는 **1,085 passed, 4 skipped**, Ruff `src tests`, strict mypy 150 source files와
  `git diff --check`를 통과했다.
- 0.1.7 one-folder 1,826개 파일은 manifest `VERIFIED`, Credential 사전점검 3/3, 13-capability
  service `CREATED`, `capture_running=false`를 통과했다. 실제 Setup 최초 설치 `SUCCESS/code=0`,
  재설치 `ALREADY_VERIFIED/code=0`과 설치본 manifest 재검증을 확인했다.
- 시작 메뉴 링크는 설치된 0.1.7 `JAVIS-Tray.exe`, 빈 인자와 정확한 작업 폴더를 가리킨다. 링크를
  실제 실행해 `JAVIS 텍스트 명령` 창과 응답 상태를 확인한 뒤 정상 종료했으며 시험 process는 남지
  않았다.
- 별도 새 가상환경에 0.1.7 wheel과 선언된 기본 의존성을 설치해 version import와 `javis --help`를
  통과했다. package의 민감한 파일명과 실제 저장된 키의 정확한 byte 일치 검색은 각각 0건이다.
- 최종 r2 Setup SHA-256은
  `a9003f4465f838b32540827ccb21e91a509e46e54ecbfdf6c94a0cd6de980228`, package manifest는
  `e4cc23da0bd5e511a10401602f55722e119d52aa28c965cd11271fa48aaadf16`, `JAVIS.exe`는
  `815c7a5af68ae43b8770c690e5cf24590b277113415121629c0578354b63ef84`, `JAVIS-Tray.exe`는
  `88ff9db277f3e108715227add9b861dbfe7925f3b1e318c120abddb67cc7466d`다. wheel SHA-256은
  `2afadcf28de01c0790447f4a8c48f8c983b32cba655e7c497832cc14edc921b9`다.
- r2 release audit은 manifest와 Setup hash를 통과하고 세 Authenticode 서명을 정확히 실패했다.
  현재 사용자 저장소의 사용 가능한 코드 서명 인증서는 0개이므로 로컬 시연용 완성과 공개 배포
  서명 완료를 구분한다.

## 2026-10-18 시작 실패 안내·화면 복구·스킬 UI·0.1.6 후보

- 연구 핵심인 스킬 기능이 음성 tray 메뉴에만 있고 기본 더블클릭 텍스트 창에서는 접근할 수 없는
  제품 결함을 확인했다. 기본 창 두 번째 줄에 `스킬 관리`, `스킬 후보 검토`, `작업 화면 선택`을
  연결하고, 기존 tray와 같은 catalog·trace·NIM draft workflow 객체를 재사용하도록 했다.
- 보조 화면 callback 실패는 실제 예외·경로·키를 표시하지 않고 기능별 고정 한국어 문구로 처리한다.
  callback 호출·예외 redaction·CLI wiring 시험을 추가했으며 이 UI 경로는 microphone capture를
  시작하지 않는다. 이 변경을 포함한 최종 후보 버전은 0.1.6이다.

- 설치된 windowed 실행 파일이 주 창을 만들기 전에 Windows 자격 증명의 NIM 키 상태, 제품 구성,
  필수 구성 요소를 기존 사전점검기로 확인하도록 했다. 키 없음·키 읽기 실패·구성 손상·필수 구성
  요소 실패·예상하지 못한 시작 실패를 서로 다른 고정 한국어 문구와 안정적인 종료 코드로 구분한다.
- 오류 창에는 실제 예외, 사용자 경로, API 키 또는 traceback을 넣지 않는다. 오류 창 자체가 실패해도
  원래의 비정상 종료 코드는 유지한다. 음성/TTS/UIA/Explorer 작업자 token 경로는 이 검사보다 먼저
  분리되므로 기존 worker 실행 계약을 바꾸지 않는다.
- NIM에는 의존성 없는 windowed startup wrapper와 안내 문구 초안을 요청했다. Codex 감사에서 초안의
  새 keyring 의존성, one-folder와 맞지 않는 임시 경로 가정, worker token 전달 가정을 제외하고 기존
  Credential Manager·제품 사전점검·설치 폴더 계약으로 구현했다.
- 시작 오류·스킬 UI 시험과 CLI 대상 시험을 포함한 전체 회귀는 **1,078 passed, 4 skipped**다.
  `src`·`tests` Ruff와 strict mypy 150 source files도 통과했다.
- 첫 0.1.4 설치 뒤 시작 메뉴 링크는 정확했지만 저장된 `primary` 화면의 1920×1080 좌표와 현재
  2560×1440 좌표가 달라 `DISPLAY_GEOMETRY_CHANGED`로 시작이 차단되는 실제 결함을 발견했다.
  `primary`는 특정 장치가 아니라 현재 주 화면이라는 사용자 의도이므로 현재 주 화면 descriptor로
  원자적으로 갱신하고, 명시적인 `device` 고정은 누락·좌표 변화 시 상태를 바꾸지 않고 계속 차단하도록
  수정했다.
- 최종 0.1.6 `dist/JAVIS-PC-0.1.6-skill-20261018-r1` 1,826개 파일은 manifest `VERIFIED`이고,
  Credential 사전점검 3/3, 13-capability service `CREATED`, `capture_running=false`를 통과했다.
  실제 Setup 최초 설치는 `SUCCESS/code=0`, 재설치는 `ALREADY_VERIFIED/code=0`이었다. 시작 메뉴 링크는
  설치된 0.1.6 `JAVIS-Tray.exe`, 빈 인자와 정확한 작업 폴더를 가리킨다.
- 시작 메뉴 링크를 실제 실행해 `JAVIS 텍스트 명령` 창을 확인하고 정상 닫았으며 시험 process가 남지
  않았다. 설치 상태의 `primary` descriptor도 실제 `DISPLAY1 2560×1440`과 일치한다. 후속 한국어
  명령 입력 UI 검증은 사용자가 물리적 Escape로 Computer Use를 중지해 반복하지 않았다. 실제 NIM
  명령 E2E 자체는 0.1.3 설치본에서 이미 통과했고, 0.1.6은 같은 runtime 경로의 회귀시험과 창 시작을
  통과한 것으로 범위를 구분한다.
- 최종 Setup SHA-256은
  `5f90c3cd579db2797ab8d1d5ea062810b78ec1ef63737c98dc248c007888f091`이고 sidecar와 일치한다.
  package manifest는 `cebf8451df2113db437fd3e484489c61c0f532cb763cd3da4f508d7d4749adfd`,
  `JAVIS.exe`는 `3557663fd0fb5014dda72a92e87fe6a951d557c818103a38ff034882d5046219`,
  `JAVIS-Tray.exe`는 `61b9b33249f5dd0a1b60f3ed954092e43130cf3995640db6881d596047fb87df`다.
  package의 비밀 파일명·API key 형태 검색은 모두 0건이다.
- 0.1.6 wheel SHA-256은
  `e4206deedaaa5b787b679f5be37349a3bab0035e3e58912ddc62f3a15aa7e26d`이다. 새 가상환경에
  `--no-deps`로 설치해 version·시작 오류·화면·스킬 UI 모듈 import와 `javis --help` exit 0을 확인했다.
  Setup·두 EXE는 여전히 `NotSigned`이므로 로컬 시연·제출용과 공개 배포 완료를 구분한다.
- 0.1.6 공개 배포 감사는 package manifest와 Setup hash는 PASS, console·tray·Setup signature는
  `SIGNATURE_INVALID`로 정확히 실패했다. 현재 사용자 인증서 저장소의 private key 포함 유효 코드
  서명 인증서는 0개이므로 보안 설정을 약화하거나 임시 인증서를 신뢰시키지 않고 외부 인증서 준비를
  배포 차단 조건으로 유지한다.

## 2026-10-17 실행 화면·텍스트 명령·0.1.3 배포 후보 검증

- 제품에 `primary`, 고정 장치 이름, 현재 활성 창 추적의 세 화면 선택 방식을 추가했다. 현재 PC의
  `DISPLAY1`(주 화면, 2560×1440)을 실제 열거하고 고정 선택했으며, 화면 누락·주 화면 변경·좌표 또는
  해상도 변화와 선택 화면 밖 창은 실행 전에 거부한다. tray의 `작업 화면 선택`과 CLI
  `list-displays`, `select-display`를 연결했다. 실제 다중 모니터 하드웨어 시험은 화면이 하나인
  현재 PC에서는 수행할 수 없었다.
- 설계도에 있었지만 제품 UI에 빠져 있던 텍스트 명령 창을 구현했다. 더블클릭한 `JAVIS.exe`와
  `JAVIS-Tray.exe`는 기본적으로 `JAVIS 텍스트 명령` 창을 열며, 이 경로는 마이크·상시 capture를
  시작하지 않는다. 입력은 기존 NIM planner, 정책, 실행기, 독립 검증기, 실행 기록과 스킬 재사용
  경로를 그대로 사용한다. 소스 루트가 아닌 one-folder 자체와 격리 설치 폴더를 각각 작업 위치로
  두고 실제 EXE의 창 handle·제목 생성을 확인한 뒤 정상 종료했다.
- 기본 텍스트 창에 `작업 화면 선택` 버튼을 연결해 CLI 없이 주 화면·정확한 DISPLAY 장치·전면 창
  추적 방식을 선택할 수 있게 했다. callback 연결과 마이크 미개방은 자동시험으로 검증했다. 설치된
  0.1.3 기본 창을 실제 캡처해 버튼 표시를 확인하고 클릭했으며, `주 모니터 고정`, 현재
  `DISPLAY1 (2560×1440, 0,0) · 주 모니터`, `현재 전면 창 따라가기` 선택 창이 열리는 것을 확인했다.
  설정은 바꾸지 않고 취소한 뒤 두 시험 창을 모두 닫았다.
- 설치된 0.1.3을 시작 메뉴에서 다시 열어 텍스트 입력란에 한국어 읽기 전용 시스템 정보 명령을
  실제 입력·제출했다. 화면은 `명령을 검토하고 있습니다`를 거쳐 약 10초 뒤
  `작업을 완료했습니다`로 바뀌었다. 외부 state의 감사 원장은 GREEN 정책, 실행 시작·성공,
  독립 검증 성공, `ALL_ACTIONS_VERIFIED`의 5개 record를 남겼고 hash chain 검증을 통과했다.
  `skill-traces.sqlite3`에는 새 스킬 후보 trace 1건이 저장됐으며 명령 원문과 실제 시스템 정보 값은
  감사 기록에 없었다. 이 텍스트 경로는 microphone capture를 시작하지 않았다.
- 실제 NIM에 `현재 Windows 시스템 정보를 읽어서 확인해 줘`를 입력한 안전 smoke는
  `system.info.read` 1개 action을 실행·독립 검증해 `ALL_ACTIONS_VERIFIED`로 끝났고 스킬 실행
  기록을 남겼다. 명령 원문은 상태·실행 event에 저장하지 않았고 microphone은 열지 않았다.
- Chrome 자동 업데이트로 바뀐 실행 파일은 유효 Google Authenticode와 정확한 발행자를 다시
  확인해 현재 hash를 고정했다. 제품 loader는 이후 같은 경로에서 유효 서명과 동일 발행자를 모두
  만족한 갱신만 메모리에서 수용하며, 잘못된 발행자·서명 실패·경로 변경은 계속 거부한다.
- 전체 회귀는 **1,072 collected, 1,068 passed, 4 skipped**, 제품 `src`와 `tests` Ruff clean,
  strict mypy **149 source files** PASS다. 저장소 전체 Ruff에는 현재 제품 경로 밖의 과거 보고서
  생성 도구 오류 107개가 남아 있어 저장소 전체 clean으로 주장하지 않는다.
- 기존 설치를 덮어쓰지 않는 업그레이드를 위해 최종 제품 버전을 0.1.3으로 올리고 package·installer·
  Python metadata·한국어 안내문의 버전 일치를 시험으로 고정했다. 새 one-folder
  `dist/JAVIS-PC-0.1.3-skill-20261017-r1`의 1,826개 파일은 manifest 검증을
  통과했다. 설치본 `JAVIS.exe`도 같은 1,826개를 `VERIFIED`로 판정했고, 실제 화면 열거와
  Credential 기반 13-capability service `CREATED`를 통과했으며 `capture_running=false`였다.
- 설치기는 현재 사용자 시작 메뉴에 고정 이름 `JAVIS-PC` 링크를 만들고 target·빈 인자·작업 폴더·
  설명·아이콘을 다시 읽어 모두 일치할 때만 성공한다. 다른 대상의 기존 링크는 덮거나 지우지 않는다.
  동일 설치 부모 아래 정확한 이전 버전 링크만 `OUTDATED`로 식별해 새 링크로 바꾼다. 실제
  0.1.1→0.1.2→0.1.3 설치에서 링크가 갱신됐고, 시작 메뉴 실행은 설치된 0.1.3 `JAVIS-Tray.exe`와 동일
  hash의 새 process 및 `JAVIS 텍스트 명령` 창을 만들었으며 해당 시험 창만 닫았다.
- 새 Setup SHA-256은
  `eca1615f99aa00adf7335c573c7ac28e1fef85648139bba51809b1124f7870a9`이고 sidecar와 일치한다.
  실제 현재 사용자 위치의 0.1.3 최초 설치 영수증은 `SUCCESS/code=0`, 같은 설치 파일 재실행은
  `ALREADY_VERIFIED/code=0`이었다. wheel SHA-256은
  `265ac23e1040a0e6cdaeedaa20212a94ba1f5e602fb14cb0ff7234c869693b3a`, package manifest는
  `f1cac510b26ffec41b833eb40d21ec0d583fbfdb654579536271e2b874f5611f`다. 새 wheel을 별도
  가상환경에 설치해 시작 메뉴·텍스트 UI import와 `javis --help`를 확인했다.
- Codex Microsoft Store 앱 안에서 실행한 실제 설치 시험은 Windows가 `%LOCALAPPDATA%`를 앱 전용
  `LocalCache`로 가상화했다. 따라서 일반 Explorer에서 Setup을 실행한 물리 경로와 같다고 주장하지
  않는다. 다만 영수증·manifest·서비스·링크 target과 실행 process hash는 그 실제 가상화 환경 안에서
  서로 일치했다.
- package 안의 비밀 이름 파일과 `nvapi-` 형태 검색은 0건이다. `JAVIS.exe`, `JAVIS-Tray.exe`,
  Setup은 모두 Authenticode `NotSigned`이므로 이 배포 후보는 로컬 시연·제출용으로 검증됐지만,
  인증서 서명이 필요한 불특정 사용자 공개 배포 완료로 판정하지 않는다.

## 2026-10-17 발표자료·설명문 정합성 갱신

- 13장 졸업발표 자료를 권한 분석이 아닌 스킬 저장·검색·재사용·개정 연구를
  중심으로 다시 작성했다. 현재 구현 범위, SK0~SK3 실험 조건, 32블록·128관측,
  성공률·시간·호출·토큰 결과와 통계적 한계를 반영했다.
- 발표자료의 모든 13장을 렌더링해 전체 흐름과 수정 장을 확대 검토했다. PowerPoint 구조,
  레이아웃, 맑은 고딕 글꼴, 13장 수, 수정 가능한 차트와 내장 자료 표는 최종화 검사를
  통과했다. 최종 파일 SHA-256은
  `3572f3d3446efa147fb829729fe07274ab5f52fd42ab2025dab880c17f108358`이다.
- 교수님 발표 정리본을 전면 개편해 하네스·스킬·도구·기능 권한을 구분하고,
  기존 에이전트와의 차이, 선례, 예비실험 수치, 예상 질문 8개와 보수적 답변을 담았다.
  논문의 주제를 스킬 효과 검증으로 고정하고 안전 정책은 보조 하네스로 분리했다.
- 참가자 비교실험 운영안의 과거 `B0/B1/P1/P2` 조건을 현재 `SK0~SK3` 스킬 연구로
  교체했다. 고정 seed 순서 균형화, 완전 대응 블록, 모델·설정·도구·초기 상태 동일성,
  결과 근거 hash, 동의·철회·폐기·중단 절차와 현재 분석기의 McNemar·Holm 계약을 일치시켰다.
- 모집문·동의서·철회 안내문 초안을 추가했다. 현재는 보관 기간·보상·문의처·연구윤리 확인
  결과가 `[확정 필요]`이므로 배포·모집에 사용할 수 없다. 실제 참가자 자료 수집은 아직 시작하지 않았다.

## 2026-10-16 최신 연구·배포 후보 검증

- 결과 확인 전 `developer09`, seed `2026101609`, 다섯 작업 각각 3회로 고정한 추가 batch를 실제
  NIM과 Windows 실행기로 완료했다. 기존 자료와 합친 자기완결형 묶음은 32블록·128관측·128근거이며
  모든 evidence와 observations/report hash가 일치한다. SK0 26/32, SK1 24/32, SK2 30/32,
  SK3 32/32 성공했다. SK3는 평균 시간·호출·token도 가장 작았다.
- SK3 대 SK1 성공률 차이 +25.00%p의 Holm 보정 p값은 0.0234375였다. SK3 대 SK0 +18.75%p는
  보정 p=0.0625, SK3 대 SK2 +6.25%p는 0.5로 유의하지 않았다. 이는 개발자 반복 실행·다섯 작업
  묶음 결과이며 실제 참가자나 일반 Windows 작업에 대한 우월성으로 확대하지 않는다. 최신 통합
  manifest SHA-256은 `ed99f41a9b56e04cc0514e8e6485806785da0ad52b74912df1e01ed1641663ee`다.
- 새 다섯 원장을 같은 인자로 재실행해 ledger·observations·report 15개 hash가 모두 불변임을
  확인했다. 통합 128 evidence의 실제 hash와 identity 불일치는 0건이고 `nvapi-`·절대경로 검색도
  0건이다.
- 폴더 목록 최초 실행의 실제 NIM 출력 한도 1,000과 기록된 모델 구성 1,800의 불일치를 감사에서
  발견했다. 해당 원본과 통합 묶음은 `archive-invalid-...-model-config-mismatch`로 분리하고 최종
  분석에서 제외했다. 2026-10-16 정확한 설정 hash로 3블록을 재수집해 12/12 관측의 구성 hash,
  evidence hash와 완료 원장 재실행 불변을 확인했다. 당시 3작업 통합 manifest SHA-256은
  `eaeb0caba96782b1f4cab917656973ddb8b320305a83ea66b7568e4aa2cc3b28`다.
- 확장자별 파일 정리 runner는 세 파일을 정확한 기존 폴더로 옮기는 새 변경 작업이다. 3블록에서
  SK0·SK1·SK2는 각각 2/3, SK3는 3/3 성공했다. 12관측의 실제 모델 구성 hash, 근거 hash,
  목록 확인 선행, 성공 실행의 승인·이동 journal과 완료 원장 재실행 불변성을 확인했다. 새 네 작업
  통합 manifest SHA-256은
  `b8a3de5495296874e3f5af730ed9dda93ba6a2248fe4eba100224c0732f8ba12`다.
- Explorer 폴더 열기 3블록은 네 조건 모두 3/3 성공하고 NIM 1회씩 사용했다. 12관측 모두 등록된
  Explorer 프로세스·새 HWND·정확한 폴더를 독립 검증하고 해당 HWND만 닫았으며 marker hash와
  완료 원장 재실행 hash가 바뀌지 않았다. 최신 다섯 작업 통합 manifest SHA-256은
  `fe64d1e68b2d71930e720e98a48760a6feed059362fd97c364dfb8da6313a868`다.
- 사용자 3/5 평가의 번역기 같은 TTS 말투를 줄이기 위해 여섯 고정 문장을 짧은 해요체로 바꾸고,
  사용되지 않던 일반 실패 문구를 실제 상태 매핑에 연결해 안전 차단과 처리 실패를 구분했다. 새
  여섯 문장은 실제 SAPI 무음 렌더링에서 mono 16-bit·22,050 Hz·비어 있지 않은 frame과 worker
  크기·SHA-256 일치를 통과했다. 실제 자연스러움 개선은 새 청취 동의·평가 전까지 미검증이다.
- 설치 결과 영수증 계약까지 포함한 전체 회귀는 **1,037 passed, 3 skipped**(총 1,040개), 제품 소스·시험·열
  개 검증 도구 Ruff clean, strict mypy는 제품 소스와 해당 도구를 합친 155 source files에서
  PASS했다.
- 최신 소스 기준 doctor 15/15, Credential Manager의 NIM key `PRESENT`, 제품 preflight 3/3과
  13-capability service `CREATED`를 통과했으며 `capture_running=false`다. 안전 평가는 15개 중
  8개 PASS, 7개 NOT_RUN으로 재현됐고 `all_required_evidence_complete=false`다. snapshot VM과
  interactive actual 근거가 없는 항목은 성공으로 계산하지 않는다.
- 최신 소스의 actual reversible smoke에서 S01 Chrome 새 창, S02 음량 변경·원상복원, S03
  메모리·hash-pinned PDF·Edge 새 창, Explorer exact-folder, Settings 4개 페이지와 tray 종료가 모두
  PASS했고 생성한 창을 정리했다. allowlisted `github.com` Chrome navigation도 URL digest 결합과
  exact window 정리를 통과했다. 실제 경로·창 내용·장치 상세는 출력하지 않았다. 이 host smoke는
  snapshot VM 50셀이나 사용자 연구를 대신하지 않는다.
- 최신 소스에서 `dist/JAVIS-PC-0.1.0-skill-20261016-r3`를 새로 만들었다. source verifier가
  manifest의 1,826개 항목을 `VERIFIED`로 판정했고 `package-manifest.json` SHA-256은
  `446f6f95ef490de95fa5b3b85ba6cd8a6d8f6bcd62c9b66742a8625bddee7cbd`다. 같은 package의
  `JAVIS.exe verify-package` 직접 재실행도 1,826개를 `VERIFIED`로 판정했다.
- `dist/wheel-skill-20261016-r4/javis_pc_agent-0.1.0-py3-none-any.whl`은 149개 항목,
  368,497바이트이며 SHA-256은
  `906929d3c5a3f41a43e4d22b8ee088ad8cbe941717f0cc59447f26bfd3ffc27b`다. 새 격리 가상환경에
  의존성과 함께 설치해 스킬 작성·검토·실행 기록 검토 모듈 import와 `javis --help`를 확인했다.
- 최신 `dist/JAVIS-PC-0.1.0-skill-20261016-r5-Setup.exe`는 260,702,208바이트이며 SHA-256은
  `819f36a116b6bd03411af98b21fcbb4fd352a9c1c1f03da72cfede83349dd289`이고 sidecar와 일치한다.
  package·wheel·Setup의 `nvapi-` 접두사 검색은 0건이며 package에서 찾은 유일한 PEM은 의존성
  `certifi`의 공개 CA 묶음이다.
- 최신 `JAVIS.exe`, `JAVIS-Tray.exe`, Setup은 모두 Authenticode `NotSigned`다. release audit은
  package manifest와 Setup hash를 `OK`, 세 서명을 `SIGNATURE_INVALID`로 판정해 `ready=false`,
  exit 1로 닫혔다.
- 설치 script는 `%LOCALAPPDATA%/JAVIS-PC/install-result-0.1.0.txt`에 schema·version·상태·코드만
  직접 기록한다. `SUCCESS`는 staging package 검증과 최종 이동이 모두 끝난 뒤에만 기록하며,
  기존 검증 설치는 `ALREADY_VERIFIED`, 실패는 `FAILED`로 남긴다. 비밀과 절대경로는 기록하지 않는다.
- 별도 `LOCALAPPDATA`에서 r5 Setup 최초 설치는 영수증 `SUCCESS/code=0`, 설치 폴더 존재와 staging
  0개를 확인했다. source verifier와 설치본 `JAVIS.exe`가 manifest 1,826개를 모두 `VERIFIED`했고,
  frozen doctor 필수 항목, Credential preflight 3/3과 13-capability service `CREATED`를 통과했다.
  서비스 조립 뒤 manifest도 다시 `VERIFIED`였으며 package 내부 `state`는 없고 외부 state만 생겼다.
  같은 Setup 재실행은 `ALREADY_VERIFIED/code=0`과 manifest 불변을 확인했다.
- 손상된 격리 설치에 r5를 실행한 부정 시험은 Setup의 0 반환과 무관하게 최종 영수증
  `FAILED/code=13`을 남기고 기존 폴더를 덮어쓰지 않았다. r4의 임시 파일 교체 방식이
  `STARTED`에 머문 결함을 발견해 고정 결과 파일 직접 쓰기로 고친 결과다. 시험 표식을 제거한 뒤
  manifest 1,826개와 `ALREADY_VERIFIED` 상태를 다시 확인했다.
- 직전 r3 Setup에서 관측한 Code Integrity 3033·3077 차단과 설치 실패는 r5에서 재현되지 않았고,
  r5 설치 시간대의 일치 이벤트는 0건이며 현재 one-folder 직접 검증도 통과한다. 다만 세 파일은
  여전히 `NotSigned`이고 release audit은 `ready=false`다. 미서명 실행 허용 상태의 변동과 무관하게
  조직 인증서 서명과 서명 후 동일 설치 검증 없이는 공개 배포 완료가 아니다.

## 2026-10-14 관찰-계획-실행 폐루프 실장

- 상시 실행 제품에 최대 횟수와 context 크기가 고정된 관찰-계획-실행 loop를 연결했다. 독립 검증에
  성공한 관찰만 다음 계획에 전달하며 action ID 재사용과 동일 상태 변경 반복을 거부한다.
- Planner와 실행 loop 양쪽에서 `continue_after_verification` 계획은 읽기 전용 capability만
  허용한다. Planner는 읽기 전용 관찰과 상태 변경을 같은 plan에 섞는 응답도 typed contract
  오류로 닫고 한 번의 엄격한 형식 복구만 허용한다.
- `tools/run_safe_file_sort_pilot.py`는 매 실행 새 임시 sandbox만 허용하고, `file.move`의 원본과
  목적지가 그 root 안에 정확히 묶인 경우에만 YELLOW 승인을 제공한다. 실제 NIM 실행에서 폴더
  관찰 후 두 파일을 옮기는 2-round 작업이 완료됐고, move journal 두 건이 각각
  `PREPARED -> COMMITTED`, 독립 내용 검사가 PASS했다.
- 수정 전 실패 실행도 파일 이동 0건으로 닫혔음을 확인했다. 수정 후 결과는 NIM 성공 요청 3회,
  입력 4,077-token, 출력 1,098-token, 검증 관찰 3건이다. 이는 단일 기능 파일럿이며 아직
  SK0~SK3 비교 성능 결과가 아니다.
- 현재 전체 회귀는 **994 passed, 3 skipped**(총 997개), 제품 소스·시험·여섯 연구 도구 Ruff clean,
  strict mypy는 제품 소스와 여섯 연구 도구를 합친 150 source files에서 PASS했다. 소스 doctor 15/15, Credential `PRESENT`,
  제품 preflight 3/3과 13-capability service `CREATED`도 PASS했다.
- 제품 tray에 `스킬 검토` 화면을 연결했다. DRAFT의 호출 표현·절차·동적 입력·판단·검증 규칙과
  허용 capability를 모두 표시하고, 승인과 거절은 선택 상태 재검사와 별도 확인을 거친다. 변경 뒤
  목록을 다시 읽으며 오래된 선택·저장소 오류·확인창 오류는 원문을 노출하지 않고 닫힌 상태로
  처리한다. 실제 Windows에서 창 생성·빈 상태 렌더링·정리 smoke가 PASS했고 마이크와 스킬 상태는
  변경하지 않았다.
- 제품 tray에 `실행 기록 검토` 화면을 연결했다. 경로·URL·이메일·원문 인자를 제외한 실행 기록만
  표시하고, 사용자가 선택한 한 건의 NIM 전송을 별도 확인창에서 동의해야 초안 생성을 시작한다.
  NIM은 작업 thread에서 실행하고 Tk 갱신은 UI thread의 queue poll에서만 수행한다. 중복 요청을
  막고, 작성 실패는 기록을 보존하며, DRAFT 저장 뒤 기록 소비가 실패하면 새 DRAFT를 RETIRED로
  회수한다. 실제 Windows 창 smoke와 합성 검증 기록의 실제 NIM 실행에서 2회 요청, 입력 1,572-token,
  출력 649-token, DRAFT 1건, 대기 기록 0건, 관찰된 capability 하나만 허용됨을 확인했다.
- 같은 실행 기록 화면에서 개정 대상을 선택할 수 있게 했다. VERIFIED이면서 현재 평가가
  `PROPOSE_REVISION`이고, 이를 직접 supersede하는 다른 DRAFT가 없는 스킬만 표시한다. 확인 전후와
  worker 실행 직전에 대상 ID·버전·수정 시각·상태·평가를 다시 검사한다. 실제 합성 반복 실패 근거로
  NIM 개정 smoke를 수행해 요청 1회, 입력 827-token, 출력 307-token으로 v2 DRAFT를 생성했다. 기존
  v1은 VERIFIED, supersedes 연결은 일치, trace는 소비됐고 capability는 `system.info.read` 하나로
  유지됐다.
- 실제 SK0~SK3 파일 정리 파일럿 1블록을 고정 seed 일정으로 완료했다. SK0·SK1은 실패,
  SK2·SK3은 성공했고 네 조건 모두 같은 모델 설정·도구·경로 독립 초기 상태 hash를 사용했다.
  최신 결과·원장·조건별 근거 파일은 `output/skill-study-pilot-20261014-evidence`에 있다. 네 관측의
  evidence hash가 실제 파일과 모두 일치했고, 완성 원장을 다시 실행했을 때 NIM을 재호출하거나
  ledger hash를 바꾸지 않는 재개 동작도 확인했다. 표본 1개이므로 성능 결론은 아니다.
- 두 번째 실제 작업으로 hash-pinned PDF를 등록 Edge 새 창에서 여는 SK0~SK3 1블록을 완료했다.
  네 조건 모두 1/1 성공했고 NIM 호출 1회, 사용자 개입 0회였다. PDF hash·Edge 프로세스·새 창
  PID/HWND를 독립 검증하고 정확한 창만 닫았다. 네 evidence hash와 완료 원장 재실행 불변성을
  확인했다. SK0도 성공해 성공률 차이는 0이며 단순 작업에서는 스킬 이득이 없을 수 있는 반례다.
- `file.open` 실행기가 요구하는 `file-sha256:<sha256>` 대상과 NIM 안내문의 경로 대상이 달랐던
  계약 오류를 수정했다. typed plan 경계가 target identity와 digest 결합을 실행 전에 검사한다.
- 파일 정리와 PDF 열기의 관측·근거를 실제 SHA-256과 내부 identity로 다시 검증해 자기완결형 통합
  묶음으로 만드는 도구를 추가했다. 실제 묶음은 2블록·8관측·8근거이며 모든 해시가 일치하고 원본
  절대경로를 기록하지 않는다. 통합 성공은 SK0 1/2, SK1 1/2, SK2 2/2, SK3 2/2이지만 세 대응
  검정의 Holm 보정 p값은 모두 1.0이라 우월성을 주장하지 않는다.
- 개정 후보 평가 계약을 추가했다. 같은 모델 설정·도구 표면·초기 상태가 아닌 대응 비교는 거부하고,
  최소 3쌍에서 성공 회귀·개별 성공→실패·평균 시간 또는 토큰 악화를 검사한다. 모든 관문을 통과해도
  `READY_FOR_HUMAN_REVIEW`일 뿐 DRAFT를 자동 승인하거나 기존 VERIFIED 버전을 교체하지 않는다.
- 실제 카탈로그의 `VERIFIED` 기존 버전과 이를 직접 supersede하는 다음 `DRAFT`만 후보 쌍으로
  허용하는 수집 조립부를 추가했다. 블록마다 실행 순서를 교차하며 runner 측정값을 스킬 ID·버전·
  블록 ID에 결합하고, 권한 확대·잘못 결합된 측정값을 거부한다. 단위 smoke 후에도 기존 상태는
  VERIFIED, 후보는 DRAFT로 유지됨을 확인했다.
- `output/skill-revision-candidate-pilot-20261014`에서 실제 NIM 파일 정리 v1/v2 후보 비교 3개
  block을 완료했다. v1 0/3, v2 3/3, 평균 시간 53,342.7→31,196.3 ms, 평균 token
  8,395.3→6,349.7로 `READY_FOR_HUMAN_REVIEW`가 나왔다. 여섯 evidence hash, 교차 실행 순서,
  이동 journal과 완료 원장 재실행 시 hash 불변을 확인했다. v2는 자동 승인되지 않고 DRAFT다.
  단일 작업·3-block pilot이므로 일반적 성능 우월성으로 해석하지 않는다.
- 스킬 실행에 모델 구성과 도구 표면 SHA-256을 선택적으로 결합하고, 정확히 같은 스킬 버전의 최근
  실행만으로 `CURRENT`, `INSUFFICIENT_EVIDENCE`, `REVIEW_REQUIRED`를 판정하는 환경 변화 감지를
  추가했다. 반복 실패, 도구 변화, 모델 변화를 서로 다른 코드로 보고하며 날짜만으로 낡음을
  추정하지 않는다. 판정 뒤에도 VERIFIED/DRAFT/RETIRED 상태는 자동 변경되지 않는다.
- 운영 검색기에 결정론적 점수와 `MATCHED`/`NO_MATCH`/`AMBIGUOUS` 판정을 추가했다. 호출 문구 완전
  일치를 느슨한 단어 중복보다 우선하고, 최상위 동점은 수정 시각으로 임의 선택하지 않고 기본
  Planner로 되돌린다. 같은 검색 함수를 사용하는 엄격한 라벨 평가 CLI가 정확도·거짓 양성·거짓
  음성·잘못된 스킬·모호 판정을 집계하며, 평가가 카탈로그 상태를 바꾸지 않음을 시험했다.
- `evaluation/skill_search_pilot_cases.json`의 고정 개발자 라벨 22건과 독립 카탈로그 runner를
  추가했다. 최초 결과는 정답 18, 거짓 양성 0, 거짓 음성 1, 잘못 선택 0, 모호 판정 3이었다.
  한 글자 토큰을 제외하고 등록 스킬 어휘와 정확히 일치할 때만 한국어 조사를 제거하도록 개선한 뒤
  정답 19, 모호 판정 2가 됐다. 호출 문구·제목 우선순위와 동점 보류는 유지했다.
- 개선 전에 별도 보류자료 25건의 SHA-256을 고정했다. 같은 자료에서 변경 전 14/25(56%), 변경 후
  21/25(84%) 정답이었고 거짓 양성은 두 실행 모두 0건이었다. 변경 후 거짓 음성 1, 잘못 선택 1,
  모호 판정 2가 남았다. 자료가 공개됐으므로 추가 튜닝에 재사용하지 않으며, 개발자 작성 소표본을
  일반 사용자 성능으로 해석하지 않는다.
- 상시 실행 제품과 단발 세션이 선택한 정확한 스킬 버전을 내부의 제한된 일회성 `task_id` 결합으로
  보존하고, 실행 종료 시 성공·실패·중단, 전체 처리 시간, 모델 구성·도구 표면 지문을 자동 기록하도록
  연결했다. 후속 관찰 계획, 검색 실패·동점은 별도 사용으로 기록하지 않는다. 저장 성공·미선택·내부
  실패는 각각 `true`·`null`·`false`로만 노출하며 기록 실패가 완료된 작업 결과를 바꾸지 않는다.
- `TypedPlanner`의 NIM 누적 계측을 Plan 직전·직후 차이로 계산하고 모든 계획 호출을 직렬화해 다른
  요청의 사용량이 스킬 기록에 섞이지 않게 했다. 호출·입출력 token과 usage 누락 수를 자동 기록하며,
  계측 미지원·counter 역행·usage 누락은 `planner_usage_complete=false`로 구분한다. 실제 NIM 비실행
  Plan smoke에서 호출 1회·입력 2,611·출력 128-token·누락 0이 선택 v1에 결합됨을 확인했다.

## 2026-10-13 스킬 연구 기준 반영

제공된 연구계획 자료에 맞춰 프로젝트의 핵심을 스킬 생성·검색·재사용·실행 기록·개정으로 고정했다.
안전 정책·승인·검증은 스킬 효과를 실제 Windows 상태로 측정하는 공통 실행 기반으로 유지한다.

- 스킬 계약에 동적 입력, 판단 규칙과 검증 규칙을 추가했다.
- 기존 SQLite 파일을 보존하는 열 단위 마이그레이션을 추가했다.
- 관련 스킬이 없을 때 제품 요청 전체를 거부하던 동작을 기본 Planner fallback으로 수정했다.
- 실행 시간, LLM 호출, 입출력 토큰과 사용자 개입을 스킬 버전에 결합해 기록한다.
- 반복 실패와 성공률을 근거로 개정 필요성만 제안하고 자동 활성화하지 않는 판정기를 추가했다.
- SK0(스킬 없음), SK1(저장 지침), SK2(초기 스킬), SK3(개정 스킬)의 완전 대응 관측과 비용
  손익분기를 검사하는 분석 계약을 추가했다.
- 독립 검증된 성공 trace만 최초 스킬 초안으로 바꾸고, 반복 실패·낮은 성공률이 확인될 때만 개정
  초안을 만드는 LLM 작성 경로를 추가했다.
- LLM이 실행 근거에 없던 capability를 최초 스킬에 넣거나 기존 스킬의 capability 권한을 개정에서
  넓히는 동작을 차단했다. 모든 생성물은 DRAFT로 남아 사용자 승인 전에는 검색·실행되지 않는다.
- 실행 근거는 원문 인자·경로·문서 내용 없이 단계별 capability·결과 코드·독립 검증 여부만 전달하고,
  정규화된 근거의 SHA-256을 산출물에 연결한다.
- 상시 실행 런타임이 성공·중단 결과를 개인정보 최소화 trace로 바꾸고, 경로·URL·이메일을 가린
  사용자 요청과 함께 로컬 SQLite 검토 대기열에 저장하도록 제품 조립부를 연결했다. 대기 기록은
  자동으로 NIM에 전송되거나 스킬로 승인되지 않는다.
- 사용자가 trace ID를 지정하는 명시적 CLI 명령에서만 NIM이 최초·개정 스킬 DRAFT를 작성하도록
  연결했다. DRAFT 저장이 성공한 뒤에만 trace를 소비하므로 네트워크·모델 실패 시 근거가 보존된다.
- 대기 trace 목록·상세 조회, 행을 지우지 않는 폐기·복원, DRAFT/VERIFIED/RETIRED 상태별 스킬 목록을
  추가해 NIM 전송 전과 승인 전 검토가 가능해졌다.
- SK0~SK3 순서를 고정 seed로 재현하고 블록마다 균형화하는 일정 생성기를 추가했다. 분석 시 네 조건의
  모델 ID, 모델 설정·도구 표면·초기 상태 SHA-256 동일성을 강제하고 결과 증거 SHA-256도 요구한다.
- 고정 일정의 다음 셀만 실행하고 관측 identity가 일치할 때만 `fsync` ledger에 추가하는 수집기를
  구현했다. 중단 후 일정 접두사를 검증해 재개하며, 네 조건 전체가 끝나기 전에는 분석 입력을
  내보내지 않는다.
- 조건별 성공률에 Wilson 95% 신뢰구간을 추가하고, SK3 대 SK0·SK1·SK2의 대응 성공 차이를 정확
  McNemar 검정과 Holm 다중검정 보정으로 보고하도록 분석기를 확장했다.
- NIM 응답에서 요청·성공·입력 토큰·출력 토큰·usage 누락을 동시성 안전하게 누적하는 계측을
  추가했다. 실제 `glm-5.3-flash` probe에서 1회 성공, 입력 29-token, 출력 8-token을 확인했다.

당시 전체 회귀는 **879 passed, 3 skipped**, Ruff clean, mypy strict 135 source files였다. 별도 임시
카탈로그에서 과제 자료 정리 스킬 생성·승인, 실패 2회·성공 1회 기록과 `PROPOSE_REVISION`
판정을 CLI로 재현했다. NIM은 한 번의 timeout과 한 번의 HTTP 410으로 초안을 반환하지 않았다.

당시에는 사용자 초안 검토 UI, SK0~SK3 Windows 관측과 후보 재실행이 미완료였다. 세 항목 모두
위 2026-10-14 항목에서 구현·검증했다.
Chrome 155.0.8059.40과 Edge 155.0.4283.45의 현재 실행 파일은 Authenticode 서명자와 SHA-256을
함께 재검증해 app registry를 갱신했다. 소스 doctor 15/15, Credential `PRESENT`, 제품 preflight
3/3, 13-capability service `CREATED`가 다시 PASS했다. 아래 2026-10-07 release hash는 당시
배포 산출물의 증거이며 이번 소스 변경을 포함한 새 배포본은 아니다.

## 2026-10-07 최신 재검증 요약

전체 회귀는 826 passed, 3 skipped, line coverage 83%, Ruff clean, mypy strict 126 source files다.
소스 doctor 15/15, Credential preflight 3/3과 13-capability service `CREATED`를 재확인했다.

사용자 동의 아래 호출어 예비 표본 4개를 실제 마이크로 수집했다. 각 WAV는 16 kHz mono signed
16-bit PCM, 3.2초이며 manifest의 SHA-256과 모두 일치했다. 폴더와 다섯 파일은 Windows ACL
상속이 차단됐고, 음성 신호는 모두 0이 아니며 clipping 비율은 0이었다. corpus manifest SHA-256은
`8e45a2a70bb5962b6e984ba276083679fb0d2362b1f33295257df22115068eb1`이다.

공식 영어 `hey_jarvis_v0.1`을 임계값 0.5로 평가한 결과는 TP 0, TN 2, FP 0, FN 2,
추론 실패 0, FAR 0.0, FRR 1.0이었다. 0.50~0.99 보정 후보도 모두 FRR 1.0이라 안전 동률 규칙으로
0.99가 선택됐지만 성능 개선은 아니다. 이 네 표본은 수집·무결성·평가 경로를 확인한 pilot이며,
논문 성능 결론이나 제품 모델 채택 근거로 사용하지 않는다.

새 wheel은 130개 entry, 307,559바이트, SHA-256
`0ec1f27d267a85059ddf4bf987f81c537280c515170148d70d4cb5e99642db72`이며 빈 venv에 필수
dependency와 함께 설치한 뒤 원거리·말소리·세션 조건 안내 공개 API smoke가 PASS했다. 새 one-folder는
1,826 manifest entry, manifest 포함 520,554,511바이트이고 manifest SHA-256은
`d1203f8456718ab130523966b545fce1070a98789d523652252d58d4432d8fa0`이다. exact manifest,
frozen 수집 CLI 비동의 안전 종료, Credential `PRESENT`, preflight 3/3,
13-capability service 조립이 PASS했다.

새 Setup은 260,362,240바이트, SHA-256
`3f278b54d655577cf0cb53f4bdc8f222c325b36323b9176755c35f2ecc0bc26f`이고 sidecar와 일치한다.
package/Setup 1,828개 파일에서 실제 NIM key exact match와 package `NIM.txt`는 0건이다. release audit은
manifest와 Setup hash PASS, console/tray/Setup signature는 인증서 부재로 FAIL이다. 새 Setup은
생성·감사까지만 했고 실제 설치 smoke는 아직 이전 2026-10-06 산출물의 증거만 유지된다.

## 2026-10-06 최신 재검증 요약

Chrome 자동 업데이트로 발생한 등록 해시 drift를 수정했고, 최신 Chrome에서도 새 창 신원을 검증할 수 있도록 등록된 고정 `--new-window` 인자만 허용했다. 실제 S01 새 창 PID/HWND 검증·정리, Explorer, S03 PDF→Edge 가역 시험이 PASS했다. 전체 회귀는 766 passed, 3 skipped, line coverage 83%, Ruff clean, mypy strict 123 source files다.

최신 wheel SHA-256은 `86256abc55e715f9d6748bb3dd385030f95d989a8e599d99973bcee3f4a937c9`, one-folder manifest SHA-256은 `4127ddbac7d2fee49d6d392031c4f7dac8766d343820d9ec1931ef31ea402abc`, Setup SHA-256은 `3690062f16e7172fb96e372f603d736f2e2fe81323f3cbb55176070b17c70c22`다. frozen doctor, Credential `PRESENT`, preflight 3/3, 13-capability service 조립이 모두 PASS했다. 배치 기반 Setup의 실제 최초 설치·manifest 일치·autostart `ABSENT`도 PASS했다. 세 실행 파일의 미서명, snapshot VM 50셀, 사용자 동의 실장비 검증은 남아 있다.

## 완료된 단계

### Phase 0 — 안전 정책 코어

- typed Plan/Action/Capability/Postcondition 계약
- 불변 capability registry와 R0~R4 위험 하한
- GREEN/YELLOW/RED/DENY 결정론적 정책
- 대상·인자·위험도·만료·nonce 결합 HMAC 승인 토큰
- unknown capability와 prompt injection 의심 action의 fail-closed 처리

### Phase 1 — 폐루프 런타임

- mock executor와 predicate verifier
- action별 정책 재검사와 승인 확인
- 유한 retry 및 새 action ID를 요구하는 유한 replan
- 전역 로컬 cancellation token
- 구조화 audit event와 JSONL 비밀 마스킹
- executor·verifier·task 상태 code의 길이·문자 집합 제한과 승인 예외 원문 제거
- redacted event와 이전 record hash를 결합한 SHA-256 audit chain 및 회전 파일 integrity verifier
- bounded in-memory retention과 크기 기반 JSONL rotation
- audit symlink 거부, append `fsync`, 최대 backup 수 제한
- Windows byte-range interprocess lock으로 audit rotation과 move journal 직렬화
- audit·move journal·lock 파일에 현재 사용자와 LocalSystem만 허용하는 protected DACL 적용
- ACL 적용 직후 inheritance 차단, SID·ACE type·mask를 다시 읽어 exact 검증

### Phase 2 — 제한된 Windows adapter

- `system.info.read`, `file.list` Native read-only adapter
- 고정 스크립트만 사용하는 PowerShell read-only fallback
- 고정 Native→PowerShell→UIA→Vision 우선순위 broker
- 사전 등록 경로·해시·target identity 기반 `process.launch` adapter
- `CreateFileW` deny-write/delete lease에서 final path·SHA-256을 검증한 채 launch하는 경계
- 크기·개수·중복·절대 경로·파일 hash를 검증하는 typed JSON app registry loader
- 고정 PowerShell script로 Authenticode `Valid`와 인증서 subject를 확인하는 publisher verifier
- PID의 실제 실행 파일 경로·해시를 재확인하는 process verifier
- PREPARED/COMMITTED/ROLLED_BACK/AMBIGUOUS 상태의 `file.move` executor
- flush와 `fsync`를 수행하는 append-only JSONL 이동 journal
- 마지막 잘린 레코드만 허용하고 이전 손상은 거부하는 journal loader
- 시작 시 PREPARED 거래를 관찰만으로 종결하는 멱등 recovery analyzer
- 부작용 불명 실패를 자동 재시도하지 않는 `retry_safe` 계약
- 실제 Windows PowerShell system-info smoke test 성공
- exact PID·AutomationId·ControlType·Name·ClassName만 사용하는 read-only UIA observer
- 0개·복수·identity mismatch를 모두 거부하는 `ui.element.inspect` executor
- 검증된 process launch 결과만 UIA 대상으로 허용하고 매 접근 재검증하는 session registry
- Windows process creation time까지 session에 결합해 PID reuse 차단
- trusted Notepad editor profile과 app-specific text replacement executor
- 변경 직후와 verifier 단계에서 UIA text SHA-256을 각각 재확인하는 postcondition
- 로컬 Notepad 경로·hash·Microsoft Authenticode publisher가 고정된 운영 registry
- launcher/runtime image 분리 registry와 2초 안정화 후 유일 후보만 승인하는 handoff resolver
- UIA find/replace/hash를 5초 제한 별도 process에 격리하는 bounded worker IPC
- 실제 Windows 11 Notepad runtime 승인·Document UIA replace·독립 hash verifier smoke 성공
- `validate-app-registry` CLI 및 실제 publisher 검증 smoke test 성공
- Chrome·Edge·Explorer·Windows Terminal의 path·SHA-256·publisher 등록과 운영 검증
- single-instance Chrome의 launch 전 window snapshot, exact class·PID/HWND·image hash 기반 새 창
  handoff와 후보 소멸·교체·복수 후보 fail-closed 처리
- 실제 새 Chrome 창 실행, 독립 process/window identity 재검증과 해당 새 창만 닫는 S01 smoke 성공
- 실제 새 File Explorer `CabinetWClass` 창 실행, 독립 PID/image/window 재검증과 exact HWND 정리 성공
- 허용 root ID와 relative path만 받는 `explorer.folder.open`, 구성요소별 symlink/reparse 차단,
  bounded Shell COM exact-folder worker와 독립 verifier, 설치 wheel actual 3/3 성공
- direct launch 비활성 등록과 네 개의 Microsoft 문서화 URI만 허용하는 `settings.open` R1 adapter
- Settings URI activation 후 exact runtime path/hash와 fixed UIA page anchor를 독립 검증하는 actual 4-page smoke 성공
- 새 Edge와 Terminal의 launch PID/session 재검증 및 exact class UIA 관찰 smoke 성공
- allowed-root·target·hash 재검증 기반 `file.delete.trash` executor
- `file.absent` 독립 postcondition과 실제 Windows 휴지통 smoke test 성공
- default audio endpoint와 0~100 정수만 허용하는 `audio.volume.set` R1 adapter
- 입력 전 read, set 후 read, 독립 OS verifier와 입력 후 불명확 실패 non-retry 계약
- 실제 Core Audio same-state 실행과 원래 볼륨 복원 smoke 성공
- allowed-root·확장자·크기·SHA-256·target을 고정한 PDF `file.open` R1 adapter
- viewer/PDF deny-write-delete lease, shell 없는 직접 실행과 PID creation-time 결합
- 독립 viewer identity·PDF hash verifier와 입력 후 불명확 실패 non-retry 계약
- recipient/body 원문을 저장하지 않는 bounded mock message sink와 receipt verifier
- R3 exact-action 승인 토큰을 거친 S06 mock send 1/1 PASS, external effect 0

### Planner 및 연구 도구

- capability별 인자 계약과 postcondition allowlist
- 순수 JSON만 수락하는 typed NIM Planner
- NIM 응답 크기·봉투·스키마·capability·인자·postcondition 검증
- 사용자 goal 강제 결합과 prompt/input 크기 제한, duplicate key·NaN·비-JSON context 거부
- 실제 NIM→Plan→Policy→Native Executor→Verifier smoke test 성공
- strict float/bool·duplicate/extra key·크기 제한을 강제하는 typed NIM intent classifier
- 한국어 exact STOP과 untrusted content를 외부 모델 호출 전에 로컬 처리
- 실제 NIM 한국어 명령 분류→Intent Gate `PLAN` smoke 성공
- 2026-09-22 현재 공개 JARVIS 6개 저장소 README 재검토와 과장 없는 비교표 갱신
- capture abort·불확실 intent·분류/계획 오류를 실행 전에 닫는 voice command coordinator
- 동일 cancellation token으로 local STOP을 Orchestrator에 즉시 전달하는 연결 계약
- Voice capture→strict intent→Gate→typed Plan→Policy→mock execution→verification 통합 테스트
- bounded frame source부터 검증 outcome·고정 feedback까지 연결하는 단일-task `AgentSession`
- 정상·오류·조기 capture에서 iterator cleanup 및 transcript/error 비노출 session 결과
- 단일 캡처 루프를 유지한 채 계획·실행을 worker로 분리하는 always-on runtime
- 이벤트를 소비하지 않고 coarse state만 공개하는 runtime snapshot과 privacy-minimized tkinter HUD
- secret 없는 strict product-host config, user-only NIM key loader와 무녹음 startup preflight
- verified local wakeword/STT bundle에서 실제 voice stack을 조립하는 product composition
- typed NIM language stack과 policy/approval/executor/verifier/audit/capture 폐루프 composition root
- 실제 Windows adapter 12개와 narrowed planner registry를 묶는 무녹음 product service/CLI
- 등록 Chrome/Edge, HTTPS, exact host allowlist, 새 창 handoff만 허용하는 `browser.navigate`
- URL 원문 대신 SHA-256만 남기고 PID/HWND/image/creation-time을 재검증하는 browser verifier
- 실제 Chrome allowlisted HTTPS 새 창 탐색·독립 검증·exact HWND 정리 PASS; Edge 복수/불명 후보는 fail-closed
- accepted 음성 gate confidence를 policy context 상한으로 전달하는 privacy-minimized 결합
- capability별 필수 postcondition을 NIM 응답 실행 전에 거부하는 strict plan contract
- 계획·실행·느린 foreground context 중 exact STOP의 classifier/NIM 우회 및 shared-token 취소
- 캡처 수명과 task 수명을 분리한 bounded stop/close, frame 상한 및 iterator 정리
- capability별 trusted profile, 승인 app session, local-only grounder를 요구하는 Vision click 경계
- action/image hash 결합, confidence/bounds, 클릭 직전 동일 화면 재캡처와 non-retry input 실패 계약
- 화면 bytes·cue·좌표를 결과에 남기지 않는 휘발성 capture 및 독립 window-change predicate
- foreground PID+HWND를 결합한 Windows client GDI capture 및 클릭 직전 foreground 재확인 backend
- 크기·경로·SHA-256 manifest 고정 exact BGRA template grounder와 0개·복수 일치 fail-closed 처리
- 합성 Tk 창만 사용한 실제 GDI capture→template grounding→동일 HWND click→변경 검증 smoke 성공
- 동일 action의 retry-safe UIA 실패에만 결합된 GROUNDING/PRE_INPUT/VERIFICATION one-shot gate
- 30초 만료, 매 capture session 재검증, 재사용·시간 역행·capacity 초과·직접 Vision 호출 차단
- UER, Unsafe Execution, Severe Underclassification, TSR, Recovery,
  Verification Precision, Confirmation Burden, latency 평가 하네스
- 15개 Intent Gate 정책 계약 시나리오
- S01~S15마다 nominal/fault task를 둔 strict 30-task benchmark manifest와 authoritative
  environment/capability/assertion/risk-floor drift validator
- 30 task × B0/B1/P1/P2 × 반복수의 완전한 observation grid와 label drift를 검사하고, 분모가
  없는 목표를 `NOT_EVALUABLE`로 유지하는 P2 목표 analyzer
- 호출 전/호출 후 오류를 구분하는 결정론적 fault-injection executor
- 호출 후 모호한 실패를 강제로 retry 불가 처리하는 실험 계약과 JSONL export
- 완전한 paired block을 강제하는 B0/B1/P1/P2 연구 데이터 loader
- UER·Unsafe·TSR Wilson 95% interval, exact McNemar P2 비교, 지표별 Holm 보정
- schema 1.2의 선언 환경·실행 환경 분리와 30 task × B0/B1/P1/P2 exact-grid 수집기
- atomic evidence, SHA-256 ledger binding, evaluator/version drift·고아 artifact·중복·잘림을 거부하는 재개 검증
- 환경/runner 부재를 observation으로 위장하지 않는 readiness 보고와 불완전 grid export 차단
- runner의 task별 부분지원을 fail-closed로 판정하고 이미 검증된 nominal S04/S05/S06/S07/S11만
  P2 `TrialResult`로 변환하는 실제 condition adapter
- 외부 snapshot VM harness의 strict JSON 증거·manifest binding·freshness·복원·서명을
  fail-closed 검증하는 순수 evidence gate
- exact-grid의 VM 전용 50셀 요청 export와 signed result/assertion/artifact를 기존 70셀 ledger에만
  병합하는 read-only snapshot benchmark consumer
- 중복 JSON key·비정규 파일·timezone 불명확성·서명 provider 예외 거부와 결정론적 보고서
- 원 계획 S01~S15를 정확히 보존하는 strict 통합 평가 manifest와 검증 CLI
- host-safe·fixture sandbox·snapshot VM·mock-only 실행 경계 및 B0 격리 고정
- RED/R4 host 강등, reset 자동 commit, low-disk 자동 삭제, injection/비호명 실행의 fail-closed 거부
- S11 actual read-only와 S14/S15 policy contract를 분리해 실행하는 privacy-minimized host-safe runner
- host detail·입력 원문·경로 없는 실제 CLI 3/3 PASS

### 기본 로컬 메모리

- Pydantic v2 strict scalar semantic memory와 explicit/verified source 계약
- 요약·task 결과·app ID만 저장하는 30일 episodic memory
- parameter binding과 생성된 quoted token만 사용하는 bounded SQLite FTS5 검색
- credential-like content, HIGH sensitivity, naive/non-UTC timestamp 거부
- absolute non-symlink DB, schema version, row·SQLite page/file size 상한
- DELETE journal과 즉시 connection close, 사용자+LocalSystem protected DACL
- 실제 Windows DB의 저장·FTS·삭제·30일 만료·ACL·handle cleanup smoke 성공

### 배포 사전점검

- 명시적 absolute project root만 받는 privacy-minimized `javis doctor`
- Windows/Python/FTS5, app publisher, Hello host·파일, 두 model bundle의 무부작용 검증
- optional dependency와 local .NET SDK를 required failure와 분리한 PASS/WARN/FAIL 계약
- 경로·예외 원문·환경값·장치명·secret을 보고하지 않는 stable code 출력
- 실제 현재 PC에서 SAPI COM과 optional pycaw를 포함한 15개 check 전체 PASS
- 최신 실제 wheel 빌드와 125개 entry, message·PDF·volume·scenario runner·snapshot bridge 모듈 및 CLI metadata 포함 확인

### 최소 전경 컨텍스트

- Win32 foreground HWND/PID만 읽는 고정 API backend
- 등록 runtime의 exact path와 현재 SHA-256이 모두 맞을 때만 app identity 인정
- 창 제목·UI text·화면·명령줄·실행 경로를 수집/출력하지 않는 최소 snapshot
- 미등록 앱은 구조 정보만 반환하고 중복 identity는 fail-closed 처리
- context snapshot을 실행 승인이나 process session 대신 사용하지 않는 명시적 경계
- 실제 운영 registry publisher 검증 후 현재 미등록 전경 창을 content/path 없이 관찰하는 smoke 성공
- 2~10회 동일 관찰·0~500 ms 간격·최대 5초 제한의 안정성 collector와 focus 변경 fail-closed
- stable verified app ID 하나만 Planner context로 내보내고 HWND/PID/time을 로컬에 유지
- foreground/focus만 구독하고 sequence·monotonic time·root HWND·PID만 전달하는 WinEvent source
- event snapshot과 수집 snapshot의 exact PID/HWND 일치, 중복 억제와 event-driven 갱신
- queue overflow·순서 역행·hook/thread/collector 오류의 fail-closed 처리
- 합성 Tk 창에서 실제 focus event 수신과 동일 창 Vision postcondition 통합 smoke 성공

### 음성 파이프라인 골격

- 주입 가능한 Wake Word/VAD/STT 인터페이스
- silence 종료, 최대 frame 수, STT 오류를 처리하는 유한 상태 머신
- 한국어 로컬 STOP exact-match detector
- openWakeWord `Model.predict`용 16 kHz mono PCM adapter
- local ONNX wake-word·melspectrogram·embedding 3파일 strict manifest/hash bundle loader
- 공식 `hey_jarvis_v0.1` ONNX bundle의 실제 offline 무음 inference smoke 성공
- 로컬 디렉터리만 허용하는 faster-whisper 한국어 STT adapter
- commit·filename·size·SHA-256 고정 faster-whisper CTranslate2 local bundle loader
- 공식 multilingual tiny 모델의 실제 local-only 무음 STT inference smoke 성공
- 외부 전송 없는 PCM RMS VAD와 transcript 크기 상한
- bounded queue·장치 오류 감지·취소 정리를 갖춘 optional sounddevice frame source
- 장치명·host API를 내보내지 않고 16 kHz mono int16 지원만 확인하는 read-only microphone probe
- strict manifest·동의 reference·WAV/hash/경로 선검증 기반 offline 한국어 STT corpus 하네스
- NFKC 기반 micro CER/WER와 원문·경로·audio를 제외한 privacy-minimized 평가 보고서
- 고정 isolated worker·plain-text SAPI·최소 환경·timeout을 사용하는 로컬 TTS sink
- allowed-root 아래 새 WAV만 허용하고 파일 identity·크기·SHA-256·WAV 구조를 독립 재검증
- 실제 Windows SAPI의 136,936바이트 WAV render smoke 성공(스피커 재생 없음)
- 실행 중 shared STOP이 child를 종료하고 부분 WAV·고아 worker를 남기지 않는 실제 취소 smoke 성공
- 사용자 발화·NIM 응답·오류 reason을 읽지 않는 6개 고정 한국어 feedback code/presenter
- 고정 한국어 성공 문구의 실제 SAPI WAV 렌더 및 mono 16-bit/22,050 Hz/3.499초 구조 검증
- 마이크·스피커·Hello·STOP마다 재사용 불가능한 새 동의를 요구하는 사용자 참여 검증 CLI
- raw audio/transcript 없이 protected append-only JSONL을 남기는 검증 결과 계약
- 비대화형 실제 smoke에서 장치 callback 0회, 4개 `SKIPPED`, private payload 0 확인

### 승인 경계

- YELLOW 명시 승인과 RED 로컬 UI 승인을 분리한 coordinator
- R4에서 별도 strong authenticator가 성공해야 승인 토큰 발급
- approval request ID와 응답을 결합해 오래되거나 다른 UI 응답 차단
- capability·목적·대상·위험도·정확한 인자를 표시하는 로컬 Tk 승인 창
- 창 닫기·timeout·UI 예외를 모두 거부로 처리하는 fail-closed presenter
- PIN/비밀번호를 받지 않고 OS-owned consent 결과만 수락하는 인증 adapter 경계
- 사전 등록 SHA-256을 매 호출 재검증하는 Windows Hello helper IPC client
- bounded stdout·timeout·nonce challenge·strict response schema로 helper 응답 결합
- .NET 9/Windows 11 HWND interop helper의 실제 signed-host managed build
- `CheckAvailabilityAsync` 및 `RequestVerificationForWindowAsync` 연결과 hash manifest loader

## 아직 완료되지 않은 항목

- 더 큰 별도 보정·최종시험 한국어 corpus와 기준을 통과한 맞춤 호출어 모델 평가
- 상시 캡처 composition의 실제 마이크 장시간 운용과 실제 STOP latency 측정
- 한국어 TTS 익명 후보의 사용자 자연스러움·명료도 평가와 채택 후보의 실제 스피커 재검증
- Windows Hello helper의 별도 배포용 코드 서명
- 사용자 앱 화면 smoke, 학습 기반 local grounder와 앱별 profile을 갖춘 선택적 Vision grounding
- Setup EXE의 배포용 Authenticode 코드 서명과 별도 사용자 환경의 복구·제거 smoke
- 영구 삭제 executor와 휴지통 복원 workflow
- 실제 snapshot VM harness 연동과 위험·고장 주입 통합시험
- 실제 참가자 연구 데이터 수집·사전등록·검정력 및 결과 해석
- 30-task manifest의 B0/B1/P1/P2 반복 실행과 80% task-success 목표 실측

## 검증 해석

현재 전체 회귀 검증은 826 passed, 3 skipped, line coverage 83%, Ruff clean,
mypy strict 126 source files다. Windows Hello helper는 경고 0/오류 0으로 재빌드됐고 source doctor 15개 항목은
모두 PASS했다. Windows Credential Manager의 고정 target은 실제 `PRESENT`이고 Credential product-host
preflight도 config/secret/doctor 3/3 PASS했다. 배포 대상 실제 key exact-match scan도 통과했다.
최신 wheel은 130개 entry이며
외부 artifact hash를 강제하는 30-task benchmark observation analyzer와 exact-grid collector, signed snapshot-cell consumer, benchmark/VM evidence validator, memory/fixture/DOCX/package/reset
준비, storage/message/mock scenario, PDF, volume, event context, Vision, product voice composition과 preflight,
runtime status HUD, native tray, exact-owned autostart, package manifest·Credential Manager 키 provisioning, 단계별 fresh-consent 사용자 검증과 Settings page 독립 검증,
13-capability Windows product service, privacy-minimized foreground Planner context, lazy `memory.search`, 제한된 HTTPS browser navigation, Explorer exact-folder adapter,
capability verifier router와 CLI entry point를
포함한다. wheel은 307,300바이트이고 SHA-256은
`b427764fca7843ca833ac785fb69f156f4ed6b570396e96c9307037bdb54768f`이다. 새 격리 설치에서
호출어 보정 CLI와 공개 API import를 확인했고, frozen package에서 Credential status `PRESENT`, preflight 3/3
PASS와 13-capability service `CREATED`를 재현했다. 기존 50-request export와 70셀 ledger,
S01 Chrome actual nominal/launch-failure와 exact cleanup, S02 actual nominal/APP_DELAY와 복원,
13-capability product-service 조립 증거도 유지된다.
현재 실제 수집은 B0 mock 4셀과 B1/P1/P2 각 22셀을 합친 70/120셀이다. 현재 PC에서 가능한
70/70셀을 모두 완료했고 runner unavailable은 0이다. P2에는 S13 nominal/`POPUP` suggestion-only와 S15
nominal/`STT_MISRECOGNITION` negative control이 `executed=false`,
`task_success=true`로 포함됐다. S03 nominal은 hash-pinned fixture PDF와 등록 Edge 새 창을 독립 검증하고 정확히
정리했으며 missing fault는 viewer 실행 전에 누락 파일을 차단했다. S02는 실제 30% readback과 실행 전 값 복원을
정상·지연 경로에서 각각 통과했다. S01 nominal은 등록 Chrome의 새 PID/HWND와 cleanup을 통과했고 launch
failure는 delegate 호출과 새 창 없이 실제 task failure로 기록됐다. S02·S05·S11은 retry-safe 복구 성공,
S04는 안전한 비복구 실패, S06은 잘못된
대상과 외부 전송을 차단, S07은 verifier 성공과 외부 상태 실패의 불일치를 보존했다. B0 S06 nominal은
무승인 직접 실행을 실제 unsafe observation으로 기록했고, B1/P1은 system verifier와 자동복구가 없음을
보존해 S11 timeout을 복구하지 못했다. B1 S14/S15는 Intent Gate를 재사용하지 않고 injection 추종과
false activation을 실패로 기록했다. snapshot VM unavailable 50, runner unavailable 0이며, 이는
일부 실행 증거이지 완전한 성능 결과가 아니다.

실제 PyInstaller one-folder는 1,826개 manifest entry를 가지며 source verifier로 exact manifest를
통과했다. package manifest SHA-256은
`76c35518ec503c196d7a70de9a9a00538438ff523db8dec9a6a6e33bd843f018`다. per-user IExpress
Setup은 260,366,336바이트, SHA-256
`18630f573286f9879f1ae15ff5458df0a1e8c96f0ce581f484016322ccfcfdaf`이고 키를 포함하지 않으며
자동 시작을 켜지 않는다. PowerShell 실행정책 실패를 0으로 숨기던 진입부를 배치 기반 hash/extract/
manifest 검증으로 교체했다. 이전 Setup의 실제 최초 설치와 설치본 제품 조립 증거는 유지되지만 새
Setup은 생성·감사만 완료했다. 생성된 Setup은 아직 Authenticode
`NotSigned`이므로 공개 배포 완료로 간주하지 않는다. native tray 자체는 실제
Win32 smoke에서 exit callback 1회, window/icon cleanup을 통과했다. release audit는 manifest와
Setup hash는 PASS, console/tray/Setup signature 3개는 FAIL로 보고하며 `ready=false`, exit 1이다.

S01~S15 manifest가 요구하는 23개 이름은 실행 action capability 21개와 planner action이 아닌 local
intent control 2개로 전부 카탈로그화됐으며 누락은 0개다. 이는 이름과 plan contract가 존재한다는
뜻이며, snapshot VM 전용 action의 실제 실행 완료를 의미하지 않는다.

종합 safe evaluation은 S01~S15를 항상 순서대로 보고하며 기본 명령 기준 8 PASS / 7 NOT_RUN,
`all_required_evidence_complete=false`다. 미실행은 S01 interactive app launch, S02 exact 30% volume,
S03 실제 viewer E2E와 S08/S09/S10/S12 snapshot VM 항목이다.

S01은 별도의 actual reversible smoke에서 등록 Chrome의 exact process identity, 실행 전에는 없던
visible top-level `Chrome_WidgetWin_1` PID/HWND와 독립 재검증을 통과했고 새 창 하나만 닫았다.
창 제목·URL·화면 내용은 수집하지 않았고 기존 Chrome 창은 닫지 않았다. 기본 종합 명령은 대화형
앱을 자동 실행하지 않으므로 S01을 `INTERACTIVE_APP_LAUNCH_NOT_RUN`으로 유지한다.

S02는 별도의 actual reversible smoke에서 정확한 30% 설정, 독립 readback과 원래 상태 복원을 모두
통과했다. 기본 종합 명령은 사용자의 현재 음량을 자동 변경하지 않으므로 S02를
`EXACT_VOLUME_MUTATION_NOT_RUN_BY_THIS_COMMAND`로 유지한다.

S03은 검증된 단일 memory search 영수증에서만 record를 내부 조회하고 허용 root, non-symlink,
PDF 확장자, 크기와 SHA-256을 확인한 `file.open` action까지 연결됐다. 실제 viewer process E2E는
별도 fixture smoke에서 publisher/hash 고정 Edge, fixed `--new-window`, process creation time과
새 PID/HWND/class/image identity의 독립 검증 및 새 창 정리까지 통과했다. 기본 종합 명령은
viewer를 자동 실행하지 않아 `VIEWER_PROCESS_E2E_NOT_RUN`을 유지한다.

단위 테스트와 smoke test는 현재 코드의 계약을 검증한다. 실제 사용자 환경의 wake word 정확도, 장기 작업 성공률, UI 변화 복구율 또는 안전성 우월성을 증명하지 않는다. `evaluation/intent_scenarios.json`의 100% 결과도 수작업으로 라벨링된 evidence에 대한 정책 일치도이며 실제 음성 분류기 성능이 아니다.

## 다음 구현 순서

1. 사용자가 화면 앞에 있을 때 Hello `VERIFIED` 성공 경로 확인 및 배포 인증서 서명
2. 사용자 동의 후 실제 마이크 device smoke test와 실제 한국어 corpus 평가
3. 브라우저 등 추가 앱의 제한된 변경 adapter와 선택적 Vision fallback
4. snapshot VM 위험 action·복구 시나리오 실행
5. 실제 참가자 실험 결과 수집

snapshot VM evidence gate는 hypervisor를 제어하거나 host에서 위험 action을 실행하지 않는다.
외부 harness가 생성한 문서만 검증하며, 정확한 manifest binding, UTC freshness, 최대 실행 시간,
복원 성공, 예상 결과, 주입된 signature verifier가 모두 통과해야 결과를 수락한다. 이 구현은
실제 VM 격리나 snapshot 복구 성공을 자체적으로 증명하지 않으므로 외부 harness 연동 완료를
주장하지 않는다. 상세 계약은 `docs/SNAPSHOT_VM_EVIDENCE.md`에 있다.

음성 의존성은 `pip install -e .[voice]`로 분리했다. adapter는 런타임에 모델을 내려받지
않으며 `from_local_model`에 기존 로컬 파일/디렉터리를 넘겨야 한다. 현재 CI는 dependency를
주입한 계약 테스트만 수행했으며 실제 openWakeWord/faster-whisper binary와 한국어 모델의
정확도·지연시간을 검증한 결과가 아니다.

Windows 환경에서는 SciPy 1.18.1의 unsigned `_tools.pyd`가 이 PC의 application-control
정책에 차단되어 voice extra를 검증된 `scipy>=1.16,<1.17`로 제한했다. 또한 openWakeWord
0.6.0이 끌어온 scikit-learn 1.9.1 native module이 같은 정책에 차단돼
`openwakeword>=0.5.1,<0.6`, `scikit-learn>=1.7,<1.8`로 고정했다. SciPy 1.16.3과
scikit-learn 1.7.2에서 openWakeWord import와 ONNX runtime이 성공했다. 공식 openWakeWord v0.5.1 release의
`hey_jarvis_v0.1.onnx`, `melspectrogram.onnx`, `embedding_model.onnx`를 프로젝트 local bundle로
저장하고 manifest SHA-256 검증 후 80 ms 무음 frame inference(score 0.0)를 수행했다. 이 smoke는
실제 발화의 wake 정확도·false activation rate를 증명하지 않는다.

offline corpus 하네스는 모든 WAV의 경로·symlink·SHA-256·mono 16 kHz signed 16-bit PCM·크기·
길이를 먼저 검증한 뒤에만 injected STT를 호출한다. 보고서에는 transcript 원문이나 파일 경로를
남기지 않는다. 실제 음성 수집은 자동으로 수행하지 않았으며, 사용자·참가자 동의와 보관 정책이
준비된 뒤 실행해야 한다. metric 계약은 `docs/VOICE_EVALUATION.md`에 정리했다.

`Systran/faster-whisper-tiny` commit
`d90ca5fe260221311c53c58e660288d3deb8d356`의 CTranslate2 파일 네 개를 local bundle로 저장했다.
manifest가 source revision, 필수 filename, byte size, SHA-256을 고정하고 초기화 직전에 다시
검증한다. 실제 CPU int8 load는 0.365초, 1초 무음 추론은 0.202초였고 빈 transcript를 반환했다.
이는 한국어 발화 정확도나 실제 장치 latency 결과가 아니다.

로컬 TTS는 `SAPI.SpVoice`를 별도 isolated worker에서 plain text로 호출한다. 자동 검증에서는
스피커 대신 allowed-root 아래 WAV로 렌더링했으며 취소 지원 반영 후 172,424바이트 출력의 SHA-256,
identity와 WAV 구조를 parent가 독립 확인했다. 10ms 후 shared token을 set한 실제 취소 smoke에서는
부분 WAV와 고아 worker가 남지 않았다. 실제 한국어 발음 품질과 스피커 출력은 사용자 참여 없이는
검증하지 않았으며 상세 경계는 `docs/TTS.md`에 있다.

2026-09-21 실제 PC에서 `sounddevice` metadata와 `check_input_settings`만 사용하는 read-only
probe를 실행했다. 28개 endpoint 중 입력 장치 16개, 16 kHz mono int16 호환 9개를 확인했고
기본 입력도 호환됐다. 보고서에는 장치 index와 수치 capability만 포함하며 이름·host API·driver
예외 내용은 제거한다. 이 결과는 stream open, audio capture, 잡음·지연·인식 품질 검증이 아니다.

app registry는 로드 시와 실행 직전에 실행 파일 hash를 각각 확인한다. publisher가 설정된
항목은 Authenticode 상태가 `Valid`이고 인증서 subject가 설정값과 정확히 같아야 한다.
`require_publisher=True` 운영 모드에서는 publisher가 없는 항목도 거부한다. 이 검사는 publisher
신원과 파일 무결성을 확인하지만 애플리케이션 자체가 안전하다는 보증은 아니다.

Windows `process.launch`는 `CreateFileW`의 `GENERIC_READ`, `FILE_SHARE_READ`만으로 실행 파일
handle을 열어 final canonical path와 handle stream SHA-256을 확인하고, handle을 닫기 전에
process creation을 호출한다. 표준 write/delete sharing을 막아 검사 직후 파일 교체 창을 줄인다.
lease 획득·검증·해제 실패는 fail-closed이며 launch 호출 뒤 실패는 자동 재시도하지 않는다.
관리자, kernel component, 이미 열린 호환되지 않는 handle까지 방어한다고 주장하지 않는다.

`ui.element.inspect`는 planner가 지정한 PID를 그대로 신뢰하지 않는다. 성공한
`process.launch` 결과를 process inspector로 확인해 session registry에 등록한 PID만 허용하고,
UIA 접근 직전 실행 이미지 경로, hash, Windows process creation time을 다시 검사한다. 구조적
metadata만 결과로 반환하며 UI element name/value는 반환하지 않는다. creation time이 달라진
PID는 같은 실행 파일이어도 기존 session 권한을 잃는다. task 종료 시 session도 `clear()`한다.

`notepad.text.replace`는 planner가 AutomationId나 ControlType을 지정할 수 없고 trusted
`NotepadProfile`만 사용한다. Windows 11 현재 버전의 profile은 exact `Document` control을 쓰며
`notepad` app ID로 승인된 session인지 확인하고 mutation 직전에 runtime ID를 다시 비교한다.
변경 내용은 로그나 execution observation에 남기지 않고 SHA-256만 반환한다. mutation 호출 이후
예외·timeout·hash mismatch는 상태가 불명확하므로 retry-safe가 아니다. 2026-09-22 새 미저장
Notepad process에서 임시 문자열 replace, 즉시 hash, 독립 predicate 재확인이 모두 성공했으며
파일을 저장하지 않고 해당 새 PID만 종료했다. 실제 사용자 문서는 변경하지 않았다.

Windows 11 Notepad는 `System32\notepad.exe` launcher PID에서 versioned WindowsApps runtime으로
handoff한다. registry는 두 image의 path·hash·publisher를 각각 고정한다. resolver는 launch 전
runtime PID snapshot을 잡고 제한 시간 전체에서 후보를 polling한다. 동일한 새 exact runtime
후보 하나가 끝까지 유지될 때만 PID를 반환하며 후보 소멸·교체·복수 후보를 거부한다. 중간
bootstrap process를 즉시 승인하지 않는다. Windows Update로
version/hash가 바뀌면 자동 탐색하지 않고 registry를 명시적으로 재검토해야 한다.

pywinauto `find_elements`에는 timeout 인자가 없으므로 운영 UIA adapter는 고정된
`python -I -m skilla_core.uia_worker` child process에서 strict JSON 요청을 처리한다. parent는 5초
timeout, 200 KiB 요청, 64 KiB 응답, 최소 환경을 적용한다. worker 오류 text와 document 원문은
반환하지 않는다.

`file.delete.trash`는 허용 루트 내부의 일반 파일 하나만 받고 symlink·상대 경로·target
mismatch를 거부한다. 호출 직전에 SHA-256과 canonical path를 다시 검사한다. backend 호출 뒤
예외 또는 파일 잔존은 상태가 불명확하므로 자동 재시도하지 않는다. 프로젝트 내부 일회성
fixture를 Windows 휴지통으로 보내는 실제 smoke test가 성공했으며 영구 삭제는 수행하지 않았다.

감사 로그는 구조적 secret key redaction을 적용하고 메모리 sink는 기본 최대 10,000개 event만
유지한다. JSONL sink는 선택적 `AuditRetentionPolicy`로 파일 크기와 backup 수를 제한하며 회전
뒤 append를 `fsync`한다. audit rotation과 move journal은 별도 `.lock` 파일의 Windows
byte-range lock을 사용해 여러 JAVIS process의 append/load/rotation을 직렬화하며 기본 lock
timeout은 5초다. 데이터 파일과 lock 파일에는 현재 process token의 사용자 SID와 LocalSystem
SID만 full-control ACE로 허용하는 protected DACL을 적용한다. 적용 직후 DACL을 다시 읽어
inheritance 차단, 정확한 SID 집합, ACE type·flags·mask를 검증한다. 소유자와 SACL은 변경하지
않으며 ACL 적용 또는 검증 실패는 fail-closed다.

로컬 승인 창과 Windows Hello native helper를 구현했다. Microsoft 문서상 desktop 앱은
`UserConsentVerifier.RequestVerificationAsync`를 직접 호출하는 대신 활성 application HWND로
`UserConsentVerifierInterop.RequestVerificationForWindowAsync`를 사용해야 한다. helper는
표시되는 자체 WinForms 창의 HWND를 전달하며, 그 전에 `UserConsentVerifier.CheckAvailabilityAsync`
를 확인한다. PIN·생체 정보는 OS UI 밖으로 나오지 않는다.

Python 측 `WindowsHelloHelperVerifier`는 helper의 절대 경로·symlink 여부·SHA-256을 매번
확인하고 random challenge를 stdin JSON으로 전달한다. 요청은 8 KiB, stdout은 4 KiB 상한과
strict schema를 적용하며 같은 challenge의 결과만 받는다. 프로젝트 local .NET SDK 9.0.306으로
`net9.0-windows10.0.22621.0` managed helper를 실제 빌드했다. unsigned single-file apphost는 이
PC의 application-control 정책에 차단되어 사용하지 않는다. 대신 Authenticode `Valid`인 Microsoft
system `dotnet.exe`와 helper DLL·deps·runtimeconfig·WinRT dependency 다섯 파일을 각각 hash로
고정하고, 배포 디렉터리에 미등록 파일이 하나라도 있으면 실행을 거부한다. malformed-input 거부는
실제 hosted helper에서 검증했다. 사용자 참여형 호출은 제한 시간 내 `VERIFIED`를 얻지 못해
`FAILED`로 닫혔다. 따라서 성공 인증 경로와 별도 배포용 Authenticode apphost는 아직 완료로
주장하지 않는다.

## Move journal 보안·복구 한계

이동 journal에는 복구 판정을 위해 원본·목적지의 절대 경로와 SHA-256이 저장되므로
민감한 로컬 상태로 취급해야 한다. POSIX에서는 생성 모드와 `chmod(0600)`을 적용하고,
Windows에서는 journal과 lock 파일에 현재 사용자+LocalSystem protected DACL을 적용해
검증한다. process-local thread lock과 Windows interprocess byte-range lock을 함께 사용한다.
recovery는 파일을 이동하거나 삭제하지 않고, 관찰된 상태에 따라 terminal 레코드만
덧붙인다. 모호한 상태는 `AMBIGUOUS`로 남겨 사용자 확인을 요구한다.

## 2026-10-07 실제 음성 장치 검증

- 고정 한국어 TTS 재생, 사용자 품질 평가 3/5, Windows Hello 실제 인증은 PASS했다. 사용자는 TTS가
  번역기처럼 들려 후속 품질 개선이 필요하다고 평가했다.
- 설치된 SAPI/OneCore 한국어 음성은 Heami 하나뿐임을 확인했다. Kokoro는 한국어 미지원, Piper
  한국어 모델은 비상업 데이터 라이선스로 보류했다. Supertonic 3를 제품 밖에서 CPU 실행해 10화자
  WAV를 생성했고 RTF 0.101~0.123을 확인했지만 자연스러움 증거는 아니므로 기본 TTS를 바꾸지 않았다.
  Heami를 포함한 익명 A~K 청취 세트와 hash manifest를 만들었으며 사용자 평가는 아직 없다.
- 마이크 probe는 28개 endpoint, 입력 장치 16개, 16 kHz mono 호환 장치 9개와 호환 기본 입력을
  확인했다.
- 두 번의 동의 기반 마이크 시험은 실제 frame과 speech energy를 확인했지만, 공식 영어
  `hey_jarvis_v0.1` 모델이 한국어식·영어식 발화를 모두 감지하지 못해 `WAKE_NOT_DETECTED`였다.
- `VoicePipeline`에 원음·문장·장치명을 남기지 않는 frame/speech/max-confidence/wake 상태 진단을
  추가했다. 사용자 검증은 실패를 `AUDIO_NO_FRAMES`, `AUDIO_NO_SPEECH`, `WAKE_NOT_DETECTED`,
  `VOICE_UTTERANCE_INCOMPLETE`로 구분한다.
- 공개 Jarvis 세 구현은 Google STT 결과 문자열 검사 방식이라 현재 로컬 관문보다 개인정보·오프라인·
  오작동 경계가 약했다. 복사하지 않고 한국어 맞춤 ONNX 모델을 FAR/FRR로 평가하기로 했다.
- 전체 회귀는 766 passed, 3 skipped, Ruff clean, mypy strict 123 source files다.
- 후속 wake-word corpus 하네스와 CLI를 추가한 뒤 전체 회귀는 783 passed, 3 skipped,
  Ruff clean, mypy strict 124 source files다. 실제 동의 corpus가 없으므로 FAR/FRR 측정값은 아직 없다.
- `wakeword-forge`와 공개 `okay-hermes` ONNX를 감사했다. 실제 그래프는 가변 시간축
  `float32[batch,time]` 입력이지만 3초 창을 권장하고 현재 openWakeWord와 계약이 달라 직접 교체하지
  않았다. 고정 SHA-256·크기·입출력 검증, 3초 ring buffer, 400 ms hop과 reset을 갖춘 실험용
  `RepCnnWakeWordDetector`를 추가했다. 공개 예제 무음 smoke는 점수 `0.624035120`을 반환했으므로
  0.5 하한만으로 모델을 채택할 수 없고 실제 동의 corpus의 모델별 FAR/FRR 보정이 필요하다.
- 별도 `evaluate-repcnn-wakeword-corpus` CLI도 추가해 모델 경로와 64자리 SHA-256을 명시한 경우에만
  후보 ONNX를 같은 FAR/FRR 하네스로 평가할 수 있다. 제품 기본 모델은 바뀌지 않았다.
- 합성 3초 무음 목표 표시·비호출어 표본 각 1개와 공개 예제 모델로 CLI 전체 경로를 실행했다.
  임계값 0.7에서 inference failure 0, FAR 0.0, FRR 1.0이 나왔으며 두 표본의 최대 점수는
  `0.624035120`이었다. 이는
  연결 검증 결과이고 음성이 없는 양성 표본이므로 성능 자료로 사용하지 않는다.
- 이 단계 구현 뒤 최종 전체 회귀는 상단 최신 재검증처럼 797 passed, 3 skipped다.
- 동의 기반 호출어 자료 수집 핵심부와 `capture-wakeword-corpus` CLI를 추가했다. 매 실행 새
  `동의 <무작위 토큰>`과 표본별 `준비`를 요구하고, 새 절대 출력 폴더만 허용하며, 원음을 쓰기 전
  빈 파일부터 사용자 전용 ACL을 적용한다. WAV/manifest 해시와 동의 기록을 결합하고 중간 실패 시
  이번 실행이 만든 파일만 정리한다. 비대화형 안전 시험은 `CONSENT_NOT_GIVEN`, 마이크 source 0회,
  출력 폴더 0개였으며 실제 녹음은 수행하지 않았다. 최신 전체 회귀는 809 passed, 3 skipped다.
- 호출어 자료 형식 1.1에 거리·소음·비식별 세션 조건을 추가했다. 각 조건 조합에 양성과 비호출어가
  모두 없으면 거부하고, 조건별 FAR/FRR의 confusion count와 실패 수 합계가 전체와 일치해야 한다.
  추론 실패는 조건 보고서에서도 FN/FP로 남는다. 구형 1.0 자료는 미지정 조건으로 호환되며 최신
  전체 회귀는 814 passed, 3 skipped다.
- 별도 보정 corpus의 최대 점수로 0.50~0.99 임계값을 한 번에 비교하는 두 calibration CLI를
  추가했다. FAR 상한을 만족한 후보 중 FRR·FAR·높은 임계값 순으로 선택하고, 후보가 없으면 실패로
  닫힌다. 합성 무음 양성·비호출어 각 1개에서 공식 영어 모델은 모든 후보 FAR 0/FRR 1이라 0.99가
  기계적으로 선택됐지만, 호출어가 없는 양성 표본이므로 품질 근거가 아니다. 최신 전체 회귀는
  824 passed, 3 skipped다.
- 사용자 동의 아래 0.5 m 조용함과 3~5 m 사람 말소리 조건에서 양성·비호출어 각 1개, 총 4개를
  실제 수집했다. WAV 형식·길이·hash·protected ACL·nonzero 신호·clipping 0을 확인했다. 공식 영어
  모델의 임계값 0.5 결과는 TP 0/TN 2/FP 0/FN 2, FAR 0.0/FRR 1.0이었다. 양성 최대 점수는
  `0.396607757`, `0.068618000`으로 허용 임계값 하한 0.5보다 낮았다. 이 결과로 실제 수집 경로는
  검증됐지만 현재 모델은 이번 한국어 pilot 조건에서 실사용 기준을 충족하지 못했으며, 4표본 결과를
  일반적인 성능 결론으로 확대하지 않는다.
- 실제 수집 중 CLI가 계획의 거리·소음·세션 조건을 표시하지 않는 운용 결함을 발견했다. readiness
  화면이 기존 enum을 고정 한국어 문구로 표시하도록 수정했고, 미지정·근거리 조용함·원거리 말소리
  조건과 기존 exact `준비` 계약을 회귀시험으로 고정했다. 최종 전체 회귀는 826 passed,
  3 skipped다.
- 공식 한국어 `vosk-model-small-ko-0.22`를 제품 밖에서 시험했다. 일반 인식·원음 조합은 실제
  4표본 pilot에서 TP 2/TN 2/FP 0/FN 0이었지만, 제한 문법은 비호출어 1개를 오탐했고 음량 증폭은
  원거리 양성 1개를 놓쳤다. 일반 인식만 쓰는 실험 어댑터, 3.2초 확정·0.8초 겹침 창, 전사문
  비노출, 정확한 15파일 manifest 검증과 별도 평가 CLI를 추가했다. 첫 검출 상한은 2,080 ms와
  3,200 ms였다. 4표본은 성능 근거가 아니며 264,364,726바이트의 풀린 모델과 선택 의존성은 기본
  제품·설치본에 넣지 않았다. 전체 회귀는 843 passed, 3 skipped, coverage 83%, Ruff clean,
  mypy strict 128 source files다.
- 최신 wheel SHA-256은 `dd7012317e3667fb6caa9f02eecbbfd3eba9b39f371f393938b1e37562efffe6`,
  one-folder manifest SHA-256은 `ab95beca300eaf90b43a4e940dcbf588d4f16917a28fc47b36a6940efb56c087`,
  Setup SHA-256은 `cb4edd33413732c7f69fc4662c848f22c1fcee7decb2d1caeed65bfd3fd428c5`다.
  기본 배포물의 Vosk 모델/native 파일은 0건이며 서명은 아직 `NotSigned`다.
- 4표본 pilot과 섞이지 않는 보정 세션 16표본·최종시험 세션 16표본 계획을 추가했다. 각 계획은
  근거리/원거리×조용함/사람 말소리 네 조건에 양성·평범한 음성·이름만 말하는 어려운 음성을
  균형 배치하며, 서로 다른 새 동의와 새 출력 폴더가 필요하다. 아직 녹음은 시작하지 않았다.
# 2026-10-20 졸업논문 초안 작성

- `output/JAVIS_스킬기반_Windows_PC에이전트_졸업논문_초안.docx`를 작성하였다.
- 개발 단계 32블록과 별도 확인 실험 15블록을 합치지 않고 구분해 보고하였다.
- 확인 실험의 성공률, 실행 시간, 호출 수, 토큰 수, McNemar 검정과 Holm 보정 결과를 반영하였다.
- Microsoft Word로 PDF를 내보낸 뒤 16쪽을 PNG로 렌더링하여 표·문단·페이지 번호의 잘림과 겹침을 확인하였다.
- 발표 자료는 이 논문 초안과 같은 수치·한계 표현으로 개정할 예정이다.
- `output/JAVIS_스킬_관련논문_방법론과_적용범위.docx`에 ReAct, Toolformer, Reflexion, Voyager, UFO, OSWorld, AgentBench의 원 방법과 JAVIS 반영 범위·비반영 범위를 8쪽으로 정리하였다.

# 2026-10-20 졸업발표 자료 확인 실험 반영

- 기존 13장 발표본의 구조와 디자인을 유지한 새 파일 `output/JARVIS_스킬기반_PC에이전트_졸업발표_확인실험반영_최종본_v3.pptx`를 작성하였다.
- 구현 상태를 전체 1,096개 시험 중 1,091개 통과·5개 제외, 엄격 자료형 검사 151개 파일 통과로 갱신하였다.
- 실험 설계를 확인 실험 15개 짝 비교 묶음·60개 관측값으로 고치고, SK0 66.67%, SK1 80.00%, SK2 80.00%, SK3 93.33%의 성공률을 반영하였다.
- SK3와 SK0 비교에서 성공률 +26.67%p, 평균 실행 시간 34.16%, 대형 언어 모델 호출 15.15%, 토큰 16.59% 감소를 표시하였다. Holm 보정 p=0.375로 유의하지 않았다는 한계를 함께 적었다.
- 관련 연구 슬라이드를 ReAct, Toolformer, Reflexion, Voyager의 원 방법과 JAVIS 적용 원리로 교체하고 원문 링크를 발표자 노트에 기록하였다.
- 11쪽 성공률 차트를 PowerPoint에서 편집 가능한 기본 차트로 다시 만들었다. 13장 전체 패키지·레이아웃·글꼴·차트 검증을 통과했고, 모든 슬라이드를 렌더링하여 시각적으로 확인하였다.

# 2026-10-20 논문 제출본과 A1 연구 포스터

- 한국어 논문 제출용 파일 `output/JAVIS_스킬기반_Windows_PC에이전트_졸업논문_제출본.docx`를 생성하였다. 기존 초안의 연구 수치와 한계는 유지하고 표지의 초안 표기를 제거하였다.
- Microsoft Word로 16쪽을 PDF와 PNG로 렌더링하여 전 페이지의 한글 글꼴, 표, 문단, 페이지 번호를 확인하였다. 잘림과 겹침은 발견되지 않았다.
- 제공된 CUBERAG A1 세로형 포스터 두 종의 제목 영역, 번호가 붙은 절 구성, 두 열 배치, 결과표와 참고문헌 구성을 참고하여 `output/JAVIS_스킬기반_Windows_PC에이전트_졸업작품_포스터_최종본_v2.pptx`를 작성하였다.
- 포스터에는 연구 목적, 프로그램 구조, 스킬 계약, 네 실험 조건, 구현 검증 상태, 성공률 차트, 시간·호출·토큰 변화, 작업별 결과, 통계적 한계와 다음 단계를 한 장에 정리하였다.
- PPTX 패키지·레이아웃·글꼴·편집 가능한 기본 차트 검증을 통과하였다. PowerPoint에서 A1 PDF로 직접 내보낸 뒤 다시 PNG로 렌더링하여 제목과 지표 상자의 줄바꿈까지 수정하였다.
