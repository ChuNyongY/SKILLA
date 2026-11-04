"""Run a read-only SK0-SK3 folder-inventory study in fresh sandboxes."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter_ns

from javis_core import (
    Action,
    ActionStatus,
    ApprovalTokenService,
    CapabilityExecutorRouter,
    CapabilityRegistry,
    CapabilityVerifierRouter,
    InMemoryAuditSink,
    NativeReadOnlyExecutor,
    NimChatTransport,
    Orchestrator,
    Plan,
    PolicyEngine,
    Postcondition,
    PredicateVerifier,
    TypedPlanner,
    default_registry,
    load_nim_credential,
)
from javis_core.observation_loop import InMemoryVerifiedResultObserver
from javis_core.skill_study import (
    SkillStudyCondition,
    SkillStudyScheduleCell,
    SkillTrialObservation,
    build_skill_study_schedule,
    evaluate_skill_study,
)
from javis_core.skill_study_collection import SkillStudyCollector
from tools.run_safe_file_sort_pilot import _policy_context
from tools.run_skill_study_pilot import (
    MODEL,
    _bounded_repetitions,
    _canonical_sha256,
    _file_sha256,
    _validated_output_directory,
    _write_evidence_exclusive,
    _write_report_atomic,
)
from tools.run_skill_study_pilot import (
    MODEL_CONFIGURATION as BASE_MODEL_CONFIGURATION,
)

TASK_ID = "folder-inventory"
PARTICIPANT_ID = "pilot01"
EXPECTED_NAMES = ("alpha.txt", "beta.csv", "notes.md")
MODEL_CONFIGURATION = {**BASE_MODEL_CONFIGURATION, "max_tokens": 1_000}


def _registry() -> CapabilityRegistry:
    return CapabilityRegistry(
        item
        for item in default_registry().list()
        if item.capability_id == "file.list"
    )


def _goal() -> str:
    return "List the names in the exact authorized folder without changing any file."


def _condition_context(
    condition: SkillStudyCondition,
    root: Path,
) -> dict[str, object]:
    context: dict[str, object] = {
        "authorized_folder": {
            "path": str(root),
            "target_identity": str(root),
            "expected_names": list(EXPECTED_NAMES),
        }
    }
    if condition is SkillStudyCondition.SK1_STORED_INSTRUCTION:
        context["stored_instruction"] = (
            "Use file.list exactly once for the authorized folder and do not modify files."
        )
    elif condition is SkillStudyCondition.SK2_INITIAL_SKILL:
        context["initial_skill"] = {
            "steps": ["list the exact authorized folder once"],
            "dynamic_inputs": ["authorized folder path"],
            "verification_rules": ["the exact three expected names are returned"],
            "allowed_capabilities": ["file.list"],
        }
    elif condition is SkillStudyCondition.SK3_REVISED_SKILL:
        context["revised_skill"] = {
            "steps": ["list the exact authorized folder once"],
            "dynamic_inputs": ["authorized folder path"],
            "decision_rules": [
                "never use another path",
                "never emit a state-changing action",
                "never emit more than one action",
            ],
            "verification_rules": [
                "the exact three expected names are returned",
                "all fixture file hashes remain unchanged",
            ],
            "allowed_capabilities": ["file.list"],
        }
    return context


def _validate_exact_plan(plan: Plan, root: Path) -> Action:
    if plan.goal != _goal() or len(plan.steps) != 1:
        raise ValueError("inventory pilot requires exactly one action for the exact goal")
    action = plan.steps[0]
    if (
        action.capability_id != "file.list"
        or action.arguments != {"path": str(root)}
        or action.target_identity != str(root)
        or action.expected_postconditions
        != (Postcondition(predicate="execution.success"),)
        or plan.continue_after_verification
    ):
        raise ValueError("inventory pilot plan did not preserve the exact read-only binding")
    return action


def _fixture_hashes(root: Path) -> dict[str, str]:
    return {name: _file_sha256(root / name) for name in EXPECTED_NAMES}


def _write_fixture(root: Path) -> None:
    values = {
        "alpha.txt": "alpha\n",
        "beta.csv": "column\nvalue\n",
        "notes.md": "# notes\n",
    }
    for name, value in values.items():
        (root / name).write_text(value, encoding="utf-8")


class FolderInventoryConditionRunner:
    def __init__(self, evidence_directory: Path) -> None:
        self._registry = _registry()
        self._evidence_directory = evidence_directory
        self._model_configuration_sha256 = _canonical_sha256(MODEL_CONFIGURATION)
        self._tool_surface_sha256 = _canonical_sha256(
            [item.model_dump(mode="json") for item in self._registry.list()]
        )
        with tempfile.TemporaryDirectory(prefix="javis-inventory-state-") as raw:
            root = Path(raw)
            _write_fixture(root)
            hashes = _fixture_hashes(root)
        self._initial_state_sha256 = _canonical_sha256({"files": hashes})

    def run(self, cell: SkillStudyScheduleCell) -> SkillTrialObservation:
        started = perf_counter_ns()
        succeeded = False
        hashes_unchanged = False
        reason = "RUNNER_FAILED"
        evidence_plan: dict[str, object] = {"accepted": False}
        transport = NimChatTransport(
            load_nim_credential(),
            model=MODEL,
            timeout_seconds=60,
            max_tokens=1_000,
        )
        with tempfile.TemporaryDirectory(prefix="javis-inventory-study-") as raw:
            root = Path(raw).resolve(strict=True)
            _write_fixture(root)
            before = _fixture_hashes(root)
            observer = InMemoryVerifiedResultObserver()
            try:
                plan = TypedPlanner(transport, self._registry).plan(
                    _goal(),
                    trusted_context=_condition_context(cell.condition, root),
                )
                action = _validate_exact_plan(plan, root)
                evidence_plan = {
                    "accepted": True,
                    "step_count": 1,
                    "capability_id": action.capability_id,
                    "target_binding_matches": True,
                }
                outcome = Orchestrator(
                    policy=PolicyEngine(self._registry),
                    executor=CapabilityExecutorRouter(
                        "native",
                        {"file.list": NativeReadOnlyExecutor((root,))},
                    ),
                    verifier=CapabilityVerifierRouter(
                        {"file.list": PredicateVerifier()}
                    ),
                    audit=InMemoryAuditSink(),
                    approvals=ApprovalTokenService(
                        b"javis-inventory-study-approval-key-0001"
                    ),
                    verified_result_observer=observer,
                ).run(plan, _policy_context)
                observed = observer.observations
                hashes_unchanged = _fixture_hashes(root) == before
                succeeded = (
                    outcome.status is ActionStatus.SUCCEEDED
                    and len(observed) == 1
                    and observed[0].observed.get("entries") == list(EXPECTED_NAMES)
                    and observed[0].observed.get("count") == len(EXPECTED_NAMES)
                    and observed[0].observed.get("truncated") is False
                    and tuple(sorted(path.name for path in root.iterdir()))
                    == EXPECTED_NAMES
                    and hashes_unchanged
                )
                reason = "EXACT_INVENTORY_VERIFIED" if succeeded else "RESULT_MISMATCH"
            except Exception as error:
                reason = type(error).__name__.upper()[:80]
            metrics = transport.metrics_snapshot()

        elapsed_ms = max(0, (perf_counter_ns() - started) // 1_000_000)
        evidence = {
            "schema_version": "1.0",
            "participant_id": cell.participant_id,
            "task_id": cell.task_id,
            "repetition": cell.repetition,
            "condition": cell.condition.value,
            "succeeded": succeeded,
            "reason": reason,
            "plan": evidence_plan,
            "expected_name_count": len(EXPECTED_NAMES),
            "fixture_hashes_unchanged": hashes_unchanged,
            "nim_metrics": metrics.model_dump(mode="json"),
            "path_emitted": False,
            "file_contents_emitted": False,
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
            user_interventions=0,
            run_cost_microunits=0,
            model_id=MODEL,
            model_configuration_sha256=self._model_configuration_sha256,
            tool_surface_sha256=self._tool_surface_sha256,
            initial_state_sha256=self._initial_state_sha256,
            outcome_evidence_sha256=evidence_sha256,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory")
    parser.add_argument("--participant-id", default=PARTICIPANT_ID)
    parser.add_argument("--repetitions", type=_bounded_repetitions, default=1)
    parser.add_argument("--seed", type=int, default=20_261_014)
    arguments = parser.parse_args(argv)
    output = _validated_output_directory(arguments.output_directory)
    schedule = build_skill_study_schedule(
        participant_id=arguments.participant_id,
        task_ids=(TASK_ID,),
        repetitions=arguments.repetitions,
        seed=arguments.seed,
    )
    collector = SkillStudyCollector(schedule, output / "ledger.jsonl")
    runner = FolderInventoryConditionRunner(output)
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
