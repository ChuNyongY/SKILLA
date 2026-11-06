"""Collect one real, paired SK0-SK3 file-sort pilot in an empty output directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from skilla_core import (
    ApprovalTokenService,
    CapabilityExecutorRouter,
    CapabilityVerifierRouter,
    FileMovedPredicate,
    FileMoveExecutor,
    InMemoryAuditSink,
    InMemoryMoveJournal,
    NativeReadOnlyExecutor,
    NimChatTransport,
    Orchestrator,
    PolicyEngine,
    PredicateVerifier,
    TypedPlanner,
    load_nim_credential,
)
from skilla_core.observation_loop import (
    BoundedObservationAgent,
    InMemoryVerifiedResultObserver,
    ObservationLoopStatus,
    OrchestratorRoundRunner,
)
from skilla_core.skill_study import (
    SkillStudyCondition,
    SkillStudyScheduleCell,
    SkillTrialObservation,
    build_skill_study_schedule,
    evaluate_skill_study,
)
from skilla_core.skill_study_collection import SkillStudyCollector
from tools.run_safe_file_sort_pilot import (
    ExactFileSortCompletionProbe,
    SandboxYellowApproval,
    _pilot_registry,
    _policy_context,
)

MODEL = "z-ai/glm-5.3-flash"
MODEL_CONFIGURATION = {
    "model": MODEL,
    "timeout_seconds": 60,
    "max_tokens": 1_800,
    "reasoning_effort": "low",
    "clear_thinking": True,
    "temperature": 0.1,
}
TASK_ID = "file-sort"
PARTICIPANT_ID = "pilot01"


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_state(root: Path) -> dict[str, object]:
    directories = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir()
    )
    files = {
        path.relative_to(root).as_posix(): _file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    return {"directories": directories, "files": files}


class CountingSandboxApproval(SandboxYellowApproval):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.approvals = 0

    def approve_yellow(self, plan: Any, action: Any, decision: Any) -> bool:
        approved = super().approve_yellow(plan, action, decision)
        if approved:
            self.approvals += 1
        return approved


def _condition_context(
    condition: SkillStudyCondition,
    root: Path,
) -> dict[str, object]:
    context: dict[str, object] = {"authorized_root": str(root)}
    if condition is SkillStudyCondition.SK1_STORED_INSTRUCTION:
        context["stored_instruction"] = (
            "First inspect the folder. Move each loose *_week1.txt file into the existing "
            "subject folder named by its filename prefix, and verify each move."
        )
    elif condition is SkillStudyCondition.SK2_INITIAL_SKILL:
        context["initial_skill"] = {
            "procedure": [
                "list the authorized root",
                "classify each loose week1 text file by filename prefix",
                "move each file into the matching existing subject folder",
                "verify every move",
            ],
            "dynamic_inputs": ["current root entries", "absolute source paths"],
            "decision_rules": ["math_ maps to math", "english_ maps to english"],
            "verification_rules": ["source absent", "destination content unchanged"],
        }
    elif condition is SkillStudyCondition.SK3_REVISED_SKILL:
        context["revised_skill"] = {
            "procedure": [
                "run one read-only file.list plan before proposing any move",
                "construct exact absolute source and destination paths from verified entries",
                "move each source once into its matching existing subject folder",
                "use file.moved as the postcondition and stop after both are verified",
            ],
            "dynamic_inputs": ["verified file.list entries", "authorized absolute root"],
            "decision_rules": [
                "never combine file.list and file.move in one plan",
                "math_week1.txt maps only to math/math_week1.txt",
                "english_week1.txt maps only to english/english_week1.txt",
                "never repeat a completed move",
            ],
            "verification_rules": [
                "both original paths absent",
                "both destination hashes equal their source hashes",
            ],
        }
    return context


def _goal(root: Path) -> str:
    return (
        f"Inside the authorized root {root}, inspect the current entries, then move only "
        "math_week1.txt to math/math_week1.txt and english_week1.txt to "
        "english/english_week1.txt. Preserve contents and verify completion."
    )


class FileSortConditionRunner:
    def __init__(self, evidence_directory: Path) -> None:
        self._registry = _pilot_registry()
        self._evidence_directory = evidence_directory
        self._model_configuration_sha256 = _canonical_sha256(MODEL_CONFIGURATION)
        self._tool_surface_sha256 = _canonical_sha256(
            [item.model_dump(mode="json") for item in self._registry.list()]
        )
        self._initial_state_sha256 = _canonical_sha256(
            {
                "directories": ["english", "math"],
                "files": {
                    "english_week1.txt": hashlib.sha256(b"essay").hexdigest(),
                    "math_week1.txt": hashlib.sha256(b"algebra").hexdigest(),
                },
            }
        )

    def run(self, cell: SkillStudyScheduleCell) -> SkillTrialObservation:
        started = perf_counter_ns()
        succeeded = False
        approvals = 0
        metrics = None
        final_state: dict[str, object] = {"runner_failed": True}
        reason = "RUNNER_FAILED"
        loop_status = "ERROR"
        rounds = 0
        journal_states: list[str] = []
        with tempfile.TemporaryDirectory(prefix="skilla-skill-study-") as raw_root:
            root = Path(raw_root).resolve(strict=True)
            (root / "math").mkdir()
            (root / "english").mkdir()
            (root / "math_week1.txt").write_text("algebra", encoding="utf-8")
            (root / "english_week1.txt").write_text("essay", encoding="utf-8")
            transport = NimChatTransport(
                load_nim_credential(),
                model=MODEL,
                timeout_seconds=60,
                max_tokens=1_800,
            )
            try:
                journal = InMemoryMoveJournal()
                executor = CapabilityExecutorRouter(
                    "native",
                    {
                        "file.list": NativeReadOnlyExecutor((root,)),
                        "file.move": FileMoveExecutor((root,), journal),
                    },
                )
                verifier = CapabilityVerifierRouter(
                    {
                        "file.list": PredicateVerifier(),
                        "file.move": PredicateVerifier(
                            {"file.moved": FileMovedPredicate()}
                        ),
                    }
                )
                approval = CountingSandboxApproval(root)
                tokens = ApprovalTokenService(b"skilla-skill-study-approval-key-0001")

                def orchestrator_factory(
                    observer: InMemoryVerifiedResultObserver,
                ) -> Orchestrator:
                    return Orchestrator(
                        policy=PolicyEngine(self._registry),
                        executor=executor,
                        verifier=verifier,
                        audit=InMemoryAuditSink(),
                        approvals=tokens,
                        approval_broker=approval,
                        verified_result_observer=observer,
                    )

                goal = _goal(root)
                probe = ExactFileSortCompletionProbe(root)
                result = BoundedObservationAgent(
                    TypedPlanner(transport, self._registry),
                    OrchestratorRoundRunner(orchestrator_factory, _policy_context),
                    probe,
                    self._registry,
                    max_rounds=3,
                ).run(
                    goal,
                    trusted_context=_condition_context(cell.condition, root),
                )
                succeeded = (
                    result.status is ObservationLoopStatus.COMPLETED
                    and probe.completed(goal, result.observations)
                )
                reason = result.reason
                loop_status = result.status.value
                rounds = result.rounds
                approvals = approval.approvals
                journal_states = [item.state.value for item in journal.records]
            except Exception as error:
                succeeded = False
                reason = type(error).__name__.upper()
            finally:
                metrics = transport.metrics_snapshot()
                final_state = _relative_state(root)
        elapsed_ms = max(0, (perf_counter_ns() - started) // 1_000_000)
        evidence = {
            "schema_version": "1.0",
            "participant_id": cell.participant_id,
            "task_id": cell.task_id,
            "repetition": cell.repetition,
            "condition": cell.condition.value,
            "succeeded": succeeded,
            "loop_status": loop_status,
            "reason": reason,
            "rounds": rounds,
            "yellow_approvals": approvals,
            "nim_metrics": metrics.model_dump(mode="json"),
            "journal_states": journal_states,
            "final_state": final_state,
        }
        evidence_name = (
            f"evidence-{cell.participant_id}-{cell.task_id}-{cell.repetition}-"
            f"{cell.condition.value}.json"
        )
        evidence_sha256 = _write_evidence_exclusive(
            self._evidence_directory / evidence_name,
            evidence,
        )
        return SkillTrialObservation(
            participant_id=cell.participant_id,
            task_id=cell.task_id,
            repetition=cell.repetition,
            condition=cell.condition,
            succeeded=succeeded,
            elapsed_ms=elapsed_ms,
            llm_calls=metrics.requests,
            input_tokens=metrics.input_tokens,
            output_tokens=metrics.output_tokens,
            user_interventions=approvals,
            run_cost_microunits=0,
            model_id=MODEL,
            model_configuration_sha256=self._model_configuration_sha256,
            tool_surface_sha256=self._tool_surface_sha256,
            initial_state_sha256=self._initial_state_sha256,
            outcome_evidence_sha256=evidence_sha256,
        )


def _validated_output_directory(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError("output directory must be an existing absolute directory")
    allowed_files = {"ledger.jsonl", "observations.json", "report.json"}
    entries = tuple(path.iterdir())
    if any(
        (
            item.name not in allowed_files
            and not (
                item.name.startswith("evidence-")
                and item.name.endswith(".json")
                and all(
                    character.isascii()
                    and (character.isalnum() or character in "._-")
                    for character in item.name
                )
            )
        )
        or item.is_symlink()
        or not item.is_file()
        for item in entries
    ):
        raise ValueError("output directory contains an unknown or unsafe entry")
    return path.resolve(strict=True)


def _bounded_repetitions(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as error:
        raise argparse.ArgumentTypeError("repetitions must be an integer") from error
    if not 1 <= value <= 100:
        raise argparse.ArgumentTypeError("repetitions must be within 1..100")
    return value


def _write_report_atomic(path: Path, payload: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("temporary report path already exists")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_evidence_exclusive(path: Path, evidence: dict[str, object]) -> str:
    payload = json.dumps(
        evidence,
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise ValueError("condition evidence path already exists or is unavailable") from error
    return hashlib.sha256(payload).hexdigest()


def main(argv: tuple[str, ...] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory")
    parser.add_argument("--participant-id", default=PARTICIPANT_ID)
    parser.add_argument("--repetitions", type=_bounded_repetitions, default=1)
    parser.add_argument("--seed", type=int, default=20_261_014)
    args = parser.parse_args(argv)
    output = _validated_output_directory(args.output_directory)
    schedule = build_skill_study_schedule(
        participant_id=args.participant_id,
        task_ids=(TASK_ID,),
        repetitions=args.repetitions,
        seed=args.seed,
    )
    collector = SkillStudyCollector(schedule, output / "ledger.jsonl")
    runner = FileSortConditionRunner(output)
    while not collector.complete:
        record = collector.collect_next(runner)
        print(
            json.dumps(
                {
                    "sequence": record.sequence,
                    "condition": record.cell.condition.value,
                    "succeeded": record.observation.succeeded,
                    "elapsed_ms": record.observation.elapsed_ms,
                    "llm_calls": record.observation.llm_calls,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    observations_path = output / "observations.json"
    collector.export_observations(observations_path)
    report = evaluate_skill_study(collector.observations)
    report_path = output / "report.json"
    _write_report_atomic(report_path, report.model_dump_json(indent=2))
    print(
        json.dumps(
            {
                "observations": str(observations_path),
                "report": str(report_path),
                "complete_blocks": report.complete_blocks,
                "cost_basis": "NVIDIA free endpoint; recorded monetary cost is zero",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
