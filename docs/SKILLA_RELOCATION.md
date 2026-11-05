# 이름과 위치 변경 안내

## 현재 실행 방법

프로젝트 폴더의 `SKILLA-실행.cmd`를 실행한다. 이 파일은 자기 위치를 기준으로
`src/skilla_core`, 설정 파일, Python 실행 파일을 찾는다

- 제품명: SKILLA
- 내부 패키지: `skilla_core`
- 설치되는 명령: `skilla`
- 설치본 데이터: `%LOCALAPPDATA%/SKILLA/state/v1`
- API 키 보관 이름: `SKILLA/NVIDIA-NIM`
- 소스 실행 데이터: 프로젝트 안의 `state` 폴더

기존 설치본의 `JAVIS-PC/state/v1` 또는 과거 버전 폴더에서 스킬 데이터베이스와
표시 화면 설정 등을 복사한다. 기존 파일은 지우지 않고 새 위치의 파일을 우선한다
API 키도 기존 Windows 자격 증명에서 읽어 새 이름으로 저장한 다음 읽어 확인한다
프로젝트 소스의 `state` 폴더는 이름을 바꿀 때 함께 옮겨야 한다

## 프로젝트 폴더 이름을 바꿀 때

1. SKILLA를 종료
2. 프로젝트 전체 폴더를 새 이름으로 변경 — `src`, `.venv`, `config`, `models`, `state` 포함
3. 새 위치의 `SKILLA-실행.cmd`로 실행
4. 바탕화면·시작 메뉴·자동 시작 바로가기는 새 위치를 가리키도록 다시 등록

현재 개발 폴더를 Codex가 열고 있으면 Windows가 폴더 이동을 거부한다. 이 경우
Codex와 SKILLA를 모두 종료한 뒤 바탕화면의 `SKILLA-프로젝트폴더변경.ps1`을 실행한다.
스크립트는 `JAVIS` 폴더를 `SKILLA`로 바꾸며, 대상 폴더가 이미 있거나 프로젝트 안의
프로그램이 실행 중이면 덮어쓰지 않고 중단한다.

Windows 가상환경 안의 `skilla.exe` 같은 설치 명령에는 설치 당시 Python의 절대 경로가
들어갈 수 있다. 폴더 변경 뒤에는 위 실행 파일을 사용하거나 새 위치에서 가상환경을
다시 설치한다. 외부 바로가기는 폴더 이름 변경을 스스로 추적하지 않는다

검증: `tests/test_source_relocation.py`에서 다른 이름의 한글·공백 포함 폴더로 소스를
복사하고, 무관한 작업 폴더에서 설정 파일과 격리 보조 프로세스 로딩을 확인했다
또한 2026-11-05에 완성된 `dist/SKILLA-PC-0.1.9-release-r9` 배포본을
프로젝트 바깥의 `C:\Users\YongE\Desktop\SKILLA-RELOCATION-TEST-20261105`로
복사하여 실제 실행했다. 실행 프로세스의 경로와 창 제목에는 이전 명칭이 없었고,
`SKILLA.exe verify-package <새 위치>`에서 1,868개 파일의 무결성 검사가 통과했다.
같은 새 위치에서 Doctor 검사는 Windows, Python, SQLite, 앱 목록, 승인 도우미,
Whisper large-v3-turbo, Supertonic 3, 마이크·오디오 관련 의존성을 모두 통과했다.
개발용 .NET SDK는 배포본에 포함하지 않아 경고로 표시되지만 제품 실행 조건은 아니다.

소스 위치 변경 시험은 `tests/test_source_relocation.py`가 담당한다. 2026-11-05에
상태 UI, 음성 파이프라인, 제품 조립, 스킬 재사용·후보 검토 시험을 통과했으며,
마지막 UI 변경 뒤 전체 자동시험을 다시 실행해 종료 코드 0을 확인했다.

## GitHub 저장소 이름을 바꿀 때

앱 실행은 GitHub 저장소 이름이나 원격 URL을 조회하지 않는다. 저장소 이름을 바꿔도
받아 둔 소스의 상대 경로 구조가 같으면 위 실행 구조는 유지된다

GitHub에서 실제 이름을 바꾼 다음에는 로컬 Git의 원격 주소를 새 주소로 갱신하고
`git remote -v`로 확인한다. 저장소 이름 변경과 PC 폴더 이름 변경은 별개다
현재 원격 저장소는 `https://github.com/ChuNyongY/JARVIS.git`이며 이 작업에서는
변경하지 않았다. GitHub에서 저장소 이름을 먼저 `SKILLA`로 변경한 다음 아래 명령으로
로컬 원격 주소를 갱신한다.

```powershell
git remote set-url origin https://github.com/ChuNyongY/SKILLA.git
git remote -v
```

원격 저장소가 실제로 바뀌기 전에 위 주소를 먼저 적용하면 `git fetch`와 `git push`가
실패할 수 있다.

## 보존한 과거 명칭

기존 발표 자료, 실험 결과 식별자와 과거 배포본은 당시 결과를 추적하기 위한 기록이다.
현재 제품의 UI, 실행 파일, Python 패키지, 명령, 데이터 저장 위치에는 사용하지 않는다.
핵심 소스에서 이전 명칭이 남은 곳은 다음 두 개의 읽기 전용 이전 경로뿐이다.

- `JAVIS-PC/NVIDIA-NIM`: 기존 Windows 자격 증명을 새 SKILLA 이름으로 옮길 때만 읽음
- `JAVIS-PC/state`: 기존 스킬과 설정을 새 SKILLA 데이터 폴더로 옮길 때만 읽음

이 두 문자열을 바로 삭제하면 기존 사용자의 API 키와 저장 스킬을 찾지 못하므로,
이전 완료 후 제거할 호환 입력으로 의도적으로 보존한다.
