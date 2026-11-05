from __future__ import annotations

import shutil
import subprocess
import time
import wave
import winsound
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .cancellation import CancellationToken
from .tts_ipc import TtsSpeakRequest


class NaturalTtsError(RuntimeError):
    pass


class SpeechSink(Protocol):
    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None: ...


class EdgeNeuralTtsRunner:
    """Use a free Edge neural voice while keeping generated speech files transient."""

    def __init__(
        self,
        project_root: Path,
        state_root: Path,
        *,
        voice: str = "ko-KR-SunHiNeural",
        timeout_seconds: float = 20.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._edge_tts = (
            project_root.resolve(strict=True)
            / ".venv-edge-tts"
            / "Scripts"
            / "edge-tts.exe"
        )
        self._state_root = state_root.resolve(strict=True)
        self._voice = voice
        self._timeout_seconds = timeout_seconds

    def probe(self) -> None:
        if not self._edge_tts.is_file():
            raise NaturalTtsError("EDGE_TTS_NOT_INSTALLED")
        if shutil.which("ffmpeg.exe") is None:
            raise NaturalTtsError("FFMPEG_NOT_INSTALLED")

    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None:
        request = TtsSpeakRequest(text=text, rate=rate, volume=volume)
        if cancellation is not None and cancellation.is_cancelled:
            return
        self.probe()
        work = self._state_root / "natural-tts"
        work.mkdir(parents=False, exist_ok=True)
        identity = uuid4().hex
        mp3_path = work / f"{identity}.mp3"
        wav_path = work / f"{identity}.wav"
        rate_percent = max(-50, min(50, -4 + request.rate * 8))
        volume_percent = max(-100, min(0, request.volume - 100))
        try:
            self._run_checked(
                [
                    str(self._edge_tts),
                    "--voice",
                    self._voice,
                    f"--rate={rate_percent:+d}%",
                    "--pitch=-2Hz",
                    f"--volume={volume_percent:+d}%",
                    "--text",
                    request.text,
                    "--write-media",
                    str(mp3_path),
                ],
                cancellation,
            )
            ffmpeg = shutil.which("ffmpeg.exe")
            if ffmpeg is None:
                raise NaturalTtsError("FFMPEG_NOT_INSTALLED")
            self._run_checked(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(mp3_path),
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "24000",
                    "-ac",
                    "1",
                    str(wav_path),
                ],
                cancellation,
            )
            self._play_wav(wav_path, cancellation)
        finally:
            for path in (wav_path, mp3_path):
                path.unlink(missing_ok=True)

    def _run_checked(
        self,
        command: list[str],
        cancellation: CancellationToken | None,
    ) -> None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError as error:
            raise NaturalTtsError("NATURAL_TTS_START_FAILED") from error
        deadline = time.monotonic() + self._timeout_seconds
        while process.poll() is None:
            if cancellation is not None and cancellation.is_cancelled:
                process.kill()
                process.wait()
                return
            if time.monotonic() >= deadline:
                process.kill()
                process.wait()
                raise NaturalTtsError("NATURAL_TTS_TIMED_OUT")
            time.sleep(0.05)
        if process.returncode != 0:
            raise NaturalTtsError("NATURAL_TTS_PROCESS_FAILED")

    @staticmethod
    def _play_wav(path: Path, cancellation: CancellationToken | None) -> None:
        with wave.open(str(path), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        try:
            deadline = time.monotonic() + duration + 0.25
            while time.monotonic() < deadline:
                if cancellation is not None and cancellation.is_cancelled:
                    break
                time.sleep(0.05)
        finally:
            winsound.PlaySound(None, 0)


class FallbackSpeechSink:
    """Keep voice feedback available when the online neural voice is unavailable."""

    def __init__(self, primary: SpeechSink, fallback: SpeechSink) -> None:
        self._primary = primary
        self._fallback = fallback

    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None:
        try:
            self._primary.speak(
                text,
                rate=rate,
                volume=volume,
                cancellation=cancellation,
            )
        except (NaturalTtsError, OSError, wave.Error):
            if cancellation is not None and cancellation.is_cancelled:
                return
            self._fallback.speak(
                text,
                rate=rate,
                volume=volume,
                cancellation=cancellation,
            )
