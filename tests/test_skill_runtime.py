import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from javis_core import (
    Action,
    LocalSkillCatalog,
    Plan,
    SkillAwarePlanner,
    SkillOutcome,
    SkillPlanningMode,
    SkillProposal,
    SkillRevisionDecision,
    SkillStalenessDecision,
    SkillStatus,
)
from javis_core.registry import default_registry
from javis_core.skill_runtime import SkillRuntimeError


def catalog(tmp_path: Path) -> LocalSkillCatalog:
    return LocalSkillCatalog((tmp_path / "skills.sqlite3").resolve(), default_registry())


def proposal(**updates: object) -> SkillProposal:
    values: dict[str, object] = {
        "key": "volume-control",
        "title": "볼륨 조절",
        "description": "기본 출력 장치 볼륨을 읽거나 설정한다.",
        "triggers": ("볼륨", "소리"),
        "procedure": ("현재 볼륨을 읽는다.", "요청값을 확인한다.", "결과를 다시 읽는다."),
        "dynamic_inputs": ("현재 볼륨", "사용자 요청 볼륨"),
        "decision_rules": ("요청값은 0에서 100 사이여야 한다.",),
        "verification_rules": ("설정 후 실제 볼륨을 다시 읽어 요청값과 비교한다.",),
        "allowed_capabilities": ("audio.volume.read", "audio.volume.set"),
    }
    values.update(updates)
    return SkillProposal(**values)  # type: ignore[arg-type]


def test_draft_cannot_be_found_or_used_until_approved(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    draft = store.propose(proposal())
    assert store.search("볼륨") == ()
    with pytest.raises(SkillRuntimeError, match="only verified"):
        store.record_use(draft, SkillOutcome.SUCCEEDED, "VERIFIED")
    verified = store.approve(draft.skill_id)
    assert store.search("소리")[0].skill_id == verified.skill_id
    use = store.record_use(verified, SkillOutcome.SUCCEEDED, "VOLUME_MATCHED")
    assert use.skill_version == 1


def test_revision_is_a_new_draft_and_retires_old_only_after_approval(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    first = store.approve(store.propose(proposal()).skill_id)
    revision = store.propose_revision(
        first.skill_id,
        proposal(description="기본 출력 장치 볼륨을 안전하게 조절하고 읽어 확인한다."),
    )
    assert store.search("볼륨")[0].skill_id == first.skill_id
    approved = store.approve(revision.skill_id)
    assert store.require(first.skill_id).status.value == "RETIRED"
    assert store.search("볼륨")[0].skill_id == approved.skill_id
    assert approved.version == 2
    with pytest.raises(SkillRuntimeError, match="only verified"):
        store.record_use(first, SkillOutcome.SUCCEEDED, "STALE_VERSION")


def test_unknown_capability_cannot_enter_a_skill(tmp_path: Path) -> None:
    with pytest.raises(SkillRuntimeError, match="unregistered"):
        catalog(tmp_path).propose(proposal(allowed_capabilities=("powershell.raw",)))


def test_skills_can_be_listed_by_lifecycle_status(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    draft = store.propose(proposal())
    assert store.list(status=None) == (draft,)
    assert store.list(status=draft.status) == (draft,)
    assert store.list(status=SkillStatus.VERIFIED) == ()


class Planner:
    def __init__(self, capability_id: str) -> None:
        self.capability_id = capability_id
        self.context: dict[str, object] | None = None
        self.calls = 0

    def plan(
        self,
        goal: str,
        *,
        trusted_context: dict[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan:
        self.calls += 1
        self.context = trusted_context
        return Plan(goal=goal, steps=(Action(capability_id=self.capability_id, purpose="test"),))


def test_skill_is_retrieved_then_binds_the_planner_to_its_allowlist(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    store.approve(store.propose(proposal()).skill_id)
    planner = Planner("audio.volume.read")
    plan = SkillAwarePlanner(planner, store).plan("볼륨 알려 줘")
    assert plan.steps[0].capability_id == "audio.volume.read"
    assert planner.context is not None and "verified_skill" in planner.context
    selected = planner.context["verified_skill"]
    assert isinstance(selected, dict)
    assert selected["dynamic_inputs"] == ("현재 볼륨", "사용자 요청 볼륨")

    with pytest.raises(SkillRuntimeError, match="outside the selected skill"):
        SkillAwarePlanner(Planner("file.delete.trash"), store).plan("볼륨 알려 줘")


def test_planner_falls_back_to_base_plan_when_no_skill_matches(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    planner = Planner("system.info.read")
    plan = SkillAwarePlanner(planner, store).plan("시스템 정보 알려 줘")
    assert plan.steps[0].capability_id == "system.info.read"
    assert planner.context is None


def test_input_free_system_info_skill_skips_base_planner(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    verified = store.approve(
        store.propose(
            proposal(
                key="system-information-check",
                title="컴퓨터 시스템 정보 확인",
                description="Windows 시스템 정보를 읽고 결과를 확인한다.",
                triggers=("시스템 정보", "컴퓨터 정보", "윈도우 정보"),
                procedure=("시스템 정보를 읽는다.", "실행 성공 여부를 확인한다."),
                dynamic_inputs=(),
                decision_rules=(),
                verification_rules=("시스템 정보 조회가 성공했는지 확인한다.",),
                allowed_capabilities=("system.info.read",),
            )
        ).skill_id
    )
    planner = Planner("file.delete.trash")
    skill_planner = SkillAwarePlanner(planner, store)

    plan = skill_planner.plan("내 컴퓨터 시스템 정보를 확인하죠")

    assert plan.steps[0].capability_id == "system.info.read"
    assert planner.calls == 0
    selection = skill_planner.claim_selected_skill(plan.task_id)
    assert selection is not None
    assert selection.skill.skill_id == verified.skill_id
    assert selection.usage.llm_calls == 0
    assert selection.usage.complete


def test_use_metrics_support_revision_assessment_without_auto_approval(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    verified = store.approve(store.propose(proposal()).skill_id)
    first = store.record_use(
        verified,
        SkillOutcome.FAILED,
        "TARGET_NOT_FOUND",
        elapsed_ms=1200,
        llm_calls=2,
        input_tokens=300,
        output_tokens=80,
        user_interventions=1,
    )
    store.record_use(verified, SkillOutcome.FAILED, "TARGET_NOT_FOUND")
    store.record_use(verified, SkillOutcome.SUCCEEDED, "VERIFIED")
    assert first.planning_mode is SkillPlanningMode.INITIAL_SKILL
    assessment = store.assess_revision(verified.skill_id)
    assert assessment.decision is SkillRevisionDecision.PROPOSE_REVISION
    assert assessment.reason_code == "REPEATED_FAILURE"
    assert store.require(verified.skill_id).status.value == "VERIFIED"


def test_matching_environment_is_current_without_changing_skill_status(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    verified = store.approve(store.propose(proposal()).skill_id)
    model_hash = "a" * 64
    tool_hash = "b" * 64
    for _ in range(3):
        use = store.record_use(
            verified,
            SkillOutcome.SUCCEEDED,
            "VERIFIED",
            model_configuration_sha256=model_hash,
            tool_surface_sha256=tool_hash,
        )
        assert use.model_configuration_sha256 == model_hash
        assert use.tool_surface_sha256 == tool_hash

    assessment = store.assess_staleness(verified.skill_id, model_hash, tool_hash)

    assert assessment.decision is SkillStalenessDecision.CURRENT
    assert assessment.reason_code == "ENVIRONMENT_MATCHED"
    assert assessment.observations_considered == 3
    assert store.require(verified.skill_id).status is SkillStatus.VERIFIED


@pytest.mark.parametrize(
    ("recorded_model", "recorded_tool", "reason"),
    (
        ("c" * 64, "b" * 64, "MODEL_CONFIGURATION_CHANGED"),
        ("a" * 64, "d" * 64, "TOOL_SURFACE_CHANGED"),
    ),
)
def test_environment_drift_requires_review(
    tmp_path: Path,
    recorded_model: str,
    recorded_tool: str,
    reason: str,
) -> None:
    store = catalog(tmp_path)
    verified = store.approve(store.propose(proposal()).skill_id)
    for _ in range(3):
        store.record_use(
            verified,
            SkillOutcome.SUCCEEDED,
            "VERIFIED",
            model_configuration_sha256=recorded_model,
            tool_surface_sha256=recorded_tool,
        )

    assessment = store.assess_staleness(
        verified.skill_id,
        "a" * 64,
        "b" * 64,
    )

    assert assessment.decision is SkillStalenessDecision.REVIEW_REQUIRED
    assert assessment.reason_code == reason
    assert store.require(verified.skill_id).status is SkillStatus.VERIFIED


def test_recent_repeated_failure_takes_precedence_over_environment_drift(
    tmp_path: Path,
) -> None:
    store = catalog(tmp_path)
    verified = store.approve(store.propose(proposal()).skill_id)
    for outcome in (SkillOutcome.FAILED, SkillOutcome.FAILED, SkillOutcome.SUCCEEDED):
        store.record_use(
            verified,
            outcome,
            "TARGET_NOT_FOUND" if outcome is SkillOutcome.FAILED else "VERIFIED",
            model_configuration_sha256="c" * 64,
            tool_surface_sha256="d" * 64,
        )

    assessment = store.assess_staleness(
        verified.skill_id,
        "a" * 64,
        "b" * 64,
    )

    assert assessment.decision is SkillStalenessDecision.REVIEW_REQUIRED
    assert assessment.reason_code == "RECENT_REPEATED_FAILURE"
    assert assessment.repeated_failure_code == "TARGET_NOT_FOUND"


def test_staleness_needs_complete_recent_environment_evidence(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    verified = store.approve(store.propose(proposal()).skill_id)
    store.record_use(verified, SkillOutcome.SUCCEEDED, "VERIFIED")
    too_few = store.assess_staleness(verified.skill_id, "a" * 64, "b" * 64)
    assert too_few.decision is SkillStalenessDecision.INSUFFICIENT_EVIDENCE
    assert too_few.reason_code == "TOO_FEW_OBSERVATIONS"

    for _ in range(2):
        store.record_use(
            verified,
            SkillOutcome.SUCCEEDED,
            "VERIFIED",
            model_configuration_sha256="a" * 64,
            tool_surface_sha256="b" * 64,
        )
    legacy_window = store.assess_staleness(verified.skill_id, "a" * 64, "b" * 64)
    assert legacy_window.decision is SkillStalenessDecision.INSUFFICIENT_EVIDENCE
    assert legacy_window.reason_code == "MISSING_ENVIRONMENT_EVIDENCE"


def test_staleness_uses_only_latest_requested_window(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    verified = store.approve(store.propose(proposal()).skill_id)
    store.record_use(
        verified,
        SkillOutcome.SUCCEEDED,
        "OLD_ENVIRONMENT",
        model_configuration_sha256="c" * 64,
        tool_surface_sha256="d" * 64,
    )
    for _ in range(3):
        store.record_use(
            verified,
            SkillOutcome.SUCCEEDED,
            "VERIFIED",
            model_configuration_sha256="a" * 64,
            tool_surface_sha256="b" * 64,
        )

    assessment = store.assess_staleness(verified.skill_id, "a" * 64, "b" * 64)

    assert assessment.decision is SkillStalenessDecision.CURRENT


def test_environment_hashes_reject_noncanonical_sha256(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    verified = store.approve(store.propose(proposal()).skill_id)
    with pytest.raises(ValueError, match="should match pattern"):
        store.record_use(
            verified,
            SkillOutcome.SUCCEEDED,
            "VERIFIED",
            model_configuration_sha256="A" * 64,
            tool_surface_sha256="b" * 64,
        )


def test_existing_catalog_schema_is_migrated_without_losing_skills(tmp_path: Path) -> None:
    path = (tmp_path / "skills.sqlite3").resolve()
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE skills(
              skill_id TEXT PRIMARY KEY, key TEXT NOT NULL, version INTEGER NOT NULL,
              status TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
              triggers_json TEXT NOT NULL, procedure_json TEXT NOT NULL,
              capabilities_json TEXT NOT NULL, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL, supersedes_skill_id TEXT);
            CREATE UNIQUE INDEX skill_version ON skills(key, version);
            CREATE TABLE skill_uses(
              use_id TEXT PRIMARY KEY, skill_id TEXT NOT NULL, skill_version INTEGER NOT NULL,
              outcome TEXT NOT NULL, observed_at TEXT NOT NULL, detail_code TEXT NOT NULL);
            """
        )
    store = LocalSkillCatalog(path, default_registry())
    created = store.propose(proposal())
    assert created.dynamic_inputs == ("현재 볼륨", "사용자 요청 볼륨")
    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(skill_uses)")}
    assert "model_configuration_sha256" in columns
    assert "tool_surface_sha256" in columns
    assert "planner_usage_complete" in columns
    assert "planner_responses_without_usage" in columns


def test_skill_time_must_be_timezone_aware(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        catalog(tmp_path).propose(proposal(), now=datetime(2026, 10, 10))
