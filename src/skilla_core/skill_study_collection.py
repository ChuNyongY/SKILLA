from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from pydantic import Field

from .models import FrozenModel
from .skill_study import (
    SkillStudyError,
    SkillStudyScheduleCell,
    SkillTrialObservation,
)


class SkillStudyConditionRunner(Protocol):
    def run(self, cell: SkillStudyScheduleCell) -> SkillTrialObservation: ...


class SkillStudyLedgerRecord(FrozenModel):
    sequence: int = Field(ge=1)
    cell: SkillStudyScheduleCell
    observation: SkillTrialObservation


class SkillStudyCollector:
    """Resume-safe, append-only collector for a fixed SK0-SK3 schedule."""

    def __init__(
        self,
        schedule: tuple[SkillStudyScheduleCell, ...],
        ledger_path: Path,
    ) -> None:
        if not schedule:
            raise SkillStudyError("skill study collection requires a schedule")
        if (
            not ledger_path.is_absolute()
            or ledger_path.is_symlink()
            or not ledger_path.parent.is_dir()
        ):
            raise SkillStudyError("skill study ledger path must be absolute and local")
        self._schedule = schedule
        self._path = ledger_path
        self._records = self._load()
        if len(self._records) > len(schedule):
            raise SkillStudyError("skill study ledger exceeds the schedule")
        for index, record in enumerate(self._records):
            if record.sequence != index + 1 or record.cell != schedule[index]:
                raise SkillStudyError("skill study ledger does not match the schedule prefix")
            _validate_observation(record.cell, record.observation)

    @property
    def complete(self) -> bool:
        return len(self._records) == len(self._schedule)

    @property
    def observations(self) -> tuple[SkillTrialObservation, ...]:
        return tuple(record.observation for record in self._records)

    def collect_next(self, runner: SkillStudyConditionRunner) -> SkillStudyLedgerRecord:
        if self.complete:
            raise SkillStudyError("skill study schedule is already complete")
        cell = self._schedule[len(self._records)]
        observation = runner.run(cell)
        _validate_observation(cell, observation)
        record = SkillStudyLedgerRecord(
            sequence=len(self._records) + 1,
            cell=cell,
            observation=observation,
        )
        self._append(record)
        self._records += (record,)
        return record

    def export_observations(self, destination: Path) -> None:
        if not self.complete:
            raise SkillStudyError("cannot export an incomplete skill study schedule")
        if (
            not destination.is_absolute()
            or destination.is_symlink()
            or not destination.parent.is_dir()
        ):
            raise SkillStudyError("skill study export path must be absolute and local")
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        if temporary.exists() or temporary.is_symlink():
            raise SkillStudyError("skill study temporary export path already exists")
        payload = json.dumps(
            [item.model_dump(mode="json") for item in self.observations],
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

    def _load(self) -> tuple[SkillStudyLedgerRecord, ...]:
        if not self._path.exists():
            return ()
        if not self._path.is_file() or self._path.is_symlink():
            raise SkillStudyError("skill study ledger must be a regular file")
        if self._path.stat().st_size > 50_000_000:
            raise SkillStudyError("skill study ledger exceeded size limit")
        try:
            records = []
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    raise ValueError
                records.append(SkillStudyLedgerRecord.model_validate_json(line))
            return tuple(records)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise SkillStudyError("invalid skill study ledger") from exc

    def _append(self, record: SkillStudyLedgerRecord) -> None:
        payload = (record.model_dump_json() + "\n").encode("utf-8")
        try:
            with self._path.open("ab") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise SkillStudyError("failed to append skill study ledger") from exc


def _validate_observation(
    cell: SkillStudyScheduleCell,
    observation: SkillTrialObservation,
) -> None:
    identity = (
        observation.participant_id,
        observation.task_id,
        observation.repetition,
        observation.condition,
    )
    expected = (cell.participant_id, cell.task_id, cell.repetition, cell.condition)
    if identity != expected:
        raise SkillStudyError("runner observation does not match the scheduled cell")
