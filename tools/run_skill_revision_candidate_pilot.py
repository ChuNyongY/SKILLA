"""Run a real three-block file-sort comparison for a VERIFIED/DRAFT skill pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from time import perf_counter_ns
from uuid import UUID, uuid4

from skilla_core import (
    ApprovalTokenService,
    CapabilityExecutorRouter,
    CapabilityVerifierRouter,
    FileMovedPredicate,
    FileMoveExecutor,
    InMemoryAuditSink,
    InMemoryMoveJournal,
    LocalSkillCatalog,
    NativeReadOnlyExecutor,
    NimChatTransport,
    Orchestrator,
    PolicyEngine,
    PredicateVerifier,
    SkillCandidateCollector,
    SkillCandidateRunMeasurement,
    SkillProposal,
    SkillRecord,
    TypedPlanner,
    load_nim_credential,
)
from skilla_core.observation_loop import (
    BoundedObservationAgent,
    InMemoryVerifiedResultObserver,
    ObservationLoopStatus,
    OrchestratorRoundRunner,
)
from tools.run_safe_file_sort_pilot import (
    ExactFileSortCompletionProbe,
    SandboxYellowApproval,
    _pilot_registry,
    _policy_context,
)
from tools.run_skill_study_pilot import (
    MODEL,
    MODEL_CONFIGURATION,
    _canonical_sha256,
    _relative_state,
    _write_evidence_exclusive,
    _write_report_atomic,
)

BLOCK_IDS = ("block-1", "block-2", "block-3")


def _initial_proposal() -> SkillProposal:
    return SkillProposal(
        key="weekly-file-sort",
        title="주간 과제 파일 정리",
        description="파일명 접두어에 따라 기존 과목 폴더로 이동한다.",
        triggers=("과제 자료 정리", "이번 주 파일 정리"),
        procedure=(
            "허용된 폴더의 현재 항목을 확인한다.",
            "파일명 접두어로 과목을 판단한다.",
            "해당 과목 폴더로 파일을 이동한다.",
            "각 이동 결과를 검증한다.",
        ),
        dynamic_inputs=("현재 폴더 항목", "절대 원본 경로", "절대 목적지 경로"),
        decision_rules=("math_는 math 폴더", "english_는 english 폴더"),
        verification_rules=("원본 경로가 없어야 함", "목적지 내용이 같아야 함"),
        allowed_capabilities=("file.list", "file.move"),
    )


def _revised_proposal() -> SkillProposal:
    return SkillProposal(
        key="weekly-file-sort",
        title="주간 과제 파일 정리",
        description="검증된 목록을 사용해 각 파일을 정확히 한 번 이동한다.",
        triggers=("과제 자료 정리", "이번 주 파일 정리"),
        procedure=(
            "상태 변경 전에 file.list만 포함한 읽기 전용 계획을 실행한다.",
            "검증된 항목으로 정확한 절대 원본과 목적지 경로를 만든다.",
            "각 파일을 한 번만 해당 과목 폴더로 이동한다.",
            "file.moved로 두 이동을 검증한 뒤 종료한다.",
        ),
        dynamic_inputs=("검증된 file.list 항목", "허용된 절대 루트"),
        decision_rules=(
            "file.list와 file.move를 한 계획에 섞지 않음",
            "math_week1.txt는 math/math_week1.txt만 허용",
            "english_week1.txt는 english/english_week1.txt만 허용",
            "완료된 이동을 반복하지 않음",
        ),
        verification_rules=(
            "두 원본 경로가 없어야 함",
            "두 목적지 내용 hash가 원본과 같아야 함",
        ),
        allowed_capabilities=("file.list", "file.move"),
    )


class CountingApproval(SandboxYellowApproval):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.count = 0

    def approve_yellow(self, plan: object, action: object, decision: object) -> bool:
        approved = super().approve_yellow(plan, action, decision)  # type: ignore[arg-type]
        if approved:
            self.count += 1
        return approved


class FileSortRevisionRunner:
    def __init__(self, evidence_directory: Path) -> None:
        self._evidence_directory = evidence_directory
        self._registry = _pilot_registry()
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

    def run(self, skill: SkillRecord, block_id: str) -> SkillCandidateRunMeasurement:
        started = perf_counter_ns()
        succeeded = False
        loop_status = "ERROR"
        reason = "RUNNER_FAILED"
        rounds = 0
        approvals = 0
        journal_states: list[str] = []
        final_state: dict[str, object] = {"runner_failed": True}
        transport = NimChatTransport(
            load_nim_credential(),
            model=MODEL,
            timeout_seconds=60,
            max_tokens=1_800,
        )
        with tempfile.TemporaryDirectory(prefix="javis-revision-study-") as raw_root:
            root = Path(raw_root).resolve(strict=True)
            (root / "math").mkdir()
            (root / "english").mkdir()
            (root / "math_week1.txt").write_text("algebra", encoding="utf-8")
            (root / "english_week1.txt").write_text("essay", encoding="utf-8")
            journal = InMemoryMoveJournal()
            try:
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
                approval = CountingApproval(root)
                tokens = ApprovalTokenService(b"javis-revision-pilot-key-material-01")

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

                goal = (
                    f"Inside the authorized root {root}, organize math_week1.txt and "
                    "english_week1.txt into their matching existing subject folders, "
                    "preserve contents, and verify completion."
                )
                context = {
                    "authorized_root": str(root),
                    "verified_skill": {
                        "skill_id": str(skill.skill_id),
                        "version": skill.version,
                        "title": skill.title,
                        "procedure": skill.procedure,
                        "dynamic_inputs": skill.dynamic_inputs,
                        "decision_rules": skill.decision_rules,
                        "verification_rules": skill.verification_rules,
                        "allowed_capabilities": skill.allowed_capabilities,
                    },
                }
                probe = ExactFileSortCompletionProbe(root)
                result = BoundedObservationAgent(
                    TypedPlanner(transport, self._registry),
                    OrchestratorRoundRunner(orchestrator_factory, _policy_context),
                    probe,
                    self._registry,
                    max_rounds=3,
                ).run(goal, trusted_context=context)
                succeeded = (
                    result.status is ObservationLoopStatus.COMPLETED
                    and probe.completed(goal, result.observations)
                )
                loop_status = result.status.value
                reason = result.reason
                rounds = result.rounds
                approvals = approval.count
                journal_states = [item.state.value for item in journal.records]
            except Exception as error:
                reason = type(error).__name__.upper()
            finally:
                metrics = transport.metrics_snapshot()
                final_state = _relative_state(root)
        elapsed_ms = max(0, (perf_counter_ns() - started) // 1_000_000)
        evidence = {
            "schema_version": "1.0",
            "block_id": block_id,
            "skill_id": str(skill.skill_id),
            "skill_version": skill.version,
            "succeeded": succeeded,
            "loop_status": loop_status,
            "reason": reason,
            "rounds": rounds,
            "yellow_approvals": approvals,
            "nim_metrics": metrics.model_dump(mode="json"),
            "journal_states": journal_states,
            "final_state": final_state,
        }
        filename = f"evidence-{block_id}-v{skill.version}-{uuid4()}.json"
        evidence_hash = _write_evidence_exclusive(
            self._evidence_directory / filename,
            evidence,
        )
        return SkillCandidateRunMeasurement(
            block_id=block_id,
            skill_id=skill.skill_id,
            skill_version=skill.version,
            succeeded=succeeded,
            elapsed_ms=elapsed_ms,
            total_tokens=metrics.input_tokens + metrics.output_tokens,
            model_configuration_sha256=self._model_configuration_sha256,
            tool_surface_sha256=self._tool_surface_sha256,
            initial_state_sha256=self._initial_state_sha256,
            evidence_sha256=evidence_hash,
        )


def _output_directory(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise ValueError("output directory must be an existing absolute directory")
    allowed_exact = {
        "skills.sqlite3",
        "candidate-pair.json",
        "candidate-ledger.jsonl",
        "candidate-trials.json",
        "candidate-report.json",
    }
    for item in path.iterdir():
        allowed_evidence = (
            item.name.startswith("evidence-")
            and item.name.endswith(".json")
            and all(
                character.isascii() and (character.isalnum() or character in "._-")
                for character in item.name
            )
        )
        if (
            (item.name not in allowed_exact and not allowed_evidence)
            or item.is_symlink()
            or not item.is_file()
        ):
            raise ValueError("output directory contains an unknown or unsafe entry")
    return path.resolve(strict=True)


def _load_or_create_pair(
    output: Path,
    catalog: LocalSkillCatalog,
) -> tuple[UUID, UUID]:
    path = output / "candidate-pair.json"
    if path.exists():
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
        if set(document) != {"baseline_skill_id", "candidate_skill_id"}:
            raise ValueError("invalid candidate pair metadata")
        return UUID(document["baseline_skill_id"]), UUID(document["candidate_skill_id"])
    baseline = catalog.approve(catalog.propose(_initial_proposal()).skill_id)
    candidate = catalog.propose_revision(baseline.skill_id, _revised_proposal())
    payload = json.dumps(
        {
            "baseline_skill_id": str(baseline.skill_id),
            "candidate_skill_id": str(candidate.skill_id),
        },
        indent=2,
    )
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return baseline.skill_id, candidate.skill_id


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate candidate metadata key")
        result[key] = value
    return result


def main(argv: tuple[str, ...] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory")
    args = parser.parse_args(argv)
    output = _output_directory(args.output_directory)
    catalog = LocalSkillCatalog(output / "skills.sqlite3", _pilot_registry())
    baseline_id, candidate_id = _load_or_create_pair(output, catalog)
    collector = SkillCandidateCollector(
        catalog,
        baseline_id,
        candidate_id,
        BLOCK_IDS,
        output / "candidate-ledger.jsonl",
    )
    runner = FileSortRevisionRunner(output)
    while not collector.complete:
        record = collector.collect_next(runner)
        print(
            json.dumps(
                {
                    "sequence": record.sequence,
                    "block_id": record.trial.block_id,
                    "baseline_succeeded": record.trial.baseline_succeeded,
                    "candidate_succeeded": record.trial.candidate_succeeded,
                    "baseline_executed_first": record.trial.baseline_executed_first,
                }
            ),
            flush=True,
        )
    collector.export_trials(output / "candidate-trials.json")
    report = collector.evaluate()
    _write_report_atomic(
        output / "candidate-report.json",
        report.model_dump_json(indent=2),
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
