"""Run GPU speech recognition in a disposable local process."""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread

from .voice import AudioFrame
from .voice_adapters import FasterWhisperSpeechToText
from .worker_process import STT_WORKER_TOKEN, fixed_worker_command

_MAX_AUDIO_BYTES = 2 * 1024 * 1024
_MAX_RESPONSE_BYTES = 128 * 1024


class CudaWhisperWorker:
    def __init__(self, model_root: Path, language: str) -> None:
        self._lock = Lock()
        self._closed = False
        environment = {
            key: os.environ[key]
            for key in (
                "SystemRoot", "WINDIR", "SYSTEMDRIVE", "TEMP", "TMP", "PATH",
                "LOCALAPPDATA", "APPDATA", "USERPROFILE",
            )
            if key in os.environ
        }
        self._process = subprocess.Popen(
            fixed_worker_command("skilla_core.stt_worker", STT_WORKER_TOKEN),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            reply = self._request(
                json.dumps({"model": str(model_root), "language": language}).encode(),
                timeout=60,
            )
            if reply != {"status": "ready"}:
                raise RuntimeError("GPU speech recognition worker did not start")
        except Exception:
            self.close()
            raise
        atexit.register(self.close)

    def transcribe(self, frames: tuple[AudioFrame, ...]) -> str:
        if not frames:
            return ""
        if any(frame.sample_rate != 16_000 or frame.channels != 1 for frame in frames):
            raise ValueError("GPU speech recognition requires mono 16 kHz PCM")
        if sum(len(frame.pcm_s16le) for frame in frames) > _MAX_AUDIO_BYTES:
            raise ValueError("GPU speech input exceeded its size limit")
        pcm = b"".join(frame.pcm_s16le for frame in frames)
        with self._lock:
            try:
                response = self._request(pcm, timeout=15)
                status = response.get("status")
                transcript = response.get("text")
                if status == "ok" and isinstance(transcript, str) and len(transcript) <= 10_000:
                    return transcript
                if status == "rejected":
                    raise ValueError("GPU speech input did not pass transcription checks")
                raise RuntimeError("GPU speech recognition failed")
            except (RuntimeError, OSError):
                self.close()
                raise

    def _request(self, payload: bytes, *, timeout: int) -> Mapping[str, object]:
        if self._closed:
            raise RuntimeError("GPU speech recognition worker is closed")
        output: Queue[bytes] = Queue(maxsize=1)

        def exchange() -> None:
            process = self._process
            assert process.stdin is not None and process.stdout is not None
            try:
                process.stdin.write(len(payload).to_bytes(4, "little") + payload)
                process.stdin.flush()
                output.put(process.stdout.readline(_MAX_RESPONSE_BYTES + 1))
            except (OSError, ValueError):
                output.put(b"")

        Thread(target=exchange, name="skilla-cuda-stt-ipc", daemon=True).start()
        try:
            raw = output.get(timeout=timeout)
            if not raw.endswith(b"\n") or len(raw) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("GPU speech recognition worker disconnected")
            response = json.loads(raw)
        except (Empty, ValueError) as error:
            raise RuntimeError("GPU speech recognition worker timed out or failed") from error
        if not isinstance(response, dict):
            raise RuntimeError("GPU speech recognition worker response was invalid")
        return response

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        atexit.unregister(self.close)
        with suppress(OSError, subprocess.TimeoutExpired):
            if self._process.poll() is None:
                self._process.terminate()
                self._process.wait(timeout=2)
        if self._process.poll() is not None:
            for stream in (self._process.stdin, self._process.stdout):
                if stream is not None:
                    with suppress(OSError):
                        stream.close()


def _read_request(limit: int) -> bytes | None:
    stream = sys.stdin.buffer
    header = stream.read(4)
    if not header:
        return None
    size = int.from_bytes(header, "little")
    if len(header) != 4 or not 0 < size <= limit:
        raise ValueError("invalid audio request size")
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("incomplete audio request")
    return data


def _reply(**data: str) -> None:
    sys.stdout.buffer.write(json.dumps(data).encode() + b"\n")
    sys.stdout.buffer.flush()


def main() -> int:
    try:
        initial = _read_request(8192)
        if initial is None:
            return 1
        setup = json.loads(initial)
        model = FasterWhisperSpeechToText.from_local_model(
            Path(setup["model"]), language=setup["language"], device="cuda",
            compute_type="int8_float16",
        )
        with suppress(ValueError):
            model.transcribe((AudioFrame(pcm_s16le=bytes(32_000)),))
        _reply(status="ready")
        while (pcm := _read_request(_MAX_AUDIO_BYTES)) is not None:
            try:
                text = model.transcribe((AudioFrame(pcm_s16le=pcm),))
            except ValueError:
                _reply(status="rejected")
            else:
                _reply(status="ok", text=text)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
