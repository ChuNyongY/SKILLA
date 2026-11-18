# SKILLA 원격 재계획 관측값 최소화 규격

상태: source 구현·자동검사 완료, 설치 패키지 미재빌드

작성일: 2026-11-18

## 목적

여러 단계 작업에서 로컬 실행 결과를 다음 NIM 계획 요청에 넣을 때, 기능별로 원격 전송을 허용할
필드를 고정한다. `execution.observed` 전체를 복사하지 않고, 등록된 capability와 허용 필드가
정확히 일치할 때만 최소 자료를 만든다.

2026-11-18 현재 `TaskLocalObservationProjector`와 `BoundedObservationAgent` 사이에 이 경계를
구현했다. 다음 설치 패키지를 만들기 전 source 기준이며 기존 0.2.11 Setup에는 포함되지 않는다.

이 규격은 현재 Windows 제품 구성에서 실제 연결되는 15개 capability를 대상으로 한다. 기본
`CapabilityRegistry`에 이름만 존재하고 제품 실행기와 검증기가 연결되지 않은 기능은 포함하지 않는다.

## 공통 원칙

1. 허용표에 없는 필드는 원격 payload에서 제거한다.
2. 새 필드가 실행기에 추가돼도 허용표를 따로 갱신하기 전에는 원격으로 보내지 않는다.
3. 절대경로, 상대경로, 파일명, 컴퓨터 이름, PID, HWND, UI runtime ID는 로컬 전용이다.
4. SHA-256도 필요가 없으면 보내지 않는다. 해시는 평문이 아니지만 동일 대상을 연결하는 식별자가 된다.
5. 원격 모델이 로컬 대상을 다시 지정해야 하면 경로 대신 한 작업 안에서만 유효한 opaque handle을 쓴다.
6. opaque handle은 실행기에서 실제 대상에 연결하며 NIM이 새 handle을 만들거나 내용을 해석할 수 없다.
7. 허용 필드의 값도 자료형, 길이, 열거형 범위를 다시 검사한다.
8. projection 실패 시 원본 관측값을 대신 전송하지 않고 후속 재계획을 중단한다.

## 현재 제품 기능별 허용표

| capability | 원격 전송 허용 | 로컬에만 유지 | 필요 시 대체 표현 |
|---|---|---|---|
| `system.info.read` | `system`, `release`, `version`, `machine` | `hostname` | 없음 |
| `process.launch` | `app_id` | `pid`, `hwnd` | `launched=true` |
| `explorer.folder.open` | `root_id` | `pid`, `hwnd`, process creation time, directory hash | `opened=true` |
| `settings.open` | `app_id`, `page_id` | `pid`, page profile hash | `opened=true` |
| `audio.volume.read` | `volume_percent` | 없음 | 없음 |
| `audio.volume.set` | `volume_percent` | 없음 | `matched=true` |
| `file.list` | `count`, `truncated`, `root_index` | `entries`, `relative_path` | `entry_handles`와 확장자·파일/폴더 종류 |
| `storage.status.read` | free-percent bucket, `low_disk`, `mutation_count`, `root_id` | 실제 byte 수치와 실제 경로 | 없음 |
| `cleanup.suggest` | 위 storage 필드와 `suggestion_code` | 실제 byte 수치와 실제 경로 | 없음 |
| `file.move` | 성공 여부 | `source`, `destination`, transaction ID, source hash | 로컬 source·destination handle |
| `file.delete.trash` | 성공 여부 | `path`, source hash | 로컬 target handle |
| `browser.navigate` | `app_id`, `host`, `scheme` | `pid`, `hwnd`, process creation time, URL hash | `opened=true` |
| `browser.search.web` | `search_engine` | query hash, 브라우저 process 정보 | `opened=true` |
| `media.youtube.play.recent` | `selection_mode`, `lookback_days` | selection hash와 브라우저 process 정보 | `opened=true` |
| `memory.search` | `match_count` | results digest, memory ID, 저장 값 | task-local memory handle |

`성공 여부`는 `VerifiedActionObservation`이 성공한 실행만 담는 현재 구조에서는 필드로 중복될 수 있다.
원격 문맥에서 명시가 필요할 때만 `verified=true`처럼 고정된 값으로 표현한다.

## 파일 목록을 사용하는 작업

과제 자료 정리처럼 다음 계획이 파일별 대상을 알아야 하는 작업은 단순히 `entries`를 제거하면 진행할
수 없다. 기본 비공개 방식은 다음과 같다.

```text
로컬 file.list
→ 각 항목에 task-local handle 부여
→ 로컬에서 확장자·파일/폴더 여부만 추출
→ NIM에는 handle과 최소 속성만 전달
→ NIM은 handle별 분류 계획 제안
→ 로컬 실행기가 handle을 실제 경로로 복원
→ 실행 직전 동일 파일인지 다시 확인
```

파일명 자체가 과목 판단에 꼭 필요하면 두 가지 중 하나를 선택해야 한다.

- 로컬 분류 규칙 또는 로컬 모델이 파일명을 처리
- 해당 작업 한 번에 한해 전송할 파일명 목록을 사용자에게 보여 주고 명시적으로 승인

기본값은 로컬 처리다. 전체 경로는 파일명 전송을 승인한 경우에도 보내지 않는다.

## opaque handle 요구 조건

- 작업별 128비트 이상의 무작위 값
- 다른 작업과 재사용 금지
- 메모리에만 보관하고 작업 종료·취소 시 즉시 삭제
- handle에 경로, 순번, 파일 hash를 인코딩하지 않음
- 실행 시 현재 파일의 identity와 최초 binding을 재검증
- 존재하지 않거나 만료된 handle은 작업 중단
- 현재 handle 원문은 원격 재계획 문맥에 들어가지만 실행 기록에는 실제 경로로 복원된 계획이 남는다.
  별도 handle 감사 로그는 만들지 않는다.

## 실패 처리

다음 경우에는 NIM 후속 요청을 만들지 않는다.

- capability가 허용표에 없음
- observed에 예상하지 않은 key가 있음
- 허용 값의 자료형이나 범위가 다름
- opaque handle binding이 없거나 만료됨
- payload 직렬화 뒤 절대경로·이메일·URL·제어문자 검사 실패
- 사용자가 파일명 전송 확인을 거절함

## 구현된 검증

1. 제품에 연결된 15개 capability의 허용 결과를 각각 고정 fixture로 검사
2. 시스템 이름, 경로, 파일명, PID, HWND, URL·선택 hash가 projection 결과에서 빠지는지 검사
3. 알 수 없는 observed key와 미등록 capability를 fail-closed로 거부
4. 파일 목록을 무작위 handle·파일/폴더 종류·안전한 확장자로 변환
5. `file.move`와 `file.delete.trash` 실행 전에 handle을 실제 경로로 복원하고 identity 재검사
6. 관측 뒤 파일 내용·크기·수정 시각이 바뀌면 실행 차단
7. `BoundedObservationAgent`의 다음 planner context에 원본 경로·파일명이 없는지 통합 검사
8. `TypedPlanner`가 최종 JSON 직전에 15개 projected schema와 경로·UNC·URL·이메일 패턴을 재검사
9. 최초 사용자 요청문의 경로와 projected observation 영역을 구분하는 회귀검사

## 남은 작업

1. 파일명이 필요한 과목 분류를 위한 로컬 규칙 또는 로컬 모델
2. 한 작업에 한해 파일명 전송을 선택할 수 있는 확인 화면
3. 깨끗한 Windows 사용자 경로에서 새 설치본 재검증

현재 기본값에서는 파일명을 원격으로 보내지 않으므로 파일 종류·확장자만으로 결정할 수 없는 과목별
분류는 자동 추측하지 않는다. 이 경우 로컬 분류 기능 또는 사용자 확인이 추가되기 전까지 중단하는 것이
의도된 안전 동작이다.
