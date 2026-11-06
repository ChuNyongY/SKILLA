"""Collect one real, paired SK0-SK3 hash-pinned PDF-open pilot."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter_ns

from skilla_core import (
    Action,
    ActionStatus,
    AppRegistryLoader,
    ApprovalTokenService,
    CapabilityExecutorRouter,
    CapabilityRegistry,
    CapabilityVerifierRouter,
    InMemoryAuditSink,
    NimChatTransport,
    Orchestrator,
    PdfOpenedVerifier,
    Plan,
    PolicyEngine,
    RegisteredApp,
    RegisteredPdfOpenExecutor,
    SkillTrialObservation,
    TypedPlanner,
    WindowsRuntimeWindowResolver,
    default_registry,
    load_nim_credential,
)
from skilla_core.skill_study import (
    SkillStudyCondition,
    SkillStudyScheduleCell,
    build_skill_study_schedule,
    evaluate_skill_study,
)
from skilla_core.skill_study_collection import SkillStudyCollector
from tools.run_safe_file_sort_pilot import _policy_context
from tools.run_skill_study_pilot import (
    MODEL,
    MODEL_CONFIGURATION,
    _bounded_repetitions,
    _canonical_sha256,
    _file_sha256,
    _validated_output_directory,
    _write_evidence_exclusive,
    _write_report_atomic,
)
from tools.s03_memory_pdf_smoke import (
    RecordingExecutor,
    _close_exact_window,
    _write_minimal_pdf,
)

TASK_ID = "pdf-open"
PARTICIPANT_ID = "pilot01"
PDF_NAME = "certification-study.pdf"


def _pdf_registry() -> CapabilityRegistry:
    return CapabilityRegistry(
        item
        for item in default_registry().list()
        if item.capability_id == "file.open"
    )


def _goal() -> str:
    return (
        "Open exactly the hash-pinned certification study PDF with the registered Edge "
        "viewer, verify that exact document and viewer window, then stop."
    )


def _condition_context(
    condition: SkillStudyCondition,
    document: Path,
    digest: str,
) -> dict[str, object]:
    context: dict[str, object] = {
        "authorized_pdf": {
            "path": str(document),
            "sha256": digest,
            "viewer_app_id": "edge",
            "target_identity": f"file-sha256:{digest}",
            "required_postcondition": "file.opened",
        }
    }
    if condition is SkillStudyCondition.SK1_STORED_INSTRUCTION:
        context["stored_instruction"] = (
            "Use one file.open action with the provided path, digest, Edge viewer, "
            "file-sha256 target identity, and file.opened postcondition."
        )
    elif condition is SkillStudyCondition.SK2_INITIAL_SKILL:
        context["initial_skill"] = {
            "procedure": [
                "read the provided immutable PDF identity",
                "open it once with the registered Edge viewer",
                "verify file.opened and stop",
            ],
            "dynamic_inputs": ["absolute PDF path", "current PDF sha256"],
            "decision_rules": ["use only the provided viewer_app_id"],
            "verification_rules": ["file hash and viewer identity must match"],
        }
    elif condition is SkillStudyCondition.SK3_REVISED_SKILL:
        context["revised_skill"] = {
            "procedure": [
                "copy the provided path, sha256 and viewer_app_id without alteration",
                "emit exactly one file.open action",
                "bind target_identity as file-sha256:<provided sha256>",
                "require file.opened and stop after verification",
            ],
            "dynamic_inputs": ["authorized_pdf object"],
            "decision_rules": [
                "never substitute another path, digest, viewer or target identity",
                "never emit more than one action",
            ],
            "verification_rules": [
                "the exact PDF hash still matches",
                "the registered Edge process and new window both match",
            ],
        }
    return context


def _validate_exact_plan(plan: Plan, document: Path, digest: str) -> Action:
    if plan.goal != _goal() or len(plan.steps) != 1:
        raise ValueError("PDF pilot requires exactly one action for the exact goal")
    action = plan.steps[0]
    if (
        action.capability_id != "file.open"
        or action.arguments
        != {
            "path": str(document),
            "sha256": digest,
            "viewer_app_id": "edge",
        }
        or action.target_identity != f"file-sha256:{digest}"
        or len(action.expected_postconditions) != 1
        or action.expected_postconditions[0].predicate != "file.opened"
        or action.expected_postconditions[0].arguments
        or plan.continue_after_verification
    ):
        raise ValueError("PDF pilot plan did not preserve the exact immutable binding")
    return action


class PdfOpenConditionRunner:
    def __init__(
        self,
        evidence_directory: Path,
        apps_path: Path,
        *,
        close_window: Callable[
            [WindowsRuntimeWindowResolver, RegisteredApp, object, object], bool
        ] = _close_exact_window,
    ) -> None:
        self._registry = _pdf_registry()
        self._evidence_directory = evidence_directory
        # Browsers update in place. Match product mode: accept a changed hash only
        # when the executable remains at the registered path and its Authenticode
        # signer exactly matches the pinned publisher.
        self._edge = AppRegistryLoader(
            require_publisher=True,
            allow_signed_updates=True,
        ).load(apps_path)["edge"]
        self._close_window = close_window
        self._model_configuration_sha256 = _canonical_sha256(MODEL_CONFIGURATION)
        self._tool_surface_sha256 = _canonical_sha256(
            [item.model_dump(mode="json") for item in self._registry.list()]
        )
        with tempfile.TemporaryDirectory(prefix="skilla-pdf-state-") as raw:
            fixture = Path(raw) / PDF_NAME
            _write_minimal_pdf(fixture)
            digest = _file_sha256(fixture)
        self._initial_state_sha256 = _canonical_sha256(
            {"files": {PDF_NAME: digest}, "viewer_app_id": "edge"}
        )

    def run(self, cell: SkillStudyScheduleCell) -> SkillTrialObservation:
        started = perf_counter_ns()
        succeeded = False
        verified = False
        window_closed = False
        reason = "RUNNER_FAILED"
        metrics = None
        evidence_plan: dict[str, object] = {"accepted": False}
        with tempfile.TemporaryDirectory(
            prefix="skilla-pdf-skill-study-",
            ignore_cleanup_errors=True,
        ) as raw_root:
            root = Path(raw_root).resolve(strict=True)
            document = root / PDF_NAME
            _write_minimal_pdf(document)
            digest = _file_sha256(document)
            transport = NimChatTransport(
                load_nim_credential(),
                model=MODEL,
                timeout_seconds=60,
                max_tokens=1_800,
            )
            recording: RecordingExecutor | None = None
            try:
                planner = TypedPlanner(transport, self._registry)
                plan = planner.plan(
                    _goal(),
                    trusted_context=_condition_context(cell.condition, document, digest),
                )
                action = _validate_exact_plan(plan, document, digest)
                evidence_plan = {
                    "accepted": True,
                    "step_count": 1,
                    "capability_id": action.capability_id,
                    "target_binding_matches": True,
                }
                pdf_executor = RegisteredPdfOpenExecutor(
                    {"edge": self._edge},
                    (root,),
                )
                recording = RecordingExecutor(pdf_executor)
                outcome = Orchestrator(
                    policy=PolicyEngine(self._registry),
                    executor=CapabilityExecutorRouter(
                        "native",
                        {"file.open": recording},
                    ),
                    verifier=CapabilityVerifierRouter(
                        {"file.open": PdfOpenedVerifier(pdf_executor)}
                    ),
                    audit=InMemoryAuditSink(),
                    approvals=ApprovalTokenService(
                        b"skilla-pdf-study-approval-key-0001"
                    ),
                ).run(plan, _policy_context)
                verified = outcome.status is ActionStatus.SUCCEEDED
                reason = outcome.reason.upper()[:80]
            except Exception as error:
                reason = type(error).__name__.upper()[:80]
            finally:
                metrics = transport.metrics_snapshot()
                if recording is not None and recording.result is not None:
                    observed = recording.result.observed
                    try:
                        window_closed = self._close_window(
                            WindowsRuntimeWindowResolver(),
                            self._edge,
                            observed.get("pid"),
                            observed.get("hwnd"),
                        )
                    except Exception:
                        window_closed = False
                succeeded = (
                    verified
                    and window_closed
                    and document.is_file()
                    and _file_sha256(document) == digest
                )
                if verified and not window_closed:
                    reason = "PDF_WINDOW_CLEANUP_FAILED"

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
            "pdf_hash_unchanged": succeeded,
            "viewer_verified": verified,
            "new_window_closed": window_closed,
            "nim_metrics": metrics.model_dump(mode="json"),
            "path_emitted": False,
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
    parser.add_argument("--seed", type=int, default=20_261_014)
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
    runner = PdfOpenConditionRunner(output, apps_path.resolve(strict=True))
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
