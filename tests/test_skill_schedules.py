from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from skilla_core.registry import default_registry
from skilla_core.skill_runtime import LocalSkillCatalog, SkillProposal
from skilla_core.skill_schedules import (
    LocalSkillScheduleRepository,
    SkillScheduleError,
    SkillScheduleSuggestionEngine,
)

KST = timezone(timedelta(hours=9))
MONDAY = datetime(2026, 11, 16, 8, 30, tzinfo=KST)


def proposal(key: str = "morning-work") -> SkillProposal:
    return SkillProposal(
        key=key,
        title="아침 작업 준비",
        description="지정한 시각에 반복 작업을 제안합니다.",
        triggers=("아침 작업 준비",),
        procedure=("현재 저장 공간을 확인한다.",),
        verification_rules=("저장 공간 결과를 확인한다.",),
        allowed_capabilities=("storage.status.read",),
    )


def repositories(tmp_path: Path):  # type: ignore[no-untyped-def]
    catalog = LocalSkillCatalog(tmp_path / "skills.sqlite3", default_registry())
    draft = catalog.propose(proposal())
    skill = catalog.approve(draft.skill_id)
    schedules = LocalSkillScheduleRepository(
        tmp_path / "skill-schedules.sqlite3",
        skill_catalog=catalog,
        acl=None,
    )
    return catalog, schedules, skill


def test_schedule_requires_verified_skill_and_valid_local_time(tmp_path: Path) -> None:
    catalog, schedules, skill = repositories(tmp_path)
    draft = catalog.propose(proposal("draft-only"))

    rule = schedules.create(
        skill.skill_id,
        hour=8,
        minute=30,
        weekdays=(0, 2, 4),
        now=MONDAY,
    )

    assert rule.local_minute == 510
    assert rule.weekdays == (0, 2, 4)
    assert rule.enabled
    with pytest.raises(SkillScheduleError, match="not verified"):
        schedules.create(
            draft.skill_id, hour=9, minute=0, weekdays=(0,), now=MONDAY
        )
    with pytest.raises(ValueError, match="schedule time"):
        schedules.create(
            skill.skill_id, hour=24, minute=0, weekdays=(0,), now=MONDAY
        )
    with pytest.raises(ValueError, match="weekdays"):
        schedules.create(
            skill.skill_id, hour=9, minute=0, weekdays=(), now=MONDAY
        )


def test_due_schedule_is_suggested_once_per_local_minute(tmp_path: Path) -> None:
    _catalog, schedules, skill = repositories(tmp_path)
    rule = schedules.create(
        skill.skill_id, hour=8, minute=30, weekdays=(0,), now=MONDAY
    )
    engine = SkillScheduleSuggestionEngine(schedules)

    first = engine.observe(MONDAY)

    assert len(first) == 1
    assert first[0].rule_id == rule.rule_id
    assert first[0].skill_id == skill.skill_id
    assert first[0].due_key == "2026-11-16T08:30+0900"
    assert engine.observe(MONDAY.replace(second=40)) == ()
    assert schedules.require(rule.rule_id).last_suggested_key == first[0].due_key


def test_schedule_ignores_other_day_or_minute_and_can_be_disabled(tmp_path: Path) -> None:
    _catalog, schedules, skill = repositories(tmp_path)
    rule = schedules.create(
        skill.skill_id, hour=8, minute=30, weekdays=(0,), now=MONDAY
    )
    engine = SkillScheduleSuggestionEngine(schedules)

    assert engine.observe(MONDAY.replace(minute=31)) == ()
    assert engine.observe(MONDAY + timedelta(days=1)) == ()
    assert not schedules.set_enabled(
        rule.rule_id, False, now=MONDAY
    ).enabled
    assert engine.observe(MONDAY) == ()
    assert schedules.delete(rule.rule_id)


def test_stale_or_forged_schedule_suggestion_fails_closed(tmp_path: Path) -> None:
    catalog, schedules, skill = repositories(tmp_path)
    schedules.create(
        skill.skill_id, hour=8, minute=30, weekdays=(0,), now=MONDAY
    )
    engine = SkillScheduleSuggestionEngine(schedules)
    suggestion = engine.observe(MONDAY)[0]

    assert engine.resolve(suggestion).skill_id == skill.skill_id
    with pytest.raises(SkillScheduleError, match="no longer valid"):
        engine.resolve(suggestion.model_copy(update={"skill_id": uuid4()}))

    catalog.retire(skill.skill_id)
    with pytest.raises(SkillScheduleError, match="not verified"):
        engine.resolve(suggestion)


def test_repository_persists_bounded_schedule_rules(tmp_path: Path) -> None:
    catalog, schedules, skill = repositories(tmp_path)
    rule = schedules.create(
        skill.skill_id, hour=8, minute=30, weekdays=(0, 1), now=MONDAY
    )
    reopened = LocalSkillScheduleRepository(
        tmp_path / "skill-schedules.sqlite3", skill_catalog=catalog, acl=None
    )

    assert reopened.list() == (rule,)
    with pytest.raises(ValueError, match="1..1000"):
        reopened.list(limit=0)
    with pytest.raises(ValueError, match="configuration"):
        LocalSkillScheduleRepository(
            Path("relative.sqlite3"), skill_catalog=catalog
        )
