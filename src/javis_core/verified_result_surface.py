from __future__ import annotations

from collections.abc import Callable

from .cyber_theme import COLORS, button, configure_window, footer, header, label, panel
from .user_visible_result import UserVisibleResultSnapshot


def run_tk_verified_result(
    result_provider: Callable[[], UserVisibleResultSnapshot | None],
) -> None:
    """Show only the allowlisted result already verified by the runtime."""
    import tkinter as tk

    root = tk.Tk()
    configure_window(root, title="SKILLA 결과 검증", geometry="980x620", minsize=(860, 540))
    shell = tk.Frame(root, bg=COLORS["bg"], padx=20, pady=16)
    shell.pack(fill="both", expand=True)
    header(shell, system_code="SYSTEM // VERIFIED", heading="결과 검증")
    footer(shell)

    body = tk.Frame(shell, bg=COLORS["bg"])
    body.pack(fill="both", expand=True)
    left = panel(body)
    left.pack(side="left", fill="both", expand=True)
    right = panel(body, alternate=True)
    right.pack(side="left", fill="y", padx=(14, 0))

    title_var = tk.StringVar(value="검증된 결과 없음")
    lines_var = tk.StringVar(value="작업을 실행하면 독립 검증을 통과한 결과가 표시됩니다.")
    label(
        left, "VERIFIED EVIDENCE", color=COLORS["muted"], size=9, bold=True, font="Consolas"
    ).pack(fill="x")
    label(left, textvariable=title_var, color=COLORS["success"], size=22, bold=True).pack(
        fill="x", pady=(12, 10)
    )
    tk.Frame(left, height=1, bg=COLORS["line"]).pack(fill="x", pady=(0, 14))
    label(left, textvariable=lines_var, size=12).pack(fill="both", expand=True, anchor="nw")

    label(right, "FINAL STATUS", color=COLORS["muted"], size=9, bold=True, font="Consolas").pack(
        fill="x"
    )
    label(right, "✓  검증 완료", color=COLORS["success"], size=20, bold=True).pack(
        fill="x", pady=(14, 18)
    )
    label(right, "표시 원칙", color=COLORS["cyan"], size=11, bold=True).pack(fill="x")
    label(
        right,
        "• 실행 결과와 작업 ID 일치\n• 독립 검증 성공\n• 허용된 요약만 표시",
        color=COLORS["text"],
        size=10,
    ).pack(fill="x", pady=(8, 20))

    def refresh() -> None:
        snapshot = result_provider()
        if snapshot is None:
            title_var.set("검증된 결과 없음")
            lines_var.set("작업을 실행하면 독립 검증을 통과한 결과가 표시됩니다.")
        else:
            title_var.set(snapshot.title)
            lines_var.set("\n".join(f"✓  {line}" for line in snapshot.lines))

    refresh_button = button(right, "새로 고침", color=COLORS["cyan"], width=14)
    refresh_button.configure(command=refresh)
    refresh_button.pack(fill="x", pady=(0, 8))
    close_button = button(right, "닫기", color=COLORS["muted"], width=14)
    close_button.configure(command=root.destroy)
    close_button.pack(fill="x")
    refresh()
    root.mainloop()
