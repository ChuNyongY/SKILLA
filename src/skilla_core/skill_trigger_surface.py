from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .cyber_theme import COLORS, button, configure_window, footer, header, label, panel
from .models import FrozenModel
from .skill_runtime import LocalSkillCatalog, SkillRecord, SkillStatus
from .skill_triggers import LocalSkillTriggerRepository, SkillTriggerRule


class TriggerSkillChoice(FrozenModel):
    skill_id: UUID
    title: str = Field(min_length=1, max_length=120)
    version: int = Field(ge=1)


class TriggerRuleSummary(FrozenModel):
    rule_id: UUID
    app_id: str
    skill_id: UUID
    skill_title: str = Field(min_length=1, max_length=120)
    skill_version: int = Field(ge=1)
    enabled: bool


class SkillTriggerDisplay(FrozenModel):
    apps: tuple[str, ...]
    skills: tuple[TriggerSkillChoice, ...]
    rules: tuple[TriggerRuleSummary, ...]
    selected_app_id: str | None = None
    selected_skill_id: UUID | None = None
    selected_rule_id: UUID | None = None
    notice: str = Field(min_length=1, max_length=180)


class SkillTriggerView(Protocol):
    def bind_handlers(
        self,
        *,
        on_select_app: Callable[[str], None],
        on_select_skill: Callable[[UUID], None],
        on_select_rule: Callable[[UUID], None],
        on_bind: Callable[[], None],
        on_toggle: Callable[[], None],
        on_delete: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None: ...

    def render(self, display: SkillTriggerDisplay) -> None: ...

    def close(self) -> None: ...

    def run(self) -> None: ...


class SkillTriggerPresenter:
    """Manage suggestion-only app bindings without executing any skill."""

    def __init__(
        self,
        repository: LocalSkillTriggerRepository,
        catalog: LocalSkillCatalog,
        view: SkillTriggerView,
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._view = view
        self._apps: tuple[str, ...] = ()
        self._skills: tuple[TriggerSkillChoice, ...] = ()
        self._rules: tuple[TriggerRuleSummary, ...] = ()
        self._selected_app_id: str | None = None
        self._selected_skill_id: UUID | None = None
        self._selected_rule_id: UUID | None = None

    def run(self) -> None:
        self._view.bind_handlers(
            on_select_app=self.select_app,
            on_select_skill=self.select_skill,
            on_select_rule=self.select_rule,
            on_bind=self.bind,
            on_toggle=self.toggle,
            on_delete=self.delete,
            on_refresh=self.refresh,
            on_close=self._view.close,
        )
        self.refresh()
        self._view.run()

    def refresh(self, notice: str = "상황 스킬 연결 정보를 불러왔습니다.") -> None:
        try:
            records = self._catalog.list(status=SkillStatus.VERIFIED, limit=100)
            rules = self._repository.list(limit=1_000)
            indexed = {record.skill_id: record for record in records}
            summaries = tuple(
                _rule_summary(rule, indexed.get(rule.skill_id)) for rule in rules
            )
        except Exception:
            self._apps = ()
            self._skills = ()
            self._rules = ()
            self._clear_selection()
            self._render("상황 스킬 정보를 불러오지 못했습니다.")
            return
        self._apps = self._repository.registered_app_ids
        self._skills = tuple(_skill_choice(record) for record in records)
        self._rules = summaries
        valid_apps = set(self._apps)
        valid_skills = {item.skill_id for item in self._skills}
        valid_rules = {item.rule_id for item in self._rules}
        if self._selected_app_id not in valid_apps:
            self._selected_app_id = None
        if self._selected_skill_id not in valid_skills:
            self._selected_skill_id = None
        if self._selected_rule_id not in valid_rules:
            self._selected_rule_id = None
        self._render(notice)

    def select_app(self, app_id: str) -> None:
        self._selected_app_id = app_id if app_id in self._apps else None
        self._render("프로그램을 선택했습니다.")

    def select_skill(self, skill_id: UUID) -> None:
        self._selected_skill_id = (
            skill_id if skill_id in {item.skill_id for item in self._skills} else None
        )
        self._render("승인된 스킬을 선택했습니다.")

    def select_rule(self, rule_id: UUID) -> None:
        self._selected_rule_id = (
            rule_id if rule_id in {item.rule_id for item in self._rules} else None
        )
        self._render("연결 규칙을 선택했습니다.")

    def bind(self) -> None:
        if self._selected_app_id is None or self._selected_skill_id is None:
            self._render("프로그램과 승인된 스킬을 각각 선택하세요.")
            return
        try:
            self._repository.bind(self._selected_app_id, self._selected_skill_id)
        except Exception:
            self.refresh("연결하지 못했습니다. 기존 연결과 스킬 상태를 확인하세요.")
            return
        self._clear_selection()
        self.refresh("상황 스킬을 연결했습니다. 감지 시 제안만 표시됩니다.")

    def toggle(self) -> None:
        selected = self._selected_rule()
        if selected is None:
            self._render("먼저 연결 규칙을 선택하세요.")
            return
        try:
            self._repository.set_enabled(selected.rule_id, not selected.enabled)
        except Exception:
            self.refresh("연결 상태를 변경하지 못했습니다.")
            return
        self._selected_rule_id = None
        self.refresh("연결 규칙의 사용 상태를 변경했습니다.")

    def delete(self) -> None:
        selected = self._selected_rule()
        if selected is None:
            self._render("먼저 연결 규칙을 선택하세요.")
            return
        try:
            deleted = self._repository.delete(selected.rule_id)
        except Exception:
            deleted = False
        self._selected_rule_id = None
        self.refresh(
            "연결 규칙을 삭제했습니다."
            if deleted
            else "연결 규칙을 삭제하지 못했습니다."
        )

    def _selected_rule(self) -> TriggerRuleSummary | None:
        return next(
            (item for item in self._rules if item.rule_id == self._selected_rule_id),
            None,
        )

    def _clear_selection(self) -> None:
        self._selected_app_id = None
        self._selected_skill_id = None
        self._selected_rule_id = None

    def _render(self, notice: str) -> None:
        self._view.render(
            SkillTriggerDisplay(
                apps=self._apps,
                skills=self._skills,
                rules=self._rules,
                selected_app_id=self._selected_app_id,
                selected_skill_id=self._selected_skill_id,
                selected_rule_id=self._selected_rule_id,
                notice=notice,
            )
        )


class TkSkillTriggerView:
    def __init__(self) -> None:
        import tkinter as tk

        parent = getattr(tk, "_default_root", None)
        self._owns_mainloop = parent is None
        self._root = tk.Tk() if parent is None else tk.Toplevel(parent)
        configure_window(
            self._root,
            title="SKILLA 상황 스킬",
            geometry="1040x690",
            minsize=(940, 620),
        )
        if parent is not None:
            self._root.transient(parent)
        shell = tk.Frame(self._root, bg=COLORS["bg"], padx=18, pady=16)
        shell.pack(fill="both", expand=True)
        header(shell, system_code="SYSTEM // CONTEXT SKILL", heading="상황 스킬 연결")
        label(
            shell,
            "등록 프로그램이 전면에 나타나면 연결된 스킬을 제안합니다. 자동 실행은 하지 않습니다.",
            color=COLORS["muted"],
            size=10,
        ).pack(fill="x", pady=(0, 10))
        columns = tk.Frame(shell, bg=COLORS["bg"])
        columns.pack(fill="both", expand=True)

        self._app_list = self._list_panel(columns, "1  등록 프로그램")
        self._skill_list = self._list_panel(columns, "2  승인된 스킬")
        self._rule_list = self._list_panel(columns, "3  현재 연결", width=44)
        self._app_list.master.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._skill_list.master.pack(side="left", fill="both", expand=True, padx=8)
        self._rule_list.master.pack(side="left", fill="both", expand=True, padx=(8, 0))

        actions = tk.Frame(shell, bg=COLORS["bg"])
        actions.pack(fill="x", pady=(12, 0))
        self._bind_button = button(actions, "연결", color=COLORS["success"], width=13)
        self._bind_button.pack(side="left")
        self._toggle_button = button(actions, "사용/중지", color=COLORS["warning"], width=13)
        self._toggle_button.pack(side="left", padx=(8, 0))
        self._delete_button = button(actions, "연결 삭제", color=COLORS["danger"], width=13)
        self._delete_button.pack(side="left", padx=(8, 0))
        self._refresh_button = button(actions, "새로 고침", width=13)
        self._refresh_button.pack(side="left", padx=(8, 0))
        self._close_button = button(actions, "닫기", color=COLORS["muted"], width=11)
        self._close_button.pack(side="right")
        self._notice = tk.StringVar(value="불러오는 중")
        label(shell, textvariable=self._notice, color=COLORS["warning"], size=9).pack(
            fill="x", pady=(10, 0)
        )
        footer(shell)
        self._app_ids: tuple[str, ...] = ()
        self._skill_ids: tuple[UUID, ...] = ()
        self._rule_ids: tuple[UUID, ...] = ()

    @staticmethod
    def _list_panel(parent: object, heading: str, *, width: int = 30):  # type: ignore[no-untyped-def]
        import tkinter as tk

        frame = panel(parent, alternate=True)
        label(frame, heading, color=COLORS["cyan"], size=11, bold=True).pack(
            fill="x", pady=(0, 8)
        )
        listbox = tk.Listbox(
            frame,
            width=width,
            height=20,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            selectbackground=COLORS["cyan_dim"],
            selectforeground=COLORS["text"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            relief="flat",
            font=("맑은 고딕", 10),
        )
        listbox.pack(fill="both", expand=True)
        return listbox

    def bind_handlers(
        self,
        *,
        on_select_app: Callable[[str], None],
        on_select_skill: Callable[[UUID], None],
        on_select_rule: Callable[[UUID], None],
        on_bind: Callable[[], None],
        on_toggle: Callable[[], None],
        on_delete: Callable[[], None],
        on_refresh: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._app_list.bind(
            "<<ListboxSelect>>",
            lambda _event: self._dispatch(self._app_list, self._app_ids, on_select_app),
        )
        self._skill_list.bind(
            "<<ListboxSelect>>",
            lambda _event: self._dispatch(self._skill_list, self._skill_ids, on_select_skill),
        )
        self._rule_list.bind(
            "<<ListboxSelect>>",
            lambda _event: self._dispatch(self._rule_list, self._rule_ids, on_select_rule),
        )
        self._bind_button.configure(command=on_bind)
        self._toggle_button.configure(command=on_toggle)
        self._delete_button.configure(command=on_delete)
        self._refresh_button.configure(command=on_refresh)
        self._close_button.configure(command=on_close)
        self._root.protocol("WM_DELETE_WINDOW", on_close)

    @staticmethod
    def _dispatch(listbox: object, values: tuple[object, ...], callback: Callable):  # type: ignore[type-arg,no-untyped-def]
        selected = listbox.curselection()  # type: ignore[attr-defined]
        if len(selected) == 1 and 0 <= int(selected[0]) < len(values):
            callback(values[int(selected[0])])

    def render(self, display: SkillTriggerDisplay) -> None:
        self._app_ids = display.apps
        self._skill_ids = tuple(item.skill_id for item in display.skills)
        self._rule_ids = tuple(item.rule_id for item in display.rules)
        self._fill(self._app_list, display.apps)
        self._fill(
            self._skill_list,
            tuple(f"{item.title}  ·  v{item.version}" for item in display.skills),
        )
        self._fill(
            self._rule_list,
            tuple(
                f"{'사용' if item.enabled else '중지'}  {item.app_id}  →  "
                f"{item.skill_title} v{item.skill_version}"
                for item in display.rules
            ),
        )
        self._select(self._app_list, self._app_ids, display.selected_app_id)
        self._select(self._skill_list, self._skill_ids, display.selected_skill_id)
        self._select(self._rule_list, self._rule_ids, display.selected_rule_id)
        self._notice.set(display.notice)

    @staticmethod
    def _fill(listbox: object, values: tuple[str, ...]) -> None:
        listbox.delete(0, "end")  # type: ignore[attr-defined]
        for value in values:
            listbox.insert("end", value)  # type: ignore[attr-defined]

    @staticmethod
    def _select(listbox: object, values: tuple[object, ...], selected: object) -> None:
        if selected in values:
            listbox.selection_set(values.index(selected))  # type: ignore[attr-defined]

    def close(self) -> None:
        self._root.destroy()

    def run(self) -> None:
        if self._owns_mainloop:
            self._root.mainloop()
        else:
            self._root.wait_window()


def run_tk_skill_trigger_review(
    repository: LocalSkillTriggerRepository,
    catalog: LocalSkillCatalog,
) -> None:
    view = TkSkillTriggerView()
    SkillTriggerPresenter(repository, catalog, view).run()


def _skill_choice(record: SkillRecord) -> TriggerSkillChoice:
    return TriggerSkillChoice(
        skill_id=record.skill_id,
        title=record.title,
        version=record.version,
    )


def _rule_summary(
    rule: SkillTriggerRule,
    skill: SkillRecord | None,
) -> TriggerRuleSummary:
    return TriggerRuleSummary(
        rule_id=rule.rule_id,
        app_id=rule.app_id,
        skill_id=rule.skill_id,
        skill_title=(skill.title if skill is not None else "현재 사용할 수 없는 스킬"),
        skill_version=rule.skill_version,
        enabled=rule.enabled,
    )
