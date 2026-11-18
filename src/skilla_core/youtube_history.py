from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Literal, Protocol, cast
from urllib.parse import parse_qsl, urlencode, urlsplit

from .browser_navigation import BrowserNavigateExecutor, BrowserNavigationVerifier
from .cancellation import CancellationToken
from .models import Action, Postcondition, VerificationResult
from .runtime_models import ExecutionResult

YoutubeSelectionMode = Literal["recent", "frequent"]
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHROME_EPOCH_OFFSET_SECONDS = 11_644_473_600
_YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
)


class YoutubeHistoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class YoutubeHistoryCandidate:
    video_id: str
    visits: int
    last_visit_time: int


class YoutubeHistoryBackend(Protocol):
    def select(
        self,
        *,
        mode: YoutubeSelectionMode,
        lookback_days: int,
    ) -> YoutubeHistoryCandidate | None: ...


class ChromiumYoutubeHistory:
    """Read only bounded YouTube visits from one explicitly configured Chrome profile."""

    def __init__(
        self,
        history_path: Path,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_rows: int = 5_000,
    ) -> None:
        if not history_path.is_absolute() or not 1 <= max_rows <= 10_000:
            raise ValueError("invalid Chrome history configuration")
        self._path = history_path
        self._now = now
        self._max_rows = max_rows

    def select(
        self,
        *,
        mode: YoutubeSelectionMode,
        lookback_days: int,
    ) -> YoutubeHistoryCandidate | None:
        if mode not in {"recent", "frequent"} or not 1 <= lookback_days <= 90:
            raise ValueError("invalid YouTube history selection")
        path = self._trusted_history_path()
        cutoff = self._chrome_timestamp(self._now()) - lookback_days * 86_400_000_000
        rows = self._snapshot_rows(path, cutoff)

        aggregated: dict[str, tuple[int, int]] = {}
        for raw_url, raw_visit_time in rows:
            if not isinstance(raw_url, str) or type(raw_visit_time) is not int:
                continue
            video_id = _youtube_video_id(raw_url)
            if video_id is None:
                continue
            visits, latest = aggregated.get(video_id, (0, 0))
            aggregated[video_id] = (visits + 1, max(latest, raw_visit_time))
        if not aggregated:
            return None
        if mode == "recent":
            video_id, (visits, latest) = max(
                aggregated.items(),
                key=lambda item: (item[1][1], item[1][0], item[0]),
            )
        else:
            video_id, (visits, latest) = max(
                aggregated.items(),
                key=lambda item: (item[1][0], item[1][1], item[0]),
            )
        return YoutubeHistoryCandidate(video_id, visits, latest)

    def _snapshot_rows(self, path: Path, cutoff: int) -> list[tuple[object, object]]:
        last_error: Exception | None = None
        for _attempt in range(3):
            try:
                before = self._source_state(path)
                with tempfile.TemporaryDirectory(prefix="skilla-history-") as temporary:
                    snapshot = Path(temporary) / "History"
                    shutil.copyfile(path, snapshot)
                    wal = path.with_name("History-wal")
                    if wal.is_file() and not wal.is_symlink():
                        shutil.copyfile(wal, snapshot.with_name("History-wal"))
                    after = self._source_state(path)
                    if before != after:
                        continue
                    database = sqlite3.connect(snapshot, timeout=1.0)
                    try:
                        database.execute("PRAGMA query_only=ON")
                        checked = database.execute("PRAGMA quick_check").fetchone()
                        if checked != ("ok",):
                            raise sqlite3.DatabaseError("history snapshot check failed")
                        return database.execute(
                            "SELECT u.url, v.visit_time "
                            "FROM visits AS v JOIN urls AS u ON u.id = v.url "
                            "WHERE v.visit_time >= ? AND u.url LIKE ? "
                            "ORDER BY v.visit_time DESC LIMIT ?",
                            (cutoff, "%youtube.com/%", self._max_rows),
                        ).fetchall()
                    finally:
                        database.close()
            except (OSError, sqlite3.Error) as error:
                last_error = error
        raise YoutubeHistoryError("Chrome history could not be read") from last_error

    @staticmethod
    def _source_state(path: Path) -> tuple[tuple[int, int], tuple[int, int] | None]:
        def state(item: Path) -> tuple[int, int]:
            metadata = item.stat()
            if metadata.st_size > 512 * 1024 * 1024:
                raise YoutubeHistoryError("Chrome history exceeded size limit")
            return metadata.st_size, metadata.st_mtime_ns

        main = state(path)
        wal = path.with_name("History-wal")
        if wal.is_symlink():
            raise YoutubeHistoryError("Chrome history WAL path is invalid")
        return main, state(wal) if wal.is_file() else None

    def _trusted_history_path(self) -> Path:
        path = self._path
        if path.is_symlink() or not path.is_file():
            raise YoutubeHistoryError("Chrome history is unavailable")
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise YoutubeHistoryError("Chrome history is unavailable") from error
        if resolved.name != "History":
            raise YoutubeHistoryError("Chrome history path is invalid")
        return resolved

    @staticmethod
    def _chrome_timestamp(value: datetime) -> int:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("history clock must be timezone-aware")
        return int((value.timestamp() + _CHROME_EPOCH_OFFSET_SECONDS) * 1_000_000)


class YoutubeRecentMediaExecutor:
    """Select locally, then request one allowlisted Chrome navigation without exposing history."""

    name = "native"

    def __init__(
        self,
        history: YoutubeHistoryBackend,
        navigation: BrowserNavigateExecutor,
    ) -> None:
        self._history = history
        self._navigation = navigation

    def execute(
        self,
        action: Action,
        cancellation: CancellationToken | None = None,
    ) -> ExecutionResult:
        started = perf_counter_ns()
        validated = self._validate(action)
        if isinstance(validated, str):
            return self._failure(action, started, validated, retry_safe=True)
        mode, lookback_days = validated
        if cancellation is not None and cancellation.is_cancelled:
            return self._failure(action, started, "STOP_REQUESTED", retry_safe=True)
        try:
            candidate = self._history.select(mode=mode, lookback_days=lookback_days)
        except YoutubeHistoryError:
            return self._failure(action, started, "BROWSER_HISTORY_UNAVAILABLE", retry_safe=True)
        if candidate is None:
            return self._failure(action, started, "YOUTUBE_HISTORY_EMPTY", retry_safe=True)
        navigation_action = _navigation_action(action, candidate.video_id)
        result = self._navigation.execute(navigation_action, cancellation)
        if not result.success:
            return result
        return result.model_copy(
            update={
                "observed": {
                    **result.observed,
                    "history_source": "chrome-local",
                    "selection_mode": mode,
                    "lookback_days": lookback_days,
                    "selection_sha256": _selection_hash(candidate.video_id),
                },
                "duration_ms": max(0, (perf_counter_ns() - started) // 1_000_000),
            }
        )

    @staticmethod
    def _validate(action: Action) -> tuple[YoutubeSelectionMode, int] | str:
        if action.capability_id != "media.youtube.play.recent":
            return "UNSUPPORTED_CAPABILITY"
        if set(action.arguments) != {"mode", "lookback_days"}:
            return "INVALID_ARGUMENTS"
        mode = action.arguments.get("mode")
        lookback_days = action.arguments.get("lookback_days")
        if mode not in {"recent", "frequent"} or type(lookback_days) is not int:
            return "INVALID_ARGUMENTS"
        if not 1 <= lookback_days <= 90:
            return "INVALID_ARGUMENTS"
        if action.target_identity != "browser-history:chrome:youtube":
            return "TARGET_IDENTITY_MISMATCH"
        if len(action.expected_postconditions) != 1:
            return "INVALID_POSTCONDITION"
        postcondition = action.expected_postconditions[0]
        if postcondition.predicate != "media.youtube.opened" or postcondition.arguments:
            return "INVALID_POSTCONDITION"
        return cast(YoutubeSelectionMode, mode), lookback_days

    @staticmethod
    def _failure(
        action: Action,
        started: int,
        error_code: str,
        *,
        retry_safe: bool,
    ) -> ExecutionResult:
        return ExecutionResult(
            action_id=action.action_id,
            executor="native",
            success=False,
            error_code=error_code,
            error_message="Local YouTube history media selection was not completed",
            retry_safe=retry_safe,
            duration_ms=max(0, (perf_counter_ns() - started) // 1_000_000),
        )


class YoutubeRecentMediaVerifier:
    def __init__(
        self,
        history: YoutubeHistoryBackend,
        navigation: BrowserNavigationVerifier,
    ) -> None:
        self._history = history
        self._navigation = navigation

    def verify(self, action: Action, result: ExecutionResult) -> VerificationResult:
        if result.action_id != action.action_id or result.executor != "native":
            return self._failure("YOUTUBE_MEDIA_BINDING_FAILED")
        if not result.success:
            return self._failure(result.error_code or "EXECUTION_FAILED")
        validated = YoutubeRecentMediaExecutor._validate(action)
        if isinstance(validated, str):
            return self._failure("YOUTUBE_MEDIA_CONTRACT_FAILED")
        mode, lookback_days = validated
        try:
            candidate = self._history.select(mode=mode, lookback_days=lookback_days)
        except YoutubeHistoryError:
            return self._failure("BROWSER_HISTORY_UNAVAILABLE")
        if candidate is None:
            return self._failure("YOUTUBE_HISTORY_EMPTY")
        if (
            result.observed.get("history_source") != "chrome-local"
            or result.observed.get("selection_mode") != mode
            or result.observed.get("lookback_days") != lookback_days
            or result.observed.get("selection_sha256")
            != _selection_hash(candidate.video_id)
        ):
            return self._failure("YOUTUBE_SELECTION_CHANGED")
        navigation_action = _navigation_action(action, candidate.video_id)
        navigation_result = result.model_copy(
            update={
                "observed": {
                    key: value
                    for key, value in result.observed.items()
                    if key
                    not in {
                        "history_source",
                        "selection_mode",
                        "lookback_days",
                        "selection_sha256",
                    }
                }
            }
        )
        verified = self._navigation.verify(navigation_action, navigation_result)
        if not verified.success:
            return self._failure(verified.reason)
        return VerificationResult(
            success=True,
            observed={
                "history_source": "chrome-local",
                "selection_mode": mode,
                "lookback_days": lookback_days,
                "selection_sha256": _selection_hash(candidate.video_id),
            },
            reason="YOUTUBE_MEDIA_OPENED_VERIFIED",
        )

    @staticmethod
    def _failure(reason: str) -> VerificationResult:
        return VerificationResult(success=False, reason=reason, recoverable=False)


def chrome_history_path(profile: str, local_app_data: Path | None = None) -> Path:
    if profile != "Default" and re.fullmatch(r"Profile [1-9][0-9]{0,2}", profile) is None:
        raise ValueError("unsupported Chrome profile")
    root = local_app_data
    if root is None:
        raw = os.environ.get("LOCALAPPDATA")
        if not raw:
            raise ValueError("LOCALAPPDATA is unavailable")
        root = Path(raw)
    if not root.is_absolute():
        raise ValueError("LOCALAPPDATA must be absolute")
    return root / "Google" / "Chrome" / "User Data" / profile / "History"


def _youtube_video_id(raw_url: str) -> str | None:
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _YOUTUBE_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
        or parsed.path != "/watch"
    ):
        return None
    values = [value for key, value in parse_qsl(parsed.query) if key == "v"]
    if len(values) != 1 or _VIDEO_ID.fullmatch(values[0]) is None:
        return None
    return values[0]


def _navigation_action(action: Action, video_id: str) -> Action:
    url = "https://www.youtube.com/watch?" + urlencode(
        {"v": video_id, "autoplay": "1"}
    )
    return Action(
        action_id=action.action_id,
        capability_id="browser.navigate",
        arguments={"browser_id": "chrome", "url": url},
        purpose=action.purpose,
        target_identity="browser:chrome:www.youtube.com",
        expected_postconditions=(
            Postcondition(predicate="browser.navigation.verified"),
        ),
    )


def _selection_hash(video_id: str) -> str:
    return hashlib.sha256(f"youtube:{video_id}".encode("ascii")).hexdigest()
