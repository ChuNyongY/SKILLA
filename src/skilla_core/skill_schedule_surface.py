from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import Field

from .models import FrozenModel
from .skill_runtime import LocalSkillCatalog, SkillStatus
from .skill_schedules import LocalSkillScheduleRepository, SkillScheduleRule

_DAY_LABELS = ("월", "화", "수", "목", "금", "토", "일")


class ScheduleSkillChoice(FrozenModel):
    skill_id: UUID
    title: str = Field(min_length=1, max_length=120)
    version: int = Field(ge=1)


class ScheduleRuleSummary(FrozenModel):
    rule_id: UUID
    label: str = Field(min_length=1, max_length=240)
    enabled: bool


class SkillScheduleDisplay(FrozenModel):
    skills: tuple[ScheduleSkillChoice, ...]
    rules: tuple[ScheduleRuleSummary, ...]
    message: str = Field(min_length=1, max_length=200)


class SkillScheduleView(Protocol):
    def bind_handlers(
        self,
        *,
        on_create: Callable[[UUID, int, int, tuple[int, ...]], None],
        on_toggle: Callable[[UUID], None],
        on_delete: Callable[[UUID], None],
        on_refresh: Callable[[], None],
    ) -> None: ...

    def render(self, display: SkillScheduleDisplay) -> None: ...

    def run(self) -> None: ...


class SkillSchedulePresenter:
    def __init__(
        self,
        schedules: LocalSkillScheduleRepository,
        skills: LocalSkillCatalog,
        view: SkillScheduleView,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    ) -> None:
        self._schedules = schedules
        self._skills = skills
        self._view = view
        self._clock = clock

    def run(self) -> None:
        self._view.bind_handlers(
            on_create=self.create,
            on_toggle=self.toggle,
            on_delete=self.delete,
            on_refresh=self.refresh,
        )
        self.refresh()
        self._view.run()

    def refresh(self, message: str = "예약 시각에도 자동 실행하지 않고 제안만 표시합니다.") -> None:
        skills = tuple(
            ScheduleSkillChoice(
                skill_id=skill.skill_id,
                title=skill.title,
                version=skill.version,
            )
            for skill in self._skills.list(status=SkillStatus.VERIFIED, limit=100)
        )
        rules = tuple(self._summary(rule) for rule in self._schedules.list(limit=1_000))
        self._view.render(SkillScheduleDisplay(skills=skills, rules=rules, message=message))

    def create(
        self,
        skill_id: UUID,
        hour: int,
        minute: int,
        weekdays: tuple[int, ...],
    ) -> None:
        self._schedules.create(
            skill_id,
            hour=hour,
            minute=minute,
            weekdays=weekdays,
            now=self._clock(),
        )
        self.refresh("예약을 저장했습니다. 실행 시각에 HUD에서 다시 확인합니다.")

    def toggle(self, rule_id: UUID) -> None:
        current = self._schedules.require(rule_id)
        self._schedules.set_enabled(rule_id, not current.enabled, now=self._clock())
        self.refresh("예약 사용 상태를 변경했습니다.")

    def delete(self, rule_id: UUID) -> None:
        self._schedules.delete(rule_id)
        self.refresh("예약을 삭제했습니다.")

    def _summary(self, rule: SkillScheduleRule) -> ScheduleRuleSummary:
        try:
            skill = self._skills.require(rule.skill_id)
            title = skill.title
        except Exception:
            title = "사용할 수 없는 스킬"
        hour, minute = divmod(rule.local_minute, 60)
        days = "·".join(_DAY_LABELS[day] for day in rule.weekdays)
        state = "사용" if rule.enabled else "중지"
        return ScheduleRuleSummary(
            rule_id=rule.rule_id,
            label=f"[{state}] {hour:02d}:{minute:02d}  {days}  {title} v{rule.skill_version}",
            enabled=rule.enabled,
        )


class TkSkillScheduleView:
    def __init__(self) -> None:
        try:
            import tkinter as tk
        except ImportError as error:
            raise RuntimeError("tkinter schedule UI is unavailable") from error
        try:
            root = tk.Tk()
        except tk.TclError as error:
            raise RuntimeError("tkinter schedule UI could not start") from error
        root.title("SKILLA 예약 스킬")
        root.geometry("900x620")
        root.configure(bg="#030711")
        self._tk = tk
        self._root = root
        self._skills: list[ScheduleSkillChoice] = []
        self._rules: list[ScheduleRuleSummary] = []
        self._on_create: Callable[[UUID, int, int, tuple[int, ...]], None] | None = None
        self._on_toggle: Callable[[UUID], None] | None = None
        self._on_delete: Callable[[UUID], None] | None = None

        tk.Label(
            root,
            text="예약 스킬",
            bg="#030711",
            fg="#43e6ff",
            font=("맑은 고딕", 22, "bold"),
        ).pack(anchor="w", padx=20, pady=(18, 4))
        self._message = tk.StringVar()
        tk.Label(
            root,
            textvariable=self._message,
            bg="#030711",
            fg="#ffb84d",
            font=("맑은 고딕", 10),
        ).pack(anchor="w", padx=20)

        body = tk.Frame(root, bg="#030711")
        body.pack(fill="both", expand=True, padx=20, pady=14)
        left = tk.Frame(body, bg="#071421", padx=12, pady=12)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg="#071421", padx=12, pady=12)
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))

        tk.Label(
            left, text="검증된 스킬", bg="#071421", fg="#d9f7ff",
            font=("맑은 고딕", 12, "bold"),
        ).pack(anchor="w")
        self._skill_list = tk.Listbox(
            left, bg="#091b2b", fg="#d9f7ff", selectbackground="#1689a8",
            font=("맑은 고딕", 10), height=12, relief="flat",
        )
        self._skill_list.pack(fill="both", expand=True, pady=8)

        time_row = tk.Frame(left, bg="#071421")
        time_row.pack(fill="x")
        tk.Label(time_row, text="시각", bg="#071421", fg="#7fa6b5").pack(side="left")
        self._hour = tk.Spinbox(time_row, from_=0, to=23, width=4, format="%02.0f")
        self._hour.pack(side="left", padx=(8, 2))
        tk.Label(time_row, text=":", bg="#071421", fg="#d9f7ff").pack(side="left")
        self._minute = tk.Spinbox(time_row, from_=0, to=59, width=4, format="%02.0f")
        self._minute.pack(side="left", padx=2)

        days = tk.Frame(left, bg="#071421")
        days.pack(fill="x", pady=10)
        self._day_values = [tk.BooleanVar(value=day < 5) for day in range(7)]
        for index, label in enumerate(_DAY_LABELS):
            tk.Checkbutton(
                days, text=label, variable=self._day_values[index], bg="#071421",
                fg="#d9f7ff", selectcolor="#091b2b", activebackground="#071421",
                activeforeground="#43e6ff",
            ).pack(side="left")
        create = tk.Button(
            left, text="예약 저장", command=self._create, bg="#091b2b", fg="#5effc5",
            relief="flat", font=("맑은 고딕", 10, "bold"), pady=7,
        )
        create.pack(fill="x")

        tk.Label(
            right, text="저장된 예약", bg="#071421", fg="#d9f7ff",
            font=("맑은 고딕", 12, "bold"),
        ).pack(anchor="w")
        self._rule_list = tk.Listbox(
            right, bg="#091b2b", fg="#d9f7ff", selectbackground="#1689a8",
            font=("맑은 고딕", 10), height=16, relief="flat",
        )
        self._rule_list.pack(fill="both", expand=True, pady=8)
        buttons = tk.Frame(right, bg="#071421")
        buttons.pack(fill="x")
        for text, command, color in (
            ("사용/중지", self._toggle, "#ffb84d"),
            ("삭제", self._delete, "#ff526c"),
            ("닫기", root.destroy, "#7fa6b5"),
        ):
            tk.Button(
                buttons, text=text, command=command, bg="#091b2b", fg=color,
                relief="flat", font=("맑은 고딕", 9, "bold"), padx=12, pady=6,
            ).pack(side="left", padx=(0, 8))

    def bind_handlers(
        self,
        *,
        on_create: Callable[[UUID, int, int, tuple[int, ...]], None],
        on_toggle: Callable[[UUID], None],
        on_delete: Callable[[UUID], None],
        on_refresh: Callable[[], None],
    ) -> None:
        self._on_create = on_create
        self._on_toggle = on_toggle
        self._on_delete = on_delete
        self._root.bind("<F5>", lambda _event: on_refresh())

    def render(self, display: SkillScheduleDisplay) -> None:
        self._skills = list(display.skills)
        self._rules = list(display.rules)
        self._message.set(display.message)
        self._skill_list.delete(0, "end")
        for skill in self._skills:
            self._skill_list.insert("end", f"{skill.title}  v{skill.version}")
        self._rule_list.delete(0, "end")
        for rule in self._rules:
            self._rule_list.insert("end", rule.label)

    def run(self) -> None:
        self._root.mainloop()

    def _selected_skill(self) -> ScheduleSkillChoice | None:
        selected = self._skill_list.curselection()  # type: ignore[no-untyped-call]
        return self._skills[selected[0]] if selected else None

    def _selected_rule(self) -> ScheduleRuleSummary | None:
        selected = self._rule_list.curselection()  # type: ignore[no-untyped-call]
        return self._rules[selected[0]] if selected else None

    def _create(self) -> None:
        skill = self._selected_skill()
        weekdays = tuple(index for index, value in enumerate(self._day_values) if value.get())
        if skill is None or not weekdays or self._on_create is None:
            return
        try:
            self._on_create(
                skill.skill_id,
                int(self._hour.get()),
                int(self._minute.get()),
                weekdays,
            )
        except (TypeError, ValueError):
            self._message.set("시각과 요일을 확인하세요.")

    def _toggle(self) -> None:
        rule = self._selected_rule()
        if rule is not None and self._on_toggle is not None:
            self._on_toggle(rule.rule_id)

    def _delete(self) -> None:
        rule = self._selected_rule()
        if rule is not None and self._on_delete is not None:
            self._on_delete(rule.rule_id)


def run_tk_skill_schedule_review(
    schedules: LocalSkillScheduleRepository,
    skills: LocalSkillCatalog,
) -> None:
    SkillSchedulePresenter(schedules, skills, TkSkillScheduleView()).run()
