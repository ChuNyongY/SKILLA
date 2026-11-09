from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "ui_actual"
TARGETS = {
    "SKILLA 결과 검증": "SKILLA_실제구현_결과검증.png",
    "SKILLA 스킬 검토": "SKILLA_실제구현_스킬관리.png",
    "SKILLA 실행 기록 검토": "SKILLA_실제구현_개정후보검토.png",
}


def visible_windows() -> dict[str, int]:
    user32 = ctypes.windll.user32
    found: dict[str, int] = {}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if title in TARGETS and title not in found:
            found[title] = hwnd
        return True

    user32.EnumWindows(callback_type(visit), 0)
    return found


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    windows = visible_windows()
    missing = sorted(set(TARGETS) - set(windows))
    if missing:
        raise SystemExit(f"열려 있지 않은 UI: {', '.join(missing)}")
    for title, filename in TARGETS.items():
        image = ImageGrab.grab(window=windows[title], include_layered_windows=True)
        path = OUTPUT / filename
        image.save(path)
        print(f"{title}: {path} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()
