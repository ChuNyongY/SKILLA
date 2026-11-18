from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from skilla_core.registry import default_registry
from skilla_core.skill_runtime import LocalSkillCatalog, SkillProposal
from skilla_core.skill_schedule_surface import SkillScheduleDisplay, SkillSchedulePresenter
from skilla_core.skill_schedules import LocalSkillScheduleRepository


class View:
    def __init__(self) -> None:
        self.display: SkillScheduleDisplay | None = None
        self.ran = False
        self.on_create: Callable[[UUID, int, int, tuple[int, ...]], None] | None = None
        self.on_toggle: Callable[[UUID], None] | None = None
        self.on_delete: Callable[[UUID], None] | None = None

    def bind_handlers(
        self,
        *,
        on_create: Callable[[UUID, int, int, tuple[int, ...]], None],
        on_toggle: Callable[[UUID], None],
        on_delete: Callable[[UUID], None],
        on_refresh: Callable[[], None],
    ) -> None:
        self.on_create = on_create
        self.on_toggle = on_toggle
        self.on_delete = on_delete

    def render(self, display: SkillScheduleDisplay) -> None:
        self.display = display

    def run(self) -> None:
        self.ran = True


def setup(tmp_path: Path) -> tuple[LocalSkillCatalog, LocalSkillScheduleRepository, object]:
    catalog = LocalSkillCatalog(tmp_path / "skills.sqlite3", default_registry())
    draft = catalog.propose(
        SkillProposal(
            key="morning-work",
            title="아침 작업 준비",
            description="반복 작업",
            triggers=("아침 작업 준비",),
            procedure=("저장 공간 확인",),
            allowed_capabilities=("storage.status.read",),
        )
    )
    skill = catalog.approve(draft.skill_id)
    schedules = LocalSkillScheduleRepository(
        tmp_path / "schedules.sqlite3", skill_catalog=catalog, acl=None
    )
    return catalog, schedules, skill


def test_presenter_creates_toggles_and_deletes_schedule_without_execution(
    tmp_path: Path,
) -> None:
    catalog, schedules, skill = setup(tmp_path)
    view = View()
    now = datetime(2026, 11, 16, 8, 0, tzinfo=timezone(timedelta(hours=9)))
    presenter = SkillSchedulePresenter(schedules, catalog, view, clock=lambda: now)

    presenter.run()
    assert view.ran
    assert view.display is not None
    assert len(view.display.skills) == 1
    assert view.on_create is not None
    view.on_create(skill.skill_id, 8, 30, (0, 1, 2, 3, 4))  # type: ignore[attr-defined]
    assert view.display is not None
    assert "08:30" in view.display.rules[0].label
    assert "아침 작업 준비" in view.display.rules[0].label

    rule_id = view.display.rules[0].rule_id
    assert view.on_toggle is not None
    view.on_toggle(rule_id)
    assert not schedules.require(rule_id).enabled
    assert view.on_delete is not None
    view.on_delete(rule_id)
    assert schedules.list() == ()
