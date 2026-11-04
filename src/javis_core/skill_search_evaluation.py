from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from .models import FrozenModel
from .skill_runtime import (
    LocalSkillCatalog,
    SkillRetrievalDecision,
)


class SkillSearchEvaluationError(ValueError):
    pass


class SkillSearchCase(FrozenModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    query: str = Field(min_length=1, max_length=4_000)
    expected_skill_key: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{1,63}$",
    )

    @model_validator(mode="after")
    def query_is_safe_text(self) -> SkillSearchCase:
        if not self.query.strip() or "\0" in self.query:
            raise ValueError("skill search query must be non-empty and contain no NUL")
        return self


class SkillSearchOutcome(StrEnum):
    CORRECT = "CORRECT"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    FALSE_NEGATIVE = "FALSE_NEGATIVE"
    WRONG_SKILL = "WRONG_SKILL"
    AMBIGUOUS = "AMBIGUOUS"


class SkillSearchCaseResult(FrozenModel):
    case_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    expected_skill_key: str | None = None
    retrieval_decision: SkillRetrievalDecision
    selected_skill_key: str | None = None
    outcome: SkillSearchOutcome


class SkillSearchReport(FrozenModel):
    total: int = Field(ge=1)
    correct: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)
    wrong_skill: int = Field(ge=0)
    ambiguous: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    results: tuple[SkillSearchCaseResult, ...] = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def counts_cover_every_case(self) -> SkillSearchReport:
        classified = (
            self.correct
            + self.false_positive
            + self.false_negative
            + self.wrong_skill
            + self.ambiguous
        )
        if classified != self.total or len(self.results) != self.total:
            raise ValueError("skill search report counts must cover every case exactly once")
        return self


def evaluate_skill_search(
    catalog: LocalSkillCatalog,
    cases: tuple[SkillSearchCase, ...],
) -> SkillSearchReport:
    if not cases:
        raise SkillSearchEvaluationError("skill search evaluation requires cases")
    if len(cases) > 10_000:
        raise SkillSearchEvaluationError("skill search evaluation exceeded case limit")
    if len({case.case_id for case in cases}) != len(cases):
        raise SkillSearchEvaluationError("skill search case identifiers must be unique")

    results: list[SkillSearchCaseResult] = []
    for case in cases:
        retrieval = catalog.retrieve(case.query)
        selected_key = (
            retrieval.selected_skill.key if retrieval.selected_skill is not None else None
        )
        if retrieval.decision is SkillRetrievalDecision.AMBIGUOUS:
            outcome = SkillSearchOutcome.AMBIGUOUS
        elif retrieval.decision is SkillRetrievalDecision.NO_MATCH:
            outcome = (
                SkillSearchOutcome.CORRECT
                if case.expected_skill_key is None
                else SkillSearchOutcome.FALSE_NEGATIVE
            )
        elif case.expected_skill_key is None:
            outcome = SkillSearchOutcome.FALSE_POSITIVE
        elif selected_key == case.expected_skill_key:
            outcome = SkillSearchOutcome.CORRECT
        else:
            outcome = SkillSearchOutcome.WRONG_SKILL
        results.append(
            SkillSearchCaseResult(
                case_id=case.case_id,
                expected_skill_key=case.expected_skill_key,
                retrieval_decision=retrieval.decision,
                selected_skill_key=selected_key,
                outcome=outcome,
            )
        )

    frozen_results = tuple(results)
    count = len(frozen_results)
    counts = {
        outcome: sum(item.outcome is outcome for item in frozen_results)
        for outcome in SkillSearchOutcome
    }
    return SkillSearchReport(
        total=count,
        correct=counts[SkillSearchOutcome.CORRECT],
        false_positive=counts[SkillSearchOutcome.FALSE_POSITIVE],
        false_negative=counts[SkillSearchOutcome.FALSE_NEGATIVE],
        wrong_skill=counts[SkillSearchOutcome.WRONG_SKILL],
        ambiguous=counts[SkillSearchOutcome.AMBIGUOUS],
        accuracy=counts[SkillSearchOutcome.CORRECT] / count,
        results=frozen_results,
    )


def load_skill_search_cases(path: Path) -> tuple[SkillSearchCase, ...]:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise SkillSearchEvaluationError(
            "skill search case path must be an absolute regular file"
        )
    if path.stat().st_size > 2_000_000:
        raise SkillSearchEvaluationError("skill search case file exceeded size limit")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
        if not isinstance(document, list):
            raise TypeError
        cases = tuple(SkillSearchCase.model_validate(item) for item in document)
        if not cases:
            raise ValueError
        return cases
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise SkillSearchEvaluationError("invalid skill search case document") from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result
