# 릴리스 전 안전 체크리스트 증거

최종 갱신: 2026-11-19 (SKILLA-PC 0.2.16)

원 계획서의 릴리스 전 자동화 체크리스트 13개를 현재 코드와 직접 대응한다. `PASS`는 명시된
계약 범위의 자동 테스트를 뜻하며 실제 마이크·사용자·snapshot VM 증거를 대신하지 않는다.

| # | 원 계획 체크 | 판정 | 직접 자동화 증거 | 남은 실제 증거 |
|---:|---|---|---|---|
| 1 | unknown capability는 항상 deny | PASS | `test_policy.py::test_unknown_capability_is_denied`, `test_contracts.py::test_unknown_capability_is_rejected_at_plan_boundary` | 없음(결정론적 경계) |
| 2 | LLM raw shell 출력은 실행 불가 | PASS | `test_planner.py::test_unknown_capability_is_rejected`, `powershell.raw`가 registry에 없고 R4/DENY | 없음(현재 capability 집합) |
| 3 | RED는 autonomy와 무관하게 자동 승인 불가 | PASS | `test_policy.py::test_r4_requires_strong_auth`, `test_orchestrator.py::test_r4_requires_strong_auth_before_execution` | Hello 실제 성공은 별도 사용자 검증 |
| 4 | wakeword 없는 일반 대화는 실행 불가 | PASS(계약) | `test_voice.py::test_non_wake_audio_is_ignored`, `test_host_safe_scenarios.py::test_stt_misrecognized_wake_word_creates_no_plan`, intent scenario bundle | 실제 한국어 FAR/FRR corpus |
| 5 | Planner 장애 중에도 STOP 작동 | PASS(계약) | `test_always_on_runtime.py::test_exact_stop_during_planning_prevents_executor_start`, `test_stop_bypasses_blocked_context_and_prevents_model_calls` | 실제 마이크 STOP latency |
| 6 | 승인 뒤 target 변경 시 승인 무효 | PASS | `test_approval.py::test_changed_target_invalidate_approval`, `test_changed_arguments_invalidate_approval` | 없음(토큰 경계) |
| 7 | action별 authorization token 확인 | PASS | `test_approval.py::test_approval_round_trip_and_replay_block`, orchestrator 승인 검증 | 실제 RED VM 반복 |
| 8 | retry 횟수 상한 존재 | PASS | `test_orchestrator.py::test_recoverable_failure_retries_within_budget`, ambiguous side effect는 1회로 중단 | 실제 UI failure 반복 |
| 9 | verifier 실패 후 다음 step 진행 금지 | PASS | `test_orchestrator.py::test_unknown_postcondition_is_not_retried`, cancellation 중 verification 미실행 | 실제 다단계 UI 변화 |
| 10 | web/PDF/email 문구가 capability 추가 불가 | PASS(계약) | `test_intent.py::test_untrusted_page_text_cannot_initiate_action`, prompt-injection hard deny | 실제 웹·PDF adversarial corpus |
| 11 | 비밀번호·API key가 로그에 남지 않음 | PASS | `test_audit_and_cancellation.py::test_jsonl_audit_redacts_nested_secrets`, Credential backend/CLI 비노출 테스트, 배포 exact-key scan 0 | 없음(현재 sink와 배포물) |
| 12 | screenshot 기본 영구 저장 금지 | PASS(현재 Vision 경계) | `test_vision.py::test_window_changed_predicate_recaptures_without_retaining_pixels`; 이미지 필드는 반환 모델에 없음 | 실제 사용자 앱 capture 보존 감사 |
| 13 | audit에서 task/action/policy/result 연결 | PASS | orchestrator 성공·거부·retry 테스트의 구조화 event와 JSONL hash-chain 검증 | 장시간 실제 runtime audit 표본 |

## 승인 토큰 결합 필드

`ApprovalClaims`와 검증 경계는 `task_id`, `action_id`, `capability_id`, `arguments_hash`,
`target_identity`, `risk`(원 계획서의 `risk_level`), `issued_at`, `expires_at`, `nonce`를 결합한다. replay, 만료, 인자 변경,
대상 변경은 각각 자동 테스트로 거부한다.

## 현재 릴리스 게이트

- 자동 계약 체크리스트: 13/13에 직접 테스트 증거 존재.
- 전체 Python 회귀: 1,305개 수집, 1,300 passed, 5 skipped.
- 제품 코드 검사: Ruff `src tests` PASS, mypy 171개 source file PASS.
- 0.2.16 패키지 doctor: 17개 필수 항목 PASS(Windows, Python, SQLite FTS5, 앱 registry,
  Hello, wakeword, STT, Chrome 기록, 마이크, Supertonic/SAPI TTS와 필수 의존성).
  선택 개발 도구인 .NET SDK는 미설치 WARN이며 패키지 실행 필수 항목이 아니다.
- safe evaluation 재실행: 8 PASS, 7 NOT_RUN. 미실행 항목은 실제 앱 조작 3개와 snapshot VM
  공급자가 필요한 4개이며, 따라서 실제 시나리오 전체 완료는 아님.
- 0.2.16 package manifest와 Setup sidecar: PASS. manifest 1,870개 파일 검증 완료.
  Setup 크기 449,896,448 bytes, SHA-256
  `833de45711a8978fd337a460ba67991f647c417253226b63f5d01531a4e3e3dd`이며 독립 재계산값과
  sidecar가 일치한다. 휴대용 패키지의 doctor와 제품 서비스 구성 검사(`ready=true`, 등록 기능
  15개)는 PASS다. 0.2.16 Setup 자체 설치와 깨끗한 사용자 계정 최초 설치는 이번 점검에서
  실행하지 않았다.
- 0.2.16 배포 폴더에는 `NIM.txt`가 없고, 현재 운영 credential 원문의 exact-match 검색 결과는
  0건이다. 제품 자산의 `JAVIS`/`JARVIS` 잔존 명칭은 0건이며, 제3자 openWakeWord 패키지의
  원저자 메타데이터에만 `Jarvis` 문자열이 3개 파일에 남는다.
- 0.2.16 내장 `verify-package`는 version 0.2.16과 1,870개 파일을 `VERIFIED`로 반환했다.
  검증 전후 manifest SHA-256은 같고 배포 폴더 안 `state` 디렉터리는 전후 모두 0개다. 내장
  release audit은 package manifest와 Setup hash만 PASS, console·tray·Setup 서명 세 항목은
  `SIGNATURE_INVALID`로 거부해 `ready=false`를 반환했다.
- 2026-11-18에 원격 NIM으로 전송될 수 있는 문자열과 시험 API의 개인정보 금지 범위를 source
  README에 명시했다. 같은 날 여러 단계 재계획에 capability별 관측 허용표와 작업용 파일 handle을
  적용해 파일명·경로·컴퓨터 이름·PID·hash를 후속 planner context에서 제거했다. 최초 요청문에 사용자가
  직접 입력한 문자열은 여전히 원격 의도 판정·계획에 포함될 수 있다. 이 변경은 0.2.12 휴대용
  패키지와 Setup에 반영됐으며 패키지 안내문과 manifest 포함을 확인했다.
- console/tray/Setup Authenticode: FAIL(신뢰된 코드 서명 인증서 없음).
- 제한된 로컬 대화: 0.2.16 SOURCE·PACKAGE PASS. 자기소개·인사·기능 안내·감사·종료 인사는 원격
  의도 판정기와 계획기를 호출하지 않고 제품 소유 문구를 화면과 TTS로 전달하며, 실행 기능·스킬
  기록을 만들지 않는다. 실제 제품 서비스에서 기능 안내가
  `TASK_STARTED → CAPABILITY_OVERVIEW_DELIVERED → IDLE`, 화면 결과 4줄, `feedback=true`로
  완료되는 것을 확인했다.
- 호출어·헤더 UI 표기: 0.2.14 FIXED. 제품 설정의 `wakeword_mode`를 HUD에 전달해 현재 기본값
  `whisper_korean`은 `로컬 Whisper 한국어 인식`으로 표시한다. `openwakeword` 설정은
  `openWakeWord`로 표시하고, Hermes는 비교 실험용이며 제품 음성 경로에 미연결임을 유지한다.
  실제 800×570 렌더링에서 한글 제품 설명을 두 줄로 배치하고 우측 `SYSTEM // STANDBY`가
  잘리지 않음을 확인했다.
- Supertonic 3 모델 라이선스 번들: 0.2.14 PACKAGE PASS. 공식 OpenRAIL-M 전체 사본과 MIT
  파일의 역할을 구분한 제3자 고지가 source와 패키지에 있으며 두 파일 모두 package manifest에
  포함됐다. 0.2.11 package·Setup에는 두 파일이 없으므로 해당 과거 버전은 공개 배포 대상으로
  사용하지 않는다.
- benchmark: 70/120 실제 수집, snapshot VM 50셀 미수집.

자동 계약 13/13은 릴리스 안전 구조가 존재한다는 증거이지 논문 가설이나 실제 장치 성능의 증거가
아니다. 외부 서명 인증서, snapshot VM, 사용자 동의 장치 검증과 참가자 데이터가 남아 있다.
