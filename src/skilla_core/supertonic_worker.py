"""Isolated local speech generation; invoked with the existing sherpa runtime."""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path


def main() -> None:
    import numpy as np
    import sherpa_onnx

    request = json.loads(sys.stdin.buffer.read(8193))
    text = request["text"]
    if not isinstance(text, str) or not 1 <= len(text) <= 500 or "\x00" in text:
        raise ValueError("invalid speech text")
    model = Path(request["model"])
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
                duration_predictor=str(model / "duration_predictor.int8.onnx"),
                text_encoder=str(model / "text_encoder.int8.onnx"),
                vector_estimator=str(model / "vector_estimator.int8.onnx"),
                vocoder=str(model / "vocoder.int8.onnx"),
                tts_json=str(model / "tts.json"),
                unicode_indexer=str(model / "unicode_indexer.bin"),
                voice_style=str(model / "voice.bin"),
            ),
            num_threads=4,
            provider="cpu",
            debug=False,
        )
    )
    generator = sherpa_onnx.OfflineTts(config)
    options = sherpa_onnx.GenerationConfig()
    options.sid = 0
    options.num_steps = 8
    options.speed = request["speed"]
    options.extra["lang"] = "ko"
    audio = generator.generate(text, options)
    samples = np.clip(np.asarray(audio.samples) * request["volume"] / 100, -1, 1)
    pcm = (samples * 32767).astype("<i2").tobytes()
    with open(request["output"], "xb") as handle, wave.open(handle, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(audio.sample_rate)
        output.writeframes(pcm)


if __name__ == "__main__":
    main()
