from __future__ import annotations

from skilla_core.cancellation import CancellationToken
from skilla_core.natural_tts import FallbackSpeechSink, NaturalTtsError


class RecordingSink:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[str] = []

    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None:
        del rate, volume, cancellation
        self.messages.append(text)
        if self.fail:
            raise NaturalTtsError("offline")


def test_fallback_sink_uses_neural_voice_when_available() -> None:
    primary = RecordingSink()
    fallback = RecordingSink()

    FallbackSpeechSink(primary, fallback).speak("완료")

    assert primary.messages == ["완료"]
    assert fallback.messages == []


def test_fallback_sink_uses_windows_voice_when_neural_voice_fails() -> None:
    primary = RecordingSink(fail=True)
    fallback = RecordingSink()

    FallbackSpeechSink(primary, fallback).speak("완료")

    assert primary.messages == ["완료"]
    assert fallback.messages == ["완료"]


def test_fallback_sink_does_not_speak_after_cancellation() -> None:
    primary = RecordingSink(fail=True)
    fallback = RecordingSink()
    cancellation = CancellationToken()
    cancellation.cancel()

    FallbackSpeechSink(primary, fallback).speak("완료", cancellation=cancellation)

    assert fallback.messages == []
