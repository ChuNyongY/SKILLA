from pathlib import Path

from skilla_core.package_manifest import verify_package_manifest, write_package_manifest
from tools.build_windows_package import ASSET_DIRECTORIES, _copy_trusted_tree

SUPERTONIC_DIRECTORY = Path("models/supertonic3")


def test_supertonic_model_and_sample_code_licenses_are_distinct() -> None:
    model_license = (SUPERTONIC_DIRECTORY / "LICENSE.MODEL-OpenRAIL-M.txt").read_text(
        encoding="utf-8"
    )
    sample_code_license = (SUPERTONIC_DIRECTORY / "LICENSE").read_text(
        encoding="utf-8"
    )
    notice = (SUPERTONIC_DIRECTORY / "THIRD_PARTY_NOTICE.SKILLA.txt").read_text(
        encoding="utf-8"
    )

    assert model_license.startswith("BigScience Open RAIL-M License")
    assert "5. Use-based restrictions." in model_license
    assert "Attachment A" in model_license
    assert "Use Restrictions" in model_license
    assert sample_code_license.startswith("MIT License")
    assert "LICENSE.MODEL-OpenRAIL-M.txt" in notice
    assert "The separate file named LICENSE" in notice

    package_readme = Path("docs/PACKAGE_README.ko.txt").read_text(encoding="utf-8")
    assert "Supertonic 3 모델은 OpenRAIL-M 조건" in package_readme
    assert "models\\supertonic3\\LICENSE.MODEL-OpenRAIL-M.txt" in package_readme
    assert "정확한 전체 조건이 요약보다 우선" in package_readme


def test_windows_package_copies_the_complete_supertonic_license_bundle(
    tmp_path: Path,
) -> None:
    assert SUPERTONIC_DIRECTORY in ASSET_DIRECTORIES
    copied = tmp_path / "supertonic3"

    _copy_trusted_tree(SUPERTONIC_DIRECTORY.resolve(strict=True), copied)

    assert (copied / "LICENSE.MODEL-OpenRAIL-M.txt").read_bytes() == (
        SUPERTONIC_DIRECTORY / "LICENSE.MODEL-OpenRAIL-M.txt"
    ).read_bytes()
    assert (copied / "THIRD_PARTY_NOTICE.SKILLA.txt").read_bytes() == (
        SUPERTONIC_DIRECTORY / "THIRD_PARTY_NOTICE.SKILLA.txt"
    ).read_bytes()

    write_package_manifest(tmp_path.resolve(strict=True), "test")
    packaged_paths = {
        entry.path for entry in verify_package_manifest(tmp_path.resolve(strict=True)).files
    }
    assert "supertonic3/LICENSE.MODEL-OpenRAIL-M.txt" in packaged_paths
    assert "supertonic3/THIRD_PARTY_NOTICE.SKILLA.txt" in packaged_paths
