from __future__ import annotations

import os
import re
from collections.abc import Callable
from contextlib import suppress
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from .autostart import ShortcutBackend, ShortcutSpec, WindowsComShortcutBackend


class StartMenuError(RuntimeError):
    """Privacy-safe failure while managing the owned Start Menu shortcut."""


class StartMenuStatus(StrEnum):
    ABSENT = "ABSENT"
    REGISTERED = "REGISTERED"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"
    REMOVED = "REMOVED"
    UPDATED = "UPDATED"
    OUTDATED = "OUTDATED"
    CONFLICT = "CONFLICT"


ProgramsDirectoryProvider = Callable[[], Path]


def current_user_programs_directory() -> Path:
    try:
        from win32com.shell import shell, shellcon  # type: ignore[import-untyped]

        value = shell.SHGetFolderPath(0, shellcon.CSIDL_PROGRAMS, None, 0)
    except Exception as error:
        raise StartMenuError("START_MENU_FOLDER_UNAVAILABLE") from error
    return _trusted_directory(Path(value), "START_MENU_FOLDER_INVALID")


class StartMenuShortcutRegistrar:
    """Own one current-user Start Menu link without enabling autostart."""

    _NAME = "SKILLA-PC.lnk"
    _TARGET_NAME = "SKILLA-Tray.exe"

    def __init__(
        self,
        install_root: Path,
        *,
        programs_directory_provider: ProgramsDirectoryProvider = (
            current_user_programs_directory
        ),
        backend: ShortcutBackend | None = None,
    ) -> None:
        root = _trusted_directory(install_root, "START_MENU_INSTALL_ROOT_INVALID")
        target = _trusted_file(
            root / self._TARGET_NAME,
            "START_MENU_TARGET_INVALID",
        )
        if target.parent != root:
            raise StartMenuError("START_MENU_TARGET_INVALID")
        programs = _trusted_directory(
            programs_directory_provider(),
            "START_MENU_FOLDER_INVALID",
        )
        self._path = programs / self._NAME
        self._install_root = root
        self._install_parent = root.parent
        self._backend = backend or WindowsComShortcutBackend()
        self._specification = ShortcutSpec(
            target=str(target),
            arguments="",
            working_directory=str(root),
            description="SKILLA 로컬 스킬 AI 에이전트",
            icon_location=f"{target},0",
        )

    @property
    def shortcut_path(self) -> Path:
        return self._path

    def status(self) -> StartMenuStatus:
        if not self._path.exists():
            return StartMenuStatus.ABSENT
        if self._path.is_symlink() or not self._path.is_file():
            return StartMenuStatus.CONFLICT
        try:
            observed = self._backend.read(self._path)
        except Exception:
            return StartMenuStatus.CONFLICT
        if _specifications_match(observed, self._specification):
            return StartMenuStatus.ALREADY_REGISTERED
        if self._is_owned_previous_version(observed):
            return StartMenuStatus.OUTDATED
        return StartMenuStatus.CONFLICT

    def register(self) -> StartMenuStatus:
        status = self.status()
        if status is StartMenuStatus.ALREADY_REGISTERED:
            return status
        if status not in {StartMenuStatus.ABSENT, StartMenuStatus.OUTDATED}:
            raise StartMenuError("START_MENU_SHORTCUT_CONFLICT")
        temporary = self._path.with_name(f".SKILLA-PC-{uuid4().hex}.lnk")
        if status is StartMenuStatus.ABSENT:
            try:
                descriptor = os.open(
                    self._path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                os.close(descriptor)
            except FileExistsError as error:
                raise StartMenuError("START_MENU_SHORTCUT_CONFLICT") from error
            except OSError as error:
                raise StartMenuError("START_MENU_REGISTRATION_FAILED") from error
        try:
            self._backend.write(temporary, self._specification)
            staged = self._backend.read(temporary)
            if not _specifications_match(staged, self._specification):
                raise StartMenuError("START_MENU_REGISTRATION_VERIFY_FAILED")
            os.replace(temporary, self._path)
            observed = self._backend.read(self._path)
        except Exception as error:
            with suppress(Exception):
                if temporary.exists() and not temporary.is_symlink():
                    self._backend.delete(temporary)
            if status is StartMenuStatus.ABSENT:
                self._remove_failed_new_shortcut()
            raise StartMenuError("START_MENU_REGISTRATION_FAILED") from error
        if not _specifications_match(observed, self._specification):
            raise StartMenuError("START_MENU_REGISTRATION_VERIFY_FAILED")
        return (
            StartMenuStatus.UPDATED
            if status is StartMenuStatus.OUTDATED
            else StartMenuStatus.REGISTERED
        )

    def unregister(self) -> StartMenuStatus:
        status = self.status()
        if status is StartMenuStatus.ABSENT:
            return status
        if status is not StartMenuStatus.ALREADY_REGISTERED:
            raise StartMenuError("START_MENU_SHORTCUT_NOT_OWNED")
        self._backend.delete(self._path)
        if self._path.exists():
            raise StartMenuError("START_MENU_REMOVAL_VERIFY_FAILED")
        return StartMenuStatus.REMOVED

    def _remove_failed_new_shortcut(self) -> None:
        if self._path.exists() and not self._path.is_symlink():
            with suppress(Exception):
                self._backend.delete(self._path)

    def _is_owned_previous_version(self, observed: ShortcutSpec) -> bool:
        try:
            target = Path(observed.target).resolve(strict=True)
            working = Path(observed.working_directory).resolve(strict=True)
        except (OSError, RuntimeError):
            return False
        return (
            target.name.casefold() == self._TARGET_NAME.casefold()
            and target.parent == working
            and target.parent.parent == self._install_parent
            and target.parent != self._install_root
            and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", target.parent.name)
            is not None
            and observed.arguments == ""
            and observed.description == self._specification.description
            and os.path.normcase(observed.icon_location)
            == os.path.normcase(f"{target},0")
        )


def _trusted_file(path: Path, code: str) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise StartMenuError(code)
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise StartMenuError(code) from error
    if not resolved.is_file():
        raise StartMenuError(code)
    return resolved


def _trusted_directory(path: Path, code: str) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise StartMenuError(code)
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise StartMenuError(code) from error
    if not resolved.is_dir():
        raise StartMenuError(code)
    return resolved


def _specifications_match(first: ShortcutSpec, second: ShortcutSpec) -> bool:
    return (
        os.path.normcase(first.target) == os.path.normcase(second.target)
        and first.arguments == second.arguments
        and os.path.normcase(first.working_directory)
        == os.path.normcase(second.working_directory)
        and first.description == second.description
        and os.path.normcase(first.icon_location)
        == os.path.normcase(second.icon_location)
    )
