"""Shared palette and controls for the SKILLA desktop windows."""

from collections.abc import Callable
from tkinter import Button, Label, Menu, Menubutton, Misc

BACKGROUND = "#030711"
PANEL = "#091b2b"
FIELD = "#071421"
BORDER = "#123c52"
TEXT = "#d9f7ff"
MUTED = "#9abac8"
ACCENT = "#43e6ff"
WARNING = "#ffb84d"
DANGER = "#ff8295"
FONT = ("맑은 고딕", 11)


def heading(parent: Misc, title: str, description: str) -> None:
    Label(parent, text="S . K . I . L . L . A", bg=BACKGROUND, fg=ACCENT,
          font=("Consolas", 14, "bold")).pack(anchor="w")
    Label(parent, text=title, bg=BACKGROUND, fg=TEXT,
          font=("맑은 고딕", 23, "bold")).pack(anchor="w", pady=(5, 2))
    Label(parent, text=description, bg=BACKGROUND, fg=MUTED,
          font=FONT, justify="left").pack(anchor="w", pady=(0, 14))


def button(
    parent: Misc, label: str, action: Callable[[], None], *,
    primary: bool = False, color: str = TEXT,
) -> Button:
    return Button(
        parent, text=label, command=action, bg=ACCENT if primary else FIELD,
        fg=BACKGROUND if primary else color, activebackground="#b6f4ff",
        activeforeground=BACKGROUND, disabledforeground="#638392", relief="flat",
        highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
        font=("맑은 고딕", 10, "bold"), padx=12, pady=7,
    )


def action_menu(
    parent: Misc, label: str, actions: tuple[tuple[str, Callable[[], None] | None], ...],
) -> Menubutton:
    control = Menubutton(
        parent, text=f"{label} ▾", takefocus=True, font=("맑은 고딕", 10, "bold"),
        bg=FIELD, fg=TEXT, activebackground=ACCENT, activeforeground=BACKGROUND,
        padx=12, pady=7, highlightthickness=1, highlightcolor=ACCENT,
        highlightbackground=BORDER,
    )
    menu = Menu(control, tearoff=False, font=FONT)
    for item, action in actions:
        if action is not None:
            menu.add_command(label=item, command=action)
    control.configure(menu=menu)
    return control
