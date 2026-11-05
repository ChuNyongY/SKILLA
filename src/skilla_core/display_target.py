from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable
from contextlib import suppress
from enum import StrEnum
from importlib import import_module
from pathlib import Path
from threading import RLock
from typing import Any, Literal, Protocol

from pydantic import Field, StrictBool, StrictInt, model_validator

from .models import FrozenModel

_MAX_SELECTION_BYTES = 8 * 1024
_DEVICE_NAME = re.compile(r"^\\\\\.\\DISPLAY[1-9][0-9]*$", re.IGNORECASE)


class DisplayTargetError(RuntimeError):
    """Stable, privacy-safe display boundary failure."""

    def __init__(self, code: str) -> None:
        if re.fullmatch(r"[A-Z0-9_]{2,64}", code) is None:
            raise ValueError("invalid display error code")
        super().__init__(code)
        self.code = code


class DisplayTargetMode(StrEnum):
    PRIMARY = "primary"
    DEVICE = "device"
    FOLLOW_FOREGROUND = "follow_foreground"


class DisplayBounds(FrozenModel):
    left: StrictInt = Field(ge=-65_536, le=65_536)
    top: StrictInt = Field(ge=-65_536, le=65_536)
    width: StrictInt = Field(ge=1, le=16_384)
    height: StrictInt = Field(ge=1, le=16_384)

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains_center(self, window: DisplayBounds) -> bool:
        center_x = window.left + window.width // 2
        center_y = window.top + window.height // 2
        return self.left <= center_x < self.right and self.top <= center_y < self.bottom


class DisplayDescriptor(FrozenModel):
    device_name: str = Field(min_length=12, max_length=32)
    primary: StrictBool
    bounds: DisplayBounds

    @model_validator(mode="after")
    def canonical_device_name(self) -> DisplayDescriptor:
        if _DEVICE_NAME.fullmatch(self.device_name) is None:
            raise ValueError("invalid Windows display device name")
        if self.device_name != self.device_name.upper():
            raise ValueError("display device name must be canonical uppercase")
        return self


class DisplaySelection(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    mode: DisplayTargetMode
    selected_display: DisplayDescriptor | None = None

    @model_validator(mode="after")
    def mode_matches_selection(self) -> DisplaySelection:
        if self.mode is DisplayTargetMode.FOLLOW_FOREGROUND:
            if self.selected_display is not None:
                raise ValueError("follow-foreground mode must not pin a display")
            return self
        if self.selected_display is None:
            raise ValueError("fixed display mode requires a selected display")
        if self.mode is DisplayTargetMode.PRIMARY and not self.selected_display.primary:
            raise ValueError("primary mode requires the current primary display")
        return self


class DisplayBackend(Protocol):
    def enumerate_displays(self) -> tuple[DisplayDescriptor, ...]: ...

    def foreground_window_bounds(self) -> DisplayBounds: ...


class DisplayCaptureLike(Protocol):
    left: int
    top: int
    width: int
    height: int


class WindowsDisplayBackend:
    """Read monitor geometry and foreground bounds without capturing pixels."""

    def enumerate_displays(self) -> tuple[DisplayDescriptor, ...]:
        if os.name != "nt":
            raise DisplayTargetError("DISPLAY_WINDOWS_REQUIRED")
        try:
            win32api = import_module("win32api")
            win32con = import_module("win32con")
            rows = win32api.EnumDisplayMonitors()
            displays = tuple(
                self._descriptor(win32api.GetMonitorInfo(row[0]), win32con)
                for row in rows
            )
        except DisplayTargetError:
            raise
        except Exception:
            raise DisplayTargetError("DISPLAY_ENUMERATION_FAILED") from None
        _validate_display_snapshot(displays)
        return tuple(sorted(displays, key=lambda item: item.device_name))

    def foreground_window_bounds(self) -> DisplayBounds:
        if os.name != "nt":
            raise DisplayTargetError("DISPLAY_WINDOWS_REQUIRED")
        try:
            win32gui = import_module("win32gui")
            hwnd = int(win32gui.GetForegroundWindow())
            if hwnd <= 0 or not bool(win32gui.IsWindowVisible(hwnd)):
                raise DisplayTargetError("DISPLAY_FOREGROUND_UNAVAILABLE")
            left, top, right, bottom = tuple(
                int(value) for value in win32gui.GetWindowRect(hwnd)
            )
            return DisplayBounds(
                left=left,
                top=top,
                width=right - left,
                height=bottom - top,
            )
        except DisplayTargetError:
            raise
        except Exception:
            raise DisplayTargetError("DISPLAY_FOREGROUND_UNAVAILABLE") from None

    @staticmethod
    def _descriptor(info: object, win32con: Any) -> DisplayDescriptor:
        if not isinstance(info, dict):
            raise DisplayTargetError("DISPLAY_ENUMERATION_FAILED")
        raw_name = info.get("Device")
        raw_bounds = info.get("Monitor")
        raw_flags = info.get("Flags")
        if (
            not isinstance(raw_name, str)
            or not isinstance(raw_bounds, tuple)
            or len(raw_bounds) != 4
            or type(raw_flags) is not int
        ):
            raise DisplayTargetError("DISPLAY_ENUMERATION_FAILED")
        left, top, right, bottom = tuple(int(value) for value in raw_bounds)
        return DisplayDescriptor(
            device_name=raw_name.upper(),
            primary=bool(raw_flags & int(win32con.MONITORINFOF_PRIMARY)),
            bounds=DisplayBounds(
                left=left,
                top=top,
                width=right - left,
                height=bottom - top,
            ),
        )


class DisplaySelectionStore:
    def __init__(self, path: Path, *, max_bytes: int = _MAX_SELECTION_BYTES) -> None:
        if not path.is_absolute() or max_bytes < 128:
            raise ValueError("invalid display selection store")
        self._path = path
        self._max_bytes = max_bytes

    @property
    def exists(self) -> bool:
        return self._path.exists() or self._path.is_symlink()

    def load(self) -> DisplaySelection:
        path = self._path
        if path.is_symlink() or not path.is_file():
            raise DisplayTargetError("DISPLAY_SELECTION_INVALID")
        try:
            size = path.stat().st_size
            if not 2 <= size <= self._max_bytes:
                raise DisplayTargetError("DISPLAY_SELECTION_INVALID")
            raw = path.read_bytes()
            if len(raw) > self._max_bytes:
                raise DisplayTargetError("DISPLAY_SELECTION_INVALID")
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_json_constant,
            )
            return DisplaySelection.model_validate(document)
        except DisplayTargetError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise DisplayTargetError("DISPLAY_SELECTION_INVALID") from None

    def save(self, selection: DisplaySelection) -> None:
        if not isinstance(selection, DisplaySelection):
            raise TypeError("selection must be a DisplaySelection")
        parent = self._path.parent
        if parent.is_symlink() or not parent.is_dir() or self._path.is_symlink():
            raise DisplayTargetError("DISPLAY_SELECTION_STORE_UNAVAILABLE")
        payload = (
            json.dumps(
                selection.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        if len(payload) > self._max_bytes:
            raise DisplayTargetError("DISPLAY_SELECTION_INVALID")
        temporary: Path | None = None
        try:
            descriptor, raw_path = tempfile.mkstemp(
                dir=parent,
                prefix=".display-selection-",
                suffix=".tmp",
            )
            temporary = Path(raw_path)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            temporary = None
        except OSError:
            raise DisplayTargetError("DISPLAY_SELECTION_STORE_UNAVAILABLE") from None
        finally:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)


class DisplayTargetController:
    """Persist one display target and fail closed when the topology drifts."""

    def __init__(self, backend: DisplayBackend, store: DisplaySelectionStore) -> None:
        self._backend = backend
        self._store = store
        self._lock = RLock()

    def displays(self) -> tuple[DisplayDescriptor, ...]:
        with self._lock:
            snapshot = self._backend.enumerate_displays()
            _validate_display_snapshot(snapshot)
            return snapshot

    def ensure_selection(self) -> DisplaySelection:
        with self._lock:
            if self._store.exists:
                selection = self._store.load()
                if selection.mode is DisplayTargetMode.PRIMARY:
                    current_primary = _primary_display(self.displays())
                    if selection.selected_display != current_primary:
                        selection = DisplaySelection(
                            mode=DisplayTargetMode.PRIMARY,
                            selected_display=current_primary,
                        )
                        self._store.save(selection)
                    return selection
                self._resolve_locked(selection)
                return selection
            primary = _primary_display(self.displays())
            selection = DisplaySelection(
                mode=DisplayTargetMode.PRIMARY,
                selected_display=primary,
            )
            self._store.save(selection)
            return selection

    def current(self) -> DisplaySelection:
        with self._lock:
            return self.ensure_selection()

    def select_primary(self) -> DisplaySelection:
        with self._lock:
            selection = DisplaySelection(
                mode=DisplayTargetMode.PRIMARY,
                selected_display=_primary_display(self.displays()),
            )
            self._store.save(selection)
            return selection

    def select_device(self, device_name: str) -> DisplaySelection:
        with self._lock:
            canonical = device_name.upper()
            selected = next(
                (item for item in self.displays() if item.device_name == canonical),
                None,
            )
            if selected is None:
                raise DisplayTargetError("DISPLAY_DEVICE_MISSING")
            selection = DisplaySelection(
                mode=DisplayTargetMode.DEVICE,
                selected_display=selected,
            )
            self._store.save(selection)
            return selection

    def select_follow_foreground(self) -> DisplaySelection:
        with self._lock:
            selection = DisplaySelection(mode=DisplayTargetMode.FOLLOW_FOREGROUND)
            self._resolve_locked(selection)
            self._store.save(selection)
            return selection

    def resolve(self) -> DisplayDescriptor:
        with self._lock:
            return self._resolve_locked(self.ensure_selection())

    def allows_window(self, bounds: DisplayBounds) -> bool:
        if not isinstance(bounds, DisplayBounds):
            raise TypeError("bounds must be DisplayBounds")
        with self._lock:
            return self.resolve().bounds.contains_center(bounds)

    def _resolve_locked(self, selection: DisplaySelection) -> DisplayDescriptor:
        displays = self.displays()
        if selection.mode is DisplayTargetMode.FOLLOW_FOREGROUND:
            foreground = self._backend.foreground_window_bounds()
            selected = next(
                (item for item in displays if item.bounds.contains_center(foreground)),
                None,
            )
            if selected is None:
                raise DisplayTargetError("DISPLAY_FOREGROUND_OFFSCREEN")
            return selected
        expected = selection.selected_display
        assert expected is not None
        current = next(
            (item for item in displays if item.device_name == expected.device_name),
            None,
        )
        if current is None:
            raise DisplayTargetError("DISPLAY_DEVICE_MISSING")
        if selection.mode is DisplayTargetMode.PRIMARY and not current.primary:
            raise DisplayTargetError("DISPLAY_PRIMARY_CHANGED")
        if current != expected:
            raise DisplayTargetError("DISPLAY_GEOMETRY_CHANGED")
        return current


def build_windows_display_controller(state_directory: Path) -> DisplayTargetController:
    if not state_directory.is_absolute() or state_directory.is_symlink():
        raise ValueError("state directory must be an absolute non-symlink path")
    try:
        resolved = state_directory.resolve(strict=True)
    except OSError as error:
        raise DisplayTargetError("DISPLAY_SELECTION_STORE_UNAVAILABLE") from error
    if not resolved.is_dir():
        raise DisplayTargetError("DISPLAY_SELECTION_STORE_UNAVAILABLE")
    return DisplayTargetController(
        WindowsDisplayBackend(),
        DisplaySelectionStore(resolved / "display-selection.json"),
    )


def run_tk_display_selector(controller: DisplayTargetController) -> None:
    """Show a local-only selector; saving requires an explicit button press."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    displays = controller.displays()
    current = controller.current()
    root = tk.Tk()
    root.title("SKILLA 작업 화면 선택")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    choice = tk.StringVar()
    options: list[tuple[str, str]] = [("주 모니터 고정", "primary")]
    options.extend(
        (
            f"{item.device_name} ({item.bounds.width}×{item.bounds.height}"
            f", {item.bounds.left},{item.bounds.top})"
            + (" · 주 모니터" if item.primary else ""),
            item.device_name,
        )
        for item in displays
    )
    options.append(("현재 전면 창 따라가기", "follow_foreground"))
    initial = current.mode.value
    if current.mode is DisplayTargetMode.DEVICE:
        assert current.selected_display is not None
        initial = current.selected_display.device_name
    choice.set(initial)
    ttk.Label(root, text="SKILLA가 화면 작업에 사용할 디스플레이를 선택하세요.").pack(
        padx=18, pady=(16, 8)
    )
    for label, value in options:
        ttk.Radiobutton(root, text=label, value=value, variable=choice).pack(
            anchor="w", padx=22, pady=3
        )

    def save() -> None:
        selected = choice.get()
        try:
            if selected == "primary":
                controller.select_primary()
            elif selected == "follow_foreground":
                controller.select_follow_foreground()
            else:
                controller.select_device(selected)
        except DisplayTargetError as error:
            messagebox.showerror("SKILLA", f"화면 선택을 저장하지 못했습니다. ({error.code})")
            return
        messagebox.showinfo("SKILLA", "작업 화면을 저장했습니다.")
        root.destroy()

    buttons = ttk.Frame(root)
    buttons.pack(fill="x", padx=18, pady=16)
    ttk.Button(buttons, text="취소", command=root.destroy).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="저장", command=save).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


def display_guard(
    controller: DisplayTargetController,
) -> Callable[[DisplayCaptureLike], bool]:
    """Adapt a controller to the vision capture boundary without importing vision."""

    def allowed(capture: DisplayCaptureLike) -> bool:
        try:
            bounds = DisplayBounds(
                left=capture.left,
                top=capture.top,
                width=capture.width,
                height=capture.height,
            )
            return controller.allows_window(bounds)
        except (AttributeError, TypeError, ValueError, DisplayTargetError):
            return False

    return allowed


def _validate_display_snapshot(displays: tuple[DisplayDescriptor, ...]) -> None:
    if not displays:
        raise DisplayTargetError("DISPLAY_NONE_AVAILABLE")
    names = tuple(item.device_name for item in displays)
    if len(names) != len(set(names)):
        raise DisplayTargetError("DISPLAY_ENUMERATION_AMBIGUOUS")
    if sum(item.primary for item in displays) != 1:
        raise DisplayTargetError("DISPLAY_PRIMARY_AMBIGUOUS")


def _primary_display(displays: tuple[DisplayDescriptor, ...]) -> DisplayDescriptor:
    _validate_display_snapshot(displays)
    return next(item for item in displays if item.primary)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ValueError("duplicate JSON key")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")
