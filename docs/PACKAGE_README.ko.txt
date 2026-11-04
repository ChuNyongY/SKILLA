SKILLA-PC 0.1.9 로컬 Windows 패키지

이 프로그램은 현재 사용자 권한으로 실행합니다. NIM 키는 패키지에 들어 있지 않으며 Windows
자격 증명 관리자에 따로 저장합니다.

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

텍스트 명령으로 실행

- Setup으로 설치하면 현재 사용자의 시작 메뉴에 `SKILLA-PC` 바로가기가 생성됩니다.
- 키를 저장한 뒤 시작 메뉴의 `SKILLA-PC`, SKILLA-Tray.exe 또는 SKILLA.exe를 실행하면 텍스트 명령
  창이 열립니다.
- 이 실행 방식은 마이크를 열지 않습니다.
- 같은 기능을 명령으로 실행할 수도 있습니다.
  .\SKILLA.exe run-product-console-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path

스킬 관리

- 기본 텍스트 창의 `스킬 관리`에서 저장된 스킬의 상태와 버전을 확인할 수 있습니다.
- `스킬 후보 검토`에서는 성공한 작업 기록으로 만든 후보를 확인하고, NIM 초안 생성 후 사람이
  승인하거나 폐기할 수 있습니다.
- 두 화면을 여는 데 실패해도 내부 예외나 경로를 표시하지 않고 고정된 한국어 안내만 표시합니다.

작업 화면 선택

0. 텍스트 명령 창의 `작업 화면 선택` 버튼을 누르면 명령줄 없이 선택할 수 있습니다.
1. 연결된 화면과 현재 선택을 확인합니다.
   .\SKILLA.exe list-displays (Get-Location).Path
2. 주 모니터, 현재 전면 창 또는 정확한 장치 이름을 선택합니다.
   .\SKILLA.exe select-display (Get-Location).Path primary
   .\SKILLA.exe select-display (Get-Location).Path follow_foreground
   .\SKILLA.exe select-display (Get-Location).Path '\\.\DISPLAY1'

음성 트레이 모드

- 마이크 사용에 동의한 경우에만 다음 명령을 직접 실행합니다.
  .\SKILLA-Tray.exe run-product-tray-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path

자동 시작은 기본 해제입니다. 명시적으로 원할 때만 install-autostart-credential을 실행하십시오.
삭제할 때는 `remove-start-menu`, remove-autostart-credential과 remove-nim-credential을 먼저
실행한 뒤 설치 폴더를 제거합니다. 사용자 상태는 자동으로 삭제하지 않습니다. 이 패키지는 아직
Authenticode 서명되지 않았으므로 Windows 경고가 표시될 수 있습니다.
