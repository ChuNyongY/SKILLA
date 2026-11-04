# SKILLA-PC Agent

> 현재 상태: **스킬 중심 Windows 에이전트 및 제한된 Windows adapter prototype**. 로컬 스킬
> 카탈로그의 생성·승인·검색·사용 기록·개정 구조와, 스킬 실행을 제한하는 정책·승인·검증 폐루프가
> 구현됐다. tray에서 실행 기록의 NIM 전송에 동의하고 최초·개정 초안을 생성한 뒤 검토·승인하는 흐름도
> 구현됐다. 실제 마이크·장시간 운용 검증과 범용 변경 작업은
> 아직 완료하지 않았다.

SKILLA-PC Agent는 한국어 음성·텍스트 요청을 받아 사용자의 반복 Windows 작업을 **스킬로 만들고,
찾고, 사용하며, 실행 결과를 기록해 사용자 승인으로 새 버전으로 갱신하는** 로컬 Windows 에이전트다.
연구의 핵심은 스킬의 생성·검색·재사용·개정이 성공률과 반복 비용에 미치는 영향이다. 안전
정책·승인·검증은 연구 주제를 대체하지 않고, 스킬이 실제 PC에서 잘못된 권한이나 대상을 사용하지
못하게 하며 성공 여부를 실제 상태로 측정하는 공통 실행 기반이다.

발표·시험용 확인 자료:

- [실제 구현·모델·실험 확인표](docs/SKILLA_IMPLEMENTATION_FACTS.md)
- [UI 시험·캡처 가이드](docs/SKILLA_UI_TEST_GUIDE.md)
- `output/SKILLA_졸업작품_포스터_실제구현_종합본.pptx` — 실제 실행 화면을 넣은 2쪽 포스터

## 무엇이 다른가

공개된 JARVIS 계열 프로젝트에는 이미 웨이크워드, 로컬 STT/TTS, LLM 도구 호출, 메모리, 앱 실행,
PowerShell, 화면 인식 등이 존재한다. SKILLA의 중심은 모델이 매번 즉흥적으로 도구를 고르는 방식 대신,
사용자별 반복 업무를 버전 있는 **검증된 스킬**로 축적하는 것이다. 연구 초점은 같은 모델과 같은 Windows
도구에서도 스킬 검색·사용·갱신 구조가 작업 재현성과 성공률을 높이는지, 그리고 그 실행을 안전 경계가
어떻게 제한하는지다.

```text
Wake/VAD/STT
  -> Addressedness + Intent Gate
  -> Verified Skill Retrieval
  -> Skill procedure + capability allowlist
  -> Typed Plan
  -> Deterministic Capability Policy
  -> GREEN | YELLOW | RED | DENY
  -> Exact-action Approval Token
  -> Native API | Allowlisted PowerShell | UIA | Vision
  -> Postcondition Verifier
  -> Success | Bounded Retry/Replan | Abort
```

스킬 중심 핵심 기능은 다음과 같다.

- 사용자는 반복 작업을 로컬 스킬 초안으로 만들고, 승인된 스킬만 실행에 사용한다.
- 스킬은 제목·호출 문구·절차·허용 capability·버전을 가지며, 실행 결과를 버전과 함께 기록한다.
- 반복 절차와 함께 동적 입력, 판단 규칙과 검증 규칙을 저장하되 현재 파일명·경로·내용은 매번 다시 확인한다.
- 스킬 변경은 기존 절차를 덮어쓰지 않고 새 DRAFT 버전으로 생성되며, 사용자 승인 뒤에만 VERIFIED가 된다.
- 검증 실행에는 모델 구성과 도구 표면의 SHA-256을 남길 수 있고, 최근 실행의 환경 변화나 반복 실패는
  스킬을 자동 폐기하지 않은 채 사람의 재검토 대상으로 표시한다.
- 상시 실행 제품은 선택된 스킬을 LLM 계획 필드가 아닌 내부 일회성 `task_id` 결합으로 보존하고,
  작업이 끝나면 성공·실패·중단, 처리 시간, 계획기 NIM 호출·토큰과 환경 지문을 해당 스킬 버전에
  자동 기록한다. usage 누락 여부도 함께 남겨 불완전한 토큰 값을 완전한 측정처럼 사용하지 않는다.
- Planner는 선택된 스킬의 capability allowlist 밖의 작업을 계획할 수 없다.
- 관련 스킬이 없으면 요청을 거부하지 않고 동일한 기본 Planner로 일반 계획을 생성한다.
- 검색 점수가 같은 최상위 스킬이 둘 이상이면 임의로 하나를 고르지 않고 기본 Planner로 돌아간다.
  `evaluate-skill-search`는 운영과 같은 검색기로 정답 라벨 자료의 정확도·오검출·미검출·오검색·
  모호 판정을 측정한다.
- 스킬은 새 권한이나 임의 shell 명령을 만들지 못한다. 실제 실행 권한은 registry와 정책이 계속 통제한다.
- 최초 스킬은 독립 검증된 성공 기록에서만 초안으로 만들고, 개정 초안은 기존 capability 권한을
  확대할 수 없으며 사용자 승인 전에는 활성화되지 않는다.

안전 실행 경계는 다음을 보장한다.

- LLM은 typed plan을 제안하지만 실행 권한을 결정하지 않는다.
- 승인 후 대상·인자·위험도가 바뀌거나 토큰이 재사용되면 실행을 거부한다.
- 실행 성공은 도구의 응답이 아니라 실제 Windows postcondition으로 판단한다.
- 웹·PDF·이메일 등 신뢰하지 않는 콘텐츠는 스킬, capability, 권한을 추가할 수 없다.

## 현재 구현된 범위

- SQLite 기반 로컬 스킬 카탈로그: DRAFT → VERIFIED → RETIRED lifecycle
- `skill-create`, `skill-approve`, `skill-search`, `skill-revise`, `skill-record-use`,
  `skill-assess-staleness` CLI
- 엄격한 정답 JSON으로 실제 검색 경로를 측정하는 `evaluate-skill-search` CLI
- 고정 한국어 라벨과 별도 VERIFIED 카탈로그로 운영 검색기를 재현하고 cases·report·DB 해시를
  남기는 `run_skill_search_pilot` 도구. 조사 처리 개선 후 개발자료 19/22, 변경 전 고정한 보류자료
  21/25 정답이며 두 자료 모두 관찰된 거짓 양성은 0건이다(개발자 라벨 경로 시험).
- 선택한 로컬 실행 trace만 NIM에 보내 DRAFT를 만드는 `skill-draft-from-trace-nim`,
  `skill-revision-from-trace-nim` CLI
- NIM 접속 없이 대기 trace와 DRAFT를 검토하고, trace를 감사 보존형으로 폐기·복원하는 CLI
- tray의 `실행 기록 검토`에서 최소화 기록을 확인하고 명시적으로 동의한 한 건만 NIM에 보내
  최초 DRAFT 또는 반복 실패 근거가 있는 VERIFIED 스킬의 개정 DRAFT를 만든다. `스킬 검토`에서
  전체 초안을 확인한 뒤 승인·거절한다.
- 선택된 VERIFIED 스킬의 capability allowlist에 Plan을 결합하는 `SkillAwarePlanner`
- 제품 서비스의 스킬 카탈로그와 스킬 우선 Planner 연결. 소스 실행은 `state/skills.sqlite3`,
  기존 사용자 데이터와의 호환을 위해 검증된 설치본은 `%LOCALAPPDATA%/JAVIS-PC/state/<version>/skills.sqlite3`을 사용해 package
  manifest와 사용자 상태를 분리
- Pydantic 기반 Plan, Action, Capability, Policy, Approval, Verification 계약
- 불변 capability registry와 기본 R0~R4 위험 하한
- GREEN/YELLOW/RED/DENY 정책 엔진
- 대상·인자 변경과 재사용을 차단하는 HMAC 승인 토큰
- mock executor, postcondition verifier, 유한 retry/replan, 전역 STOP
- 민감 값을 마스킹하고 회전 파일까지 SHA-256 chain으로 연결하는 JSONL 감사 로그
- 허용 경로 기반 Native/PowerShell read-only adapter
- 사전 등록·해시 검증 앱 실행과 PID 실행 파일 사후 검증
- 저널 기반 동일 볼륨 파일 이동 및 불명확 실패 자동 재시도 금지
- hash와 선택적 Authenticode publisher를 검증하는 typed app registry
- 명시적 로컬 승인 창과 fail-closed OS 인증 adapter 경계
- 검증된 프로세스 session에만 접근하는 exact-match read-only UIA observation
- trusted profile·text hash 재검증 기반 Notepad UIA replacement
- launcher/runtime handoff 안정화와 timeout 격리 UIA worker를 거친 실제 Notepad smoke
- 서명·hash가 고정된 Chrome·Edge·Explorer·Terminal 등록과 실제 Edge/Terminal UIA smoke
- direct launch를 막고 네 고정 URI, runtime identity와 locale-independent UIA page anchor를 검증하는 Windows Settings adapter
- allowed-root·hash 재검증과 독립 absence 검증을 갖춘 Windows 휴지통 이동
- 고정 endpoint·0~100 contract·독립 OS readback을 갖춘 Windows master-volume adapter
- 허용 root·PDF hash·등록 viewer lease와 PID creation-time을 결합한 `file.open` adapter
- R3 승인·payload hash·content-free mock receipt를 결합한 메시지 draft/send 경계
- 고정된 드라이브 root만 읽고 경로·바이트 수를 노출하지 않는 저장공간 상태/정리 제안 경계
- 값·경로 대신 결과 binding만 공개하는 bounded SQLite `memory.search`
- 검증된 단일 memory ID를 허용-root hash-pinned PDF action으로 연결하는 S03 resolver
- 등록된 로컬 source set만 읽는 network-free `browser.fixture.read`
- 등록 Chrome/Edge에서 exact-host HTTPS 주소만 새 창으로 여는 `browser.navigate`
- 단계별 새 동의가 있어야 마이크·스피커·Windows Hello를 실행하는 `run-user-validation`
- 기존 파일을 덮어쓰지 않는 원자적 DOCX fixture writer와 독립 ZIP/XML verifier
- installer를 실행하지 않는 lease·hash·publisher 기반 `package.verify`
- commit 권한 없이 휘발성 영수증만 만드는 VM 전용 `system.reset.prepare`
- audit·move journal·lock 파일의 사용자+LocalSystem protected DACL과 프로세스 간 잠금
- 외부 snapshot VM harness 증거를 검증하는 manifest·freshness·복원·서명 fail-closed gate
- S08/S09/S10/S12 증거의 누락·추가·중복 run을 거부하는 HMAC-SHA256 batch verifier
- 동의 reference와 WAV/hash를 선검증하고 원문을 보고하지 않는 offline 한국어 STT 평가 하네스
- 녹음 없이 16 kHz mono int16 지원만 확인하는 privacy-minimized microphone probe
- 제목·텍스트·경로를 읽지 않고 등록 앱의 경로·SHA-256만 확인하는 최소 전경 컨텍스트
- foreground/focus WinEvent에 반응하고 PID/HWND 일치·overflow fail-closed를 강제하는 이벤트 컨텍스트
- SHA-256 고정 local ONNX bundle과 실제 offline openWakeWord inference 경로
- commit·size·SHA-256 고정 local faster-whisper bundle과 실제 offline STT inference 경로
- paired B0/B1/P1/P2의 Wilson interval·exact McNemar·Holm 보정 연구 분석기
- credential 차단·FTS literal 검색·30일 episode 만료를 갖춘 SQLite semantic/episodic memory
- 실행 파일 handle을 유지해 검사→실행 교체 창을 줄이는 Windows deny-write/delete lease
- YELLOW/RED/R4 승인 채널·강한 인증 coordinator
- Intent Gate와 한국어 로컬 STOP 감지기
- 로컬 STOP·untrusted-content 우회를 갖춘 strict JSON NIM intent classifier
- Voice capture→Intent Gate→typed Plan 연결과 shared-token 즉시 STOP coordinator
- 실행 중 shared STOP·bounded worker·WAV 독립 검증을 갖춘 로컬 Windows SAPI TTS sink
- 사용자/NIM/오류 원문 대신 6개 고정 한국어 상태 문구만 읽는 voice feedback presenter
- frame capture→intent→plan→policy/execution/verification→feedback 단일-task composition root
- 작업과 독립적으로 캡처를 유지하고 계획·실행 중 exact STOP을 로컬 처리하는 always-on runtime
- 승인 session·foreground HWND·휘발성 window hash·클릭 직전 재캡처를 강제하는 local-only Vision 경계
- hash-pinned exact BGRA template grounder와 foreground client GDI capture/mouse backend(기본 비활성)
- 일회성 합성 창에서 실제 GDI→grounding→동일 HWND click→화면 변경 검증 smoke 성공
- 같은 action의 retry-safe UIA 실패 뒤 세 번의 one-shot screenshot만 허용하는 selective capture gate
- S01~S15의 host/fixture/VM/mock 경계와 B0 격리를 고정한 strict 평가 manifest
- S01~S15별 nominal/fault를 포함한 strict 30-task benchmark manifest와 drift validator
- actual reversible S01 Chrome process/window 및 S03 memory→PDF→Edge window smoke
- 논문 지표 평가 하네스와 안전한 system-info smoke CLI

실기기에서 TTS 스피커 재생과 Windows Hello 성공 인증은 PASS했다. 남은 범위는 실제 한국어
wake word/STT 정확도, 평점 3/5인 TTS 말투 개선, 추가 앱별 변경 adapter, Vision fallback,
snapshot VM 위험 작업, 고급 procedural memory다.

## 스킬 및 안전 불변식

1. DRAFT 스킬은 검색·실행되지 않는다.
2. 스킬은 등록되지 않은 capability와 임의 shell 명령을 추가할 수 없다.
3. 스킬 절차가 바뀌면 새 초안 버전을 만들고, 기존 VERIFIED 버전을 몰래 바꾸지 않는다.
4. 스킬이 선택돼도 정책은 실행 직전 다시 평가한다.
5. RED 작업은 자동 승인하지 않는다.
6. 승인 후 대상이나 인자가 바뀌면 토큰을 거부한다.
7. verifier 실패 시 다음 action으로 진행하지 않는다.
8. 전역 STOP은 LLM을 우회해 Orchestrator와 공유하는 one-way cancellation token을 set한다.

## MVP 경계

대상 앱은 File Explorer, 브라우저, Notepad, Windows Settings, Terminal로 제한한다. 실행 우선순위는 Native API → 제한된 PowerShell → UIA → Vision이다. 영구 삭제·메시지 발송·종료·초기화 같은 위험 작업은 mock executor 또는 snapshot 복구가 가능한 Windows VM에서만 시험한다.

현재 PC용 앱 registry 검증:

```powershell
.\.venv\Scripts\python.exe -m javis_core.cli validate-app-registry config/apps.json --require-publisher
```

Windows Update로 실행 파일 hash가 바뀌면 자동 우회하지 말고 새 파일의 서명과 publisher를
검토한 뒤 registry를 명시적으로 갱신한다.

비목표는 모든 Windows 앱 지원, 관리자 권한 상시 보유, 임의 셸 실행, 스킬의 무승인 자동 활성화,
완전 자율 RED 실행, 범용 대화 비서와의 기능 경쟁이다. 클라우드 또는 로컬 LLM 선택은 구현 옵션이며
연구 기여가 아니다.

## 연구 설계

연구 질문은 다음과 같다.

> 동일한 LLM과 Windows 도구에서, 반복 작업을 검증된 스킬로 생성·검색·사용·개정하는 구조가 매번
> 즉흥적으로 계획하는 방식보다 작업 성공률·재현성·복구율을 높이는가? 또한 안전 실행 경계는 그 과정에서
> 허용되지 않은 capability와 잘못된 대상 실행을 차단하는가?

주 실험은 SK0(스킬 없음), SK1(동일 내용을 일반 저장 지침으로 제공), SK2(최초 검증 스킬),
SK3(실패 기록을 반영한 개정 스킬)로 둔다. 각 조건에 같은 LLM, Windows 도구, 초기 상태, 실행
예산과 안전 실행 경계를 적용한다. 작업 성공률, 실행 시간, 모델 호출 수, 입출력 토큰, 사용자 추가
확인 횟수, 실행 비용과 스킬 생성·개정 비용을 측정한다. 기존 B0/B1/P1/P2 안전 비교는 실행 기반을
검증하는 별도 보조 실험으로 유지한다. 아직 스킬의 성능 우월성을 주장하지 않는다.

`build-skill-study-schedule`로 조건 순서를 균형화하고, `analyze-skill-study`는 같은 대응 블록에서
모델·설정·도구·초기 상태가 하나라도 달라지면 분석을 거부한다.

## 개발 환경

Python 3.12 환경에서 다음 명령을 사용한다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,voice,uia,trash,audio-control,packaging]"
pytest
python -m javis_core.cli doctor (Get-Location).Path
# Setup 설치본은 첫 실행 시 마스킹된 초기 설정 창에서 키를 받아
# 현재 사용자의 Windows Credential Manager에 저장하고 재검증한 뒤 시작한다.
# 개발 환경이나 수동 복구에서는 다음 echo 없는 prompt 명령을 사용할 수 있다.
python -m javis_core.cli provision-nim-credential
python -m javis_core.cli preflight-product-host-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path
python -m javis_core.cli check-product-service-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path
# 실제 마이크와 tray를 시작하므로 사용자 참여 상태에서만 실행
# tray의 "실행 기록 검토"에서 동의 후 DRAFT를 만들고, "스킬 검토"에서 승인·거절할 수 있음
python -m javis_core.cli run-product-tray-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path
# Tk HUD 대체 실행 경로
python -m javis_core.cli run-product-host-credential (Get-Location).Path (Resolve-Path .\config\product_host.json).Path
python -m javis_core.cli foreground-context config/apps.json --require-publisher
python -m javis_core.cli smoke-system-info
python tools/run_safe_file_sort_pilot.py
# 기존의 빈 절대 출력 폴더를 지정하는 1블록 SK0~SK3 실제 파일럿
python -m tools.run_skill_study_pilot C:\absolute\empty-pilot-output
python -m tools.run_pdf_open_skill_study_pilot C:\absolute\empty-pdf-pilot-output
python -m tools.run_skill_revision_candidate_pilot C:\absolute\empty-candidate-output
python -m tools.bundle_skill_study C:\absolute\empty-bundle-output --source C:\absolute\first-observations.json C:\absolute\first-evidence --source C:\absolute\second-observations.json C:\absolute\second-evidence
python -m tools.run_skill_search_pilot C:\absolute\empty-search-output
python -m javis_core.cli evaluate-skill-revision-candidate C:\absolute\paired-candidate-trials.json
python -m javis_core.cli evaluate evaluation/example_trials.json
python -m javis_core.cli intent-scenarios evaluation/intent_scenarios.json
python -m javis_core.cli validate-integrated-scenarios evaluation/integrated_scenarios.json
python -m javis_core.cli validate-benchmark-tasks evaluation/benchmark_tasks.json evaluation/integrated_scenarios.json
python -m javis_core.cli analyze-benchmark-results evaluation/benchmark_tasks.json evaluation/integrated_scenarios.json C:\absolute\benchmark-observations.json C:\absolute\benchmark-evidence
python -m javis_core.cli evaluate-wakeword-corpus C:\absolute\wake-corpus\manifest.json C:\absolute\wake-corpus models/openwakeword/manifest.json --threshold 0.5
python -m javis_core.cli evaluate-repcnn-wakeword-corpus C:\absolute\wake-corpus\manifest.json C:\absolute\wake-corpus C:\absolute\model\jarvis.onnx <64자리-model-sha256> --threshold 0.7
python -m javis_core.cli run-host-safe-scenarios evaluation/integrated_scenarios.json (Get-Location).Path
python -m javis_core.cli run-mock-scenarios evaluation/integrated_scenarios.json
python -m javis_core.cli run-fixture-scenarios evaluation/integrated_scenarios.json
python -m javis_core.cli audit-scenario-capabilities evaluation/integrated_scenarios.json
python -m javis_core.cli run-safe-evaluation evaluation/integrated_scenarios.json (Get-Location).Path
python tools/s01_chrome_smoke.py
python tools/s02_volume_smoke.py
python tools/s03_memory_pdf_smoke.py
python tools/build_windows_package.py
python tools/build_windows_installer.py
```

## 로드맵

- Phase 0: 타입 계약, registry, policy, approval token, 단위 테스트 — 완료
- Phase 1: mock executor와 verifier, 상태 머신, 구조화 audit log — 완료
- Phase 2: read-only Native API와 제한된 PowerShell adapter — 완료
- Phase 3: UIA, 로컬 STOP, 승인 UI — 부분 완료(Hello 실제 인증·Edge/Terminal 관찰 완료, 추가 변경 adapter·Vision 미완료)
- Phase 4: 한국어 음성 파이프라인, 고장 주입, B0/B1/P1/P2 실험 — 부분 완료(실기기·참가자 평가 미완료)

상세 비교와 설계는 [차별성 문서](docs/DIFFERENTIATION.md), [아키텍처 문서](docs/ARCHITECTURE.md),
[snapshot VM 증거 계약](docs/SNAPSHOT_VM_EVIDENCE.md)을 참고한다.
음성 corpus 형식과 CER/WER 정의는 [한국어 음성 평가 계약](docs/VOICE_EVALUATION.md)에 있다.
공개 Jarvis 호출 방식과 한국어 호출어 모델 선택 근거는
[호출어 비교·감사 문서](docs/WAKEWORD_REFERENCE_AUDIT.md)에 있다.
학습·임계값 보정·최종 시험 분리와 거리·소음 조건은
[한국어 호출어 모델 실험계획서](docs/WAKEWORD_STUDY_PROTOCOL.md)에 있다.
NIM 의도 제안과 로컬 실행 결정의 분리는 [Intent classifier 문서](docs/INTENT_CLASSIFIER.md)에 있다.
음성 명령의 계획 전 연결과 STOP token 계약은 [음성 명령 문서](docs/VOICE_COMMAND.md)에 있다.
로컬 Windows SAPI 출력과 WAV 검증 경계는 [TTS 문서](docs/TTS.md)에 있다.
한국어 TTS 품질 개선 후보와 블라인드 청취 기준은
[한국어 로컬 TTS 후보 감사](docs/TTS_CANDIDATE_AUDIT.md)에 있다.
단일 음성 작업의 composition 계약은 [Agent session 문서](docs/AGENT_SESSION.md)에 있다.
상시 캡처·비동기 계획/실행·STOP 계약은 [상시 런타임 문서](docs/ALWAYS_ON_RUNTIME.md)에 있다.
Vision fallback의 비활성 기본값과 실행 안전조건은 [Vision 문서](docs/VISION.md)에 있다.
UIA fallback 증거와 screenshot 횟수 결합은 [Selective capture 문서](docs/SELECTIVE_CAPTURE.md)에 있다.
WinEvent 기반 최소 컨텍스트 갱신은 [이벤트 컨텍스트 문서](docs/CONTEXT_EVENTS.md)에 있다.
고정 통합 시나리오와 실행 격리는 [S01~S15 평가 계약](docs/INTEGRATED_SCENARIOS.md)에 있다.
Windows Core Audio 설정과 불명확 실패 경계는 [볼륨 adapter 문서](docs/VOLUME.md)에 있다.
Hash-pinned PDF 실행 경계는 [PDF open 문서](docs/PDF_OPEN.md)에 있다.
메시지 mock과 외부 전송 경계는 [메시지 adapter 문서](docs/MESSAGE.md)에 있다.
저장공간 상태와 무변경 정리 제안 경계는 [저장공간 모니터 문서](docs/STORAGE_MONITOR.md)에 있다.
제한된 기억 검색은 [memory search 문서](docs/MEMORY_SEARCH.md)에 있다.
네트워크 없는 source-set 읽기는 [fixture read 문서](docs/FIXTURE_READ.md)에 있다.
새 DOCX 작성 경계는 [document write 문서](docs/DOCUMENT_WRITE.md)에 있다.
설치 패키지 identity 검증은 [package verify 문서](docs/PACKAGE_VERIFY.md)에 있다.
초기화 준비와 수동 commit 분리는 [reset prepare 문서](docs/RESET_PREPARE.md)에 있다.
실험 데이터 구조와 검정 해석은 [paired-study 분석 계약](docs/STUDY_ANALYSIS.md)에 있다.
Windows Hello 빌드·IPC 계약은 [네이티브 helper 문서](native/WindowsHelloHelper/README.md)에 있다.
로컬 저장·검색·민감정보·retention 계약은 [메모리 문서](docs/MEMORY.md)에 있다.
최소 전경 앱 판별과 비권한성 경계는 [컨텍스트 문서](docs/CONTEXT.md)에 있다.
Windows Settings allowlist와 검증 한계는 [Settings adapter 문서](docs/SETTINGS.md)에 있다.
설치·빌드·무부작용 사전점검 순서는 [배포 문서](docs/DEPLOYMENT.md)에 있다.
현재 완료 범위와 남은 작업은 [구현 상태](docs/STATUS.md), 위협과 잔여 위험은 [위협 모델](docs/THREAT_MODEL.md)에 정리한다.
연구 목적, SK0~SK3 조건, 비용 계산과 구현 간극은 [스킬 연구 기준](docs/SKILL_RESEARCH_PLAN.md)에 정리한다.
최신 공개 Windows JARVIS 계열과의 기능·안전성 차이는 [GitHub 비교 문서](docs/GITHUB_COMPARISON.md)에 있다.
LLM 하네스·스킬의 역할, 성능 영향, 선행 연구와 쉬운 설명은 [하네스와 스킬 문서](docs/HARNESS_AND_SKILLS.md)에 있다.
스킬 생성·검색·사용·개정의 실제 런타임 경계는 [스킬 런타임 문서](docs/SKILL_RUNTIME.md)에 있다.
한국어 조사 처리의 변경 전·후 고정 자료 결과는 [스킬 검색 파일럿](docs/SKILL_SEARCH_PILOT.md)에 있다.
단순 PDF 열기 작업의 SK0~SK3 반례 결과는 [PDF 스킬 파일럿](docs/PDF_SKILL_STUDY_PILOT.md)에 있다.
두 작업의 자기완결형 근거와 통합 기술통계는 [통합 스킬 파일럿](docs/COMBINED_SKILL_STUDY_PILOT.md)에 있다.
