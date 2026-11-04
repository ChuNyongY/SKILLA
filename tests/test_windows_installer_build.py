from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from javis_core.package_manifest import PackageManifestError
from tools.build_windows_installer import VERSION as INSTALLER_VERSION
from tools.build_windows_installer import (
    InstallerBuildError,
    create_payload_archive,
    render_install_script,
    resolve_installer_paths,
)
from tools.build_windows_package import VERSION as PACKAGE_VERSION


def test_release_version_is_consistent_across_builders_and_metadata() -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert PACKAGE_VERSION == INSTALLER_VERSION == "0.1.9"
    assert metadata["project"]["version"] == PACKAGE_VERSION
    assert Path("docs/PACKAGE_README.ko.txt").read_text(encoding="utf-8").startswith(
        f"SKILLA-PC {PACKAGE_VERSION} "
    )


def test_install_template_never_enables_startup_or_embeds_secret(tmp_path: Path) -> None:
    template = Path("packaging/install_package.cmd")
    destination = tmp_path / "install.cmd"

    render_install_script(template, destination, "a" * 64)

    rendered = destination.read_text(encoding="utf-8")
    assert "__VERSION__" not in rendered
    assert "__PAYLOAD_SHA256__" not in rendered
    assert "install-autostart" not in rendered
    assert "nvapi-" not in rendered
    assert "powershell" not in rendered.casefold()
    assert "certutil.exe" in rendered
    assert "tar.exe" in rendered
    assert ".installing-" in rendered
    assert "install-result-%version%.txt" in rendered
    assert "status=STARTED" not in rendered
    assert "echo status=%~1" in rendered
    assert "SKILLA.exe.verified" not in rendered
    assert 'SKILLA.exe" install-start-menu "%destination%"' in rendered


def test_install_template_records_success_only_after_verify_and_move(tmp_path: Path) -> None:
    destination = tmp_path / "install.cmd"
    render_install_script(
        Path("packaging/install_package.cmd"),
        destination,
        "a" * 64,
    )

    rendered = destination.read_text(encoding="utf-8")
    verify_index = rendered.index('"%staging%\\SKILLA.exe" verify-package')
    move_index = rendered.index('move "%staging%" "%destination%"')
    shortcut_index = rendered.index(
        '"%destination%\\SKILLA.exe" install-start-menu "%destination%"',
        move_index,
    )
    success_index = rendered.index("call :write_result SUCCESS 0")

    assert verify_index < move_index < shortcut_index < success_index
    assert "call :write_result ALREADY_VERIFIED 0" in rendered
    assert "call :write_result FAILED 13" in rendered
    assert "call :write_result FAILED %failure%" in rendered
    assert ":fail_verify\nset \"failure=18\"" in rendered
    assert ":fail_move\nset \"failure=19\"" in rendered
    assert ":fail_shortcut\nset \"failure=20\"" in rendered


def test_install_result_contains_only_fixed_non_secret_fields(tmp_path: Path) -> None:
    destination = tmp_path / "install.cmd"
    render_install_script(
        Path("packaging/install_package.cmd"),
        destination,
        "a" * 64,
    )

    rendered = destination.read_text(encoding="utf-8")
    result_block = rendered.split("\n:write_result\n", maxsplit=1)[1]

    assert "echo schema_version=1" in result_block
    assert "echo version=%version%" in result_block
    assert "echo status=%~1" in result_block
    assert "echo code=%~2" in result_block
    assert '"%resultTemporary%"' not in result_block
    assert "echo %destination%" not in result_block
    assert "echo %payload%" not in result_block
    assert "nvapi-" not in result_block


def test_payload_archive_requires_a_verified_package(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "SKILLA.exe").write_bytes(b"not-manifested")

    with pytest.raises(PackageManifestError):
        create_payload_archive(package, tmp_path / "payload.zip")

    assert not (tmp_path / "payload.zip").exists()


def test_install_template_rejects_invalid_hash(tmp_path: Path) -> None:
    with pytest.raises(InstallerBuildError, match="HASH_INVALID"):
        render_install_script(
            Path("packaging/install_package.cmd"),
            tmp_path / "install.cmd",
            "not-a-hash",
        )


def test_installer_paths_accept_verified_custom_package_and_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    package = tmp_path / "package"
    output = tmp_path / "output"
    for directory in (repository, package, output):
        directory.mkdir()
    observed: list[Path] = []
    monkeypatch.setattr(
        "tools.build_windows_installer.verify_package_manifest",
        lambda path: observed.append(path),
    )

    resolved_package, setup, checksum = resolve_installer_paths(
        repository,
        package=package,
        destination=output / "SKILLA-Candidate.exe",
    )

    assert resolved_package == package.resolve()
    assert setup == output.resolve() / "SKILLA-Candidate.exe"
    assert checksum == output.resolve() / "SKILLA-Candidate.exe.sha256"
    assert observed == [package.resolve()]


@pytest.mark.parametrize("existing_name", ["SKILLA.exe", "SKILLA.exe.sha256"])
def test_installer_paths_never_overwrite_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing_name: str,
) -> None:
    repository = tmp_path / "repository"
    package = tmp_path / "package"
    output = tmp_path / "output"
    for directory in (repository, package, output):
        directory.mkdir()
    (output / existing_name).write_bytes(b"existing")
    monkeypatch.setattr(
        "tools.build_windows_installer.verify_package_manifest",
        lambda _path: None,
    )

    with pytest.raises(InstallerBuildError, match="DESTINATION_EXISTS"):
        resolve_installer_paths(
            repository,
            package=package,
            destination=output / "SKILLA.exe",
        )


def test_installer_paths_reject_invalid_custom_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    package = tmp_path / "package"
    repository.mkdir()
    package.mkdir()
    monkeypatch.setattr(
        "tools.build_windows_installer.verify_package_manifest",
        lambda _path: None,
    )

    with pytest.raises(InstallerBuildError, match="DESTINATION_INVALID"):
        resolve_installer_paths(
            repository,
            package=package,
            destination=tmp_path / "missing" / "SKILLA.zip",
        )
