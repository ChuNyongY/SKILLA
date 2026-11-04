from __future__ import annotations

from pathlib import Path

import pytest

from javis_core.autostart import ShortcutSpec
from javis_core.start_menu import (
    StartMenuError,
    StartMenuShortcutRegistrar,
    StartMenuStatus,
)


class MemoryShortcutBackend:
    def __init__(self) -> None:
        self.fail_write = False

    def read(self, path: Path) -> ShortcutSpec:
        return ShortcutSpec.model_validate_json(path.read_text(encoding="utf-8"))

    def write(self, path: Path, specification: ShortcutSpec) -> None:
        if self.fail_write:
            raise OSError("fixture write failure")
        path.write_text(specification.model_dump_json(), encoding="utf-8")

    def delete(self, path: Path) -> None:
        path.unlink()


def registrar(
    tmp_path: Path,
    backend: MemoryShortcutBackend,
) -> StartMenuShortcutRegistrar:
    install = tmp_path / "install"
    programs = tmp_path / "programs"
    install.mkdir()
    programs.mkdir()
    (install / "SKILLA-Tray.exe").write_bytes(b"fixture")
    return StartMenuShortcutRegistrar(
        install.resolve(),
        programs_directory_provider=lambda: programs.resolve(),
        backend=backend,
    )


def test_register_verify_idempotent_and_remove_owned_shortcut(tmp_path: Path) -> None:
    backend = MemoryShortcutBackend()
    owned = registrar(tmp_path, backend)

    assert owned.status() is StartMenuStatus.ABSENT
    assert owned.register() is StartMenuStatus.REGISTERED
    assert owned.status() is StartMenuStatus.ALREADY_REGISTERED
    assert owned.register() is StartMenuStatus.ALREADY_REGISTERED
    record = backend.read(owned.shortcut_path)
    assert Path(record.target).name == "SKILLA-Tray.exe"
    assert record.arguments == ""
    assert Path(record.working_directory).name == "install"
    assert record.icon_location.endswith("SKILLA-Tray.exe,0")
    assert owned.unregister() is StartMenuStatus.REMOVED
    assert owned.status() is StartMenuStatus.ABSENT


def test_conflicting_link_is_never_overwritten_or_removed(tmp_path: Path) -> None:
    backend = MemoryShortcutBackend()
    owned = registrar(tmp_path, backend)
    foreign = ShortcutSpec(
        target=str((tmp_path / "foreign.exe").resolve()),
        arguments="--foreign",
        working_directory=str(tmp_path.resolve()),
        description="foreign",
        icon_location="",
    )
    backend.write(owned.shortcut_path, foreign)

    assert owned.status() is StartMenuStatus.CONFLICT
    with pytest.raises(StartMenuError, match="START_MENU_SHORTCUT_CONFLICT"):
        owned.register()
    with pytest.raises(StartMenuError, match="START_MENU_SHORTCUT_NOT_OWNED"):
        owned.unregister()
    assert backend.read(owned.shortcut_path) == foreign


def test_failed_write_removes_only_new_placeholder(tmp_path: Path) -> None:
    backend = MemoryShortcutBackend()
    owned = registrar(tmp_path, backend)
    backend.fail_write = True

    with pytest.raises(StartMenuError, match="START_MENU_REGISTRATION_FAILED"):
        owned.register()

    assert not owned.shortcut_path.exists()


def test_install_root_must_contain_exact_tray_executable(tmp_path: Path) -> None:
    programs = tmp_path / "programs"
    install = tmp_path / "install"
    programs.mkdir()
    install.mkdir()

    with pytest.raises(StartMenuError, match="START_MENU_TARGET_INVALID"):
        StartMenuShortcutRegistrar(
            install.resolve(),
            programs_directory_provider=lambda: programs.resolve(),
            backend=MemoryShortcutBackend(),
        )


def test_owned_previous_version_is_upgraded_but_foreign_parent_is_not(
    tmp_path: Path,
) -> None:
    backend = MemoryShortcutBackend()
    parent = tmp_path / "SKILLA-PC"
    old_root = parent / "0.1.1"
    new_root = parent / "0.1.2"
    programs = tmp_path / "programs"
    for directory in (old_root, new_root, programs):
        directory.mkdir(parents=True, exist_ok=True)
    old_target = old_root / "SKILLA-Tray.exe"
    new_target = new_root / "SKILLA-Tray.exe"
    old_target.write_bytes(b"old")
    new_target.write_bytes(b"new")
    owned = StartMenuShortcutRegistrar(
        new_root.resolve(),
        programs_directory_provider=lambda: programs.resolve(),
        backend=backend,
    )
    backend.write(
        owned.shortcut_path,
        ShortcutSpec(
            target=str(old_target.resolve()),
            arguments="",
            working_directory=str(old_root.resolve()),
            description="SKILLA 로컬 스킬 AI 에이전트",
            icon_location=f"{old_target.resolve()},0",
        ),
    )

    assert owned.status() is StartMenuStatus.OUTDATED
    assert owned.register() is StartMenuStatus.UPDATED
    assert owned.status() is StartMenuStatus.ALREADY_REGISTERED
    assert Path(backend.read(owned.shortcut_path).target) == new_target.resolve()
