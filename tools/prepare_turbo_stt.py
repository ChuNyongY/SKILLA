"""Download a revision-pinned public Whisper turbo bundle and record its hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

REPOSITORY = "dropbox-dash/faster-whisper-large-v3-turbo"
REVISION = "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
FILES = (
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.json",
    "preprocessor_config.json",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "models" / "faster-whisper-large-v3-turbo"
    snapshot_download(
        REPOSITORY,
        revision=REVISION,
        local_dir=target,
        allow_patterns=list(FILES),
        token=False,
        max_workers=3,
    )
    files = {}
    for name in FILES:
        if name == "preprocessor_config.json":
            continue
        item = target / name
        with item.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        files[name] = {"path": name, "sha256": digest, "size": item.stat().st_size}
    manifest = {
        "schema_version": "1.0",
        "source_repository": REPOSITORY,
        "source_revision": REVISION,
        "files": files,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("TURBO_BUNDLE_READY", flush=True)


if __name__ == "__main__":
    main()
