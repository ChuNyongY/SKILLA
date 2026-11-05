from __future__ import annotations

import sys
from pathlib import Path

TTS_WORKER_TOKEN = "__skilla_tts_worker__"
UIA_WORKER_TOKEN = "__skilla_uia_worker__"
EXPLORER_WORKER_TOKEN = "__skilla_explorer_worker__"


class WorkerProcessError(RuntimeError):
    pass


def fixed_worker_command(module: str, frozen_token: str) -> list[str]:
    if module not in {
        "skilla_core.tts_worker",
        "skilla_core.uia_worker",
        "skilla_core.explorer_folder_worker",
    }:
        raise WorkerProcessError("WORKER_MODULE_INVALID")
    if frozen_token not in {
        TTS_WORKER_TOKEN,
        UIA_WORKER_TOKEN,
        EXPLORER_WORKER_TOKEN,
    }:
        raise WorkerProcessError("WORKER_TOKEN_INVALID")
    if not getattr(sys, "frozen", False):
        bootstrap = Path(__file__).resolve(strict=True).with_name("_worker_bootstrap.py")
        return [sys.executable, "-I", str(bootstrap), module]
    try:
        current = Path(sys.executable).resolve(strict=True)
        console = current.with_name("SKILLA.exe")
        if console.is_symlink():
            raise OSError("worker executable is a symlink")
        console = console.resolve(strict=True)
    except OSError as error:
        raise WorkerProcessError("FROZEN_WORKER_EXECUTABLE_INVALID") from error
    if not console.is_file():
        raise WorkerProcessError("FROZEN_WORKER_EXECUTABLE_INVALID")
    return [str(console), frozen_token]
