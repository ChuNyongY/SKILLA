import pytest

from skilla_core import (
    AudioFrame,
    CaptureStatus,
    KoreanWakeVoicePipeline,
    VoicePipeline,
)


class FakeWakeDetector:
    def score(self, frame: AudioFrame) -> float:
        return 0.95 if frame.pcm_s16le.startswith(b"W") else 0.1


class FakeVad:
    def is_speech(self, frame: AudioFrame) -> bool:
        return not frame.pcm_s16le.startswith(b"S")


class FakeStt:
    def __init__(self, transcript: str = "스킬라 크롬 열어", *, fail: bool = False) -> None:
        self.transcript = transcript
        self.fail = fail
        self.captured: tuple[AudioFrame, ...] = ()

    def transcribe(self, frames: tuple[AudioFrame, ...]) -> str:
        self.captured = frames
        if self.fail:
            raise RuntimeError("injected")
        return self.transcript


def frame(marker: bytes) -> AudioFrame:
    return AudioFrame(pcm_s16le=marker + b"0")


def pipeline(stt: FakeStt, **limits: int) -> VoicePipeline:
    return VoicePipeline(
        FakeWakeDetector(),
        FakeVad(),
        stt,
        end_silence_frames=limits.get("end_silence_frames", 2),
        max_capture_frames=limits.get("max_capture_frames", 10),
    )


def test_non_wake_audio_is_ignored() -> None:
    voice = pipeline(FakeStt())
    assert voice.feed(frame(b"N")) is None
    assert not voice.is_capturing
    assert voice.diagnostics.frame_count == 1
    assert voice.diagnostics.speech_frame_count == 1
    assert voice.diagnostics.max_wake_confidence == 0.1
    assert not voice.diagnostics.wake_detected


def test_korean_pipeline_reports_live_input_level_and_silence() -> None:
    import struct

    voice = KoreanWakeVoicePipeline(FakeVad(), FakeStt())
    voice.feed(AudioFrame(pcm_s16le=struct.pack("<100h", *([2000] * 100))))
    quiet = voice.diagnostics.input_level
    voice.feed(AudioFrame(pcm_s16le=struct.pack("<100h", *([5000] * 100))))
    assert 0 < quiet < voice.diagnostics.input_level <= 1
    voice.feed(AudioFrame(pcm_s16le=b"\x00\x00" * 100))
    assert voice.diagnostics.input_level == 0


def test_wake_speech_and_silence_produce_transcript() -> None:
    stt = FakeStt()
    voice = pipeline(stt)

    assert voice.feed(frame(b"W")) is None
    assert voice.feed(frame(b"A")) is None
    assert voice.feed(frame(b"S")) is None
    result = voice.feed(frame(b"S"))

    assert result is not None
    assert result.status is CaptureStatus.TRANSCRIBED
    assert result.transcript == "스킬라 크롬 열어"
    assert len(stt.captured) == 2
    assert not voice.is_capturing


def test_capture_buffer_is_bounded() -> None:
    voice = pipeline(FakeStt(), end_silence_frames=2, max_capture_frames=3)
    voice.feed(frame(b"W"))
    voice.feed(frame(b"A"))
    result = voice.feed(frame(b"A"))

    assert result is not None
    assert result.status is CaptureStatus.ABORTED
    assert result.reason == "MAX_CAPTURE_FRAMES_EXCEEDED"


def test_stt_failure_resets_pipeline() -> None:
    voice = pipeline(FakeStt(fail=True), end_silence_frames=1)
    voice.feed(frame(b"W"))
    result = voice.feed(frame(b"S"))

    assert result is not None
    assert result.status is CaptureStatus.ABORTED
    assert result.reason == "STT_FAILED"
    assert not voice.is_capturing


def test_manual_cancel_discards_audio_without_transcription() -> None:
    stt = FakeStt()
    voice = pipeline(stt)
    voice.feed(frame(b"W"))
    assert voice.is_capturing

    voice.cancel()

    assert not voice.is_capturing
    assert stt.captured == ()
    assert voice.diagnostics.frame_count == 0


def test_cancel_can_preserve_privacy_minimized_diagnostics() -> None:
    voice = pipeline(FakeStt())
    voice.feed(frame(b"N"))

    voice.cancel(reset_diagnostics=False)

    assert not voice.is_capturing
    assert voice.diagnostics.frame_count == 1
    assert voice.diagnostics.speech_frame_count == 1
    assert voice.diagnostics.max_wake_confidence == 0.1


class SequencedStt:
    def __init__(self, *transcripts: str) -> None:
        self._transcripts = iter(transcripts)
        self.calls = 0

    def transcribe(self, _frames: tuple[AudioFrame, ...]) -> str:
        self.calls += 1
        return next(self._transcripts)


def korean_pipeline(
    stt: SequencedStt,
    *,
    armed_timeout_frames: int = 10,
) -> KoreanWakeVoicePipeline:
    return KoreanWakeVoicePipeline(
        FakeVad(),
        stt,
        end_silence_frames=1,
        max_capture_frames=10,
        armed_timeout_frames=armed_timeout_frames,
    )


def test_korean_wake_and_command_in_one_utterance() -> None:
    stt = SequencedStt("스킬라, 내 컴퓨터 시스템 정보를 확인해 줘")
    voice = korean_pipeline(stt)

    assert voice.feed(frame(b"A")) is None
    assert voice.feed(frame(b"A")) is None
    result = voice.feed(frame(b"S"))

    assert result is not None
    assert result.status is CaptureStatus.TRANSCRIBED
    assert result.transcript == "내 컴퓨터 시스템 정보를 확인해 줘"
    assert result.wake_confidence == 1.0
    assert stt.calls == 1


def test_korean_wake_only_arms_next_utterance() -> None:
    stt = SequencedStt("스 킬 라", "시스템 정보를 확인해 줘")
    voice = korean_pipeline(stt)

    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    assert voice.feed(frame(b"S")) is None
    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    result = voice.feed(frame(b"S"))

    assert result is not None
    assert result.transcript == "시스템 정보를 확인해 줘"
    assert stt.calls == 2


def test_korean_unaddressed_speech_is_transcribed_once_and_ignored() -> None:
    stt = SequencedStt("오늘 날씨가 좋다")
    voice = korean_pipeline(stt)

    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    assert voice.feed(frame(b"S")) is None

    assert stt.calls == 1
    assert not voice.is_capturing


def test_bare_confirmation_is_forwarded_only_while_review_is_active() -> None:
    voice = korean_pipeline(SequencedStt("네", "네", "네"))

    def utterance():
        voice.feed(frame(b"A"))
        voice.feed(frame(b"A"))
        return voice.feed(frame(b"S"))

    assert utterance() is None
    voice.set_review_active(True)
    result = utterance()
    assert result is not None and result.transcript == "네"
    voice.set_review_active(False)
    assert utterance() is None


def test_entering_review_discards_an_in_progress_command_utterance() -> None:
    stt = SequencedStt("예")
    voice = korean_pipeline(stt)

    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    assert voice.is_capturing

    voice.set_review_active(True)

    assert not voice.is_capturing
    assert voice.diagnostics.recognition_reason == "REVIEW_WAITING"
    assert stt.calls == 0
    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    result = voice.feed(frame(b"S"))
    assert result is not None
    assert result.transcript == "예"
    assert stt.calls == 1


def test_korean_exact_stop_is_available_without_wake_word() -> None:
    voice = korean_pipeline(SequencedStt("멈춰"))

    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    result = voice.feed(frame(b"S"))

    assert result is not None
    assert result.transcript == "멈춰"


def test_korean_wake_arm_expires_before_later_unaddressed_speech() -> None:
    stt = SequencedStt("스킬라", "시스템 정보를 확인해 줘")
    voice = korean_pipeline(stt, armed_timeout_frames=2)

    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    assert voice.feed(frame(b"S")) is None
    assert voice.feed(frame(b"S")) is None
    assert voice.feed(frame(b"S")) is None
    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))

    assert voice.feed(frame(b"S")) is None


def test_korean_single_noise_spike_does_not_start_transcription() -> None:
    stt = SequencedStt("수고하셨습니다")
    voice = korean_pipeline(stt)

    assert voice.feed(frame(b"A")) is None
    assert voice.feed(frame(b"S")) is None

    assert stt.calls == 0
    assert not voice.is_capturing


def test_korean_one_character_wake_typo_is_accepted_and_reported() -> None:
    voice = korean_pipeline(SequencedStt("스킬나 시스템 정보 알려줘"))

    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    result = voice.feed(frame(b"S"))

    assert result is not None
    assert result.transcript == "시스템 정보 알려줘"
    assert voice.diagnostics.last_transcript == "스킬나 시스템 정보 알려줘"
    assert voice.diagnostics.recognition_reason == "COMMAND_RECOGNIZED"


def test_korean_unrelated_word_is_not_treated_as_fuzzy_wake_word() -> None:
    voice = korean_pipeline(SequencedStt("서비스 시스템 정보 알려줘"))

    voice.feed(frame(b"A"))
    voice.feed(frame(b"A"))
    assert voice.feed(frame(b"S")) is None

    assert voice.diagnostics.last_transcript == "서비스 시스템 정보 알려줘"
    assert voice.diagnostics.recognition_reason == "WAKE_WORD_NOT_FOUND"


@pytest.mark.parametrize("transcript", ["스킬 시스템 정보 알려줘", "스키라 시스템 정보 알려줘"])
def test_korean_unlisted_near_wake_words_do_not_activate(transcript: str) -> None:
    voice = korean_pipeline(SequencedStt(transcript))

    voice.feed(frame(b"A"))
    voice.feed(frame(b"B"))
    assert voice.feed(frame(b"S")) is None
    assert voice.diagnostics.recognition_reason == "WAKE_WORD_NOT_FOUND"
