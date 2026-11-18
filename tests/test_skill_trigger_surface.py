from __future__ import annotations

from pathlib import Path
from uuid import UUID

from skilla_core.registry import default_registry
from skilla_core.skill_runtime import LocalSkillCatalog, SkillProposal
from skilla_core.skill_trigger_surface import SkillTriggerDisplay, SkillTriggerPresenter
from skilla_core.skill_triggers import LocalSkillTriggerRepository


class View:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.rendered: list[SkillTriggerDisplay] = []
        self.closed = False
        self.ran = False

    def bind_handlers(self, **handlers: object) -> None:
        self.handlers = handlers

    def render(self, display: SkillTriggerDisplay) -> None:
        self.rendered.append(display)

    def close(self) -> None:
        self.closed = True

    def run(self) -> None:
        self.ran = True


def setup(tmp_path: Path):  # type: ignore[no-untyped-def]
    catalog = LocalSkillCatalog(tmp_path / "skills.sqlite3", default_registry())
    draft = catalog.propose(
        SkillProposal(
            key="game-ready",
            title="게임 모드 준비",
            description="프로그램 실행 후 준비 작업",
            triggers=("게임 모드 준비",),
            procedure=("현재 음량을 확인한다.",),
            allowed_capabilities=("audio.volume.read",),
        )
    )
    skill = catalog.approve(draft.skill_id)
    repository = LocalSkillTriggerRepository(
        tmp_path / "triggers.sqlite3",
        registered_app_ids=("game", "editor"),
        skill_catalog=catalog,
        acl=None,
    )
    view = View()
    presenter = SkillTriggerPresenter(repository, catalog, view)
    return catalog, repository, skill, view, presenter


def invoke(view: View, name: str, *args: object) -> None:
    handler = view.handlers[name]
    assert callable(handler)
    handler(*args)


def test_presenter_lists_apps_verified_skills_and_rules(tmp_path: Path) -> None:
    _catalog, repository, skill, view, presenter = setup(tmp_path)
    repository.bind("game", skill.skill_id)

    presenter.run()

    display = view.rendered[-1]
    assert view.ran
    assert display.apps == ("editor", "game")
    assert display.skills[0].skill_id == skill.skill_id
    assert display.rules[0].app_id == "game"
    assert display.rules[0].skill_title == "게임 모드 준비"


def test_presenter_binds_toggles_and_deletes_without_running_skill(tmp_path: Path) -> None:
    _catalog, repository, skill, view, presenter = setup(tmp_path)
    presenter.run()
    invoke(view, "on_select_app", "game")
    invoke(view, "on_select_skill", skill.skill_id)

    invoke(view, "on_bind")
    rule = repository.list()[0]
    assert rule.enabled
    assert "제안만" in view.rendered[-1].notice

    invoke(view, "on_select_rule", rule.rule_id)
    invoke(view, "on_toggle")
    assert not repository.require(rule.rule_id).enabled

    invoke(view, "on_select_rule", rule.rule_id)
    invoke(view, "on_delete")
    assert repository.list() == ()


def test_presenter_requires_both_selections_and_ignores_unknown_ids(tmp_path: Path) -> None:
    _catalog, repository, _skill, view, presenter = setup(tmp_path)
    presenter.run()
    invoke(view, "on_select_app", "unknown")
    invoke(view, "on_select_skill", UUID(int=0))
    invoke(view, "on_bind")

    assert repository.list() == ()
    assert "각각 선택" in view.rendered[-1].notice
