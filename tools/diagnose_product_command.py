from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from skilla_core.always_on_runtime import AlwaysOnState
from skilla_core.credential_store import load_nim_credential
from skilla_core.product_service import build_windows_product_service_with_secret_loader


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("command")
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    parser.add_argument("--approve-review", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve(strict=True)
    config = args.config.resolve(strict=True)
    service = build_windows_product_service_with_secret_loader(
        root,
        config,
        load_nim_credential,
    )
    runtime = service.runtime.runtime
    snapshots: list[dict[str, object]] = []
    started = runtime.submit_text(args.command)
    snapshots.append({"elapsed_seconds": 0.0, "event": started.model_dump(mode="json")})
    deadline = time.monotonic() + args.timeout_seconds
    last_sequence = -1
    responded_reviews: set[str] = set()
    try:
        while time.monotonic() < deadline:
            snapshot = runtime.status_snapshot()
            if snapshot.sequence != last_sequence:
                snapshots.append(
                    {
                        "elapsed_seconds": round(
                            args.timeout_seconds - max(0.0, deadline - time.monotonic()), 3
                        ),
                        "snapshot": snapshot.model_dump(mode="json"),
                    }
                )
                last_sequence = snapshot.sequence
            review = snapshot.skill_review
            if (
                args.approve_review
                and review is not None
                and str(review.review_id) not in responded_reviews
            ):
                accepted = runtime.respond_skill_review(review.review_id, True)
                snapshots.append(
                    {
                        "elapsed_seconds": round(
                            args.timeout_seconds - max(0.0, deadline - time.monotonic()), 3
                        ),
                        "review_response": {
                            "review_id": str(review.review_id),
                            "kind": review.kind.value,
                            "accepted": accepted,
                        },
                    }
                )
                responded_reviews.add(str(review.review_id))
            terminal = snapshot.state in {AlwaysOnState.IDLE, AlwaysOnState.CLOSED}
            if terminal and snapshot.sequence > 1:
                break
            time.sleep(0.25)
    finally:
        closed = runtime.close()
    print(
        json.dumps(
            {"snapshots": snapshots, "closed": closed.model_dump(mode="json")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
