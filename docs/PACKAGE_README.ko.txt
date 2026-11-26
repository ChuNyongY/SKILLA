SKILLA-PC 0.2.28 로컬 Windows 패키지

이 프로그램은 현재 사용자 권한으로 실행합니다. NIM 키는 패키지에 들어 있지 않으며 Windows
자격 증명 관리자에 따로 저장합니다.

개인정보와 원격 모델 안내

- 스킬 저장·실행, Windows 조작, STT와 TTS는 사용자 PC에서 처리합니다.
- 시스템 정보 명령, 중단 명령과 등록된 고정 대화 응답을 제외한 음성 인식 문자열은
  의도 판정과 계획 생성을 위해 NVIDIA NIM 원격 API로 전송될 수 있습니다. 음성 녹음 파일 자체는
  보내지 않습니다.
- 여러 단계 작업의 후속 계획에는 앞 단계의 검증 관측값이 전송될 수 있습니다. 이때 capability별
  허용 필드만 남기고 파일명·경로·컴퓨터 이름·PID·해시는 제거합니다. 파일 대상은 해당 작업에서만
  유효한 무작위 표식으로 바꾸고 실행 직전에 로컬에서 다시 확인합니다.
- 사용자가 최초 요청문에 직접 말하거나 입력한 파일명·경로는 요청 원문에 포함될 수 있습니다. 파일
  본문은 보내지 않습니다.
- 시험용 NIM API에는 비밀번호, API 키, 주민등록번호, 건강·금융·가족 정보 등 개인·기밀·민감정보를
  입력하지 마십시오. 시험용 API는 개발·평가용이며 공개 배포용 상용 서비스가 아닙니다.
- 현재 패키지는 사용자 발화를 장기 대화 기억으로 자동 저장하지 않습니다.

처음 한 번 준비

1. 시작 메뉴의 `SKILLA-PC`를 실행합니다.
2. NIM 키가 없으면 `SKILLA 초기 설정` 창이 열립니다. 마스킹된 입력칸에 키를 넣고
   `저장하고 계속`을 누릅니다. 키는 Windows 자격 증명 관리자에 저장되고 다시 읽히는지 확인된
   뒤에만 프로그램이 시작됩니다.
3. 명령줄에서 직접 등록하려면 PowerShell에서 설치 폴더로 이동해 다음 명령을 실행할 수도 있습니다.
   .\SKILLA.exe provision-nim-credential
4. 실행 환경을 점검합니다.
   .\SKILLA.exe preflight-product-host-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path
5. 마이크를 열지 않고 전체 서비스를 조립해 확인합니다.
   .\SKILLA.exe check-product-service-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path

시작 오류 안내

- 더블클릭 시작 전에 API 키, 제품 구성과 필수 구성 요소를 확인합니다.
- 문제가 있으면 예외 내용, 파일 경로, API 키를 표시하지 않고 고정된 한국어 안내만 표시합니다.
- API 키가 없으면 초기 설정 창이 열립니다. 저장에 실패하면 키 형식과 Windows 자격 증명 관리자
  상태를 확인하거나 위의 명령줄 등록 절차를 이용합니다.
- 구성 파일 또는 필수 구성 요소 안내가 나오면 Setup으로 다시 설치한 뒤 위의 사전점검 명령을
  실행합니다.

음성으로 사용하기

- 시작 메뉴의 SKILLA-PC 또는 배포본의 SKILLA-Tray.exe를 실행하면 음성 대기가 시작됩니다.
- “스킬라, 시스템 정보 확인해 줘”라고 말하면 인식한 문장과 작업 결과가 화면에 표시됩니다.
- 작업을 멈추려면 “스킬라, 멈춰”라고 말하거나 작업 중지를 누릅니다.
- 자기소개·인사·기능 안내는 로컬에서 화면과 음성으로 응답합니다.
- 같은 Whisper 모델로 GPU 인식을 우선 준비합니다. Windows 사용자 폴더의
  %LOCALAPPDATA%\SKILLA\voice-runtime 또는 실행 환경의 NVIDIA CUDA 라이브러리를 사용합니다.
  GPU 초기화나 실행이 실패하면 CPU로 재시도합니다.

스킬 관리

- 스킬 메뉴에서 저장된 스킬의 상태와 버전, 개정 후보, 상황 스킬, 예약 스킬을 확인할 수 있습니다.
- 개정 후보에서는 성공한 작업 기록으로 만든 후보를 확인하고, NIM 초안 생성 후 사람이
  승인하거나 폐기할 수 있습니다.
- 두 화면을 여는 데 실패해도 내부 예외나 경로를 표시하지 않고 고정된 한국어 안내만 표시합니다.

작업 화면 선택

0. 메인 화면의 설정 메뉴에서 작업 화면 선택을 열 수 있습니다.
1. 연결된 화면과 현재 선택을 확인합니다.
   .\SKILLA.exe list-displays (Get-Location).Path
2. 주 모니터, 현재 전면 창 또는 정확한 장치 이름을 선택합니다.
   .\SKILLA.exe select-display (Get-Location).Path primary
   .\SKILLA.exe select-display (Get-Location).Path follow_foreground
   .\SKILLA.exe select-display (Get-Location).Path '\\.\DISPLAY1'

상태 백업과 복원

- SKILLA를 종료한 뒤 스킬, 실행 기록, 상황 규칙, 예약 규칙 DB를 새 폴더에 백업합니다.
  $backup = Join-Path (Get-Location) "SKILLA-state-backup-20261117"
  .\SKILLA.exe backup-product-state (Get-Location).Path $backup
- 파일을 바꾸지 않고 백업의 목록, 해시와 SQLite 무결성을 확인합니다.
  .\SKILLA.exe verify-product-state-backup $backup
- 복원은 SKILLA를 종료한 상태에서 정확한 확인 문구를 입력한 경우에만 실행됩니다. 복원 직전 DB는
  state\restore-rollbacks 아래에 별도로 남습니다.
  .\SKILLA.exe restore-product-state-backup (Get-Location).Path $backup --confirm RESTORE_SKILLA_STATE

음성 트레이 모드

- 마이크 사용에 동의한 경우에만 다음 명령을 직접 실행합니다.
  .\SKILLA-Tray.exe run-product-tray-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path
- 메인 화면 중앙 계기판의 링과 MIC 퍼센트가 마이크 입력 크기에 따라 바뀝니다.
- 말을 마친 뒤 약 0.8초 동안 소리가 없으면 한 문장으로 인식합니다.

자동 시작은 기본 해제입니다. 명시적으로 원할 때만 install-autostart-credential을 실행하십시오.
삭제할 때는 `remove-start-menu`, remove-autostart-credential과 remove-nim-credential을 먼저
실행한 뒤 설치 폴더를 제거합니다. 사용자 상태는 자동으로 삭제하지 않습니다. 이 패키지는 아직
Authenticode 서명되지 않았으므로 Windows 경고가 표시될 수 있습니다.

음성 모델 라이선스

- SKILLA가 음성 출력에 사용하는 Supertonic 3 모델은 OpenRAIL-M 조건으로 배포됩니다.
- 이 라이선스는 불법 사용, 미성년자 위해, 동의 없는 사칭, 차별, 의료 조언 등 Attachment A에
  열거된 용도를 제한합니다. 정확한 전체 조건이 요약보다 우선합니다.
- 설치 후 인터넷 연결 없이도 `models\supertonic3\LICENSE.MODEL-OpenRAIL-M.txt`에서 전체 조건을,
  `models\supertonic3\THIRD_PARTY_NOTICE.SKILLA.txt`에서 모델 출처와 MIT 고지의 구분을 확인할 수
  있습니다.
