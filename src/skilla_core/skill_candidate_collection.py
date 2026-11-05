from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

from pydantic import Field

from .models import FrozenModel
from .skill_candidate_evaluation import (
    SkillCandidateEvaluation,
    SkillCandidateEvaluationError,
    SkillCandidateTrial,
    evaluate_revision_candidate,
)
from .skill_candidate_runner import (
    SkillCandidateConditionRunner,
    collect_revision_candidate_trials,
    validate_revision_candidate_pair,
)
from .skill_runtime import LocalSkillCatalog


class SkillCandidateLedgerRecord(FrozenModel):
    sequence: int = Field(ge=1)
    trial: SkillCandidateTrial


class SkillCandidateCollector:
    """Append-only, resume-safe paired runner for one exact revision candidate."""

    def __init__(
        self,
        catalog: LocalSkillCatalog,
        baseline_skill_id: UUID,
        candidate_skill_id: UUID,
        block_ids: tuple[str, ...],
        ledger_path: Path,
    ) -> None:
        if (
            not block_ids
            or len(block_ids) > 10_000
            or len(set(block_ids)) != len(block_ids)
        ):
            raise SkillCandidateEvaluationError(
                "candidate block identifiers must be non-empty and unique"
            )
        if (
            not ledger_path.is_absolute()
            or ledger_path.is_symlink()
            or not ledger_path.parent.is_dir()
        ):
            raise SkillCandidateEvaluationError(
                "candidate ledger path must be absolute in an existing directory"
            )
        self._catalog = catalog
        self._baseline_skill_id = baseline_skill_id
        self._candidate_skill_id = candidate_skill_id
        self._block_ids = block_ids
        self._path = ledger_path
        validate_revision_candidate_pair(
            catalog,
            baseline_skill_id,
            candidate_skill_id,
        )
        self._records = self._load()
        if len(self._records) > len(block_ids):
            raise SkillCandidateEvaluationError("candidate ledger exceeds the schedule")
        for index, record in enumerate(self._records):
            if record.sequence != index + 1:
                raise SkillCandidateEvaluationError(
                    "candidate ledger sequence is not contiguous"
                )
            self._validate_trial(record.trial, index)

    @property
    def complete(self) -> bool:
        return len(self._records) == len(self._block_ids)

    @property
    def trials(self) -> tuple[SkillCandidateTrial, ...]:
        return tuple(record.trial for record in self._records)

    def collect_next(
        self,
        runner: SkillCandidateConditionRunner,
    ) -> SkillCandidateLedgerRecord:
        if self.complete:
            raise SkillCandidateEvaluationError(
                "candidate evaluation schedule is already complete"
            )
        index = len(self._records)
        trial = collect_revision_candidate_trials(
            self._catalog,
            self._baseline_skill_id,
            self._candidate_skill_id,
            (self._block_ids[index],),
            runner,
            start_index=index,
        )[0]
        self._validate_trial(trial, index)
        record = SkillCandidateLedgerRecord(sequence=index + 1, trial=trial)
        self._append(record)
        self._records += (record,)
        return record

    def evaluate(
        self,
        *,
        minimum_trials: int = 3,
        maximum_elapsed_ratio: float = 1.25,
        maximum_token_ratio: float = 1.25,
    ) -> SkillCandidateEvaluation:
        if not self.complete:
            raise SkillCandidateEvaluationError(
                "cannot evaluate an incomplete candidate schedule"
            )
        return evaluate_revision_candidate(
            self.trials,
            minimum_trials=minimum_trials,
            maximum_elapsed_ratio=maximum_elapsed_ratio,
            maximum_token_ratio=maximum_token_ratio,
        )

    def export_trials(self, destination: Path) -> None:
        if not self.complete:
            raise SkillCandidateEvaluationError(
                "cannot export an incomplete candidate schedule"
            )
        if (
            not destination.is_absolute()
            or destination.is_symlink()
            or not destination.parent.is_dir()
        ):
            raise SkillCandidateEvaluationError(
                "candidate export path must be absolute in an existing directory"
            )
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        if temporary.exists() or temporary.is_symlink():
            raise SkillCandidateEvaluationError(
                "candidate temporary export path already exists"
            )
        payload = json.dumps(
            [trial.model_dump(mode="json") for trial in self.trials],
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _validate_trial(self, trial: SkillCandidateTrial, index: int) -> None:
        if (
            trial.block_id != self._block_ids[index]
            or trial.baseline_skill_id != self._baseline_skill_id
            or trial.candidate_skill_id != self._candidate_skill_id
            or trial.baseline_executed_first != (index % 2 == 0)
        ):
            raise SkillCandidateEvaluationError(
                "candidate ledger trial does not match the fixed schedule"
            )

    def _load(self) -> tuple[SkillCandidateLedgerRecord, ...]:
        if not self._path.exists():
            return ()
        if not self._path.is_file() or self._path.is_symlink():
            raise SkillCandidateEvaluationError(
                "candidate ledger must be a regular file"
            )
        if self._path.stat().st_size > 50_000_000:
            raise SkillCandidateEvaluationError("candidate ledger exceeded size limit")
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            if any(not line.strip() for line in lines):
                raise ValueError
            return tuple(
                SkillCandidateLedgerRecord.model_validate_json(line) for line in lines
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise SkillCandidateEvaluationError("invalid candidate ledger") from error

    def _append(self, record: SkillCandidateLedgerRecord) -> None:
        payload = (record.model_dump_json() + "\n").encode("utf-8")
        try:
            with self._path.open("ab") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise SkillCandidateEvaluationError(
                "failed to append candidate ledger"
            ) from error
