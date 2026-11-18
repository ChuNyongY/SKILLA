# SKILLA 로컬 모델 라이선스·배포 사전 조사

상태: 공식 자료 조사와 현재 패키지 감사, source 라이선스 번들 보완, 모델·설치본 미변경

작성일: 2026-11-18

이 문서는 법률 자문이 아니라 공식 저장소와 모델 카드에 표시된 라이선스 및 현재 SKILLA 패키지의
고지 파일을 비교한 기술 감사다. 실제 공개 배포 전에는 최종 선택 모델의 전체 라이선스와 의존성
고지를 다시 확인해야 한다.

## 후보별 확인 결과

| 구성요소 | 공식 표시 | 현재 판단 |
|---|---|---|
| Qwen3.5-4B weights | Apache-2.0 | 로컬 대화 후보. 실제 포함할 정확한 weight·quantization 출처와 hash를 별도 고정 |
| Qwen3-4B-Instruct-2507 weights | Apache-2.0 | 보수적 대화 후보. 공식 weight를 기준으로 변환·검증할 수 있음 |
| llama.cpp | MIT | Windows 로컬 실행기 후보. 배포 binary의 정확한 commit과 license 포함 필요 |
| Supertonic 3 sample code | MIT | 코드 라이선스이며 모델 라이선스를 대신하지 않음 |
| Supertonic 3 model weights | OpenRAIL-M | 사용 제한과 재배포 고지 의무가 있는 현재 TTS 모델 |
| MOSS-TTS-Nano source·weights·ONNX | Apache-2.0 표시 | 차기 TTS 비교 후보. ONNX는 companion audio tokenizer까지 정확한 파일 목록 필요 |
| MeloTTS source | MIT | source 라이선스만 확인. 한국어 weight와 포함 의존성의 조건을 별도 확인하기 전 번들 금지 |
| CosyVoice source | Apache-2.0 | source 라이선스만 확인. 선택 checkpoint의 모델 카드·weight 조건 별도 확인 필요 |

Apache-2.0 또는 MIT라고 표시된 프로젝트라도 제3자가 만든 GGUF·ONNX·checkpoint는 원본과 같은
출처라고 자동으로 가정하지 않는다. 실제 설치본에는 다운로드 URL, commit 또는 revision, 파일
SHA-256, 원본·변환 주체, 전체 license·NOTICE를 함께 고정해야 한다.

## 현재 Supertonic 3 패키지 감사

0.2.11 배포 폴더와 보완 전 source에서 다음을 확인했다.

- `models/supertonic3/README.md`: sample code는 MIT, model은 OpenRAIL-M이라고 안내하고 공식
  모델 라이선스 URL을 연결
- `models/supertonic3/LICENSE`: MIT License와 2025 Supertone copyright만 포함
- `models/supertonic3/manifest.json`: sherpa-onnx 변환 archive URL과 model file hash는 기록
- 0.2.11 `package-manifest.json`: `models/supertonic3/LICENSE` 한 개만 model license 파일로 포함
- 배포 폴더에서 OpenRAIL-M 전체 원문 파일은 확인되지 않음

공식 OpenRAIL-M 원문은 모델을 배포할 때 수령자에게 라이선스 사본을 제공하고 저작권·특허·상표·귀속
고지를 유지하도록 규정한다. README의 외부 링크만으로 전체 사본 포함 요건을 충족했다고 판정하지
않는다. 따라서 현재 0.2.11은 실행·시험 결과와 별개로 `모델 라이선스 번들` 릴리스 게이트가 미통과다.

2026-11-18 source에는 공식 모델 저장소에서 받은 전체 원문을
`LICENSE.MODEL-OpenRAIL-M.txt`로 추가하고, 기존 `LICENSE`가 MIT sample-code 고지임을 구분하는
`THIRD_PARTY_NOTICE.SKILLA.txt`를 추가했다. Windows package builder는 `models/supertonic3` 전체를
복사한 뒤 package manifest를 생성하므로 다음 빌드에서는 두 파일도 자동으로 복사·해시된다. 이 source
상태와 이미 만들어진 0.2.11 Setup의 상태는 구분한다.

## 다음 패키지 전 필수 조치

1. 공식 Supertonic 3 모델 저장소의 OpenRAIL-M 전체 원문을 별도 이름으로 포함
2. 현재 MIT 파일을 sample code 또는 변환 archive 고지로 명확히 구분
3. `THIRD_PARTY_NOTICES`에 모델명, 원본 URL, 변환 archive URL, 두 라이선스의 역할을 표시
4. package manifest에서 두 라이선스 파일과 notice의 SHA-256을 확인
5. 설치 후 오프라인 상태에서도 사용자가 전체 라이선스를 열 수 있는지 확인
6. Setup과 portable 폴더 모두 같은 고지를 포함하는지 검사
7. OpenRAIL-M Attachment A의 사용 제한을 제품 이용 안내에 반영

현재 0.2.11 Setup은 OpenRAIL-M 원문과 제3자 고지가 들어 있지 않으므로 공개 배포 적합으로 판정하지
않는다. source 보완은 완료했지만 모델 교체·재패키징·설치는 하지 않았다.

## 새 로컬 대화 모델 도입 절차

1. 공식 모델 카드와 정확한 revision 선택
2. 원본 weight license·NOTICE 저장
3. GGUF가 제3자 변환이면 변환 저장소의 작성자·revision·hash·고지를 추가 확인
4. 가능하면 공식 weight에서 고정된 llama.cpp commit으로 직접 변환해 재현 기록 생성
5. llama.cpp binary license와 build commit 포함
6. 설치본 용량과 선택 다운로드 여부 결정
7. clean PC에서 모델 hash·license·실행 binary 일치 검증

Qwen3.5-4B는 공식 Hugging Face 저장소가 Apache-2.0으로 표시되지만, 현재 조사 문서에서 가정한 Q4
GGUF 자체가 공식 배포물인지 별도로 입증되지 않았다. 따라서 성능시험 전에 exact artifact를 먼저
정해야 한다. Qwen3-4B-Instruct-2507도 같은 원칙을 적용한다.

## TTS 후보 도입 절차

- MOSS-TTS-Nano ONNX는 TTS model만으로 끝나지 않고 companion audio tokenizer가 필요하므로 두
  저장소의 파일·라이선스·hash를 하나의 bundle로 검증
- MeloTTS는 source MIT만 보고 weight 재배포를 결정하지 않음
- CosyVoice는 source Apache-2.0과 선택 checkpoint 조건을 분리해 확인
- 음성 복제 기능은 별도 동의·생체정보·오용 경계가 필요하므로 현재 비교에서 제외

## 공식 근거

- Qwen3.5-4B: https://huggingface.co/Qwen/Qwen3.5-4B
- Qwen3-4B-Instruct-2507: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- llama.cpp license: https://github.com/ggml-org/llama.cpp/blob/master/LICENSE
- Supertonic 3 model card: https://huggingface.co/Supertone/supertonic-3
- Supertonic 3 OpenRAIL-M: https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE
- MOSS-TTS-Nano: https://github.com/OpenMOSS/MOSS-TTS-Nano
- MOSS-TTS-Nano ONNX: https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX
- MeloTTS source license: https://github.com/myshell-ai/MeloTTS/blob/main/LICENSE
- CosyVoice source license: https://github.com/QwenAudio/CosyVoice/blob/main/LICENSE

## 결론

로컬 대화 모델은 Qwen Apache-2.0 계열과 llama.cpp MIT 조합이 배포 검토에 비교적 단순하다. TTS는
현재 Supertonic의 실행 안정성과 다음 빌드용 source 고지는 확보했지만 OpenRAIL-M 원문이 기존
0.2.11 설치본에는 포함되지 않아 해당 설치본의 공개 배포 게이트를 통과시키면 안 된다. MOSS는
Apache-2.0과 경량 ONNX 측면에서 다음 비교
후보지만 실제 한국어 품질과 companion tokenizer bundle을 함께 검증해야 한다.
