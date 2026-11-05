# 음성 출력 경계

## 2026-11-05 변경

사용자 요청에 따라 소스 실행 제품의 기본 출력기를 `SupertonicTtsRunner`로 변경했다.
Edge 음성은 제품 조립 경로에서 제거했다. `sherpa-onnx 1.13.8`과 프로젝트의
`models/supertonic3`에 고정한 Supertonic 3 int8 모델로 한국어를 CPU에서 생성한다.
API 호출이나 음성의 외부 전송은 없다. 모델은 SHA-256 manifest로 검사되고 Windows 패키지에 포함된다.
모델 실행기는 한 번만 메모리에 올린 뒤 다음 문장에서도 재사용한다.
생성 실패 시 Windows SAPI를 예비 경로로 유지한다. 실행 중인 제품은 재시작해야 변경을 적용한다.

`output/supertonic_portable_smoke_1.wav`과 `output/supertonic_portable_smoke_2.wav`의 실제 한국어
생성과 PCM WAV 검사를 통과했다. 같은 실행에서 각각 1.830초와 0.603초가 걸렸다.
이번 작업에서는 스피커 자동 재생과 사람 대상 자연스러움 평가는 수행하지 않았다.
아래 Edge 설명은 이전 구성 기록이며 현재 기본 출력기를 뜻하지 않는다.

2026-10-30부터 실제 제품 실행은 무료 Microsoft Edge 한국어 신경망 음성
`ko-KR-SunHiNeural`을 우선 사용한다. 이 방식은 API 키나 사용료가 없지만 인터넷 연결이 필요하며,
출력할 고정 문장이 Microsoft 음성 서비스로 전송된다. 서비스 또는 인터넷 연결이 실패하면 기존
Windows SAPI 로컬 음성으로 자동 전환한다. 설치는
`packaging/install_free_neural_tts.ps1`에서 재현할 수 있다.

자연스러운 완전 로컬 후보인 Qwen3-TTS도 검토하고 별도 환경에 설치했지만, 이 PC의 Windows
응용 프로그램 제어 정책이 필수 `torch.dll`을 차단해 실행하지 않았다. 제품을 위해 보안 정책을
해제하지 않았으며, 현재 제품 경로에는 Qwen이나 PyTorch를 포함하지 않는다.

현재 Heami 품질 평가와 Piper·Kokoro·Supertonic 3 비교, 격리 CPU 측정 및 채택 기준은
[한국어 로컬 TTS 후보 감사](TTS_CANDIDATE_AUDIT.md)에 있다.

SKILLA의 대체 TTS 구현은 Windows SAPI를 별도 Python worker process에서 호출한다. SAPI로
전환된 경우 텍스트는 네트워크나 NIM으로 보내지 않으며, worker에는 `speak` 또는 `render_wav`의
strict JSON 요청만 전달한다. 어느 출력기를 사용해도 이 모듈은 응답 문장 생성기가 아니라 이미
확정된 짧은 문장을 음성으로 출력하는 제한된 sink다.

## 안전 계약

- 입력 텍스트는 1~500자이며 NUL을 거부한다.
- 속도는 -5~5, 음량은 0~100으로 제한한다.
- worker는 고정된 `python -I -m skilla_core.tts_worker` 명령, `shell=False`, 최소 환경으로 실행한다.
- 요청·응답은 각각 8 KiB, 실행은 최대 30초로 제한하며 stderr와 내부 예외는 외부에 내보내지 않는다.
- JSON duplicate key, NaN/Infinity, extra field와 타입 coercion을 거부한다.
- SAPI `Speak`에는 plain-text 플래그를 사용해 XML/SSML 해석을 비활성화한다.
- `probe` 연산은 텍스트 없이 `SAPI.SpVoice` COM 객체 생성만 확인하며 소리나 파일을 만들지 않는다.
- WAV 출력은 주입된 절대 allowed root 아래의 새 `.wav` 파일만 허용하고 symlink와 기존 파일을
  거부한다.
- parent가 worker 응답을 신뢰하지 않고 파일 identity, 크기, SHA-256 및 WAV 구조를 다시 확인한다.
- 시작 전 이미 set된 전역 cancellation token은 SAPI 호출 전에 중단한다. 실행 중에는 10~250ms로
  제한된 poll 간격마다 같은 token을 확인하고, 취소 시 child를 terminate한 뒤 1초 내 끝나지 않으면
  kill한다. 취소·timeout·비정상 응답에 남은 부분 WAV는 제거한다.

## 실제 검증 범위

2026-10-30 현재 PC에서 Edge TTS 7.3.1로 고정 문장을 MP3로 생성하고, 설치된 ffmpeg로 mono
24,000 Hz PCM WAV로 변환한 뒤 Windows `winsound`로 실제 스피커 재생했다. 생성·변환·재생 통합
시험과 신경망 음성 성공/실패/취소 시 대체 경로 단위 시험을 통과했다. 음성 파일은 매 호출마다
`state/natural-tts` 아래에 임시로 만들고 재생 후 삭제한다. 이 검증은 동작 여부를 확인한 것이며,
사람 대상 자연스러움 비교 점수를 새로 측정한 것은 아니다.

2026-09-22 현재 PC에서 네트워크와 스피커 출력을 사용하지 않고 `render_wav`를 실행했다.
최초 worker 경계에서 136,936바이트, 실행 중 취소 지원을 추가한 뒤 172,424바이트 WAV를 생성했고,
parent의 SHA-256 길이·파일 metadata·WAV frame 검사가 모두 통과했다. 별도 실제 worker 취소 smoke는
10ms 후 token을 set해 stable cancellation 오류를 반환했고 부분 WAV와 고아 worker를 남기지 않았다.
이 smoke는 SAPI IPC, STOP 및 파일 검증 경계를 확인하지만 한국어 발음 자연스러움,
실제 스피커 재생, 음량 안전성 또는 접근성 품질을 입증하지 않는다.

당시 고정 성공 feedback인 `요청한 작업을 확인하고 완료했습니다.`도 별도로 렌더링했다. 결과는
154,344바이트, mono 16-bit, 22,050 Hz, 77,149 frame(3.499초) WAV였고 동일한 parent 검증을
통과했다. 이는 한국어 코드 경로와 비어 있지 않은 audio frame만 확인하며 사람이 들은 발음
품질 평가는 아니다.

`speak`는 실제 소리를 발생시키므로 자동 회귀검증에서는 호출하지 않는다. 사용자 참여형 검증은
짧은 고정 문장, 사전 안내, 즉시 STOP 수단을 갖춘 상태에서 별도로 수행해야 한다.

`VoiceFeedbackPresenter`는 plan 준비, 검증 완료, 안전 중단, 승인 필요, 취소, 실패의 여섯 상태만
고정 한국어 문장으로 바꾼다. `TaskOutcome.reason`, 사용자 발화, NIM 응답, 경로 또는 내부 오류는
읽지 않는다. 같은 shared cancellation token을 TTS sink에 전달하므로 STOP이 feedback worker도
종료한다. 자유 형식 대화 응답을 생성하거나 읽는 기능은 이 경계에 포함되지 않는다.

2026-10-16에는 사용자 3/5 평가에서 지적된 번역기 같은 말투를 줄이기 위해 문장을 짧은 해요체로
바꿨다. `작업 순서를 정했어요.`, `작업을 마쳤고, 결과도 확인했어요.`, `안전을 위해 여기서
멈췄어요.`, `계속하려면 화면에서 승인해 주세요.`, `작업을 취소했어요.`, `작업을 마치지 못했어요.`
여섯 문장만 허용한다. 정책 차단·잘못된 승인 같은 안전 중단과 일반 실행 실패도 서로 다른 문장으로
구분한다. 이 수정은 문구와 상태 매핑 개선이며, 새 문장의 음성 자연스러움 향상은 실제 청취 재평가
전까지 입증된 것으로 기록하지 않는다.

새 여섯 문장은 스피커를 사용하지 않는 실제 SAPI `render_wav`로 다시 검증했다. 모두 mono 16-bit,
22,050 Hz이고 50,256~87,405개의 비어 있지 않은 frame을 가졌다. 각 파일의 실제 크기와 SHA-256이
worker 응답과 일치했다. 유효 파일은 `output/tts-natural-copy-smoke-20261016-r2`에 있으며, 응답
필드 이름을 잘못 사용해 첫 파일 뒤 중단된 실행은
`output/archive-incomplete-tts-natural-copy-smoke-20261016-response-field-mismatch`로 분리했다.
WAV 생성 성공은 문구가 자연스럽게 들린다는 사람 평가를 대신하지 않는다.

배포 전 `skilla doctor`는 5초 제한 worker에서 이 `probe`를 실행한다. 실패는 내부 COM 예외나
경로를 내보내지 않고 `tts.sapi` / `SAPI_UNAVAILABLE`로만 보고한다.
