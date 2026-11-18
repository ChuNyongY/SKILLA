from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from skilla_core.registry import default_registry
from skilla_core.skill_runtime import LocalSkillCatalog, SkillProposal
from skilla_core.skill_triggers import (
    LocalSkillTriggerRepository,
    SkillTriggerError,
    SkillTriggerSuggestionEngine,
)


def proposal(key: str = "game-ready") -> SkillProposal:
    return SkillProposal(
        key=key,
        title="게임 모드 준비",
        description="등록된 프로그램의 준비 작업을 제안합니다.",
        triggers=("게임 모드 준비",),
        procedure=("현재 음량을 확인한다.",),
        verification_rules=("설정값을 다시 확인한다.",),
        allowed_capabilities=("audio.volume.read",),
    )


def repositories(tmp_path: Path):  # type: ignore[no-untyped-def]
    catalog = LocalSkillCatalog(tmp_path / "skills.sqlite3", default_registry())
    draft = catalog.propose(proposal())
    skill = catalog.approve(draft.skill_id)
    triggers = LocalSkillTriggerRepository(
        tmp_path / "skill-triggers.sqlite3",
        registered_app_ids=("game", "editor"),
        skill_catalog=catalog,
        acl=None,
    )
    return catalog, triggers, skill


def test_only_registered_apps_and_verified_skills_can_be_bound(tmp_path: Path) -> None:
    catalog, triggers, skill = repositories(tmp_path)
    draft = catalog.propose(proposal("draft-only"))

    rule = triggers.bind(
        "game", skill.skill_id, now=datetime(2026, 11, 14, tzinfo=UTC)
    )

    assert rule.enabled
    assert rule.app_id == "game"
    assert rule.skill_version == skill.version
    with pytest.raises(SkillTriggerError, match="not registered"):
        triggers.bind("unknown", skill.skill_id)
    with pytest.raises(SkillTriggerError, match="not verified"):
        triggers.bind("editor", draft.skill_id)


def test_one_app_has_one_explicit_rule_and_can_be_disabled(tmp_path: Path) -> None:
    _catalog, triggers, skill = repositories(tmp_path)
    rule = triggers.bind("game", skill.skill_id)

    with pytest.raises(SkillTriggerError, match="already has"):
        triggers.bind("game", skill.skill_id)
    disabled = triggers.set_enabled(rule.rule_id, False)

    assert not disabled.enabled
    assert triggers.match("game") is None
    assert triggers.set_enabled(rule.rule_id, True).enabled
    assert triggers.delete(rule.rule_id)
    assert not triggers.delete(rule.rule_id)


def test_engine_suggests_once_per_verified_app_transition_without_execution(
    tmp_path: Path,
) -> None:
    _catalog, triggers, skill = repositories(tmp_path)
    rule = triggers.bind("game", skill.skill_id)
    engine = SkillTriggerSuggestionEngine(triggers)

    first = engine.observe("game")

    assert first is not None
    assert first.rule_id == rule.rule_id
    assert first.skill_id == skill.skill_id
    assert engine.observe("game") is None
    assert engine.observe(None) is None
    assert engine.observe("game") is not None


def test_retired_or_revised_skill_fails_closed_until_rule_is_rebound(tmp_path: Path) -> None:
    catalog, triggers, skill = repositories(tmp_path)
    triggers.bind("game", skill.skill_id)
    catalog.retire(skill.skill_id)

    assert SkillTriggerSuggestionEngine(triggers).observe("game") is None


def test_forged_or_stale_suggestion_cannot_be_resolved(tmp_path: Path) -> None:
    _catalog, triggers, skill = repositories(tmp_path)
    triggers.bind("game", skill.skill_id)
    engine = SkillTriggerSuggestionEngine(triggers)
    suggestion = engine.observe("game")
    assert suggestion is not None

    assert engine.resolve(suggestion).skill_id == skill.skill_id
    with pytest.raises(SkillTriggerError, match="no longer valid"):
        engine.resolve(suggestion.model_copy(update={"skill_id": uuid4()}))


def test_repository_rejects_invalid_location_and_limits(tmp_path: Path) -> None:
    catalog = LocalSkillCatalog(tmp_path / "skills.sqlite3", default_registry())
    with pytest.raises(ValueError, match="configuration"):
        LocalSkillTriggerRepository(
            Path("relative.sqlite3"),
            registered_app_ids=("game",),
            skill_catalog=catalog,
        )
    with pytest.raises(ValueError, match="configuration"):
        LocalSkillTriggerRepository(
            tmp_path / "trigger.sqlite3",
            registered_app_ids=("Bad App",),
            skill_catalog=catalog,
        )


def test_list_is_bounded_and_returns_persisted_rule(tmp_path: Path) -> None:
    _catalog, triggers, skill = repositories(tmp_path)
    rule = triggers.bind("game", skill.skill_id)

    assert triggers.list() == (rule,)
    assert triggers.registered_app_ids == ("editor", "game")
    with pytest.raises(ValueError, match="1..1000"):
        triggers.list(limit=0)
