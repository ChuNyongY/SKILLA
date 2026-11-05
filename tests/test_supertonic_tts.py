import hashlib
import json
from pathlib import Path

import pytest

from skilla_core.cancellation import CancellationToken
from skilla_core.natural_tts import NaturalTtsError
from skilla_core.supertonic_tts import SupertonicTtsRunner

MODEL_FILES = (
    "duration_predictor.int8.onnx",
    "text_encoder.int8.onnx",
    "vector_estimator.int8.onnx",
    "vocoder.int8.onnx",
    "tts.json",
    "unicode_indexer.bin",
    "voice.bin",
)


def _model(root: Path) -> None:
    model = root / "models" / "supertonic3"
    model.mkdir(parents=True)
    files = {}
    for name in MODEL_FILES:
        (model / name).write_bytes(b"model")
        files[name] = {
            "size": 5,
            "sha256": hashlib.sha256(b"model").hexdigest(),
        }
    (model / "manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "files": files}),
        encoding="utf-8",
    )


def test_cancelled_generation_does_not_start_worker(tmp_path: Path) -> None:
    cancellation = CancellationToken()
    cancellation.cancel()
    output = tmp_path / "cancelled.wav"
    assert not SupertonicTtsRunner(tmp_path, tmp_path).render_wav(
        "완료", output, cancellation=cancellation
    )
    assert not output.exists()


def test_missing_runtime_reports_installation_error(tmp_path: Path) -> None:
    with pytest.raises(NaturalTtsError, match="SUPERTONIC_NOT_INSTALLED"):
        SupertonicTtsRunner(tmp_path, tmp_path).probe()


def test_probe_accepts_project_relative_complete_model(tmp_path: Path) -> None:
    _model(tmp_path)

    SupertonicTtsRunner(tmp_path, tmp_path).probe()


def test_probe_rejects_tampered_model(tmp_path: Path) -> None:
    _model(tmp_path)
    (tmp_path / "models" / "supertonic3" / "voice.bin").write_bytes(b"tampered")

    with pytest.raises(NaturalTtsError, match="SUPERTONIC_MODEL_INVALID"):
        SupertonicTtsRunner(tmp_path, tmp_path).probe()
