"""Validate spoken skill approval through the real SKILLA product composition.

The command is submitted locally to reach the review state.  A recorded user
utterance is then passed through the configured VAD and Whisper pipeline, so the
approval itself is neither typed nor mocked.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from skilla_core.always_on_runtime import AlwaysOnState
from skilla_core.credential_store import load_nim_credential
from skilla_core.product_service import build_windows_product_service_with_secret_loader
from skilla_core.stt_bundle import load_stt_bundle
from skilla_core.voice import AudioFrame


def _load_frames(path: Path, *, frame_ms: int) -> tuple[AudioFrame, ...]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        source_rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    if sample_width != 2 or channels not in {1, 2}:
        raise ValueError("approval WAV must be mono/stereo 16-bit PCM")
    samples = np.frombuffer(raw, dtype="<i2").reshape(-1, channels)
    mono = samples.astype(np.float32).mean(axis=1)
    divisor = math.gcd(source_rate, 16_000)
    converted = resample_poly(mono, 16_000 // divisor, source_rate // divisor)
    pcm = np.clip(converted, -32768, 32767).astype("<i2")
    frame_samples = 16_000 * frame_ms // 1_000
    frames: list[AudioFrame] = []
    for offset in range(0, len(pcm), frame_samples):
        chunk = pcm[offset : offset + frame_samples]
        if len(chunk) < frame_samples:
            chunk = np.pad(chunk, (0, frame_samples - len(chunk)))
        frames.append(AudioFrame(pcm_s16le=chunk.astype("<i2").tobytes()))
    silence = AudioFrame(pcm_s16le=b"\0\0" * frame_samples)
    frames.extend(silence for _ in range(12))
    return tuple(frames)


def _wait_for_review(runtime: object, timeout_seconds: float) -> object:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        snapshot = runtime.status_snapshot()
        if snapshot.state is AlwaysOnState.REVIEWING:
            return snapshot
        if snapshot.state in {AlwaysOnState.IDLE, AlwaysOnState.CLOSED}:
            raise RuntimeError(f"review was not reached: {snapshot.last_reason}")
        time.sleep(0.1)
    raise TimeoutError("skill review did not appear before timeout")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("approval_wav", type=Path)
    parser.add_argument("--command", default="시스템 정보 확인")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    root = args.project_root.resolve(strict=True)
    config = args.config.resolve(strict=True)
    approval_wav = args.approval_wav.resolve(strict=True)
    service = build_windows_product_service_with_secret_loader(
        root,
        config,
        load_nim_credential,
    )
    runtime = service.runtime.runtime
    pipeline = service.voice.pipeline
    stt_bundle = load_stt_bundle(service.configuration.stt_manifest)
    report: dict[str, object] = {
        "schema_version": "1.0",
        "stt_model": stt_bundle.source_repository,
        "stt_revision": stt_bundle.source_revision,
        "command": args.command,
        "approval_wav": approval_wav.name,
    }
    try:
        started = runtime.submit_text(args.command)
        report["start_event"] = started.model_dump(mode="json")
        review_snapshot = _wait_for_review(runtime, args.timeout_seconds)
        review = review_snapshot.skill_review
        if review is None:
            raise RuntimeError("review state did not contain review details")
        report["review"] = {
            "kind": review.kind.value,
            "title": review.title,
            "review_id": str(review.review_id),
        }

        pipeline.set_review_active(True)
        capture = None
        for frame in _load_frames(
            approval_wav,
            frame_ms=service.configuration.settings.microphone_frame_ms,
        ):
            capture = pipeline.feed(frame) or capture
        if capture is None:
            raise RuntimeError("approval audio did not produce a voice capture")
        report["voice_capture"] = capture.model_dump(mode="json")
        response = runtime.submit_capture(capture)
        report["review_response_event"] = response.model_dump(mode="json")

        runtime.wait_for_idle(timeout_seconds=30.0)
        final = runtime.status_snapshot()
        report["final"] = final.model_dump(mode="json")
        report["passed"] = bool(
            response.reason == "SKILL_REVIEW_RESPONSE_ACCEPTED"
            and final.state is AlwaysOnState.IDLE
            and final.last_reason == "ALL_ACTIONS_VERIFIED"
            and final.completed_actions >= 1
        )
    finally:
        runtime.close()

    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0 if report.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
