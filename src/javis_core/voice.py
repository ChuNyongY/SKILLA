from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from .models import FrozenModel


class AudioFrame(FrozenModel):
    pcm_s16le: bytes = Field(min_length=2, repr=False)
    sample_rate: int = Field(default=16_000, ge=8_000, le=48_000)
    channels: int = Field(default=1, ge=1, le=2)


class CaptureStatus(StrEnum):
    TRANSCRIBED = "TRANSCRIBED"
    ABORTED = "ABORTED"


class VoiceCaptureResult(FrozenModel):
    status: CaptureStatus
    transcript: str | None = None
    wake_confidence: float = Field(ge=0.0, le=1.0)
    frame_count: int = Field(ge=0)
    reason: str


class VoicePipelineDiagnostics(FrozenModel):
    """Privacy-minimized counters for diagnosing an unfinished capture."""

    frame_count: int = Field(ge=0)
    speech_frame_count: int = Field(ge=0)
    max_wake_confidence: float = Field(ge=0.0, le=1.0)
    wake_detected: bool
    last_transcript: str | None = Field(default=None, max_length=200)
    recognition_reason: str = Field(default="WAITING", pattern=r"^[A-Z_]{2,40}$")


class WakeWordDetector(Protocol):
    def score(self, frame: AudioFrame) -> float: ...


class VoiceActivityDetector(Protocol):
    def is_speech(self, frame: AudioFrame) -> bool: ...


class SpeechToText(Protocol):
    def transcribe(self, frames: tuple[AudioFrame, ...]) -> str: ...


class VoicePipeline:
    """Bounded wake/VAD/STT state machine with no microphone or network dependency."""

    def __init__(
        self,
        wake_detector: WakeWordDetector,
        vad: VoiceActivityDetector,
        stt: SpeechToText,
        *,
        wake_threshold: float = 0.75,
        end_silence_frames: int = 5,
        max_capture_frames: int = 1_500,
    ) -> None:
        if not 0.0 <= wake_threshold <= 1.0:
            raise ValueError("wake_threshold must be between 0 and 1")
        if end_silence_frames < 1 or max_capture_frames < end_silence_frames:
            raise ValueError("invalid voice capture limits")
        self._wake_detector = wake_detector
        self._vad = vad
        self._stt = stt
        self._wake_threshold = wake_threshold
        self._end_silence_frames = end_silence_frames
        self._max_capture_frames = max_capture_frames
        self._frames: list[AudioFrame] = []
        self._silence_frames = 0
        self._wake_confidence = 0.0
        self._diagnostic_frame_count = 0
        self._diagnostic_speech_frame_count = 0
        self._diagnostic_max_wake_confidence = 0.0
        self._diagnostic_wake_detected = False
        self._last_transcript: str | None = None
        self._recognition_reason = "WAITING"

    @property
    def is_capturing(self) -> bool:
        return bool(self._frames)

    @property
    def diagnostics(self) -> VoicePipelineDiagnostics:
        return VoicePipelineDiagnostics(
            frame_count=self._diagnostic_frame_count,
            speech_frame_count=self._diagnostic_speech_frame_count,
            max_wake_confidence=self._diagnostic_max_wake_confidence,
            wake_detected=self._diagnostic_wake_detected,
            last_transcript=self._last_transcript,
            recognition_reason=self._recognition_reason,
        )

    def feed(self, frame: AudioFrame) -> VoiceCaptureResult | None:
        speech = self._vad.is_speech(frame)
        self._diagnostic_frame_count += 1
        if speech:
            self._diagnostic_speech_frame_count += 1
        if not self.is_capturing:
            wake_confidence = self._wake_detector.score(frame)
            self._diagnostic_max_wake_confidence = max(
                self._diagnostic_max_wake_confidence,
                wake_confidence,
            )
            if not speech or wake_confidence < self._wake_threshold:
                return None
            self._frames.append(frame)
            self._wake_confidence = wake_confidence
            self._diagnostic_wake_detected = True
            return None

        self._frames.append(frame)
        self._silence_frames = 0 if speech else self._silence_frames + 1
        if len(self._frames) >= self._max_capture_frames:
            return self._finish(
                CaptureStatus.ABORTED,
                transcript=None,
                reason="MAX_CAPTURE_FRAMES_EXCEEDED",
            )
        if self._silence_frames < self._end_silence_frames:
            return None

        captured = tuple(self._frames[: -self._silence_frames])
        try:
            transcript = self._stt.transcribe(captured).strip()
        except Exception:
            return self._finish(
                CaptureStatus.ABORTED,
                transcript=None,
                reason="STT_FAILED",
            )
        if not transcript:
            return self._finish(
                CaptureStatus.ABORTED,
                transcript=None,
                reason="EMPTY_TRANSCRIPT",
            )
        return self._finish(
            CaptureStatus.TRANSCRIBED,
            transcript=transcript,
            reason="UTTERANCE_COMPLETE",
        )

    def cancel(self, *, reset_diagnostics: bool = True) -> None:
        self._reset()
        if reset_diagnostics:
            self._reset_diagnostics()

    def _finish(
        self,
        status: CaptureStatus,
        *,
        transcript: str | None,
        reason: str,
    ) -> VoiceCaptureResult:
        result = VoiceCaptureResult(
            status=status,
            transcript=transcript,
            wake_confidence=self._wake_confidence,
            frame_count=len(self._frames),
            reason=reason,
        )
        self._reset()
        self._reset_diagnostics()
        return result

    def _reset(self) -> None:
        self._frames.clear()
        self._silence_frames = 0
        self._wake_confidence = 0.0

    def _reset_diagnostics(self) -> None:
        self._diagnostic_frame_count = 0
        self._diagnostic_speech_frame_count = 0
        self._diagnostic_max_wake_confidence = 0.0
        self._diagnostic_wake_detected = False


_KOREAN_WAKE_PREFIX = re.compile(
    r"^\s*\uc2a4\s*\ud0ac\s*\ub77c(?:\uc57c)?"
    r"(?:\s|[,\uff0c.!?\u2026:;~\-])*(.*)$",
    re.DOTALL,
)
_LOCAL_STOP_PHRASES = frozenset(
    {
        "\uba48\ucdb0",
        "\ucde8\uc18c",
        "\uc911\uc9c0",
        "\uc2a4\ud0ac\ub77c \uc2a4\ud1b1",
        "\uc2a4\ud0ac\ub77c \uba48\ucdb0",
    }
)


class KoreanWakeVoicePipeline:
    """Transcribe complete utterances and route only Korean wake-word commands.

    Unlike a frame-scoring wake model, Whisper needs a complete speech segment.  This
    pipeline therefore performs VAD first, transcribes once at the end of the segment,
    and then checks the Korean wake prefix.  A wake-only utterance arms the following
    utterance for a bounded time, so a wake word and command may be spoken either
    together or with a short pause between them.
    """

    def __init__(
        self,
        vad: VoiceActivityDetector,
        stt: SpeechToText,
        *,
        end_silence_frames: int = 5,
        max_capture_frames: int = 1_500,
        armed_timeout_frames: int = 125,
        start_speech_frames: int = 2,
    ) -> None:
        if (
            end_silence_frames < 1
            or max_capture_frames < end_silence_frames
            or armed_timeout_frames < end_silence_frames
            or not 2 <= start_speech_frames <= 10
        ):
            raise ValueError("invalid Korean voice capture limits")
        self._vad = vad
        self._stt = stt
        self._end_silence_frames = end_silence_frames
        self._max_capture_frames = max_capture_frames
        self._armed_timeout_frames = armed_timeout_frames
        self._start_speech_frames = start_speech_frames
        self._speech_start: list[AudioFrame] = []
        self._frames: list[AudioFrame] = []
        self._silence_frames = 0
        self._armed_remaining = 0
        self._diagnostic_frame_count = 0
        self._diagnostic_speech_frame_count = 0
        self._diagnostic_max_wake_confidence = 0.0
        self._diagnostic_wake_detected = False
        self._last_transcript: str | None = None
        self._recognition_reason = "WAITING"

    @property
    def is_capturing(self) -> bool:
        return bool(self._frames)

    @property
    def diagnostics(self) -> VoicePipelineDiagnostics:
        return VoicePipelineDiagnostics(
            frame_count=self._diagnostic_frame_count,
            speech_frame_count=self._diagnostic_speech_frame_count,
            max_wake_confidence=self._diagnostic_max_wake_confidence,
            wake_detected=self._diagnostic_wake_detected,
            last_transcript=self._last_transcript,
            recognition_reason=self._recognition_reason,
        )

    def feed(self, frame: AudioFrame) -> VoiceCaptureResult | None:
        if frame.sample_rate != 16_000 or frame.channels != 1:
            raise ValueError("Korean voice recognition requires mono 16 kHz PCM")
        speech = self._vad.is_speech(frame)
        self._diagnostic_frame_count += 1
        if speech:
            self._diagnostic_speech_frame_count += 1

        if self._armed_remaining and not self._frames:
            self._armed_remaining -= 1

        if not self._frames:
            if speech:
                self._speech_start.append(frame)
                if len(self._speech_start) >= self._start_speech_frames:
                    self._frames.extend(self._speech_start)
                    self._speech_start.clear()
                    self._silence_frames = 0
                    self._last_transcript = None
                    self._recognition_reason = "LISTENING"
            else:
                self._speech_start.clear()
            if not speech and self._armed_remaining == 0:
                self._diagnostic_wake_detected = False
            return None

        self._frames.append(frame)
        self._silence_frames = 0 if speech else self._silence_frames + 1
        if len(self._frames) >= self._max_capture_frames:
            return self._complete_utterance(tuple(self._frames), "MAX_CAPTURE_FRAMES")
        if self._silence_frames < self._end_silence_frames:
            return None
        spoken = tuple(self._frames[: -self._silence_frames])
        return self._complete_utterance(spoken, "UTTERANCE_COMPLETE")

    def cancel(self, *, reset_diagnostics: bool = True) -> None:
        self._reset_utterance()
        self._armed_remaining = 0
        if reset_diagnostics:
            self._reset_diagnostics()
            self._last_transcript = None
            self._recognition_reason = "WAITING"

    def _complete_utterance(
        self,
        frames: tuple[AudioFrame, ...],
        completion_reason: str,
    ) -> VoiceCaptureResult | None:
        was_armed = self._armed_remaining > 0
        frame_count = len(self._frames)
        self._reset_utterance()
        self._recognition_reason = "TRANSCRIBING"
        try:
            transcript = self._stt.transcribe(frames).strip()
        except Exception:
            self._recognition_reason = "STT_FAILED"
            if was_armed:
                self._armed_remaining = 0
                return self._result(
                    CaptureStatus.ABORTED,
                    None,
                    frame_count,
                    "STT_FAILED",
                )
            self._reset_diagnostics()
            return None
        self._last_transcript = _visible_transcript(transcript)
        if not transcript:
            self._recognition_reason = "EMPTY_TRANSCRIPT"
            if was_armed:
                self._armed_remaining = 0
                return self._result(
                    CaptureStatus.ABORTED,
                    None,
                    frame_count,
                    "EMPTY_TRANSCRIPT",
                )
            self._reset_diagnostics()
            return None

        wake_found, command = _split_korean_wake_command(transcript)
        if was_armed:
            self._armed_remaining = 0
            if wake_found and not command:
                self._recognition_reason = "WAKE_WORD_DETECTED"
                self._arm()
                return None
            self._recognition_reason = "COMMAND_RECOGNIZED"
            return self._result(
                CaptureStatus.TRANSCRIBED,
                command if wake_found else transcript,
                frame_count,
                completion_reason,
            )
        if _normalize_local_phrase(transcript) in _LOCAL_STOP_PHRASES:
            self._recognition_reason = "LOCAL_STOP_RECOGNIZED"
            return self._result(
                CaptureStatus.TRANSCRIBED,
                transcript,
                frame_count,
                completion_reason,
            )
        if not wake_found:
            self._recognition_reason = "WAKE_WORD_NOT_FOUND"
            self._reset_diagnostics()
            return None
        if not command:
            self._recognition_reason = "WAKE_WORD_DETECTED"
            self._arm()
            return None
        self._recognition_reason = "COMMAND_RECOGNIZED"
        return self._result(
            CaptureStatus.TRANSCRIBED,
            command,
            frame_count,
            completion_reason,
        )

    def _arm(self) -> None:
        self._armed_remaining = self._armed_timeout_frames
        self._diagnostic_max_wake_confidence = 1.0
        self._diagnostic_wake_detected = True

    def _result(
        self,
        status: CaptureStatus,
        transcript: str | None,
        frame_count: int,
        reason: str,
    ) -> VoiceCaptureResult:
        result = VoiceCaptureResult(
            status=status,
            transcript=transcript,
            wake_confidence=1.0,
            frame_count=frame_count,
            reason=reason,
        )
        self._reset_diagnostics()
        return result

    def _reset_utterance(self) -> None:
        self._speech_start.clear()
        self._frames.clear()
        self._silence_frames = 0

    def _reset_diagnostics(self) -> None:
        self._diagnostic_frame_count = 0
        self._diagnostic_speech_frame_count = 0
        self._diagnostic_max_wake_confidence = 0.0
        self._diagnostic_wake_detected = False


def _split_korean_wake_command(transcript: str) -> tuple[bool, str]:
    normalized = unicodedata.normalize("NFKC", transcript).strip()
    match = _KOREAN_WAKE_PREFIX.fullmatch(normalized)
    if match is not None:
        return True, match.group(1).strip()
    token_match = re.match(r"^\s*([^\s,\uff0c.!?\u2026:;~\-]+)(.*)$", normalized, re.DOTALL)
    if token_match is None:
        return False, normalized
    token = token_match.group(1)
    if token[:1] != "\uc2a4" or not any(
        _edit_distance_at_most_one(token, wake)
        for wake in ("\uc2a4\ud0ac\ub77c",)
    ):
        return False, normalized
    command = token_match.group(2).lstrip(" \t,\uff0c.!?\u2026:;~-").strip()
    return True, command


def _normalize_local_phrase(transcript: str) -> str:
    normalized = unicodedata.normalize("NFKC", transcript).casefold()
    characters = (
        " " if unicodedata.category(character)[0] in {"P", "Z"} else character
        for character in normalized
    )
    return " ".join("".join(characters).split())


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right, strict=True)) <= 1
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    mismatch = 0
    short_index = 0
    for character in longer:
        if short_index < len(shorter) and character == shorter[short_index]:
            short_index += 1
        else:
            mismatch += 1
            if mismatch > 1:
                return False
    return True


def _visible_transcript(transcript: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", transcript).strip()
    visible = "".join(
        character
        for character in normalized
        if unicodedata.category(character) not in {"Cc", "Cf"}
    )
    return visible[:200] or None

