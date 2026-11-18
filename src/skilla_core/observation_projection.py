from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import JsonValue

from .models import Action, Plan


class RemoteObservationProjectionError(ValueError):
    pass


@dataclass(frozen=True)
class _PathBinding:
    path: Path
    is_directory: bool
    device: int
    inode: int
    size: int
    modified_ns: int


class TaskLocalObservationProjector:
    """Project verified results for remote planning without exposing local paths."""

    _HANDLE = re.compile(r"^obs_[A-Za-z0-9_-]{20,64}$")

    def __init__(self, token_factory: Callable[[], str] | None = None) -> None:
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(18))
        self._bindings: dict[str, _PathBinding] = {}
        self._path_handles: dict[Path, str] = {}

    def project(self, action: Action, observed: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
        capability = action.capability_id
        if capability == "system.info.read":
            self._exact(observed, {"system", "release", "version", "machine", "hostname"})
            return {
                key: self._bounded_string(observed[key], key, 256)
                for key in ("system", "release", "version", "machine")
            }
        if capability == "file.list":
            return self._project_file_list(action, observed)
        if capability == "process.launch":
            self._exact(observed, {"app_id", "pid"}, {"hwnd"})
            return {
                "app_id": self._identifier(observed["app_id"], "app_id"),
                "launched": True,
            }
        if capability == "explorer.folder.open":
            self._exact(
                observed,
                {
                    "app_id",
                    "root_id",
                    "directory_sha256",
                    "pid",
                    "hwnd",
                    "process_creation_time_100ns",
                },
            )
            return {
                "root_id": self._identifier(observed["root_id"], "root_id"),
                "opened": True,
            }
        if capability == "settings.open":
            self._exact(observed, {"app_id", "page_id", "pid"})
            return {
                "app_id": self._identifier(observed["app_id"], "app_id"),
                "page_id": self._identifier(observed["page_id"], "page_id"),
                "opened": True,
            }
        if capability in {"audio.volume.read", "audio.volume.set"}:
            self._exact(observed, {"volume_percent"})
            return {
                "volume_percent": self._percentage(observed["volume_percent"]),
                **({"matched": True} if capability == "audio.volume.set" else {}),
            }
        if capability in {"storage.status.read", "cleanup.suggest"}:
            required = {"free_percent_bucket", "low_disk", "mutation_count", "root_id"}
            if capability == "cleanup.suggest":
                required.add("suggestion_code")
            self._exact(observed, required)
            bucket = observed["free_percent_bucket"]
            low_disk = observed["low_disk"]
            mutation_count = observed["mutation_count"]
            if bucket not in {"LE_THRESHOLD", "GT_THRESHOLD"}:
                raise RemoteObservationProjectionError("invalid storage bucket")
            if type(low_disk) is not bool or mutation_count != 0:
                raise RemoteObservationProjectionError("invalid storage observation")
            projected: dict[str, JsonValue] = {
                "free_percent_bucket": cast(str, bucket),
                "low_disk": low_disk,
                "mutation_count": 0,
                "root_id": self._identifier(observed["root_id"], "root_id"),
            }
            if capability == "cleanup.suggest":
                code = observed["suggestion_code"]
                if code not in {"LOW_DISK_REVIEW", "NO_ACTION"}:
                    raise RemoteObservationProjectionError("invalid cleanup suggestion")
                projected["suggestion_code"] = cast(str, code)
            return projected
        if capability == "file.move":
            self._exact(observed, {"transaction_id", "source", "destination", "source_hash"})
            return {"verified": True}
        if capability == "file.delete.trash":
            self._exact(observed, {"path", "source_hash"})
            return {"verified": True}
        if capability == "browser.navigate":
            self._browser_keys(observed)
            return {
                "app_id": self._identifier(observed["app_id"], "app_id"),
                "host": self._host(observed["host"]),
                "scheme": self._https(observed["scheme"]),
                "opened": True,
            }
        if capability == "browser.search.web":
            self._browser_keys(observed, {"search_engine", "query_sha256"})
            if observed["search_engine"] != "google":
                raise RemoteObservationProjectionError("invalid search engine")
            return {"search_engine": "google", "opened": True}
        if capability == "media.youtube.play.recent":
            self._browser_keys(
                observed,
                {"history_source", "selection_mode", "lookback_days", "selection_sha256"},
            )
            mode = observed["selection_mode"]
            days = observed["lookback_days"]
            if observed["history_source"] != "chrome-local" or mode not in {"recent", "frequent"}:
                raise RemoteObservationProjectionError("invalid media selection")
            if type(days) is not int or not 1 <= days <= 90:
                raise RemoteObservationProjectionError("invalid media lookback")
            return {
                "selection_mode": cast(str, mode),
                "lookback_days": days,
                "opened": True,
            }
        if capability == "memory.search":
            self._exact(observed, {"match_count", "results_digest", "unique_memory_id"})
            count = observed["match_count"]
            if type(count) is not int or not 0 <= count <= 10:
                raise RemoteObservationProjectionError("invalid memory match count")
            return {"match_count": count}
        raise RemoteObservationProjectionError("capability has no remote observation projection")

    def resolve_plan(self, plan: Plan) -> Plan:
        resolved: list[Action] = []
        for action in plan.steps:
            if action.capability_id == "file.move":
                resolved.append(self._resolve_move(action))
            elif action.capability_id == "file.delete.trash":
                resolved.append(self._resolve_trash(action))
            else:
                if self._contains_handle(action):
                    raise RemoteObservationProjectionError(
                        "observation handle used by unsupported capability"
                    )
                resolved.append(action)
        return plan.model_copy(update={"steps": tuple(resolved)})

    def _project_file_list(
        self,
        action: Action,
        observed: Mapping[str, JsonValue],
    ) -> dict[str, JsonValue]:
        self._exact(observed, {"entries", "count", "truncated", "root_index", "relative_path"})
        entries = observed["entries"]
        count = observed["count"]
        truncated = observed["truncated"]
        root_index = observed["root_index"]
        if not isinstance(entries, list) or type(count) is not int or count != len(entries):
            raise RemoteObservationProjectionError("invalid file list count")
        if type(truncated) is not bool or type(root_index) is not int or root_index < 0:
            raise RemoteObservationProjectionError("invalid file list metadata")
        raw_path = action.arguments.get("path")
        if not isinstance(raw_path, str) or action.target_identity != raw_path:
            raise RemoteObservationProjectionError("file list action is not path-bound")
        try:
            directory = Path(raw_path).resolve(strict=True)
        except OSError as error:
            raise RemoteObservationProjectionError("file list directory is unavailable") from error
        if not directory.is_dir() or directory.is_symlink():
            raise RemoteObservationProjectionError("file list directory is unsafe")
        handles: list[JsonValue] = []
        for raw_name in entries:
            if not isinstance(raw_name, str) or not raw_name or Path(raw_name).name != raw_name:
                raise RemoteObservationProjectionError("invalid file list entry")
            try:
                child = (directory / raw_name).resolve(strict=True)
            except OSError as error:
                raise RemoteObservationProjectionError("file list entry changed") from error
            if child.parent != directory or child.is_symlink():
                raise RemoteObservationProjectionError("file list entry escaped its directory")
            binding = self._binding(child)
            handle = self._handle(binding)
            handles.append(
                {
                    "handle": handle,
                    "kind": "directory" if binding.is_directory else "file",
                    "extension": "" if binding.is_directory else self._safe_extension(child),
                }
            )
        return {
            "count": count,
            "truncated": truncated,
            "root_index": root_index,
            "entry_handles": handles,
        }

    def _resolve_move(self, action: Action) -> Action:
        source_value = action.arguments.get("source")
        destination_value = action.arguments.get("destination")
        uses_handle = self._is_handle(source_value) or self._is_handle(destination_value)
        if not uses_handle:
            return action
        if not self._is_handle(source_value) or not self._is_handle(destination_value):
            raise RemoteObservationProjectionError("file move must use two observation handles")
        if action.target_identity != source_value:
            raise RemoteObservationProjectionError("file move handle target mismatch")
        source = self._verified_path(cast(str, source_value), require_directory=False)
        destination_directory = self._verified_path(
            cast(str, destination_value), require_directory=True
        )
        destination = destination_directory / source.name
        if destination.exists():
            raise RemoteObservationProjectionError("file move destination already exists")
        return action.model_copy(
            update={
                "arguments": {"source": str(source), "destination": str(destination)},
                "target_identity": str(source),
            }
        )

    def _resolve_trash(self, action: Action) -> Action:
        value = action.arguments.get("path")
        if not self._is_handle(value):
            return action
        if action.target_identity != value:
            raise RemoteObservationProjectionError("trash handle target mismatch")
        path = self._verified_path(cast(str, value), require_directory=False)
        return action.model_copy(
            update={"arguments": {"path": str(path)}, "target_identity": str(path)}
        )

    def _binding(self, path: Path) -> _PathBinding:
        try:
            metadata = path.stat()
        except OSError as error:
            raise RemoteObservationProjectionError("observation path is unavailable") from error
        is_directory = path.is_dir()
        if not is_directory and not path.is_file():
            raise RemoteObservationProjectionError("unsupported observation path kind")
        return _PathBinding(
            path=path,
            is_directory=is_directory,
            device=metadata.st_dev,
            inode=metadata.st_ino,
            size=metadata.st_size,
            modified_ns=metadata.st_mtime_ns,
        )

    def _handle(self, binding: _PathBinding) -> str:
        existing = self._path_handles.get(binding.path)
        if existing is not None:
            return existing
        for _attempt in range(10):
            handle = f"obs_{self._token_factory()}"
            if self._HANDLE.fullmatch(handle) and handle not in self._bindings:
                self._bindings[handle] = binding
                self._path_handles[binding.path] = handle
                return handle
        raise RemoteObservationProjectionError("could not allocate a valid observation handle")

    def _verified_path(self, handle: str, *, require_directory: bool) -> Path:
        binding = self._bindings.get(handle)
        if binding is None or binding.is_directory is not require_directory:
            raise RemoteObservationProjectionError("observation handle is invalid")
        if self._binding(binding.path) != binding:
            raise RemoteObservationProjectionError("observation handle target changed")
        return binding.path

    @classmethod
    def _contains_handle(cls, action: Action) -> bool:
        values = tuple(action.arguments.values()) + (action.target_identity,)
        return any(cls._is_handle(value) for value in values)

    @classmethod
    def _is_handle(cls, value: object) -> bool:
        return isinstance(value, str) and value.startswith("obs_")

    @staticmethod
    def _safe_extension(path: Path) -> str:
        suffix = path.suffix.casefold()
        return suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ""

    @staticmethod
    def _exact(
        observed: Mapping[str, JsonValue],
        required: set[str],
        optional: set[str] | None = None,
    ) -> None:
        keys = set(observed)
        allowed = required | (optional or set())
        if not required.issubset(keys) or not keys.issubset(allowed):
            raise RemoteObservationProjectionError("unexpected observation fields")

    def _browser_keys(
        self,
        observed: Mapping[str, JsonValue],
        extra: set[str] | None = None,
    ) -> None:
        required = {
            "app_id",
            "host",
            "hwnd",
            "pid",
            "process_creation_time_100ns",
            "scheme",
            "url_sha256",
        }
        self._exact(observed, required | (extra or set()))

    @staticmethod
    def _bounded_string(value: JsonValue, name: str, maximum: int) -> str:
        if not isinstance(value, str) or not value or len(value) > maximum:
            raise RemoteObservationProjectionError(f"invalid {name}")
        return value

    @classmethod
    def _identifier(cls, value: JsonValue, name: str) -> str:
        text = cls._bounded_string(value, name, 64)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", text) is None:
            raise RemoteObservationProjectionError(f"invalid {name}")
        return text

    @classmethod
    def _host(cls, value: JsonValue) -> str:
        text = cls._bounded_string(value, "host", 253).casefold()
        if re.fullmatch(r"[a-z0-9.-]+", text) is None:
            raise RemoteObservationProjectionError("invalid host")
        return text

    @staticmethod
    def _https(value: JsonValue) -> str:
        if value != "https":
            raise RemoteObservationProjectionError("invalid browser scheme")
        return "https"

    @staticmethod
    def _percentage(value: JsonValue) -> int | float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise RemoteObservationProjectionError("invalid volume percentage")
        return value


def validate_remote_observation_context(value: object) -> None:
    """Revalidate the final projected observation area immediately before serialization."""

    if not isinstance(value, list) or len(value) > 200:
        raise RemoteObservationProjectionError("invalid projected observation collection")
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "capability_id",
            "verification_reason",
            "observed",
        }:
            raise RemoteObservationProjectionError("invalid projected observation envelope")
        capability = item["capability_id"]
        reason = item["verification_reason"]
        observed = item["observed"]
        if not isinstance(capability, str) or capability not in _PROJECTED_SCHEMAS:
            raise RemoteObservationProjectionError("invalid projected capability")
        if not isinstance(reason, str) or re.fullmatch(r"[A-Za-z0-9_.:-]{2,256}", reason) is None:
            raise RemoteObservationProjectionError("invalid projected verification reason")
        if not isinstance(observed, dict):
            raise RemoteObservationProjectionError("invalid projected observation payload")
        _validate_projected_payload(capability, observed)
        _reject_sensitive_projected_text(item)


_PROJECTED_SCHEMAS: dict[str, frozenset[str]] = {
    "system.info.read": frozenset({"system", "release", "version", "machine"}),
    "process.launch": frozenset({"app_id", "launched"}),
    "explorer.folder.open": frozenset({"root_id", "opened"}),
    "settings.open": frozenset({"app_id", "page_id", "opened"}),
    "audio.volume.read": frozenset({"volume_percent"}),
    "audio.volume.set": frozenset({"volume_percent", "matched"}),
    "file.list": frozenset({"count", "truncated", "root_index", "entry_handles"}),
    "storage.status.read": frozenset(
        {"free_percent_bucket", "low_disk", "mutation_count", "root_id"}
    ),
    "cleanup.suggest": frozenset(
        {
            "free_percent_bucket",
            "low_disk",
            "mutation_count",
            "root_id",
            "suggestion_code",
        }
    ),
    "file.move": frozenset({"verified"}),
    "file.delete.trash": frozenset({"verified"}),
    "browser.navigate": frozenset({"app_id", "host", "scheme", "opened"}),
    "browser.search.web": frozenset({"search_engine", "opened"}),
    "media.youtube.play.recent": frozenset({"selection_mode", "lookback_days", "opened"}),
    "memory.search": frozenset({"match_count"}),
}


def _validate_projected_payload(capability: str, observed: dict[object, object]) -> None:
    if set(observed) != _PROJECTED_SCHEMAS[capability]:
        raise RemoteObservationProjectionError("projected observation schema mismatch")
    if capability == "file.list":
        handles = observed["entry_handles"]
        if not isinstance(handles, list) or len(handles) > 500:
            raise RemoteObservationProjectionError("invalid projected file handles")
        for item in handles:
            if not isinstance(item, dict) or set(item) != {"handle", "kind", "extension"}:
                raise RemoteObservationProjectionError("invalid projected file handle")
            if (
                not isinstance(item["handle"], str)
                or TaskLocalObservationProjector._HANDLE.fullmatch(item["handle"]) is None
                or item["kind"] not in {"file", "directory"}
                or not isinstance(item["extension"], str)
                or re.fullmatch(r"(?:|\.[a-z0-9]{1,10})", item["extension"]) is None
            ):
                raise RemoteObservationProjectionError("invalid projected file handle")
        if type(observed["count"]) is not int or observed["count"] != len(handles):
            raise RemoteObservationProjectionError("invalid projected file count")
        if type(observed["truncated"]) is not bool or type(observed["root_index"]) is not int:
            raise RemoteObservationProjectionError("invalid projected file metadata")
    if capability in {"file.move", "file.delete.trash"} and observed["verified"] is not True:
        raise RemoteObservationProjectionError("invalid projected verification")
    for flag in ("launched", "opened", "matched", "low_disk"):
        if flag in observed and type(observed[flag]) is not bool:
            raise RemoteObservationProjectionError("invalid projected boolean")
    for count in ("mutation_count", "lookback_days", "match_count", "root_index"):
        if count in observed and type(observed[count]) is not int:
            raise RemoteObservationProjectionError("invalid projected integer")
    if "volume_percent" in observed:
        TaskLocalObservationProjector._percentage(cast(JsonValue, observed["volume_percent"]))
    if observed.get("mutation_count", 0) != 0:
        raise RemoteObservationProjectionError("invalid projected mutation count")
    if "root_index" in observed and cast(int, observed["root_index"]) < 0:
        raise RemoteObservationProjectionError("invalid projected root index")
    if "lookback_days" in observed and not 1 <= cast(int, observed["lookback_days"]) <= 90:
        raise RemoteObservationProjectionError("invalid projected lookback")
    if "match_count" in observed and not 0 <= cast(int, observed["match_count"]) <= 10:
        raise RemoteObservationProjectionError("invalid projected match count")
    if observed.get("free_percent_bucket", "GT_THRESHOLD") not in {
        "LE_THRESHOLD",
        "GT_THRESHOLD",
    }:
        raise RemoteObservationProjectionError("invalid projected storage bucket")
    if observed.get("suggestion_code", "NO_ACTION") not in {
        "LOW_DISK_REVIEW",
        "NO_ACTION",
    }:
        raise RemoteObservationProjectionError("invalid projected suggestion")
    if observed.get("scheme", "https") != "https":
        raise RemoteObservationProjectionError("invalid projected scheme")
    if observed.get("search_engine", "google") != "google":
        raise RemoteObservationProjectionError("invalid projected search engine")
    if observed.get("selection_mode", "recent") not in {"recent", "frequent"}:
        raise RemoteObservationProjectionError("invalid projected selection mode")
    for key in ("app_id", "page_id", "root_id"):
        if key in observed:
            TaskLocalObservationProjector._identifier(cast(JsonValue, observed[key]), key)
    if "host" in observed:
        TaskLocalObservationProjector._host(cast(JsonValue, observed["host"]))
    for key in ("system", "release", "version", "machine"):
        if key in observed:
            TaskLocalObservationProjector._bounded_string(
                cast(JsonValue, observed[key]), key, 256
            )


def _reject_sensitive_projected_text(value: object) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _reject_sensitive_projected_text(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _reject_sensitive_projected_text(nested)
        return
    if not isinstance(value, str):
        return
    if (
        re.search(r"(?i)[a-z]:[\\/]", value)
        or value.startswith(("\\\\", "//"))
        or "://" in value
        or "@" in value
        or "\\" in value
        or "/" in value
    ):
        raise RemoteObservationProjectionError("sensitive text in projected observation")
