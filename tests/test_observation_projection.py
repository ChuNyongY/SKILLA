import json
from pathlib import Path

import pytest

from skilla_core.models import Action, Plan, Postcondition
from skilla_core.observation_projection import (
    RemoteObservationProjectionError,
    TaskLocalObservationProjector,
)


def test_system_projection_removes_hostname_and_rejects_new_fields() -> None:
    projector = TaskLocalObservationProjector()
    action = Action(capability_id="system.info.read", purpose="read")
    observed = {
        "system": "Windows",
        "release": "11",
        "version": "10.0",
        "machine": "AMD64",
        "hostname": "private-computer-name",
    }

    projected = projector.project(action, observed)

    assert projected == {
        "system": "Windows",
        "release": "11",
        "version": "10.0",
        "machine": "AMD64",
    }
    assert "private-computer-name" not in json.dumps(projected)
    with pytest.raises(RemoteObservationProjectionError, match="unexpected"):
        projector.project(action, {**observed, "new_private_field": "secret"})


def test_file_list_uses_task_local_handles_and_resolves_move(tmp_path: Path) -> None:
    source = tmp_path / "private-course-name.pdf"
    source.write_bytes(b"coursework")
    destination_directory = tmp_path / "private-subject-folder"
    destination_directory.mkdir()
    tokens = iter(("a" * 24, "b" * 24))
    projector = TaskLocalObservationProjector(token_factory=lambda: next(tokens))
    listing = Action(
        capability_id="file.list",
        purpose="list",
        arguments={"path": str(tmp_path)},
        target_identity=str(tmp_path),
    )

    projected = projector.project(
        listing,
        {
            "entries": [source.name, destination_directory.name],
            "count": 2,
            "truncated": False,
            "root_index": 0,
            "relative_path": ".",
        },
    )

    serialized = json.dumps(projected, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert source.name not in serialized
    assert destination_directory.name not in serialized
    handles = projected["entry_handles"]
    assert isinstance(handles, list)
    file_handle = next(item["handle"] for item in handles if item["kind"] == "file")
    directory_handle = next(
        item["handle"] for item in handles if item["kind"] == "directory"
    )
    plan = Plan(
        goal="sort",
        steps=(
            Action(
                capability_id="file.move",
                purpose="move selected file",
                arguments={"source": file_handle, "destination": directory_handle},
                target_identity=file_handle,
                expected_postconditions=(Postcondition(predicate="file.moved"),),
            ),
        ),
    )

    resolved = projector.resolve_plan(plan)

    action = resolved.steps[0]
    assert action.arguments == {
        "source": str(source),
        "destination": str(destination_directory / source.name),
    }
    assert action.target_identity == str(source)


def test_file_handle_fails_closed_after_target_changes(tmp_path: Path) -> None:
    source = tmp_path / "private.txt"
    source.write_text("before", encoding="utf-8")
    destination_directory = tmp_path / "done"
    destination_directory.mkdir()
    tokens = iter(("c" * 24, "d" * 24))
    projector = TaskLocalObservationProjector(token_factory=lambda: next(tokens))
    projected = projector.project(
        Action(
            capability_id="file.list",
            purpose="list",
            arguments={"path": str(tmp_path)},
            target_identity=str(tmp_path),
        ),
        {
            "entries": [source.name, destination_directory.name],
            "count": 2,
            "truncated": False,
            "root_index": 0,
            "relative_path": ".",
        },
    )
    handles = projected["entry_handles"]
    assert isinstance(handles, list)
    file_handle = next(item["handle"] for item in handles if item["kind"] == "file")
    directory_handle = next(
        item["handle"] for item in handles if item["kind"] == "directory"
    )
    source.write_text("changed-after-observation", encoding="utf-8")
    plan = Plan(
        goal="sort",
        steps=(
            Action(
                capability_id="file.move",
                purpose="move",
                arguments={"source": file_handle, "destination": directory_handle},
                target_identity=file_handle,
            ),
        ),
    )

    with pytest.raises(RemoteObservationProjectionError, match="target changed"):
        projector.resolve_plan(plan)


@pytest.mark.parametrize(
    ("capability", "observed", "expected"),
    [
        ("audio.volume.read", {"volume_percent": 55.0}, {"volume_percent": 55.0}),
        (
            "storage.status.read",
            {
                "free_percent_bucket": "GT_THRESHOLD",
                "low_disk": False,
                "mutation_count": 0,
                "root_id": "workspace",
            },
            {
                "free_percent_bucket": "GT_THRESHOLD",
                "low_disk": False,
                "mutation_count": 0,
                "root_id": "workspace",
            },
        ),
        (
            "memory.search",
            {"match_count": 1, "results_digest": "a" * 64, "unique_memory_id": None},
            {"match_count": 1},
        ),
    ],
)
def test_read_only_projection_keeps_only_required_remote_values(
    capability: str,
    observed: dict[str, object],
    expected: dict[str, object],
) -> None:
    action = Action(capability_id=capability, purpose="read")

    assert TaskLocalObservationProjector().project(action, observed) == expected


@pytest.mark.parametrize(
    ("capability", "observed", "expected"),
    [
        (
            "process.launch",
            {"app_id": "notepad", "pid": 12, "hwnd": 34},
            {"app_id": "notepad", "launched": True},
        ),
        (
            "explorer.folder.open",
            {
                "app_id": "explorer",
                "root_id": "workspace",
                "directory_sha256": "a" * 64,
                "pid": 12,
                "hwnd": 34,
                "process_creation_time_100ns": 56,
            },
            {"root_id": "workspace", "opened": True},
        ),
        (
            "settings.open",
            {"app_id": "settings", "page_id": "sound", "pid": 12},
            {"app_id": "settings", "page_id": "sound", "opened": True},
        ),
        (
            "audio.volume.set",
            {"volume_percent": 50.0},
            {"volume_percent": 50.0, "matched": True},
        ),
        (
            "cleanup.suggest",
            {
                "free_percent_bucket": "LE_THRESHOLD",
                "low_disk": True,
                "mutation_count": 0,
                "root_id": "workspace",
                "suggestion_code": "LOW_DISK_REVIEW",
            },
            {
                "free_percent_bucket": "LE_THRESHOLD",
                "low_disk": True,
                "mutation_count": 0,
                "root_id": "workspace",
                "suggestion_code": "LOW_DISK_REVIEW",
            },
        ),
        (
            "file.move",
            {
                "transaction_id": "00000000-0000-0000-0000-000000000001",
                "source": "C:/Users/private/source.txt",
                "destination": "C:/Users/private/done/source.txt",
                "source_hash": "b" * 64,
            },
            {"verified": True},
        ),
        (
            "file.delete.trash",
            {"path": "C:/Users/private/source.txt", "source_hash": "c" * 64},
            {"verified": True},
        ),
        (
            "browser.navigate",
            {
                "app_id": "chrome",
                "host": "www.example.com",
                "hwnd": 1,
                "pid": 2,
                "process_creation_time_100ns": 3,
                "scheme": "https",
                "url_sha256": "d" * 64,
            },
            {
                "app_id": "chrome",
                "host": "www.example.com",
                "scheme": "https",
                "opened": True,
            },
        ),
        (
            "browser.search.web",
            {
                "app_id": "chrome",
                "host": "www.google.com",
                "hwnd": 1,
                "pid": 2,
                "process_creation_time_100ns": 3,
                "scheme": "https",
                "url_sha256": "e" * 64,
                "search_engine": "google",
                "query_sha256": "f" * 64,
            },
            {"search_engine": "google", "opened": True},
        ),
        (
            "media.youtube.play.recent",
            {
                "app_id": "chrome",
                "host": "www.youtube.com",
                "hwnd": 1,
                "pid": 2,
                "process_creation_time_100ns": 3,
                "scheme": "https",
                "url_sha256": "1" * 64,
                "history_source": "chrome-local",
                "selection_mode": "frequent",
                "lookback_days": 30,
                "selection_sha256": "2" * 64,
            },
            {"selection_mode": "frequent", "lookback_days": 30, "opened": True},
        ),
    ],
)
def test_state_changing_projection_never_exposes_local_receipts(
    capability: str,
    observed: dict[str, object],
    expected: dict[str, object],
) -> None:
    projected = TaskLocalObservationProjector().project(
        Action(capability_id=capability, purpose="run"), observed
    )

    assert projected == expected
    serialized = json.dumps(projected, ensure_ascii=False)
    assert "private" not in serialized
    assert "sha256" not in serialized
