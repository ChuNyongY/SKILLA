from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from javis_core import display_target
from javis_core.display_target import (
    DisplayBounds,
    DisplayDescriptor,
    DisplaySelectionStore,
    DisplayTargetController,
    DisplayTargetError,
    DisplayTargetMode,
    WindowsDisplayBackend,
    display_guard,
)

PRIMARY = DisplayDescriptor(
    device_name=r"\\.\DISPLAY1",
    primary=True,
    bounds=DisplayBounds(left=0, top=0, width=2560, height=1440),
)
SECONDARY = DisplayDescriptor(
    device_name=r"\\.\DISPLAY2",
    primary=False,
    bounds=DisplayBounds(left=-1920, top=0, width=1920, height=1080),
)
FOREGROUND = DisplayBounds(left=100, top=100, width=800, height=600)


class FakeBackend:
    def __init__(
        self,
        displays: tuple[DisplayDescriptor, ...] = (PRIMARY, SECONDARY),
        foreground: DisplayBounds = FOREGROUND,
    ) -> None:
        self.snapshot = displays
        self.foreground = foreground

    def enumerate_displays(self) -> tuple[DisplayDescriptor, ...]:
        return self.snapshot

    def foreground_window_bounds(self) -> DisplayBounds:
        return self.foreground


def controller(tmp_path: Path, backend: FakeBackend | None = None) -> DisplayTargetController:
    return DisplayTargetController(
        backend or FakeBackend(),
        DisplaySelectionStore((tmp_path / "display-selection.json").resolve()),
    )


def test_first_run_pins_primary_and_persists_exact_geometry(tmp_path: Path) -> None:
    selected = controller(tmp_path).ensure_selection()

    assert selected.mode is DisplayTargetMode.PRIMARY
    assert selected.selected_display == PRIMARY
    assert controller(tmp_path).resolve() == PRIMARY


def test_selects_secondary_with_negative_coordinates(tmp_path: Path) -> None:
    target = controller(tmp_path)

    selected = target.select_device(r"\\.\display2")

    assert selected.mode is DisplayTargetMode.DEVICE
    assert selected.selected_display == SECONDARY
    assert target.allows_window(
        DisplayBounds(left=-1500, top=200, width=500, height=400)
    )
    assert not target.allows_window(
        DisplayBounds(left=200, top=200, width=500, height=400)
    )


def test_fixed_selection_fails_closed_when_display_geometry_changes(tmp_path: Path) -> None:
    backend = FakeBackend()
    target = controller(tmp_path, backend)
    target.select_device(SECONDARY.device_name)
    backend.snapshot = (
        PRIMARY,
        SECONDARY.model_copy(
            update={"bounds": DisplayBounds(left=-1600, top=0, width=1600, height=900)}
        ),
    )

    with pytest.raises(DisplayTargetError) as error:
        target.resolve()

    assert error.value.code == "DISPLAY_GEOMETRY_CHANGED"
    assert DisplaySelectionStore(
        (tmp_path / "display-selection.json").resolve()
    ).load().selected_display == SECONDARY


def test_primary_selection_refreshes_geometry_atomically(tmp_path: Path) -> None:
    backend = FakeBackend()
    target = controller(tmp_path, backend)
    target.select_primary()
    resized = PRIMARY.model_copy(
        update={"bounds": DisplayBounds(left=0, top=0, width=1920, height=1080)}
    )
    backend.snapshot = (resized, SECONDARY)

    refreshed = target.ensure_selection()

    assert refreshed.mode is DisplayTargetMode.PRIMARY
    assert refreshed.selected_display == resized
    assert target.resolve() == resized
    assert DisplaySelectionStore(
        (tmp_path / "display-selection.json").resolve()
    ).load() == refreshed


def test_primary_selection_follows_a_new_primary_device(tmp_path: Path) -> None:
    backend = FakeBackend()
    target = controller(tmp_path, backend)
    target.select_primary()
    old_primary = PRIMARY.model_copy(update={"primary": False})
    new_primary = SECONDARY.model_copy(update={"primary": True})
    backend.snapshot = (old_primary, new_primary)

    refreshed = target.ensure_selection()

    assert refreshed.selected_display == new_primary
    assert target.resolve() == new_primary


def test_follow_foreground_resolves_monitor_by_window_center(tmp_path: Path) -> None:
    target = controller(
        tmp_path,
        FakeBackend(
            foreground=DisplayBounds(left=-1700, top=100, width=600, height=500)
        ),
    )

    target.select_follow_foreground()

    assert target.resolve() == SECONDARY


def test_missing_ambiguous_or_offscreen_display_fails_closed(tmp_path: Path) -> None:
    for backend, code in (
        (FakeBackend(displays=()), "DISPLAY_NONE_AVAILABLE"),
        (
            FakeBackend(displays=(PRIMARY, PRIMARY)),
            "DISPLAY_ENUMERATION_AMBIGUOUS",
        ),
        (
            FakeBackend(
                displays=(PRIMARY,),
                foreground=DisplayBounds(left=5000, top=5000, width=100, height=100),
            ),
            "DISPLAY_FOREGROUND_OFFSCREEN",
        ),
    ):
        target = controller(tmp_path, backend)
        with pytest.raises(DisplayTargetError) as error:
            if code == "DISPLAY_FOREGROUND_OFFSCREEN":
                target.select_follow_foreground()
            else:
                target.displays()
        assert error.value.code == code


def test_store_rejects_duplicate_keys_invalid_utf8_and_symlink(
    tmp_path: Path,
) -> None:
    path = (tmp_path / "display-selection.json").resolve()
    store = DisplaySelectionStore(path)
    for payload in (
        b'{"schema_version":"1.0","mode":"primary","mode":"device"}',
        b"\xff\xfe",
    ):
        path.write_bytes(payload)
        with pytest.raises(DisplayTargetError) as error:
            store.load()
        assert error.value.code == "DISPLAY_SELECTION_INVALID"

    path.unlink()
    target = tmp_path / "real.json"
    target.write_text("{}", encoding="utf-8")
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    with pytest.raises(DisplayTargetError):
        store.load()


def test_windows_backend_maps_win32_monitor_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    class Api:
        @staticmethod
        def EnumDisplayMonitors() -> list[tuple[int, None, tuple[int, int, int, int]]]:
            return [(11, None, (0, 0, 2560, 1440))]

        @staticmethod
        def GetMonitorInfo(_handle: int) -> dict[str, object]:
            return {
                "Device": r"\\.\DISPLAY1",
                "Monitor": (0, 0, 2560, 1440),
                "Flags": 1,
            }

    modules = {
        "win32api": Api,
        "win32con": SimpleNamespace(MONITORINFOF_PRIMARY=1),
    }
    monkeypatch.setattr(display_target.os, "name", "nt")
    monkeypatch.setattr(display_target, "import_module", lambda name: modules[name])

    assert WindowsDisplayBackend().enumerate_displays() == (PRIMARY,)


def test_display_guard_redacts_bad_capture_and_enforces_selection(tmp_path: Path) -> None:
    target = controller(tmp_path)
    target.select_primary()
    allowed = display_guard(target)

    assert allowed(SimpleNamespace(left=10, top=10, width=100, height=100))
    assert not allowed(SimpleNamespace(left=-1800, top=10, width=100, height=100))
    assert not allowed(SimpleNamespace(left="private", top=0, width=1, height=1))
