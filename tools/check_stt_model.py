"""Check the configured STT bundle with an existing WAV, without opening devices."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from skilla_core.stt_bundle import load_stt_bundle
from skilla_core.voice import AudioFrame
from skilla_core.voice_adapters import FasterWhisperSpeechToText


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with wave.open(str(arguments.wav), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            parser.error("use mono 16-bit PCM WAV")
        rate = handle.getframerate()
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
    factor = math.gcd(rate, 16_000)
    converted = resample_poly(samples.astype(np.float32), 16_000 // factor, rate // factor)
    pcm = np.clip(converted, -32768, 32767).astype("<i2").tobytes()
    started = time.perf_counter()
    bundle = load_stt_bundle(root / "models/faster-whisper-large-v3-turbo/manifest.json")
    stt = FasterWhisperSpeechToText.from_local_bundle(
        bundle, device=arguments.device, compute_type=arguments.compute_type,
    )
    load_seconds = time.perf_counter() - started
    started = time.perf_counter()
    transcript = stt.transcribe((AudioFrame(pcm_s16le=pcm),))
    report = {
        "model": bundle.source_repository,
        "revision": bundle.source_revision,
        "device": arguments.device,
        "compute_type": arguments.compute_type,
        "wav_sha256": hashlib.sha256(arguments.wav.read_bytes()).hexdigest(),
        "sample_seconds": len(pcm) / 32_000,
        "load_seconds": round(load_seconds, 3),
        "inference_seconds": round(time.perf_counter() - started, 3),
        "transcript": transcript,
    }
    arguments.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
