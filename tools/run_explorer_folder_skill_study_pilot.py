"""Collect an SK0-SK3 pilot that opens and verifies one Explorer folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter_ns

from javis_core import (
    Action,
    ActionStatus,
    AppRegistryLoader,
    ApprovalTokenService,
    CapabilityExecutorRouter,
    CapabilityRegistry,
    CapabilityVerifierRouter,
    ExplorerFolderOpenExecutor,
    ExplorerFolderVerifier,
    InMemoryAuditSink,
    NimChatTransport,
    Orchestrator,
    Plan,
    PolicyEngine,
    Postcondition,
    RegisteredApp,
    SkillTrialObservation,
    TypedPlanner,
    WindowsRuntimeWindowResolver,
    default_registry,
    explorer_folder_target_identity,
    load_nim_credential,
)
from javis_core.runtime_models import ExecutionResult
from javis_core.skill_study import (
    SkillStudyCondition,
    SkillStudyScheduleCell,
    build_skill_study_schedule,
    evaluate_skill_study,
)
from javis_core.skill_study_collection import SkillStudyCollector
from tools.explorer_folder_smoke import _close_exact_window
from tools.run_safe_file_sort_pilot import _policy_context
from tools.run_skill_study_pilot import (
    MODEL,
    MODEL_CONFIGURATION,
    _bounded_repetitions,
    _canonical_sha256,
    _validated_output_directory,
    _write_evidence_exclusive,
    _write_report_atomic,
)
from tools.s03_memory_pdf_smoke import RecordingExecutor

TASK_ID = "explorer-folder-open"
PARTICIPANT_ID = "pilot01"
ROOT_ID = "fixture"
RELATIVE_PATH = "Study Materials"
MARKER_NAME = ".study_marker"
MARKER_CONTENT = b"JAVIS explorer skill study fixture\n"


def _registry() -> CapabilityRegistry:
    return CapabilityRegistry(
        item
        for item in default_registry().list()
        if item.capability_id == "explorer.folder.open"
    )


def _goal() -> str:
    return (
        "Open exactly the authorized Study Materials folder in registered Windows "
        "Explorer, verify the exact folder and new Explorer window, then stop."
    )


def _condition_context(
    condition: SkillStudyCondition,
    target_identity: str,
) -> dict[str, object]:
    context: dict[str, object] = {
        "authorized_folder": {
            "root_id": ROOT_ID,
            "relative_path": RELATIVE_PATH,
            "target_identity": target_identity,
            "required_postcondition": "explorer.folder.verified",
        }
    }
    if condition is SkillStudyCondition.SK1_STORED_INSTRUCTION:
        context["stored_instruction"] = (
            "Use one explorer.folder.open action with the supplied root ID, relative "
            "path, target identity and explorer.folder.verified postcondition."
        )
    elif condition is SkillStudyCondition.SK2_INITIAL_SKILL:
        context["initial_skill"] = {
            "procedure": [
                "copy the authorized folder binding",
                "open it once with explorer.folder.open",
                "verify explorer.folder.verified and stop",
            ],
            "dynamic_inputs": ["root ID", "relative folder path", "folder identity"],
            "decision_rules": ["use only the supplied authorized_folder object"],
            "verification_rules": ["exact folder, process and new window must match"],
        }
    elif condition is SkillStudyCondition.SK3_REVISED_SKILL:
        context["revised_skill"] = {
            "procedure": [
                "copy every authorized_folder field without alteration",
                "emit exactly one explorer.folder.open action",
                "require explorer.folder.verified and stop after verification",
            ],
            "dynamic_inputs": ["authorized_folder object"],
            "decision_rules": [
                "never substitute another root, relative path or target identity",
                "never emit another capability or repeat the open action",
                "never request continuation after verification",
            ],
            "verification_rules": [
                "registered Explorer process identity matches",
                "one new Explorer HWND displays the exact folder",
                "the verified HWND is closed after measurement",
            ],
        }
    return context


def _write_fixture(root: Path) -> Path:
    folder = root / RELATIVE_PATH
    folder.mkdir()
    (folder / MARKER_NAME).write_bytes(MARKER_CONTENT)
    return folder


def _marker_sha256(folder: Path) -> str:
    return hashlib.sha256((folder / MARKER_NAME).read_bytes()).hexdigest()


def _validate_exact_plan(plan: Plan, target_identity: str) -> Action:
    if plan.goal != _goal() or len(plan.steps) != 1:
        raise ValueError("Explorer pilot requires exactly one action for the exact goal")
    action = plan.steps[0]
    if (
        action.capability_id != "explorer.folder.open"
        or action.arguments
        != {"root_id": ROOT_ID, "relative_path": RELATIVE_PATH}
        or action.target_identity != target_identity
        or action.expected_postconditions
        != (Postcondition(predicate="explorer.folder.verified"),)
        or plan.continue_after_verification
    ):
        raise ValueError("Explorer pilot plan did not preserve the exact folder binding")
    return action


def _close_execution_window(
    result: ExecutionResult | None,
    close_window: Callable[[int], bool],
) -> bool:
    if result is None or not result.success:
        return False
    hwnd = result.observed.get("hwnd")
    return type(hwnd) is int and close_window(hwnd)


class ExplorerFolderConditionRunner:
    def __init__(
        self,
        evidence_directory: Path,
        apps_path: Path,
        *,
        close_window: Callable[[int], bool] = _close_exact_window,
    ) -> None:
        self._registry = _registry()
        self._evidence_directory = evidence_directory
        self._explorer: RegisteredApp = AppRegistryLoader(
            require_publisher=True,
            allow_signed_updates=True,
        ).load(apps_path)["explorer"]
        self._close_window = close_window
        self._model_configuration_sha256 = _canonical_sha256(MODEL_CONFIGURATION)
        self._tool_surface_sha256 = _canonical_sha256(
            [item.model_dump(mode="json") for item in self._registry.list()]
        )
        self._initial_state_sha256 = _canonical_sha256(
            {
                "directories": [RELATIVE_PATH],
                "files": {
                    f"{RELATIVE_PATH}/{MARKER_NAME}": hashlib.sha256(
                        MARKER_CONTENT
                    ).hexdigest()
                },
                "app_id": "explorer",
            }
        )

    def run(self, cell: SkillStudyScheduleCell) -> SkillTrialObservation:
        started = perf_counter_ns()
        succeeded = False
        verified = False
        window_closed = False
        marker_unchanged = False
        reason = "RUNNER_FAILED"
        evidence_plan: dict[str, object] = {"accepted": False}
        transport = NimChatTransport(
            load_nim_credential(),
            model=MODEL,
            timeout_seconds=60,
            max_tokens=1_800,
        )
        with tempfile.TemporaryDirectory(
            prefix="javis-explorer-skill-study-",
            ignore_cleanup_errors=True,
        ) as raw:
            root = Path(raw).resolve(strict=True)
            folder = _write_fixture(root)
            marker_before = _marker_sha256(folder)
            target_identity = explorer_folder_target_identity(
                {ROOT_ID: root}, ROOT_ID, RELATIVE_PATH
            )
            if target_identity is None:
                raise RuntimeError("fixture folder identity could not be created")
            recording: RecordingExecutor | None = None
            try:
                plan = TypedPlanner(transport, self._registry).plan(
                    _goal(),
                    trusted_context=_condition_context(cell.condition, target_identity),
                )
                action = _validate_exact_plan(plan, target_identity)
                evidence_plan = {
                    "accepted": True,
                    "step_count": 1,
                    "capability_id": action.capability_id,
                    "target_binding_matches": True,
                }
                resolver = WindowsRuntimeWindowResolver(timeout_seconds=4.0)
                explorer_executor = ExplorerFolderOpenExecutor(
                    {ROOT_ID: root},
                    self._explorer,
                    window_resolver=resolver,
                )
                recording = RecordingExecutor(explorer_executor)
                outcome = Orchestrator(
                    policy=PolicyEngine(self._registry),
                    executor=CapabilityExecutorRouter(
                        "native", {"explorer.folder.open": recording}
                    ),
                    verifier=CapabilityVerifierRouter(
                        {
                            "explorer.folder.open": ExplorerFolderVerifier(
                                explorer_executor,
                                window_resolver=resolver,
                            )
                        }
                    ),
                    audit=InMemoryAuditSink(),
                    approvals=ApprovalTokenService(
                        b"javis-explorer-study-approval-key-0001"
                    ),
                ).run(plan, _policy_context)
                verified = outcome.status is ActionStatus.SUCCEEDED
                reason = outcome.reason.upper()[:80]
            except Exception as error:
                reason = type(error).__name__.upper()[:80]
            finally:
                metrics = transport.metrics_snapshot()
                if recording is not None:
                    try:
                        window_closed = _close_execution_window(
                            recording.result, self._close_window
                        )
                    except Exception:
                        window_closed = False
                marker_unchanged = (
                    folder.is_dir()
                    and (folder / MARKER_NAME).is_file()
                    and _marker_sha256(folder) == marker_before
                )
                succeeded = verified and window_closed and marker_unchanged
                if verified and not window_closed:
                    reason = "EXPLORER_WINDOW_CLEANUP_FAILED"

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
            "folder_process_window_verified": verified,
            "verified_window_closed": window_closed,
            "fixture_marker_hash_unchanged": marker_unchanged,
            "nim_metrics": metrics.model_dump(mode="json"),
            "absolute_path_emitted": False,
            "window_handle_emitted": False,
            "window_content_emitted": False,
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
    parser.add_argument("--seed", type=int, default=20_261_016)
    parser.add_argument(
        "--apps",
        default=str(Path(__file__).resolve().parent.parent / "config" / "apps.json"),
    )
    arguments = parser.parse_args(argv)
    output = _validated_output_directory(arguments.output_directory)
    apps_path = Path(arguments.apps)
    if not apps_path.is_absolute() or not apps_path.is_file() or apps_path.is_symlink():
        raise ValueError("app registry must be an absolute regular file")
    schedule = build_skill_study_schedule(
        participant_id=arguments.participant_id,
        task_ids=(TASK_ID,),
        repetitions=arguments.repetitions,
        seed=arguments.seed,
    )
    collector = SkillStudyCollector(schedule, output / "ledger.jsonl")
    runner = ExplorerFolderConditionRunner(output, apps_path.resolve(strict=True))
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
