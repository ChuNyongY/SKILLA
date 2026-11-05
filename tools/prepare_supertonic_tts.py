from __future__ import annotations

import hashlib
import json
import os
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(model: Path, manifest: dict[str, object]) -> bool:
    files = manifest.get("files")
    if not isinstance(files, dict):
        return False
    for name, raw_metadata in files.items():
        if not isinstance(name, str) or not isinstance(raw_metadata, dict):
            return False
        candidate = model / name
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or candidate.stat().st_size != raw_metadata.get("size")
            or _hash(candidate) != raw_metadata.get("sha256")
        ):
            return False
    return True


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    model = root / "models" / "supertonic3"
    manifest_path = model / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if _verify(model, manifest):
        print(f"ready={model}")
        return 0
    source_url = manifest.get("source_url")
    source_sha256 = manifest.get("source_sha256")
    files = manifest.get("files")
    if (
        not isinstance(source_url, str)
        or not isinstance(source_sha256, str)
        or not isinstance(files, dict)
    ):
        raise RuntimeError("SUPERTONIC_MANIFEST_INVALID")
    model.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="supertonic-prepare-", dir=model.parent) as temporary:
        work = Path(temporary)
        archive = work / "model.tar.bz2"
        with (
            urllib.request.urlopen(source_url, timeout=60) as response,
            archive.open("xb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if _hash(archive) != source_sha256:
            raise RuntimeError("SUPERTONIC_ARCHIVE_HASH_MISMATCH")
        extracted = work / "extracted"
        extracted.mkdir()
        with tarfile.open(archive, "r:bz2") as package:
            for member in package.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                    raise RuntimeError("SUPERTONIC_ARCHIVE_UNSAFE")
            package.extractall(extracted, filter="data")
        roots = [item for item in extracted.iterdir() if item.is_dir()]
        if len(roots) != 1:
            raise RuntimeError("SUPERTONIC_ARCHIVE_LAYOUT_INVALID")
        model.mkdir(exist_ok=True)
        for name in files:
            source = roots[0] / name
            destination = model / name
            if not source.is_file() or source.is_symlink():
                raise RuntimeError("SUPERTONIC_ARCHIVE_LAYOUT_INVALID")
            staged = model / f".{name}.preparing"
            with source.open("rb") as input_file, staged.open("xb") as output_file:
                while chunk := input_file.read(1024 * 1024):
                    output_file.write(chunk)
            os.replace(staged, destination)
    if not _verify(model, manifest):
        raise RuntimeError("SUPERTONIC_MODEL_VERIFY_FAILED")
    print(f"ready={model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
