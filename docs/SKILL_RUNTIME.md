# JAVIS 스킬 런타임: 생성·검색·사용·갱신 구조

## 프로젝트의 중심

JAVIS의 중심은 단순히 음성 명령을 도구 호출로 바꾸는 것이 아니다. 사용자가 반복하는 PC 작업을
**스킬**로 축적하고, 새 요청에서 관련 스킬을 찾아 사용하며, 실제 결과를 기록해 다음 버전을
갱신하는 Windows 에이전트다.

```text
음성/텍스트 요청
  -> Intent Gate
  -> 검증된 스킬 검색
  -> 선택된 스킬의 절차·허용 capability를 Planner에 제공
  -> typed Plan
  -> Policy / 정확한 승인 / Executor / OS Verifier
  -> 결과 기록
  -> 실패·성공 근거를 가진 새 스킬 초안 또는 개정 초안
  -> 사용자 승인 후 다음 버전 활성화
```

스킬은 실행 파일, 임의 Python 코드, PowerShell 명령을 저장하지 않는다. 스킬은 **절차와 기존
capability의 허용 목록**만 가진다. 실제 실행 권한은 기존 Capability Registry, Policy Engine,
Approval Token, Verifier가 계속 통제한다.

## 네 가지 동작

1. **생성**: 사용자가 새 반복 업무를 설명하거나 성공한 작업을 저장하고 싶다고 요청하면
   `SkillProposal`을 DRAFT로 만든다. 아직 실행에 쓰이지 않는다.
2. **검색**: 새 요청에서 로컬 카탈로그는 VERIFIED 상태의 스킬만 제목·설명·호출 문구로 검색한다.
   완전히 일치하는 호출 문구는 느슨한 단어 중복보다 우선한다. 최상위 점수가 같아 모호하거나 관련
   스킬이 없으면 동일한 Planner가 일반 계획을 만들며, 이 실행은 SK0 조건으로 측정할 수 있다.
3. **사용**: `SkillAwarePlanner`는 가장 관련 있는 검증 스킬 하나를 Planner에 제공한다. Planner가
   스킬의 허용 capability 밖의 행동을 제안하면 Plan은 거부된다.
4. **갱신**: 실행 결과와 시간·모델 호출·토큰·사용자 개입은 `SkillUseRecord`로 버전과 함께 저장한다. 절차 변경은 기존 스킬을 덮어쓰지
   않고 새 DRAFT revision을 만든다. 사용자가 승인할 때만 새 버전이 VERIFIED가 되고 이전 버전은
   RETIRED가 된다.

스킬은 절차 외에도 매번 다시 읽을 `dynamic_inputs`, 분류·예외 처리를 설명하는 `decision_rules`,
실제 완료를 판정하는 `verification_rules`를 가진다. `assess_revision()`은 최소 관측 수, 성공률과 반복
실패 code로 개정 후보 필요성만 판정한다. 이 판정은 새 버전을 자동 생성하거나 승인하지 않는다.

## 현재 환경과 맞지 않는 스킬 감지

검증된 스킬의 실행 기록에는 선택적으로 **모델 구성 지문**과 **도구 표면 지문**을 남긴다. 도구 표면
(tool surface)은 그 실행에서 사용할 수 있었던 capability 목록과 계약의 묶음을 뜻한다. 두 지문은
정규화한 구성의 SHA-256이며, 원문 설정이나 사용자 파일 내용을 저장하지 않는다.

`assess_staleness()`는 정확히 같은 `skill_id`와 버전의 최근 N회(기본 3회)만 비교한다.

- 기록이 부족하거나 기존 기록에 환경 지문이 없으면 `INSUFFICIENT_EVIDENCE`다.
- 같은 실패 코드가 최근 기록에서 두 번 이상 반복되면 `RECENT_REPEATED_FAILURE`다.
- 도구 표면 또는 모델 구성이 달라졌으면 각각 `TOOL_SURFACE_CHANGED`,
  `MODEL_CONFIGURATION_CHANGED`로 `REVIEW_REQUIRED`를 반환한다.
- 최근 실행이 모두 현재 환경과 일치하면 `CURRENT`다.

날짜가 오래됐다는 이유만으로 스킬을 낡았다고 판정하지 않는다. 판정은 재검증이 필요하다는 신호일
뿐이며, 스킬 상태를 바꾸거나 자동 폐기·자동 개정·자동 승인하지 않는다. CLI에서는
`skill-record-use`의 `--model-configuration-sha256`, `--tool-surface-sha256`로 근거를 기록하고
`skill-assess-staleness`로 판정한다. 이 근거는 연구에서 스킬 자체의 효과와 모델·도구 환경 변화의
영향을 분리하는 데 사용한다.

상시 실행 제품에서는 `SkillAwarePlanner`가 선택한 정확한 `skill_id`와 버전을 LLM이 작성하는 Plan
필드에 넣지 않고, 크기가 제한된 내부 결합표에 Plan의 `task_id`와 함께 보관한다. 관찰 후속 계획은
별도 사용으로 등록하지 않는다. 실행 종료 시 `CatalogSkillUseRecorder`가 결합을 한 번만 소비해
성공·실패·중단, 요청부터 완료까지의 시간, 모델 구성 지문과 정렬된 capability 계약 지문을
`SkillUseRecord`에 저장한다. `TypedPlanner`가 제공하는 누적 NIM 계측값은 계획 직전·직후의 차이로
계산해 호출 수와 입·출력 토큰을 같은 결합에 넣는다. 관련 스킬이 없거나 검색이 모호하면 행을 만들지
않는다.

기록기의 오류는 `skill_use_recorded=false`라는 개인정보 없는 상태로만 표시되고 이미 끝난 Windows
작업 결과는 유지된다. 결합이 없으면 `null`이며, 같은 작업을 두 번 기록할 수 없다. 자동 기록은
스킬을 승인·개정·폐기하지 않는다. 계획 호출은 직렬화하여 다른 요청의 누적값이 섞이지 않게 한다.
계측 미지원·counter 역행·NIM usage 누락은 `planner_usage_complete=false`로 남기고 누락 응답 수도
별도 저장한다. 따라서 0-token이 실제 0인지 미측정인지 구별할 수 있다. 이 값은 스킬 사용에 직접
관련된 계획기 호출만 포함하며, 모든 조건에 공통인 의도 분류기 호출은 포함하지 않는다.

## 검색 정확도 평가

`retrieve()`는 VERIFIED 스킬만 대상으로 호출 문구 완전 일치, 제목 일치, 단어 중복 순으로 점수를
계산한다. 정렬은 점수·스킬 키·버전·식별자 순으로 고정되어 같은 카탈로그와 요청에는 같은 결과가
나온다. 최상위 점수가 같은 스킬이 둘 이상이면 `AMBIGUOUS`로 판정하고 `SkillAwarePlanner`는 어느
스킬도 적용하지 않은 기본 계획으로 돌아간다. 수정 시각이 최신이라는 이유로 임의 선택하지 않는다.
느슨한 단어 점수에서는 한 글자 토큰을 제외한다. 한국어 조사는 제거한 어간이 해당 스킬의 제목·설명·
호출 문구에 등록된 완전한 어휘와 정확히 일치할 때만 인정한다. 따라서 조사 변형은 처리하면서 임의의
짧은 부분 문자열로 검색 범위를 넓히지 않는다.

`file.open` 계획은 경로만 target으로 쓰지 않는다. 제공된 소문자 SHA-256과 정확히 같은
`file-sha256:<sha256>` target identity를 typed plan 경계에서 요구한다. 실행기와 NIM 안내문이 동일한
결합을 사용하므로 잘못된 대상은 창을 열기 전에 거부된다.

`evaluate-skill-search`는 `case_id`, 요청문, 기대 스킬 키 또는 `null`로 구성한 엄격한 JSON을 읽어
운영 코드와 같은 `retrieve()`를 실행한다. 전체 정확도와 함께 거짓 양성(false positive: 없어야 할
스킬을 선택), 거짓 음성(false negative: 있어야 할 스킬을 찾지 못함), 잘못된 스킬 선택, 모호 판정을
각각 보고한다. 중복 JSON 키, 알 수 없는 필드, 중복 case ID와 빈 자료는 거부하며 평가 중 카탈로그
상태를 바꾸거나 NIM을 호출하지 않는다.

`tools/run_skill_search_pilot.py`는 비어 있는 절대경로 출력 폴더에서만 실행된다. 고정된 개발자 라벨
22건과 별도의 VERIFIED 스킬 7개로 운영 검색기를 평가하고, 기존 파일은 덮어쓰지 않는다. 2026-10-14
최초 실행은 정답 18, 거짓 양성 0, 거짓 음성 1, 잘못 선택 0, 모호 판정 3이었다. 조사 처리 개선 후
같은 자료는 19/22를 맞혔다. 개선 전에 고정한 별도 보류자료는 14/25에서 21/25로 바뀌었으며 거짓
양성은 전후 모두 0건이었다. cases·report·SQLite의 SHA-256은 각 출력 manifest에 저장됐다. 자세한
변경 전·후 결과와 해석 한계는 `docs/SKILL_SEARCH_PILOT.md`에 있다.

## 예시: “회의 자료 PDF 열어 줘”

```text
skill: meeting-pdf-open / VERIFIED / v3
trigger: 회의 자료, PDF 열기
procedure:
  1. 허용된 회의 자료 폴더에서 후보를 읽는다.
  2. 대상이 하나가 아니면 사용자에게 고르게 한다.
  3. 선택된 PDF의 hash를 확인한다.
  4. 등록된 PDF viewer로 연다.
allowed capability: file.list, file.open
```

이 스킬이 있다고 해서 PDF를 자동으로 아무거나 열거나 파일을 삭제할 수 있는 것은 아니다. `file.open`
adapter와 verifier가 대상 hash, 허용 root, viewer identity를 확인하고, 위험도에 따라 정책과 승인을
다시 적용한다.

## 안전 원칙

- DRAFT 스킬은 검색·실행되지 않는다.
- 스킬은 Capability Registry에 없는 기능을 추가할 수 없다.
- LLM이 스킬 밖 capability를 포함한 Plan을 제안하면 거부한다.
- 실행 결과는 스킬의 "성공" 주장이 아니라 독립 verifier 결과로 기록한다.
- 자동 갱신은 새로운 권한이나 행동을 즉시 활성화하지 않는다. 새 초안으로만 저장된다.
- STOP, 승인 대상·인자 binding, 실행 후 OS 검증은 모든 스킬보다 우선한다.

## 현재 구현 상태

`skill_runtime.py`에는 로컬 SQLite 기반 `LocalSkillCatalog`, DRAFT/VERIFIED/RETIRED lifecycle,
검색, 사용 기록, revision, `SkillAwarePlanner` capability binding이 구현되어 있다.

`skill_authoring.py`에는 개인정보를 줄인 실행 근거에서 LLM을 이용해 최초 스킬 또는 개정 스킬의
**초안만** 만드는 경로가 구현되어 있다. 최초 스킬은 모든 단계가 독립 검증된 성공 기록이어야 한다.
개정은 최소 관측 수·성공률·반복 실패 기준이 `PROPOSE_REVISION`일 때만 가능하고, 기존 스킬의
capability 허용 목록을 넓힐 수 없다. LLM 응답은 중복 키와 비표준 수를 거부하는 엄격한 JSON으로
검사하며, 생성된 초안은 자동 승인되지 않는다. 실행 기록의 정규화 SHA-256도 초안 산출물에 붙인다.

상시 실행 런타임은 종료된 Plan과 독립 검증 결과를 `skill_trace.py`에서 최소 기록으로 변환한다.
원래 action 인자, 파일 내용과 목적 문장은 복사하지 않고 capability, 단계 결과 코드와 독립 검증
여부만 남긴다. 사용자 요청에서는 Windows 절대 경로, URL과 이메일을 가린 뒤 로컬
`state/skill-traces.sqlite3`의 검토 대기열에 저장한다. 기록 실패는 이미 성공한 PC 작업을 실패로
바꾸지 않으며 상태에 별도로 표시한다. 이 대기 기록은 아직 NIM으로 자동 전송되거나 스킬로 자동
승인되지 않는다.

관찰이 먼저 필요한 작업은 `continue_after_verification`을 가진 읽기 전용 Plan으로 시작한다.
독립 verifier가 성공시킨 관찰만 크기가 제한된 다음 Planner context에 들어가며, 새 Plan은 이전
action ID나 동일한 상태 변경을 다시 사용할 수 없다. 읽기 전용과 상태 변경을 한 Plan에 섞거나,
상태 변경 후 계속 실행하도록 표시한 NIM 응답은 실행 전에 거부한다. 이 구조는 스킬을 사용할 때도
같아서, 스킬의 절차가 실행 결과를 대신하거나 검증을 생략하지 않는다.

`tools/run_safe_file_sort_pilot.py`로 새 임시 폴더에서 실제 NIM 폐루프를 실행할 수 있다. 2026-10-14
실행은 `file.list` 관찰 뒤 두 `file.move`를 수행해 2회 round에서 완료됐으며, 파일 내용과 최종
위치는 별도 probe가 다시 확인했다. 이 파일럿은 실행 연결을 검증하지만 스킬 재사용의 효과를
측정하는 SK0~SK3 실험을 대신하지 않는다.

개정 DRAFT는 기존 VERIFIED 버전을 바로 교체하지 않는다. `SkillCandidateCollector`는 해당 DRAFT가
기존 버전을 직접 supersede하고 capability를 넓히지 않았는지 확인한 뒤, 같은 모델 설정·도구·초기
상태의 대응 block을 실행 순서까지 교차해 추가 전용 원장에 저장한다. 성공 회귀 또는 허용 범위를
넘는 시간·토큰 악화가 있으면 거부하며, 통과해도 상태는 `READY_FOR_HUMAN_REVIEW`다.

`tools/run_skill_revision_candidate_pilot.py`는 이 경로를 실제 파일 정리 v1/v2로 검증한다. 3개
block에서 v1은 0/3, v2는 3/3이었고 여섯 evidence 파일의 SHA-256이 trial과 일치했다. v2는 평균
31,196 ms·6,350-token, v1은 평균 53,343 ms·8,395-token이었다. 이는 해당 prompt·fixture의
3-block pilot 결과이며 다른 작업이나 사용자에 대한 일반적인 성능 향상 주장이 아니다. 평가 후에도
v1은 VERIFIED, v2는 DRAFT로 유지됐다.

명시적 CLI 명령 `skill-draft-from-trace-nim`과 `skill-revision-from-trace-nim`은 사용자가 선택한
대기 trace 한 건만 Windows Credential Manager의 NIM 키로 작성기에 전달한다. 정상적으로 DRAFT가
저장된 뒤에만 해당 trace를 소비 처리하므로, NIM 실패 시 근거는 검토 대기열에 남는다.

사용자는 `skill-trace-list`와 `skill-trace-show`로 NIM 접속 없이 근거를 먼저 확인할 수 있다.
원하지 않는 기록은 `skill-trace-discard`로 숨기되 행을 삭제하지 않고, 필요하면
`skill-trace-restore`로 복원한다. `skill-list --status DRAFT`는 NIM 또는 수동으로 작성된 초안을
승인 전에 검토하는 목록이다.

제품 tray의 `스킬 검토` 화면은 이 DRAFT 목록을 로컬에서 읽어 호출 표현·절차·동적 입력·판단 규칙·
검증 규칙·허용 capability와 개정 대상을 표시한다. 승인과 거절은 별도 확인창을 거치며, 확인 전후에
동일한 DRAFT 버전과 수정 시각인지 다시 검사한다. 승인하면 VERIFIED가 되어 검색 대상이 되고,
거절하면 RETIRED가 되어 실행에 사용되지 않는다. 저장소 오류와 오래된 선택은 상태를 변경하지 않고
안전한 한국어 안내만 표시한다.

제품 tray의 `실행 기록 검토` 화면은 대기 trace의 최소화된 요청 요약·capability·결과 코드·독립
검증 여부만 표시한다. 사용자가 기록 한 건을 선택하고 “NIM으로 초안 생성” 확인창에서 외부 전송에
동의해야 작성기를 호출한다. NIM 작업은 worker thread에서 실행하며 worker는 Tk를 호출하지 않고,
UI thread가 queue를 확인해 결과만 반영한다. 같은 기록의 동시 작성은 거부하고 창은 작성 중 닫히지
않는다. 실패하면 trace를 보존하고, DRAFT 저장 뒤 trace 소비가 실패하면 새 DRAFT를 RETIRED로
회수한다. 프로세스가 두 SQLite 변경 사이에서 강제 종료되는 경우는 단일 원자 트랜잭션이 아니므로
향후 시작 시 조정 기록을 이용한 복구 대상으로 남는다.

실제 합성 성공 trace로 NIM 연결을 시험했다. 첫 출력의 Markdown 울타리는 엄격한 JSON 계약이
거부했고, invalid output을 데이터로만 전달하는 한 번의 형식 복구 뒤 DRAFT가 저장됐다. NIM 요청
2회, 입력 1,572-token, 출력 649-token이었고, 대기 trace는 0건이 됐으며 DRAFT capability는 실제
관찰된 `system.info.read` 하나뿐이었다. 이는 제품 연결 smoke이며 스킬 성능 결과가 아니다.

같은 화면에서 최초 DRAFT와 개정 DRAFT를 선택할 수 있다. 개정 목록에는 VERIFIED 상태이고 현재
`assess_revision()`이 `PROPOSE_REVISION`이며, 아직 이를 supersede하는 DRAFT가 없는 스킬만 나온다.
화면 선택 때, 확인 직후, worker 실행 직전에 ID·버전·수정 시각·VERIFIED 상태와 개정 판정을 다시
검사한다. 생성 결과는 기존 key와 capability 부분집합을 유지하고 정확한 다음 버전으로 기존 스킬을
supersede해야 한다. 새 DRAFT가 생겨도 기존 버전은 승인 전까지 VERIFIED로 유지된다.

실제 임시 카탈로그의 v1에 실패 2회·성공 1회를 기록하고 실패 trace로 NIM 개정 연결을 시험했다.
NIM 요청 1회, 입력 827-token, 출력 307-token으로 v2 DRAFT가 생성됐고 v1은 VERIFIED, supersedes
연결은 일치, trace는 소비됐으며 허용 capability는 `system.info.read` 하나로 유지됐다. 이는 제품
연결 smoke이며 개정 스킬의 성능 개선 근거는 별도 대응 실험 결과로만 판단한다.

다음 제품 단계는 현재 변경을 포함한 wheel·one-folder·Setup을 다시 만들고 깨끗한 설치 환경에서
두 검토 화면과 자격 증명 기반 시작 경로를 검증하는 것이다.
