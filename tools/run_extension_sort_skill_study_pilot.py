"""Run an SK0-SK3 extension-sort study in fresh temporary sandboxes."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter_ns

from javis_core import (
    Action,
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
    Plan,
    PolicyDecision,
    PolicyEngine,
    PredicateVerifier,
    TypedPlanner,
    load_nim_credential,
)
from javis_core.observation_loop import (
    BoundedObservationAgent,
    InMemoryVerifiedResultObserver,
    ObservationLoopResult,
    ObservationLoopStatus,
    OrchestratorRoundRunner,
    VerifiedActionObservation,
)
from javis_core.skill_study import (
    SkillStudyCondition,
    SkillStudyScheduleCell,
    SkillTrialObservation,
    build_skill_study_schedule,
    evaluate_skill_study,
)
from javis_core.skill_study_collection import SkillStudyCollector
from tools.run_safe_file_sort_pilot import (
    SandboxYellowApproval,
    _pilot_registry,
    _policy_context,
)
from tools.run_skill_study_pilot import (
    MODEL,
    MODEL_CONFIGURATION,
    _bounded_repetitions,
    _canonical_sha256,
    _relative_state,
    _validated_output_directory,
    _write_evidence_exclusive,
    _write_report_atomic,
)

TASK_ID = "extension-sort"
PARTICIPANT_ID = "pilot01"
TARGET_BY_NAME = {
    "grades.csv": "Data/grades.csv",
    "notes.txt": "Text/notes.txt",
    "report.pdf": "Documents/report.pdf",
}
CONTENTS = {
    "grades.csv": b"name,score\nstudent,95\n",
    "notes.txt": b"weekly notes\n",
    "report.pdf": b"%PDF-1.4\n% bounded fixture\n",
}


def _goal(root: Path) -> str:
    return (
        f"Inside the authorized root {root}, inspect the current entries first. Then move "
        "only report.pdf to Documents/report.pdf, grades.csv to Data/grades.csv, and "
        "notes.txt to Text/notes.txt. Match the exact lowercase extension, preserve every "
        "file's bytes, do not repeat a move, and verify completion."
    )


def _condition_context(
    condition: SkillStudyCondition,
    root: Path,
) -> dict[str, object]:
    context: dict[str, object] = {"authorized_root": str(root)}
    if condition is SkillStudyCondition.SK1_STORED_INSTRUCTION:
        context["stored_instruction"] = (
            "Inspect the folder, then sort each loose file into the existing folder assigned "
            "to its exact extension and verify the moves."
        )
    elif condition is SkillStudyCondition.SK2_INITIAL_SKILL:
        context["initial_skill"] = {
            "procedure": [
                "list the authorized root",
                "classify each loose file by exact extension",
                "move it into the corresponding existing folder",
                "verify every move",
            ],
            "dynamic_inputs": ["current root entries", "absolute source paths"],
            "decision_rules": [
                ".pdf maps to Documents",
                ".csv maps to Data",
                ".txt maps to Text",
            ],
            "verification_rules": ["source absent", "destination bytes unchanged"],
        }
    elif condition is SkillStudyCondition.SK3_REVISED_SKILL:
        context["revised_skill"] = {
            "procedure": [
                "run one read-only file.list plan before proposing any move",
                "use only entries returned by the verified observation",
                "move each loose source exactly once to its mapped existing folder",
                "verify all three destinations and stop",
            ],
            "dynamic_inputs": ["verified file.list entries", "authorized absolute root"],
            "decision_rules": [
                "never combine file.list and file.move in one plan",
                "match only the exact lowercase suffix .pdf, .csv, or .txt",
                "report.pdf maps only to Documents/report.pdf",
                "grades.csv maps only to Data/grades.csv",
                "notes.txt maps only to Text/notes.txt",
                "never repeat a completed move",
            ],
            "verification_rules": [
                "all three original paths absent",
                "all three destination hashes equal their source hashes",
            ],
        }
    return context


def _write_fixture(root: Path) -> None:
    for directory in ("Data", "Documents", "Text"):
        (root / directory).mkdir()
    for name, content in CONTENTS.items():
        (root / name).write_bytes(content)


class ExactExtensionSortCompletionProbe:
    def __init__(self, root: Path) -> None:
        self._root = root

    def completed(
        self,
        goal: str,
        observations: tuple[VerifiedActionObservation, ...],
    ) -> bool:
        del goal, observations
        try:
            return all(
                not (self._root / name).exists()
                and (self._root / destination).read_bytes() == CONTENTS[name]
                for name, destination in TARGET_BY_NAME.items()
            )
        except OSError:
            return False


class ExactExtensionSortApproval(SandboxYellowApproval):
    """Approve only one of the three exact fixture moves within the sandbox."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self._root = root.resolve(strict=True)
        self.approvals = 0

    def approve_yellow(
        self,
        plan: Plan,
        action: Action,
        decision: PolicyDecision,
    ) -> bool:
        if not super().approve_yellow(plan, action, decision):
            return False
        source_raw = action.arguments.get("source")
        destination_raw = action.arguments.get("destination")
        if not isinstance(source_raw, str) or not isinstance(destination_raw, str):
            return False
        try:
            source = Path(source_raw).resolve(strict=True)
            destination_input = Path(destination_raw)
            destination = destination_input.parent.resolve(strict=True) / destination_input.name
            source_name = source.relative_to(self._root).as_posix()
            destination_name = destination.relative_to(self._root).as_posix()
        except (OSError, ValueError):
            return False
        approved = TARGET_BY_NAME.get(source_name) == destination_name
        if approved:
            self.approvals += 1
        return approved


def _listed_before_first_move(result: ObservationLoopResult) -> bool:
    capabilities = [
        action.capability_id
        for plan in result.executed_plans
        for action in plan.steps
    ]
    try:
        first_list = capabilities.index("file.list")
        first_move = capabilities.index("file.move")
    except ValueError:
        return False
    return first_list < first_move


class ExtensionSortConditionRunner:
    def __init__(self, evidence_directory: Path) -> None:
        self._registry = _pilot_registry()
        self._evidence_directory = evidence_directory
        self._model_configuration_sha256 = _canonical_sha256(MODEL_CONFIGURATION)
        self._tool_surface_sha256 = _canonical_sha256(
            [item.model_dump(mode="json") for item in self._registry.list()]
        )
        with tempfile.TemporaryDirectory(prefix="javis-extension-state-") as raw:
            root = Path(raw)
            _write_fixture(root)
            state = _relative_state(root)
        self._initial_state_sha256 = _canonical_sha256(state)

    def run(self, cell: SkillStudyScheduleCell) -> SkillTrialObservation:
        started = perf_counter_ns()
        succeeded = False
        reason = "RUNNER_FAILED"
        loop_status = "ERROR"
        rounds = 0
        approvals = 0
        listed_before_move = False
        journal_states: list[str] = []
        final_state: dict[str, object] = {"runner_failed": True}
        transport = NimChatTransport(
            load_nim_credential(),
            model=MODEL,
            timeout_seconds=60,
            max_tokens=1_800,
        )
        with tempfile.TemporaryDirectory(prefix="javis-extension-study-") as raw:
            root = Path(raw).resolve(strict=True)
            _write_fixture(root)
            initial_state = _relative_state(root)
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
                approval = ExactExtensionSortApproval(root)
                tokens = ApprovalTokenService(
                    b"javis-extension-study-approval-key-0001"
                )

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
                probe = ExactExtensionSortCompletionProbe(root)
                result = BoundedObservationAgent(
                    TypedPlanner(transport, self._registry),
                    OrchestratorRoundRunner(orchestrator_factory, _policy_context),
                    probe,
                    self._registry,
                    max_rounds=4,
                ).run(
                    goal,
                    trusted_context=_condition_context(cell.condition, root),
                )
                listed_before_move = _listed_before_first_move(result)
                succeeded = (
                    result.status is ObservationLoopStatus.COMPLETED
                    and probe.completed(goal, result.observations)
                    and listed_before_move
                    and approval.approvals == len(TARGET_BY_NAME)
                )
                reason = (
                    result.reason
                    if result.status is not ObservationLoopStatus.COMPLETED or succeeded
                    else "RESULT_MISMATCH"
                )
                loop_status = result.status.value
                rounds = result.rounds
                approvals = approval.approvals
                journal_states = [item.state.value for item in journal.records]
            except Exception as error:
                reason = type(error).__name__.upper()[:80]
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
            "listed_before_first_move": listed_before_move,
            "nim_metrics": metrics.model_dump(mode="json"),
            "journal_states": journal_states,
            "initial_state_matches_declared": (
                _canonical_sha256(initial_state) == self._initial_state_sha256
            ),
            "final_state": final_state,
            "absolute_path_emitted": False,
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
            user_interventions=approvals,
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
    parser.add_argument("--seed", type=int, default=20_261_016)
    arguments = parser.parse_args(argv)
    output = _validated_output_directory(arguments.output_directory)
    schedule = build_skill_study_schedule(
        participant_id=arguments.participant_id,
        task_ids=(TASK_ID,),
        repetitions=arguments.repetitions,
        seed=arguments.seed,
    )
    collector = SkillStudyCollector(schedule, output / "ledger.jsonl")
    runner = ExtensionSortConditionRunner(output)
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
