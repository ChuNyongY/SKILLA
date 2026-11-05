"""Start a fixed local worker without trusting cwd, PYTHONPATH or an editable install."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    allowed = {
        "skilla_core.tts_worker",
        "skilla_core.uia_worker",
        "skilla_core.explorer_folder_worker",
    }
    if len(sys.argv) != 2 or sys.argv[1] not in allowed:
        raise SystemExit("WORKER_MODULE_INVALID")
    module = sys.argv[1]
    sys.path.insert(0, str(Path(__file__).resolve(strict=True).parents[1]))
    sys.argv = [module]
    runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
