from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from skilla_core.package_manifest import verify_package_manifest, write_package_manifest
from skilla_core.product_host import ProductHostError
from skilla_core.product_state import (
    prepare_product_state_directory,
    resolve_product_state_directory,
)


def test_source_checkout_keeps_state_below_project_root(tmp_path: Path) -> None:
    root = (tmp_path / "source").resolve()
    root.mkdir()

    assert resolve_product_state_directory(root) == root / "state"
    assert prepare_product_state_directory(root) == (root / "state").resolve()


def test_verified_package_uses_stable_schema_local_app_data_without_mutating_package(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = (tmp_path / "package").resolve()
    package.mkdir()
    (package / "SKILLA.exe").write_bytes(b"fixture")
    write_package_manifest(package, "0.1.0")
    local_app_data = (tmp_path / "local-app-data").resolve()
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    state = prepare_product_state_directory(package)

    assert state == (local_app_data / "SKILLA" / "state" / "v1").resolve()
    assert state.is_dir()
    assert not (package / "state").exists()
    assert len(verify_package_manifest(package).files) == 1


def test_verified_package_migrates_current_version_state_without_overwrite(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = (tmp_path / "package").resolve()
    package.mkdir()
    (package / "SKILLA.exe").write_bytes(b"fixture")
    write_package_manifest(package, "0.1.8")
    local_app_data = (tmp_path / "local-app-data").resolve()
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    legacy = local_app_data / "JAVIS-PC" / "state" / "0.1.7"
    legacy.mkdir(parents=True)
    legacy_database = legacy / "skills.sqlite3"
    import sqlite3

    with sqlite3.connect(legacy_database) as database:
        database.execute("CREATE TABLE skill (name TEXT NOT NULL)")
        database.execute("INSERT INTO skill VALUES ('보존할 스킬')")
    (legacy / "audit.jsonl").write_text('{"event":"old"}\n', encoding="utf-8")

    state = prepare_product_state_directory(package)

    with sqlite3.connect(state / "skills.sqlite3") as database:
        assert database.execute("SELECT name FROM skill").fetchone() == ("보존할 스킬",)
    assert (state / "audit.jsonl").read_text(encoding="utf-8") == '{"event":"old"}\n'

    with sqlite3.connect(legacy_database) as database:
        database.execute("UPDATE skill SET name = '덮어쓰면 안 됨'")
    prepare_product_state_directory(package)
    with sqlite3.connect(state / "skills.sqlite3") as database:
        assert database.execute("SELECT name FROM skill").fetchone() == ("보존할 스킬",)


def test_verified_package_rejects_reparse_legacy_state(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = (tmp_path / "package").resolve()
    package.mkdir()
    (package / "SKILLA.exe").write_bytes(b"fixture")
    write_package_manifest(package, "0.1.8")
    local_app_data = (tmp_path / "local-app-data").resolve()
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    state_root = local_app_data / "JAVIS-PC" / "state"
    state_root.mkdir(parents=True)
    target = tmp_path / "untrusted"
    target.mkdir()
    legacy = state_root / "0.1.7"
    try:
        legacy.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(ProductHostError, match="reparse point"):
        prepare_product_state_directory(package)


def test_tampered_package_fails_before_creating_external_state(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = (tmp_path / "package").resolve()
    package.mkdir()
    executable = package / "SKILLA.exe"
    executable.write_bytes(b"fixture")
    write_package_manifest(package, "0.1.0")
    executable.write_bytes(b"tampered")
    local_app_data = (tmp_path / "local-app-data").resolve()
    local_app_data.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    with pytest.raises(ProductHostError, match="integrity check failed"):
        prepare_product_state_directory(package)

    assert not (local_app_data / "SKILLA").exists()


def test_skilla_migrates_legacy_schema_state_but_preserves_newer_destination(
    monkeypatch: MonkeyPatch, tmp_path: Path,
) -> None:
    package = (tmp_path / "package").resolve()
    package.mkdir()
    (package / "SKILLA.exe").write_bytes(b"fixture")
    write_package_manifest(package, "0.1.9")
    local = (tmp_path / "local-app-data").resolve()
    legacy = local / "JAVIS-PC/state/v1"
    legacy.mkdir(parents=True)
    (legacy / "display-selection.json").write_text('{"display":"old"}', encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    destination = prepare_product_state_directory(package)
    assert destination == local / "SKILLA/state/v1"
    assert (destination / "display-selection.json").read_text() == '{"display":"old"}'
    (destination / "display-selection.json").write_text('{"display":"new"}', encoding="utf-8")
    prepare_product_state_directory(package)
    assert (destination / "display-selection.json").read_text() == '{"display":"new"}'
    assert (legacy / "display-selection.json").exists()
