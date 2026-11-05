from __future__ import annotations

import hashlib
import json
import threading
import wave
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4

from .cancellation import CancellationToken
from .natural_tts import EdgeNeuralTtsRunner, NaturalTtsError
from .tts_ipc import TtsSpeakRequest

_MODEL_FILES = (
    "duration_predictor.int8.onnx",
    "text_encoder.int8.onnx",
    "vector_estimator.int8.onnx",
    "vocoder.int8.onnx",
    "tts.json",
    "unicode_indexer.bin",
    "voice.bin",
)


class SupertonicTtsRunner:
    """Local Korean TTS using the bundled Supertonic 3 CPU ONNX model."""

    def __init__(self, project_root: Path, state_root: Path) -> None:
        self._root = project_root.resolve(strict=True)
        self._state = state_root.resolve(strict=True)
        self._model = self._root / "models" / "supertonic3"
        self._verified = False
        self._runtime: tuple[Any, Any, Any] | None = None
        self._lock = threading.Lock()

    def probe(self) -> None:
        if self._verified:
            return
        manifest_path = self._model / "manifest.json"
        if not self._model.is_dir() or not manifest_path.is_file():
            raise NaturalTtsError("SUPERTONIC_NOT_INSTALLED")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest["files"]
            if manifest["schema_version"] != "1.0" or set(files) != set(_MODEL_FILES):
                raise ValueError("invalid model manifest")
            for name in _MODEL_FILES:
                candidate = self._model / name
                metadata = files[name]
                if (
                    not candidate.is_file()
                    or candidate.is_symlink()
                    or candidate.stat().st_size != metadata["size"]
                    or _file_hash(candidate) != metadata["sha256"]
                ):
                    raise ValueError("model integrity mismatch")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise NaturalTtsError("SUPERTONIC_MODEL_INVALID") from error
        self._verified = True

    def render_wav(
        self,
        text: str,
        output: Path,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> bool:
        request = TtsSpeakRequest(text=text, rate=rate, volume=volume)
        if cancellation is not None and cancellation.is_cancelled:
            return False
        self.probe()
        if output.exists() or output.suffix.lower() != ".wav":
            raise NaturalTtsError("SUPERTONIC_OUTPUT_INVALID")
        try:
            with self._lock:
                sherpa_onnx, np, generator = self._load_runtime()
                options = sherpa_onnx.GenerationConfig()
                options.sid = 0
                options.num_steps = 8
                options.speed = 1.0 + rate * 0.08
                options.extra["lang"] = "ko"
                audio = generator.generate(request.text, options)
                if cancellation is not None and cancellation.is_cancelled:
                    return False
                samples = np.clip(np.asarray(audio.samples) * volume / 100, -1, 1)
                pcm = (samples * 32767).astype("<i2").tobytes()
                with output.open("xb") as handle, wave.open(handle, "wb") as rendered:
                    rendered.setnchannels(1)
                    rendered.setsampwidth(2)
                    rendered.setframerate(audio.sample_rate)
                    rendered.writeframes(pcm)
            with wave.open(str(output), "rb") as audio:
                if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getnframes() < 1:
                    raise NaturalTtsError("SUPERTONIC_WAV_INVALID")
        except (OSError, RuntimeError, TypeError, ValueError, wave.Error, NaturalTtsError) as error:
            output.unlink(missing_ok=True)
            if isinstance(error, NaturalTtsError):
                raise
            raise NaturalTtsError("SUPERTONIC_GENERATION_FAILED") from error
        return True

    def _load_runtime(self) -> tuple[Any, Any, Any]:
        if self._runtime is not None:
            return self._runtime
        try:
            np = import_module("numpy")
            sherpa_onnx = import_module("sherpa_onnx")
            config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
                        duration_predictor=str(self._model / "duration_predictor.int8.onnx"),
                        text_encoder=str(self._model / "text_encoder.int8.onnx"),
                        vector_estimator=str(self._model / "vector_estimator.int8.onnx"),
                        vocoder=str(self._model / "vocoder.int8.onnx"),
                        tts_json=str(self._model / "tts.json"),
                        unicode_indexer=str(self._model / "unicode_indexer.bin"),
                        voice_style=str(self._model / "voice.bin"),
                    ),
                    num_threads=4,
                    provider="cpu",
                    debug=False,
                )
            )
            generator = sherpa_onnx.OfflineTts(config)
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as error:
            raise NaturalTtsError("SUPERTONIC_RUNTIME_UNAVAILABLE") from error
        self._runtime = (sherpa_onnx, np, generator)
        return self._runtime

    def speak(
        self,
        text: str,
        *,
        rate: int = 0,
        volume: int = 100,
        cancellation: CancellationToken | None = None,
    ) -> None:
        folder = self._state / "supertonic-tts"
        folder.mkdir(exist_ok=True)
        output = folder / f"{uuid4().hex}.wav"
        try:
            if self.render_wav(text, output, rate=rate, volume=volume, cancellation=cancellation):
                EdgeNeuralTtsRunner._play_wav(output, cancellation)
        finally:
            output.unlink(missing_ok=True)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
