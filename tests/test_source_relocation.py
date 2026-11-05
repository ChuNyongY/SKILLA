from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_renamed_source_tree_loads_config_and_isolated_worker_from_unrelated_cwd(
    tmp_path: Path,
) -> None:
    source = Path(__file__).resolve().parents[1]
    relocated = tmp_path / "renamed-repository" / "스킬라 프로그램"
    package = relocated / "src" / "skilla_core"
    shutil.copytree(
        source / "src/skilla_core", package, ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(source / "config", relocated / "config")
    configuration = json.loads(
        (relocated / "config/product_host.json").read_text(encoding="utf-8")
    )
    for key in ("wakeword_manifest", "stt_manifest"):
        relative = configuration.get(key)
        if relative is None:
            continue
        item = relocated / relative
        item.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, item)
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()
    script = (
        "import sys; from pathlib import Path; "
        "root=Path(sys.argv[1]); sys.path.insert(0,str(root/'src')); "
        "from skilla_core.product_host import load_product_host_config; "
        "c=load_product_host_config(root/'config/product_host.json',root); "
        "assert c.stt_manifest.is_relative_to(root); "
        "import skilla_core; assert Path(skilla_core.__file__).is_relative_to(root); "
        "print('RELOCATION_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(relocated)],
        cwd=unrelated, capture_output=True, timeout=15, check=True,
    )
    assert result.stdout.strip() == b"RELOCATION_OK"
    worker = subprocess.run(
        [sys.executable, "-I", str(package / "_worker_bootstrap.py"), "skilla_core.tts_worker"],
        cwd=unrelated, input=b"not-json", capture_output=True, timeout=15, check=True,
    )
    response = json.loads(worker.stdout)
    assert response["success"] is False
    assert response["error_code"] == "TTS_WORKER_FAILED"
    assert not worker.stderr
