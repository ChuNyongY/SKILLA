from __future__ import annotations

import json
import re
import sqlite3
from collections import OrderedDict
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Annotated, Protocol
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .models import Action, FrozenModel, Plan, Postcondition
from .planner import NimTransportMetrics
from .registry import CapabilityRegistry


class SkillRuntimeError(RuntimeError):
    pass


class SkillStatus(StrEnum):
    DRAFT = "DRAFT"
    VERIFIED = "VERIFIED"
    RETIRED = "RETIRED"


class SkillOutcome(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class SkillPlanningMode(StrEnum):
    NO_SKILL = "NO_SKILL"
    STORED_INSTRUCTION = "STORED_INSTRUCTION"
    INITIAL_SKILL = "INITIAL_SKILL"
    REVISED_SKILL = "REVISED_SKILL"


Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

_KOREAN_QUERY_SUFFIXES = (
    "들에게서",
    "들로부터",
    "들에게",
    "들까지",
    "들부터",
    "들에서",
    "들처럼",
    "들보다",
    "들을",
    "들이",
    "들은",
    "들과",
    "들의",
    "들도",
    "들만",
    "으로부터",
    "에게서",
    "으로",
    "에서",
    "에게",
    "한테",
    "께서",
    "부터",
    "까지",
    "처럼",
    "보다",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "와",
    "과",
    "의",
    "에",
    "도",
    "만",
    "로",
)


class SkillProposal(FrozenModel):
    """A reusable procedure, not executable code and not an authority grant."""

    key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1_000)
    triggers: tuple[str, ...] = Field(min_length=1, max_length=16)
    procedure: tuple[str, ...] = Field(min_length=1, max_length=20)
    dynamic_inputs: tuple[str, ...] = Field(default=(), max_length=20)
    decision_rules: tuple[str, ...] = Field(default=(), max_length=20)
    verification_rules: tuple[str, ...] = Field(default=(), max_length=20)
    allowed_capabilities: tuple[str, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def normalized_and_unique(self) -> SkillProposal:
        if len(set(self.triggers)) != len(self.triggers):
            raise ValueError("skill triggers must be unique")
        if len(set(self.allowed_capabilities)) != len(self.allowed_capabilities):
            raise ValueError("skill capabilities must be unique")
        reusable_text = (
            *self.triggers,
            *self.procedure,
            *self.dynamic_inputs,
            *self.decision_rules,
            *self.verification_rules,
        )
        if any(not item.strip() or "\0" in item for item in reusable_text):
            raise ValueError("skill text must be non-empty and must not contain NUL")
        return self


class SkillRecord(SkillProposal):
    skill_id: UUID
    version: int = Field(ge=1)
    status: SkillStatus
    created_at: datetime
    updated_at: datetime
    supersedes_skill_id: UUID | None = None

    @model_validator(mode="after")
    def timestamps_are_utc(self) -> SkillRecord:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("skill timestamps must be timezone-aware")
        return self


class SkillUseRecord(FrozenModel):
    use_id: UUID
    skill_id: UUID
    skill_version: int = Field(ge=1)
    outcome: SkillOutcome
    observed_at: datetime
    detail_code: str = Field(pattern=r"^[A-Z0-9_.:-]{2,80}$")
    elapsed_ms: int = Field(default=0, ge=0, le=86_400_000)
    llm_calls: int = Field(default=0, ge=0, le=1_000)
    input_tokens: int = Field(default=0, ge=0, le=100_000_000)
    output_tokens: int = Field(default=0, ge=0, le=100_000_000)
    user_interventions: int = Field(default=0, ge=0, le=1_000)
    planning_mode: SkillPlanningMode = SkillPlanningMode.INITIAL_SKILL
    model_configuration_sha256: Sha256Hex | None = None
    tool_surface_sha256: Sha256Hex | None = None
    planner_usage_complete: bool = False
    planner_responses_without_usage: int = Field(default=0, ge=0, le=1_000)

    @model_validator(mode="after")
    def planner_usage_quality_is_consistent(self) -> SkillUseRecord:
        if self.planner_responses_without_usage > self.llm_calls:
            raise ValueError("usage-missing responses cannot exceed planner calls")
        if self.planner_usage_complete and self.planner_responses_without_usage:
            raise ValueError("complete planner usage cannot contain missing responses")
        return self


class SkillPerformanceSummary(FrozenModel):
    skill_id: UUID
    skill_version: int = Field(ge=1)
    observations: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    aborted: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    repeated_failure_code: str | None = None


class SkillRevisionDecision(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    KEEP = "KEEP"
    PROPOSE_REVISION = "PROPOSE_REVISION"


class SkillRevisionAssessment(FrozenModel):
    decision: SkillRevisionDecision
    reason_code: str = Field(pattern=r"^[A-Z0-9_.:-]{2,80}$")
    summary: SkillPerformanceSummary


class SkillStalenessDecision(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CURRENT = "CURRENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class SkillStalenessAssessment(FrozenModel):
    skill_id: UUID
    skill_version: int = Field(ge=1)
    decision: SkillStalenessDecision
    reason_code: str = Field(pattern=r"^[A-Z0-9_.:-]{2,80}$")
    observations_considered: int = Field(ge=0)
    repeated_failure_code: str | None = None
    current_model_configuration_sha256: Sha256Hex
    current_tool_surface_sha256: Sha256Hex


class SkillRetrievalDecision(StrEnum):
    MATCHED = "MATCHED"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"


class SkillRetrievalResult(FrozenModel):
    decision: SkillRetrievalDecision
    selected_skill: SkillRecord | None = None
    top_score: int = Field(default=0, ge=0)
    tied_skill_keys: tuple[str, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def selection_matches_decision(self) -> SkillRetrievalResult:
        if (self.decision is SkillRetrievalDecision.MATCHED) != (
            self.selected_skill is not None
        ):
            raise ValueError("only a matched retrieval may contain a selected skill")
        if self.decision is SkillRetrievalDecision.AMBIGUOUS and len(
            self.tied_skill_keys
        ) < 2:
            raise ValueError("an ambiguous retrieval requires at least two tied skills")
        if self.decision is not SkillRetrievalDecision.AMBIGUOUS and self.tied_skill_keys:
            raise ValueError("only an ambiguous retrieval may contain tied skills")
        return self


class SkillPlanUsage(FrozenModel):
    llm_calls: int = Field(default=0, ge=0, le=1_000)
    input_tokens: int = Field(default=0, ge=0, le=100_000_000)
    output_tokens: int = Field(default=0, ge=0, le=100_000_000)
    responses_without_usage: int = Field(default=0, ge=0, le=1_000)
    complete: bool = False

    @model_validator(mode="after")
    def quality_is_consistent(self) -> SkillPlanUsage:
        if self.responses_without_usage > self.llm_calls:
            raise ValueError("usage-missing responses cannot exceed planner calls")
        if self.complete and self.responses_without_usage:
            raise ValueError("complete planner usage cannot contain missing responses")
        return self


class SkillPlanSelection(FrozenModel):
    skill: SkillRecord
    usage: SkillPlanUsage = Field(default_factory=SkillPlanUsage)


class PlanProposer(Protocol):
    def plan(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan: ...


class LocalSkillCatalog:
    """Versioned local skills with explicit promotion before runtime use.

    A skill can restrict the capabilities a planner may use; it can never add a
    capability that is absent from the immutable Windows capability registry.
    """

    def __init__(self, path: Path, registry: CapabilityRegistry) -> None:
        if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir():
            raise ValueError("skill catalog path must be absolute in an existing directory")
        self._path = path
        self._registry = registry
        self._initialize()

    def propose(self, proposal: SkillProposal, *, now: datetime | None = None) -> SkillRecord:
        self._validate_capabilities(proposal)
        instant = _utc(now)
        existing = self._latest_by_key(proposal.key)
        if existing is not None and existing.status is not SkillStatus.RETIRED:
            raise SkillRuntimeError("active skill key already exists; propose a revision instead")
        return self._insert(
            proposal,
            version=1,
            status=SkillStatus.DRAFT,
            instant=instant,
            supersedes=None,
        )

    def approve(self, skill_id: UUID, *, now: datetime | None = None) -> SkillRecord:
        record = self.require(skill_id)
        if record.status is not SkillStatus.DRAFT:
            raise SkillRuntimeError("only a draft skill can be approved")
        instant = _utc(now)
        with closing(self._connect()) as db, db:
            if record.supersedes_skill_id is not None:
                db.execute(
                    "UPDATE skills SET status=?, updated_at=? WHERE skill_id=?",
                    (
                        SkillStatus.RETIRED.value,
                        instant.isoformat(),
                        str(record.supersedes_skill_id),
                    ),
                )
            db.execute(
                "UPDATE skills SET status=?, updated_at=? WHERE skill_id=?",
                (SkillStatus.VERIFIED.value, instant.isoformat(), str(skill_id)),
            )
        return self.require(skill_id)

    def propose_revision(
        self,
        skill_id: UUID,
        proposal: SkillProposal,
        *,
        now: datetime | None = None,
    ) -> SkillRecord:
        previous = self.require(skill_id)
        if previous.status is not SkillStatus.VERIFIED:
            raise SkillRuntimeError("only a verified skill can be revised")
        if proposal.key != previous.key:
            raise SkillRuntimeError("a revision must keep the same skill key")
        self._validate_capabilities(proposal)
        return self._insert(
            proposal,
            version=previous.version + 1,
            status=SkillStatus.DRAFT,
            instant=_utc(now),
            supersedes=previous.skill_id,
        )

    def retire(self, skill_id: UUID, *, now: datetime | None = None) -> SkillRecord:
        record = self.require(skill_id)
        instant = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE skills SET status=?, updated_at=? WHERE skill_id=?",
                (SkillStatus.RETIRED.value, instant.isoformat(), str(skill_id)),
            )
        return self.require(record.skill_id)

    def require(self, skill_id: UUID) -> SkillRecord:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM skills WHERE skill_id=?", (str(skill_id),)).fetchone()
        if row is None:
            raise SkillRuntimeError("skill not found")
        return _record(row)

    def search(self, query: str, *, limit: int = 3) -> tuple[SkillRecord, ...]:
        if not 1 <= limit <= 20:
            raise ValueError("skill search limit must be within 1..20")
        return tuple(record for _, record in self._scored_matches(query)[:limit])

    def retrieve(self, query: str) -> SkillRetrievalResult:
        """Resolve one verified skill or fail safely when the best score is tied."""
        scored = self._scored_matches(query)
        if not scored:
            return SkillRetrievalResult(decision=SkillRetrievalDecision.NO_MATCH)
        top_score = scored[0][0]
        tied = tuple(record for score, record in scored if score == top_score)
        if len(tied) > 1:
            return SkillRetrievalResult(
                decision=SkillRetrievalDecision.AMBIGUOUS,
                top_score=top_score,
                tied_skill_keys=tuple(sorted(record.key for record in tied)),
            )
        return SkillRetrievalResult(
            decision=SkillRetrievalDecision.MATCHED,
            selected_skill=tied[0],
            top_score=top_score,
        )

    def list(
        self,
        *,
        status: SkillStatus | None = None,
        limit: int = 20,
    ) -> tuple[SkillRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("skill list limit must be within 1..100")
        query = "SELECT * FROM skills"
        parameters: tuple[object, ...] = ()
        if status is not None:
            query += " WHERE status=?"
            parameters = (status.value,)
        query += " ORDER BY updated_at DESC, key, version DESC LIMIT ?"
        parameters += (limit,)
        with closing(self._connect()) as db:
            rows = db.execute(query, parameters).fetchall()
        return tuple(_record(row) for row in rows)

    def record_use(
        self,
        skill: SkillRecord,
        outcome: SkillOutcome,
        detail_code: str,
        *,
        now: datetime | None = None,
        elapsed_ms: int = 0,
        llm_calls: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        user_interventions: int = 0,
        model_configuration_sha256: str | None = None,
        tool_surface_sha256: str | None = None,
        planner_usage_complete: bool = False,
        planner_responses_without_usage: int = 0,
    ) -> SkillUseRecord:
        current = self.require(skill.skill_id)
        if (
            current.status is not SkillStatus.VERIFIED
            or current.version != skill.version
            or current.key != skill.key
        ):
            raise SkillRuntimeError("only verified skills may be used")
        result = SkillUseRecord(
            use_id=uuid4(),
            skill_id=current.skill_id,
            skill_version=current.version,
            outcome=outcome,
            observed_at=_utc(now),
            detail_code=detail_code,
            elapsed_ms=elapsed_ms,
            llm_calls=llm_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            user_interventions=user_interventions,
            model_configuration_sha256=model_configuration_sha256,
            tool_surface_sha256=tool_surface_sha256,
            planner_usage_complete=planner_usage_complete,
            planner_responses_without_usage=planner_responses_without_usage,
            planning_mode=(
                SkillPlanningMode.INITIAL_SKILL
                if current.version == 1
                else SkillPlanningMode.REVISED_SKILL
            ),
        )
        with closing(self._connect()) as db, db:
            db.execute(
                """
                INSERT INTO skill_uses(
                  use_id, skill_id, skill_version, outcome, observed_at, detail_code,
                  elapsed_ms, llm_calls, input_tokens, output_tokens,
                  user_interventions, planning_mode, model_configuration_sha256,
                  tool_surface_sha256, planner_usage_complete,
                  planner_responses_without_usage)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(result.use_id), str(result.skill_id), result.skill_version,
                    result.outcome.value, result.observed_at.isoformat(), result.detail_code,
                    result.elapsed_ms, result.llm_calls, result.input_tokens,
                    result.output_tokens, result.user_interventions,
                    result.planning_mode.value, result.model_configuration_sha256,
                    result.tool_surface_sha256, int(result.planner_usage_complete),
                    result.planner_responses_without_usage,
                ),
            )
        return result

    def summarize_use(self, skill_id: UUID) -> SkillPerformanceSummary:
        skill = self.require(skill_id)
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT outcome, detail_code FROM skill_uses
                WHERE skill_id=? AND skill_version=? ORDER BY observed_at, use_id
                """,
                (str(skill.skill_id), skill.version),
            ).fetchall()
        outcomes = tuple(SkillOutcome(row["outcome"]) for row in rows)
        failure_codes: dict[str, int] = {}
        for row in rows:
            if SkillOutcome(row["outcome"]) is SkillOutcome.FAILED:
                code = str(row["detail_code"])
                failure_codes[code] = failure_codes.get(code, 0) + 1
        repeated = None
        if failure_codes:
            code, count = sorted(failure_codes.items(), key=lambda item: (-item[1], item[0]))[0]
            if count >= 2:
                repeated = code
        succeeded = outcomes.count(SkillOutcome.SUCCEEDED)
        return SkillPerformanceSummary(
            skill_id=skill.skill_id,
            skill_version=skill.version,
            observations=len(outcomes),
            succeeded=succeeded,
            failed=outcomes.count(SkillOutcome.FAILED),
            aborted=outcomes.count(SkillOutcome.ABORTED),
            success_rate=succeeded / len(outcomes) if outcomes else 0.0,
            repeated_failure_code=repeated,
        )

    def assess_revision(
        self,
        skill_id: UUID,
        *,
        minimum_observations: int = 3,
        minimum_success_rate: float = 0.8,
    ) -> SkillRevisionAssessment:
        if minimum_observations < 1 or not 0.0 <= minimum_success_rate <= 1.0:
            raise ValueError("invalid skill revision policy")
        summary = self.summarize_use(skill_id)
        if summary.observations < minimum_observations:
            decision = SkillRevisionDecision.INSUFFICIENT_EVIDENCE
            reason = "TOO_FEW_OBSERVATIONS"
        elif summary.repeated_failure_code is not None:
            decision = SkillRevisionDecision.PROPOSE_REVISION
            reason = "REPEATED_FAILURE"
        elif summary.success_rate < minimum_success_rate:
            decision = SkillRevisionDecision.PROPOSE_REVISION
            reason = "SUCCESS_RATE_BELOW_THRESHOLD"
        else:
            decision = SkillRevisionDecision.KEEP
            reason = "PERFORMANCE_WITHIN_THRESHOLD"
        return SkillRevisionAssessment(decision=decision, reason_code=reason, summary=summary)

    def assess_staleness(
        self,
        skill_id: UUID,
        current_model_configuration_sha256: str,
        current_tool_surface_sha256: str,
        *,
        minimum_observations: int = 3,
    ) -> SkillStalenessAssessment:
        """Assess environment drift without changing the skill lifecycle state."""
        if minimum_observations < 1:
            raise ValueError("minimum observations must be positive")
        skill = self.require(skill_id)
        # Constructing the typed shell validates both caller-supplied SHA-256 values.
        base = {
            "skill_id": skill.skill_id,
            "skill_version": skill.version,
            "observations_considered": 0,
            "current_model_configuration_sha256": current_model_configuration_sha256,
            "current_tool_surface_sha256": current_tool_surface_sha256,
        }
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT outcome, detail_code, model_configuration_sha256,
                       tool_surface_sha256
                FROM skill_uses
                WHERE skill_id=? AND skill_version=?
                ORDER BY observed_at DESC, rowid DESC
                LIMIT ?
                """,
                (str(skill.skill_id), skill.version, minimum_observations),
            ).fetchall()
        evidence = base | {"observations_considered": len(rows)}
        missing_environment = any(
            row["model_configuration_sha256"] is None
            or row["tool_surface_sha256"] is None
            for row in rows
        )
        if len(rows) < minimum_observations or missing_environment:
            return SkillStalenessAssessment(
                **evidence,
                decision=SkillStalenessDecision.INSUFFICIENT_EVIDENCE,
                reason_code=(
                    "TOO_FEW_OBSERVATIONS"
                    if len(rows) < minimum_observations
                    else "MISSING_ENVIRONMENT_EVIDENCE"
                ),
            )

        failure_counts: dict[str, int] = {}
        for row in rows:
            if SkillOutcome(row["outcome"]) is SkillOutcome.FAILED:
                code = str(row["detail_code"])
                failure_counts[code] = failure_counts.get(code, 0) + 1
        repeated_failure_code = next(
            (
                code
                for code, count in sorted(
                    failure_counts.items(), key=lambda item: (-item[1], item[0])
                )
                if count >= 2
            ),
            None,
        )
        if repeated_failure_code is not None:
            return SkillStalenessAssessment(
                **evidence,
                decision=SkillStalenessDecision.REVIEW_REQUIRED,
                reason_code="RECENT_REPEATED_FAILURE",
                repeated_failure_code=repeated_failure_code,
            )
        if any(
            row["tool_surface_sha256"] != current_tool_surface_sha256 for row in rows
        ):
            return SkillStalenessAssessment(
                **evidence,
                decision=SkillStalenessDecision.REVIEW_REQUIRED,
                reason_code="TOOL_SURFACE_CHANGED",
            )
        if any(
            row["model_configuration_sha256"] != current_model_configuration_sha256
            for row in rows
        ):
            return SkillStalenessAssessment(
                **evidence,
                decision=SkillStalenessDecision.REVIEW_REQUIRED,
                reason_code="MODEL_CONFIGURATION_CHANGED",
            )
        return SkillStalenessAssessment(
            **evidence,
            decision=SkillStalenessDecision.CURRENT,
            reason_code="ENVIRONMENT_MATCHED",
        )

    def _latest_by_key(self, key: str) -> SkillRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM skills WHERE key=? ORDER BY version DESC LIMIT 1", (key,)
            ).fetchone()
        return _record(row) if row is not None else None

    def _scored_matches(self, query: str) -> tuple[tuple[int, SkillRecord], ...]:
        tokens = _tokens(query)
        normalized_query = _normalize_phrase(query)
        if not tokens or not normalized_query:
            return ()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM skills WHERE status=?",
                (SkillStatus.VERIFIED.value,),
            ).fetchall()
        scored = [
            (_retrieval_score(normalized_query, tokens, record), record)
            for row in rows
            for record in (_record(row),)
        ]
        scored = [item for item in scored if item[0] > 0]
        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].key,
                -item[1].version,
                str(item[1].skill_id),
            )
        )
        return tuple(scored)

    def _insert(
        self,
        proposal: SkillProposal,
        *,
        version: int,
        status: SkillStatus,
        instant: datetime,
        supersedes: UUID | None,
    ) -> SkillRecord:
        result = SkillRecord(
            skill_id=uuid4(), version=version, status=status, created_at=instant,
            updated_at=instant, supersedes_skill_id=supersedes, **proposal.model_dump(),
        )
        with closing(self._connect()) as db, db:
            db.execute(
                """
                INSERT INTO skills(
                  skill_id, key, version, status, title, description, triggers_json,
                  procedure_json, capabilities_json, created_at, updated_at,
                  supersedes_skill_id, dynamic_inputs_json, decision_rules_json,
                  verification_rules_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(result.skill_id), result.key, result.version, result.status.value,
                    result.title, result.description,
                    json.dumps(result.triggers, ensure_ascii=False),
                    json.dumps(result.procedure, ensure_ascii=False),
                    json.dumps(result.allowed_capabilities), result.created_at.isoformat(),
                    result.updated_at.isoformat(),
                    str(result.supersedes_skill_id) if result.supersedes_skill_id else None,
                    json.dumps(result.dynamic_inputs, ensure_ascii=False),
                    json.dumps(result.decision_rules, ensure_ascii=False),
                    json.dumps(result.verification_rules, ensure_ascii=False),
                ),
            )
        return result

    def _validate_capabilities(self, proposal: SkillProposal) -> None:
        for capability_id in proposal.allowed_capabilities:
            if self._registry.get(capability_id) is None:
                raise SkillRuntimeError("skill references an unregistered capability")

    def _initialize(self) -> None:
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS skills(
                  skill_id TEXT PRIMARY KEY, key TEXT NOT NULL, version INTEGER NOT NULL,
                  status TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
                  triggers_json TEXT NOT NULL, procedure_json TEXT NOT NULL,
                  capabilities_json TEXT NOT NULL, created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL, supersedes_skill_id TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS skill_version ON skills(key, version);
                CREATE TABLE IF NOT EXISTS skill_uses(
                  use_id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, skill_version INTEGER NOT NULL,
                  outcome TEXT NOT NULL, observed_at TEXT NOT NULL, detail_code TEXT NOT NULL,
                  elapsed_ms INTEGER NOT NULL DEFAULT 0, llm_calls INTEGER NOT NULL DEFAULT 0,
                  input_tokens INTEGER NOT NULL DEFAULT 0,
                  output_tokens INTEGER NOT NULL DEFAULT 0,
                  user_interventions INTEGER NOT NULL DEFAULT 0,
                  planning_mode TEXT NOT NULL DEFAULT 'INITIAL_SKILL',
                  model_configuration_sha256 TEXT,
                  tool_surface_sha256 TEXT,
                  planner_usage_complete INTEGER NOT NULL DEFAULT 0,
                  planner_responses_without_usage INTEGER NOT NULL DEFAULT 0);
                """
            )
            _ensure_column(db, "skills", "dynamic_inputs_json", "TEXT NOT NULL DEFAULT '[]'")
            _ensure_column(db, "skills", "decision_rules_json", "TEXT NOT NULL DEFAULT '[]'")
            _ensure_column(db, "skills", "verification_rules_json", "TEXT NOT NULL DEFAULT '[]'")
            _ensure_column(db, "skill_uses", "elapsed_ms", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(db, "skill_uses", "llm_calls", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(db, "skill_uses", "input_tokens", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(db, "skill_uses", "output_tokens", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(db, "skill_uses", "user_interventions", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(
                db,
                "skill_uses",
                "planning_mode",
                "TEXT NOT NULL DEFAULT 'INITIAL_SKILL'",
            )
            _ensure_column(db, "skill_uses", "model_configuration_sha256", "TEXT")
            _ensure_column(db, "skill_uses", "tool_surface_sha256", "TEXT")
            _ensure_column(
                db,
                "skill_uses",
                "planner_usage_complete",
                "INTEGER NOT NULL DEFAULT 0",
            )
            _ensure_column(
                db,
                "skill_uses",
                "planner_responses_without_usage",
                "INTEGER NOT NULL DEFAULT 0",
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection


class SkillAwarePlanner:
    """Reuse a verified skill when one matches, otherwise request a base plan."""

    def __init__(
        self,
        planner: PlanProposer,
        catalog: LocalSkillCatalog,
        *,
        max_pending_selections: int = 1_024,
    ) -> None:
        if not 1 <= max_pending_selections <= 100_000:
            raise ValueError("pending skill selection limit must be within 1..100000")
        self._planner = planner
        self._catalog = catalog
        self._selection_limit = max_pending_selections
        self._selection_lock = Lock()
        self._planning_lock = Lock()
        self._selections: OrderedDict[UUID, SkillPlanSelection] = OrderedDict()

    def plan(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan:
        retrieval = self._catalog.retrieve(goal)
        if retrieval.decision is not SkillRetrievalDecision.MATCHED:
            plan, _usage = self._plan_with_usage(
                goal,
                trusted_context=trusted_context,
                untrusted_context=untrusted_context,
            )
            return plan
        skill = retrieval.selected_skill
        if skill is None:  # defensive narrowing; model validation enforces this invariant
            raise SkillRuntimeError("matched skill retrieval did not contain a skill")
        deterministic_plan = _deterministic_verified_skill_plan(
            goal,
            skill,
            untrusted_context=untrusted_context,
        )
        if deterministic_plan is not None:
            if not _is_observation_context(trusted_context):
                self._remember_selection(
                    deterministic_plan.task_id,
                    SkillPlanSelection(
                        skill=skill,
                        usage=SkillPlanUsage(complete=True),
                    ),
                )
            return deterministic_plan
        context = dict(trusted_context or {})
        context["verified_skill"] = {
            "skill_id": str(skill.skill_id),
            "version": skill.version,
            "title": skill.title,
            "procedure": skill.procedure,
            "dynamic_inputs": skill.dynamic_inputs,
            "decision_rules": skill.decision_rules,
            "verification_rules": skill.verification_rules,
            "allowed_capabilities": skill.allowed_capabilities,
        }
        plan, usage = self._plan_with_usage(
            goal, trusted_context=context, untrusted_context=untrusted_context
        )
        allowed = set(skill.allowed_capabilities)
        if any(action.capability_id not in allowed for action in plan.steps):
            raise SkillRuntimeError("planner proposed a capability outside the selected skill")
        if not _is_observation_context(trusted_context):
            self._remember_selection(
                plan.task_id,
                SkillPlanSelection(skill=skill, usage=usage),
            )
        return plan

    def claim_selected_skill(self, task_id: UUID) -> SkillPlanSelection | None:
        """Return and remove the exact skill selected for one top-level plan."""
        with self._selection_lock:
            return self._selections.pop(task_id, None)

    def _remember_selection(
        self,
        task_id: UUID,
        selection: SkillPlanSelection,
    ) -> None:
        with self._selection_lock:
            if task_id in self._selections:
                raise SkillRuntimeError("planner reused a pending task identifier")
            self._selections[task_id] = selection
            while len(self._selections) > self._selection_limit:
                self._selections.popitem(last=False)

    def _plan_with_usage(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None,
        untrusted_context: str | None,
    ) -> tuple[Plan, SkillPlanUsage]:
        # All calls share this lock so a fallback plan cannot contaminate a skill delta.
        with self._planning_lock:
            before = _planner_metrics_snapshot(self._planner)
            plan = self._planner.plan(
                goal,
                trusted_context=trusted_context,
                untrusted_context=untrusted_context,
            )
            after = _planner_metrics_snapshot(self._planner)
        return plan, _planner_usage_delta(before, after)


def _deterministic_verified_skill_plan(
    goal: str,
    skill: SkillRecord,
    *,
    untrusted_context: str | None,
) -> Plan | None:
    """Compile simple, input-free read-only skills without another LLM call."""
    if (
        untrusted_context is not None
        or skill.key != "system-information-check"
        or skill.dynamic_inputs
        or skill.allowed_capabilities != ("system.info.read",)
    ):
        return None
    return Plan(
        goal=goal,
        steps=(
            Action(
                capability_id="system.info.read",
                purpose="저장된 검증 스킬로 Windows 시스템 정보를 확인한다.",
                expected_postconditions=(Postcondition(predicate="execution.success"),),
            ),
        ),
    )


def _record(row: sqlite3.Row) -> SkillRecord:
    return SkillRecord(
        skill_id=UUID(row["skill_id"]), key=row["key"], version=row["version"],
        status=SkillStatus(row["status"]), title=row["title"], description=row["description"],
        triggers=tuple(json.loads(row["triggers_json"])),
        procedure=tuple(json.loads(row["procedure_json"])),
        dynamic_inputs=tuple(json.loads(row["dynamic_inputs_json"])),
        decision_rules=tuple(json.loads(row["decision_rules_json"])),
        verification_rules=tuple(json.loads(row["verification_rules_json"])),
        allowed_capabilities=tuple(json.loads(row["capabilities_json"])),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        supersedes_skill_id=UUID(row["supersedes_skill_id"])
        if row["supersedes_skill_id"] else None,
    )


def _utc(value: datetime | None) -> datetime:
    instant = value or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("skill time must be timezone-aware")
    return instant.astimezone(UTC)


def _tokens(value: str) -> tuple[str, ...]:
    # One-character Korean particles and fillers create broad substring matches.
    # Keep two-character acronyms such as PC, but discard every one-character token.
    return _lexical_tokens(value)[:16]


def _lexical_tokens(value: str) -> tuple[str, ...]:
    return tuple(
        item.casefold()
        for item in re.findall(r"[0-9A-Za-z가-힣_]+", value)
        if len(item) >= 2
    )


def _score(tokens: tuple[str, ...], skill: SkillRecord) -> int:
    searchable = " ".join((skill.key, skill.title, skill.description, *skill.triggers)).lower()
    vocabulary = set(_lexical_tokens(searchable))
    return sum(
        1
        for token in tokens
        if token in searchable or _strip_registered_korean_suffix(token, vocabulary) is not None
    )


def _strip_registered_korean_suffix(
    token: str,
    vocabulary: set[str],
) -> str | None:
    """Return a particle-stripped token only when the skill already contains it."""
    for suffix in _KOREAN_QUERY_SUFFIXES:
        if token.endswith(suffix):
            stem = token[: -len(suffix)]
            if len(stem) >= 2 and stem in vocabulary:
                return stem
    return None


def _normalize_phrase(value: str) -> str:
    return " ".join(value.casefold().split())


def _is_observation_context(context: Mapping[str, object] | None) -> bool:
    return context is not None and "observation_round" in context


def _planner_metrics_snapshot(planner: PlanProposer) -> NimTransportMetrics | None:
    snapshot = getattr(planner, "metrics_snapshot", None)
    if not callable(snapshot):
        return None
    try:
        value = snapshot()
    except Exception:
        return None
    return value if isinstance(value, NimTransportMetrics) else None


def _planner_usage_delta(
    before: NimTransportMetrics | None,
    after: NimTransportMetrics | None,
) -> SkillPlanUsage:
    if before is None or after is None:
        return SkillPlanUsage()
    values = (
        after.requests - before.requests,
        after.successful_requests - before.successful_requests,
        after.input_tokens - before.input_tokens,
        after.output_tokens - before.output_tokens,
        after.responses_without_usage - before.responses_without_usage,
    )
    if any(value < 0 for value in values):
        return SkillPlanUsage()
    requests, successful, input_tokens, output_tokens, without_usage = values
    try:
        return SkillPlanUsage(
            llm_calls=requests,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            responses_without_usage=without_usage,
            complete=(successful == requests and without_usage == 0),
        )
    except ValueError:
        return SkillPlanUsage()


def _retrieval_score(
    normalized_query: str,
    tokens: tuple[str, ...],
    skill: SkillRecord,
) -> int:
    exact_trigger_matches = sum(
        1
        for trigger in skill.triggers
        if (normalized := _normalize_phrase(trigger)) and normalized in normalized_query
    )
    normalized_title = _normalize_phrase(skill.title)
    title_match = int(bool(normalized_title and normalized_title in normalized_query))
    # Phrase matches dominate any possible loose overlap (at most 16 query tokens).
    return exact_trigger_matches * 10_000 + title_match * 1_000 + _score(tokens, skill)


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    existing = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
