from __future__ import annotations

from typing import Any

COLORS = {
    "bg": "#030711",
    "panel": "#071421",
    "panel_alt": "#091b2b",
    "line": "#123c52",
    "cyan": "#43e6ff",
    "cyan_dim": "#1689a8",
    "text": "#d9f7ff",
    "muted": "#7fa6b5",
    "warning": "#ffb84d",
    "danger": "#ff526c",
    "success": "#5effc5",
}


def configure_window(root: Any, *, title: str, geometry: str, minsize: tuple[int, int]) -> None:
    root.title(title)
    root.geometry(geometry)
    root.minsize(*minsize)
    root.configure(bg=COLORS["bg"])


def panel(parent: Any, *, alternate: bool = False, padx: int = 14, pady: int = 12) -> Any:
    import tkinter as tk

    return tk.Frame(
        parent,
        bg=COLORS["panel_alt" if alternate else "panel"],
        highlightbackground=COLORS["line"],
        highlightthickness=1,
        padx=padx,
        pady=pady,
    )


def label(
    parent: Any,
    text: str | None = None,
    *,
    textvariable: Any | None = None,
    color: str | None = None,
    size: int = 10,
    bold: bool = False,
    anchor: str = "w",
    font: str = "맑은 고딕",
) -> Any:
    import tkinter as tk

    background = str(parent.cget("bg"))
    return tk.Label(
        parent,
        text=text,
        textvariable=textvariable,
        bg=background,
        fg=color or COLORS["text"],
        font=(font, size, "bold" if bold else "normal"),
        anchor=anchor,
        justify="left",
    )


def button(parent: Any, text: str, *, color: str | None = None, width: int = 12) -> Any:
    import tkinter as tk

    foreground = color or COLORS["cyan"]
    return tk.Button(
        parent,
        text=text,
        width=width,
        bg=COLORS["panel"],
        fg=foreground,
        activebackground=COLORS["panel_alt"],
        activeforeground=COLORS["text"],
        disabledforeground="#405866",
        relief="flat",
        bd=0,
        highlightbackground=foreground,
        highlightcolor=foreground,
        highlightthickness=1,
        font=("맑은 고딕", 9, "bold"),
        padx=8,
        pady=7,
        cursor="hand2",
    )


def header(parent: Any, *, system_code: str, heading: str) -> Any:
    import tkinter as tk

    frame = tk.Frame(parent, bg=COLORS["bg"])
    frame.pack(fill="x")
    label(
        frame,
        "S · K · I · L · L · A",
        color=COLORS["cyan"],
        size=21,
        bold=True,
        font="Consolas",
    ).pack(side="left")
    label(
        frame,
        "SKILL-BASED LOCAL AI AGENT",
        color=COLORS["muted"],
        size=8,
        font="Consolas",
    ).pack(side="left", padx=(16, 0), pady=(9, 0))
    label(
        frame,
        system_code,
        color=COLORS["warning"],
        size=9,
        bold=True,
        anchor="e",
        font="Consolas",
    ).pack(side="right", pady=(8, 0))
    tk.Frame(parent, height=1, bg=COLORS["cyan_dim"]).pack(fill="x", pady=(12, 12))
    label(parent, heading, size=19, bold=True).pack(fill="x", pady=(0, 10))
    return frame


def footer(parent: Any) -> None:
    import tkinter as tk

    frame = tk.Frame(parent, bg=COLORS["bg"])
    frame.pack(fill="x", side="bottom", pady=(12, 0))
    label(
        frame,
        "LOCAL CORE  ·  SKILL MEMORY  ·  VERIFIED EXECUTION",
        color="#315a69",
        size=8,
        font="Consolas",
    ).pack(side="left")
    label(
        frame,
        "●  ONLINE",
        color=COLORS["success"],
        size=8,
        bold=True,
        anchor="e",
        font="Consolas",
    ).pack(side="right")
