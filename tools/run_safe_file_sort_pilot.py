"""Run a bounded NIM file-sort pilot inside a newly-created temporary sandbox."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import NoReturn

from javis_core import (
    Action,
    ApprovalArtifact,
    ApprovalTokenService,
    CapabilityExecutorRouter,
    CapabilityRegistry,
    CapabilityVerifierRouter,
    FileMovedPredicate,
    FileMoveExecutor,
    InMemoryAuditSink,
    InMemoryMoveJournal,
    NativeReadOnlyExecutor,
    NimChatTransport,
    Orchestrator,
    Plan,
    PolicyContext,
    PolicyDecision,
    PolicyEngine,
    PredicateVerifier,
    TypedPlanner,
    default_registry,
    load_nim_credential,
)
from javis_core.observation_loop import (
    BoundedObservationAgent,
    InMemoryVerifiedResultObserver,
    ObservationLoopStatus,
    OrchestratorRoundRunner,
    VerifiedActionObservation,
)

MODEL = "z-ai/glm-5.3-flash"
GOAL = (
    "Inspect the exact authorized folder, then sort only math_week1.txt into math/ "
    "and english_week1.txt into english/. Preserve both file contents."
)


def _pilot_registry() -> CapabilityRegistry:
    allowed = {"file.list", "file.move"}
    return CapabilityRegistry(
        item for item in default_registry().list() if item.capability_id in allowed
    )


class SandboxYellowApproval:
    """Approve only exact file moves fully contained by one temporary root."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve(strict=True)

    def approve_yellow(
        self,
        plan: Plan,
        action: Action,
        decision: PolicyDecision,
    ) -> bool:
        del plan, decision
        if action.capability_id != "file.move" or set(action.arguments) != {
            "source",
            "destination",
        }:
            return False
        source_raw = action.arguments.get("source")
        destination_raw = action.arguments.get("destination")
        if not isinstance(source_raw, str) or not isinstance(destination_raw, str):
            return False
        try:
            source = Path(source_raw).resolve(strict=True)
            destination_input = Path(destination_raw)
            destination = destination_input.parent.resolve(strict=True) / destination_input.name
        except OSError:
            return False
        return (
            source.is_file()
            and source.is_relative_to(self._root)
            and destination.parent.is_relative_to(self._root)
            and action.target_identity == str(source)
        )

    def approve_red(
        self,
        plan: Plan,
        action: Action,
        decision: PolicyDecision,
    ) -> ApprovalArtifact | None:
        del plan, action, decision
        return None


class ExactFileSortCompletionProbe:
    def __init__(self, root: Path) -> None:
        self._root = root

    def completed(
        self,
        goal: str,
        observations: tuple[VerifiedActionObservation, ...],
    ) -> bool:
        del goal, observations
        try:
            return (
                not (self._root / "math_week1.txt").exists()
                and not (self._root / "english_week1.txt").exists()
                and (self._root / "math" / "math_week1.txt").read_text(
                    encoding="utf-8"
                )
                == "algebra"
                and (self._root / "english" / "english_week1.txt").read_text(
                    encoding="utf-8"
                )
                == "essay"
            )
        except OSError:
            return False


def _policy_context(_action: Action) -> PolicyContext:
    return PolicyContext(
        addressed_confidence=1.0,
        intent_confidence=1.0,
        target_confidence=1.0,
        target_matches_plan=True,
    )


def _relative_files(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )


def _fail(report: dict[str, object], error: Exception) -> NoReturn:
    report.update(
        {
            "status": "ERROR",
            "reason": type(error).__name__,
            "error": str(error)[:300],
        }
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1)


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="javis-file-sort-pilot-")).resolve(strict=True)
    (root / "math").mkdir()
    (root / "english").mkdir()
    (root / "math_week1.txt").write_text("algebra", encoding="utf-8")
    (root / "english_week1.txt").write_text("essay", encoding="utf-8")
    report: dict[str, object] = {
        "schema_version": "1.0",
        "root": str(root),
        "model": MODEL,
    }
    transport: NimChatTransport | None = None
    try:
        registry = _pilot_registry()
        transport = NimChatTransport(
            load_nim_credential(),
            model=MODEL,
            timeout_seconds=60,
            max_tokens=1_800,
        )
        planner = TypedPlanner(transport, registry)
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
                "file.move": PredicateVerifier({"file.moved": FileMovedPredicate()}),
            }
        )
        audit = InMemoryAuditSink()
        tokens = ApprovalTokenService(b"javis-safe-pilot-approval-key-0001")
        broker = SandboxYellowApproval(root)

        def orchestrator_factory(
            observer: InMemoryVerifiedResultObserver,
        ) -> Orchestrator:
            return Orchestrator(
                policy=PolicyEngine(registry),
                executor=executor,
                verifier=verifier,
                audit=audit,
                approvals=tokens,
                approval_broker=broker,
                verified_result_observer=observer,
            )

        probe = ExactFileSortCompletionProbe(root)
        result = BoundedObservationAgent(
            planner,
            OrchestratorRoundRunner(orchestrator_factory, _policy_context),
            probe,
            registry,
            max_rounds=3,
        ).run(
            GOAL,
            trusted_context={
                "authorized_root": str(root),
                "required_destination_by_file": {
                    "math_week1.txt": str(root / "math" / "math_week1.txt"),
                    "english_week1.txt": str(
                        root / "english" / "english_week1.txt"
                    ),
                },
            },
        )
        independently_completed = probe.completed(GOAL, result.observations)
        report.update(
            {
                "status": result.status.value,
                "reason": result.reason,
                "rounds": result.rounds,
                "observation_count": len(result.observations),
                "nim_metrics": transport.metrics_snapshot().model_dump(mode="json"),
                "final_files": _relative_files(root),
                "journal_states": [item.state.value for item in journal.records],
                "audit_events": len(audit.events),
                "independent_completed": independently_completed,
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return int(
            result.status is not ObservationLoopStatus.COMPLETED
            or not independently_completed
        )
    except Exception as error:
        if transport is not None:
            report["nim_metrics"] = transport.metrics_snapshot().model_dump(mode="json")
        report["final_files"] = _relative_files(root)
        _fail(report, error)


if __name__ == "__main__":
    raise SystemExit(main())
