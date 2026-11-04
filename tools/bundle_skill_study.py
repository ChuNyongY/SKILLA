"""Build a self-contained, hash-verified bundle from multiple skill studies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from javis_core.skill_study import (
    SkillTrialObservation,
    evaluate_skill_study,
    load_skill_study_observations,
)
from tools.run_skill_search_pilot import _prepare_empty_output, _write_json_exclusive


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence_name(observation: SkillTrialObservation) -> str:
    return (
        f"evidence-{observation.participant_id}-{observation.task_id}-"
        f"{observation.repetition}-{observation.condition.value}.json"
    )


def _strict_json_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("evidence must be a bounded regular file")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate evidence JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid evidence JSON") from error
    if not isinstance(value, dict):
        raise ValueError("evidence JSON must be an object")
    return value


def _verify_evidence(
    directory: Path,
    observation: SkillTrialObservation,
) -> Path:
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        raise ValueError("evidence directory must be an absolute regular directory")
    path = directory / _evidence_name(observation)
    document = _strict_json_object(path)
    expected_identity: dict[str, object] = {
        "participant_id": observation.participant_id,
        "task_id": observation.task_id,
        "repetition": observation.repetition,
        "condition": observation.condition.value,
        "succeeded": observation.succeeded,
    }
    if any(document.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("evidence identity does not match its observation")
    if _sha256(path) != observation.outcome_evidence_sha256:
        raise ValueError("evidence hash does not match its observation")
    return path


def _copy_exclusive(source: Path, destination: Path) -> None:
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                output_stream.write(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except OSError as error:
        raise ValueError("evidence could not be copied exclusively") from error


def build_bundle(
    output: Path,
    sources: tuple[tuple[Path, Path], ...],
) -> dict[str, object]:
    if len(sources) < 2:
        raise ValueError("a combined study requires at least two sources")
    all_observations: list[SkillTrialObservation] = []
    source_records: list[dict[str, object]] = []
    evidence_sources: list[tuple[int, SkillTrialObservation, Path]] = []
    identities: set[tuple[str, str, int, str]] = set()

    for source_index, (observations_path, evidence_directory) in enumerate(
        sources,
        start=1,
    ):
        observations = load_skill_study_observations(observations_path)
        if not observations:
            raise ValueError("skill study source must contain observations")
        expected_names = {_evidence_name(item) for item in observations}
        actual_names = {
            path.name
            for path in evidence_directory.glob("evidence-*.json")
            if path.is_file() and not path.is_symlink()
        }
        if actual_names != expected_names:
            raise ValueError("evidence directory does not exactly cover its observations")
        for observation in observations:
            identity = (
                observation.participant_id,
                observation.task_id,
                observation.repetition,
                observation.condition.value,
            )
            if identity in identities:
                raise ValueError("duplicate observation cell across sources")
            identities.add(identity)
            evidence_sources.append(
                (
                    source_index,
                    observation,
                    _verify_evidence(evidence_directory, observation),
                )
            )
        all_observations.extend(observations)
        source_records.append(
            {
                "source_index": source_index,
                "observations": len(observations),
                "tasks": sorted({item.task_id for item in observations}),
                "observations_sha256": _sha256(observations_path),
            }
        )

    ordered = tuple(
        sorted(
            all_observations,
            key=lambda item: (
                item.participant_id,
                item.task_id,
                item.repetition,
                item.condition.value,
            ),
        )
    )
    task_ids = sorted({item.task_id for item in ordered})
    report = evaluate_skill_study(ordered)
    evidence_output = output / "evidence"
    evidence_output.mkdir()
    copied_records: list[dict[str, object]] = []
    for source_index, observation, source_path in evidence_sources:
        copied_name = f"source-{source_index}-{source_path.name}"
        destination = evidence_output / copied_name
        _copy_exclusive(source_path, destination)
        digest = _sha256(destination)
        if digest != observation.outcome_evidence_sha256:
            raise RuntimeError("copied evidence hash changed")
        copied_records.append(
            {
                "file": f"evidence/{copied_name}",
                "sha256": digest,
                "participant_id": observation.participant_id,
                "task_id": observation.task_id,
                "repetition": observation.repetition,
                "condition": observation.condition.value,
            }
        )

    observations_output = output / "observations.json"
    report_output = output / "report.json"
    _write_json_exclusive(
        observations_output,
        [item.model_dump(mode="json") for item in ordered],
    )
    _write_json_exclusive(report_output, report.model_dump(mode="json"))
    manifest: dict[str, object] = {
        "schema_version": 1,
        "scope": (
            f"{len(task_ids)}-task developer pilot; heterogeneous descriptive statistics, "
            "not a general performance claim"
        ),
        "sources": source_records,
        "tasks": task_ids,
        "observations": len(ordered),
        "complete_blocks": report.complete_blocks,
        "evidence": copied_records,
        "sha256": {
            "observations": _sha256(observations_output),
            "report": _sha256(report_output),
        },
    }
    _write_json_exclusive(output / "manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory")
    parser.add_argument(
        "--source",
        nargs=2,
        action="append",
        metavar=("OBSERVATIONS", "EVIDENCE_DIRECTORY"),
        required=True,
    )
    arguments = parser.parse_args(argv)
    output = _prepare_empty_output(arguments.output_directory)
    raw_sources: list[list[str]] = arguments.source
    sources = tuple((Path(pair[0]), Path(pair[1])) for pair in raw_sources)
    if any(
        not observations.is_absolute() or not evidence.is_absolute()
        for observations, evidence in sources
    ):
        raise ValueError("source paths must be absolute")
    manifest = build_bundle(output, sources)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
