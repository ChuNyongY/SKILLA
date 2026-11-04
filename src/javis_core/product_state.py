from __future__ import annotations

import os
import re
import shutil
import sqlite3
import stat
from pathlib import Path

from .package_manifest import PackageManifestError, verify_package_manifest
from .product_host import ProductHostError

_STATE_SCHEMA_DIRECTORY = "v1"
_MIGRATED_REGULAR_FILES = ("audit.jsonl", "display-selection.json")
_MIGRATED_DATABASE_FILES = ("skills.sqlite3", "skill-traces.sqlite3")


def resolve_product_state_directory(project_root: Path) -> Path:
    """Keep mutable state outside a verified installed package.

    Source checkouts retain the historical ``<root>/state`` location. A root with a
    package manifest is treated as immutable and uses the current user's local app
    data directory, keyed by the state schema rather than the application version.
    This keeps reviewed skills and execution traces available after an upgrade.
    """
    root = _trusted_existing_directory(project_root, "product root")
    manifest_path = root / "package-manifest.json"
    if not manifest_path.exists() and not manifest_path.is_symlink():
        return root / "state"
    try:
        manifest = verify_package_manifest(root)
    except PackageManifestError as error:
        raise ProductHostError("installed package integrity check failed") from error
    raw_local_app_data = os.environ.get("LOCALAPPDATA")
    if not raw_local_app_data:
        raise ProductHostError("LOCALAPPDATA is unavailable")
    local_app_data = _trusted_existing_directory(
        Path(raw_local_app_data),
        "local application data root",
    )
    del manifest
    return local_app_data / "JAVIS-PC" / "state" / _STATE_SCHEMA_DIRECTORY


def prepare_product_state_directory(project_root: Path) -> Path:
    destination = resolve_product_state_directory(project_root)
    _reject_existing_reparse_chain(destination)
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ProductHostError("product state directory is unavailable") from error
    _reject_existing_reparse_chain(destination)
    if not destination.is_dir():
        raise ProductHostError("product state directory is unavailable")
    resolved_destination = destination.resolve(strict=True)
    root = project_root.resolve(strict=True)
    manifest_path = root / "package-manifest.json"
    if manifest_path.exists() or manifest_path.is_symlink():
        try:
            manifest = verify_package_manifest(root)
        except PackageManifestError as error:
            raise ProductHostError("installed package integrity check failed") from error
        del manifest
        legacy = _latest_legacy_state_directory(resolved_destination.parent)
        if legacy is not None:
            _migrate_legacy_version_state(legacy, resolved_destination)
    return resolved_destination


def _latest_legacy_state_directory(state_root: Path) -> Path | None:
    try:
        candidates = tuple(state_root.iterdir())
    except OSError as error:
        raise ProductHostError("product state directory is unavailable") from error
    versioned: list[tuple[tuple[int, int, int], Path]] = []
    for candidate in candidates:
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", candidate.name)
        if match is None:
            continue
        _reject_existing_reparse_chain(candidate)
        if not candidate.is_dir():
            raise ProductHostError("legacy product state directory is invalid")
        versioned.append(
            (
                (int(match.group(1)), int(match.group(2)), int(match.group(3))),
                candidate,
            )
        )
    if not versioned:
        return None
    return max(versioned, key=lambda item: item[0])[1]


def _migrate_legacy_version_state(source: Path, destination: Path) -> None:
    """Copy the current installed version's state into the stable schema directory.

    Existing destination files always win. SQLite's backup API is used so a valid
    database snapshot is produced even when the source is in WAL mode.
    """
    if not source.exists() and not source.is_symlink():
        return
    _reject_existing_reparse_chain(source)
    if not source.is_dir():
        raise ProductHostError("legacy product state directory is invalid")
    for name in _MIGRATED_DATABASE_FILES:
        source_file = source / name
        destination_file = destination / name
        if destination_file.exists() or destination_file.is_symlink():
            _require_regular_state_file(destination_file)
            continue
        if not source_file.exists() and not source_file.is_symlink():
            continue
        _require_regular_state_file(source_file)
        try:
            with (
                sqlite3.connect(source_file) as source_database,
                sqlite3.connect(destination_file) as destination_database,
            ):
                source_database.backup(destination_database)
        except (OSError, sqlite3.Error) as error:
            destination_file.unlink(missing_ok=True)
            raise ProductHostError("legacy product database migration failed") from error
        _require_regular_state_file(destination_file)
    for name in _MIGRATED_REGULAR_FILES:
        source_file = source / name
        destination_file = destination / name
        if destination_file.exists() or destination_file.is_symlink():
            _require_regular_state_file(destination_file)
            continue
        if not source_file.exists() and not source_file.is_symlink():
            continue
        _require_regular_state_file(source_file)
        try:
            shutil.copy2(source_file, destination_file)
        except OSError as error:
            destination_file.unlink(missing_ok=True)
            raise ProductHostError("legacy product state migration failed") from error
        _require_regular_state_file(destination_file)


def _require_regular_state_file(path: Path) -> None:
    if path.is_symlink() or _is_reparse_point(path):
        raise ProductHostError("product state file must not be a reparse point")
    try:
        mode = path.stat().st_mode
    except OSError as error:
        raise ProductHostError("product state file is unavailable") from error
    if not stat.S_ISREG(mode):
        raise ProductHostError("product state file is invalid")


def _trusted_existing_directory(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or _is_reparse_point(path):
        raise ProductHostError(f"{label} is invalid")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ProductHostError(f"{label} is unavailable") from error
    if not resolved.is_dir() or resolved.is_symlink() or _is_reparse_point(resolved):
        raise ProductHostError(f"{label} is invalid")
    return resolved


def _reject_existing_reparse_chain(path: Path) -> None:
    current = path
    existing: list[Path] = []
    while True:
        if current.exists() or current.is_symlink():
            existing.append(current)
        if current.parent == current:
            break
        current = current.parent
    for candidate in existing:
        if candidate.is_symlink() or _is_reparse_point(candidate):
            raise ProductHostError("product state path must not contain a reparse point")


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
