from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from skilla_core.models import Action, Postcondition, VerificationResult
from skilla_core.runtime_models import ExecutionResult
from skilla_core.youtube_history import (
    ChromiumYoutubeHistory,
    YoutubeHistoryCandidate,
    YoutubeRecentMediaExecutor,
    YoutubeRecentMediaVerifier,
)

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
CHROME_EPOCH = 11_644_473_600


def chrome_time(*, days_ago: int, sequence: int = 0) -> int:
    return int((NOW.timestamp() + CHROME_EPOCH - days_ago * 86_400) * 1_000_000) + sequence


def history_database(path: Path, visits: list[tuple[str, int]]) -> None:
    database = sqlite3.connect(path)
    with database:
        database.execute(
            "CREATE TABLE urls(id INTEGER PRIMARY KEY, url TEXT NOT NULL)"
        )
        database.execute(
            "CREATE TABLE visits(id INTEGER PRIMARY KEY, url INTEGER NOT NULL, "
            "visit_time INTEGER NOT NULL)"
        )
        for index, (url, visit_time) in enumerate(visits, start=1):
            database.execute("INSERT INTO urls(id, url) VALUES(?, ?)", (index, url))
            database.execute(
                "INSERT INTO visits(id, url, visit_time) VALUES(?, ?, ?)",
                (index, index, visit_time),
            )
    database.close()


def action(mode: str = "frequent", lookback_days: int = 30) -> Action:
    return Action(
        capability_id="media.youtube.play.recent",
        arguments={"mode": mode, "lookback_days": lookback_days},
        purpose="평소에 듣던 노래 열기",
        target_identity="browser-history:chrome:youtube",
        expected_postconditions=(Postcondition(predicate="media.youtube.opened"),),
    )


class FixedHistory:
    def __init__(self, video_id: str | None = "abcdefghijk") -> None:
        self.video_id = video_id
        self.calls = 0

    def select(self, *, mode: str, lookback_days: int):  # type: ignore[no-untyped-def]
        assert mode in {"recent", "frequent"}
        assert lookback_days == 30
        self.calls += 1
        if self.video_id is None:
            return None
        return YoutubeHistoryCandidate(self.video_id, 4, chrome_time(days_ago=1))


class Navigation:
    def __init__(self) -> None:
        self.actions: list[Action] = []

    def execute(self, request: Action, _cancellation=None) -> ExecutionResult:  # type: ignore[no-untyped-def]
        self.actions.append(request)
        return ExecutionResult(
            action_id=request.action_id,
            executor="native",
            success=True,
            observed={
                "app_id": "chrome",
                "host": "www.youtube.com",
                "hwnd": 2,
                "pid": 1,
                "process_creation_time_100ns": 3,
                "scheme": "https",
                "url_sha256": "a" * 64,
            },
            duration_ms=1,
        )


class NavigationVerifier:
    def __init__(self) -> None:
        self.actions: list[Action] = []

    def verify(self, request: Action, result: ExecutionResult) -> VerificationResult:
        self.actions.append(request)
        assert result.observed["host"] == "www.youtube.com"
        return VerificationResult(success=True, reason="BROWSER_NAVIGATION_VERIFIED")


def test_chromium_history_selects_recent_and_frequent_without_mutation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "History"
    history_database(
        path,
        [
            ("https://www.youtube.com/watch?v=aaaaaaaaaaa", chrome_time(days_ago=2)),
            ("https://www.youtube.com/watch?v=aaaaaaaaaaa", chrome_time(days_ago=3)),
            ("https://music.youtube.com/watch?v=aaaaaaaaaaa", chrome_time(days_ago=4)),
            ("https://www.youtube.com/watch?v=bbbbbbbbbbb", chrome_time(days_ago=1)),
            ("https://evil.example/watch?v=ccccccccccc", chrome_time(days_ago=0)),
            ("https://www.youtube.com/shorts/ddddddddddd", chrome_time(days_ago=0)),
        ],
    )
    backend = ChromiumYoutubeHistory(path, now=lambda: NOW)

    recent = backend.select(mode="recent", lookback_days=30)
    frequent = backend.select(mode="frequent", lookback_days=30)

    assert recent is not None and recent.video_id == "bbbbbbbbbbb"
    assert frequent is not None and frequent.video_id == "aaaaaaaaaaa"
    with sqlite3.connect(path) as database:
        assert database.execute("SELECT COUNT(*) FROM visits").fetchone() == (6,)


def test_chromium_history_rejects_ambiguous_video_parameters(tmp_path: Path) -> None:
    path = tmp_path / "History"
    history_database(
        path,
        [
            (
                "https://www.youtube.com/watch?v=aaaaaaaaaaa&v=bbbbbbbbbbb",
                chrome_time(days_ago=1),
            ),
            ("https://www.youtube.com/watch?v=too-short", chrome_time(days_ago=1)),
        ],
    )

    assert ChromiumYoutubeHistory(path, now=lambda: NOW).select(
        mode="recent", lookback_days=30
    ) is None


def test_chromium_history_reads_committed_wal_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "History"
    database = sqlite3.connect(path)
    database.execute("PRAGMA journal_mode=WAL")
    database.execute("PRAGMA wal_autocheckpoint=0")
    database.execute("CREATE TABLE urls(id INTEGER PRIMARY KEY, url TEXT NOT NULL)")
    database.execute(
        "CREATE TABLE visits(id INTEGER PRIMARY KEY, url INTEGER NOT NULL, "
        "visit_time INTEGER NOT NULL)"
    )
    database.execute(
        "INSERT INTO urls(id, url) VALUES(1, ?)",
        ("https://www.youtube.com/watch?v=walwalwal01",),
    )
    database.execute(
        "INSERT INTO visits(id, url, visit_time) VALUES(1, 1, ?)",
        (chrome_time(days_ago=1),),
    )
    database.commit()
    try:
        selected = ChromiumYoutubeHistory(path, now=lambda: NOW).select(
            mode="recent", lookback_days=30
        )
    finally:
        database.close()

    assert selected is not None
    assert selected.video_id == "walwalwal01"


def test_media_executor_opens_only_canonical_selected_video_without_exposing_url() -> None:
    history = FixedHistory()
    navigation = Navigation()
    executor = YoutubeRecentMediaExecutor(history, navigation)  # type: ignore[arg-type]

    result = executor.execute(action())

    assert result.success
    assert history.calls == 1
    request = navigation.actions[0]
    assert request.arguments["url"] == (
        "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1"
    )
    assert request.target_identity == "browser:chrome:www.youtube.com"
    serialized = result.model_dump_json()
    assert "abcdefghijk" not in serialized
    assert "youtube.com/watch" not in serialized


def test_media_verifier_reselects_history_and_checks_navigation() -> None:
    history = FixedHistory()
    navigation = Navigation()
    executor = YoutubeRecentMediaExecutor(history, navigation)  # type: ignore[arg-type]
    request = action()
    result = executor.execute(request)
    navigation_verifier = NavigationVerifier()
    verifier = YoutubeRecentMediaVerifier(
        history,
        navigation_verifier,  # type: ignore[arg-type]
    )

    verified = verifier.verify(request, result)

    assert verified.success
    assert verified.reason == "YOUTUBE_MEDIA_OPENED_VERIFIED"
    assert history.calls == 2
    assert navigation_verifier.actions[0].arguments["url"] == (
        "https://www.youtube.com/watch?v=abcdefghijk&autoplay=1"
    )


def test_media_executor_fails_closed_when_history_has_no_candidate() -> None:
    result = YoutubeRecentMediaExecutor(
        FixedHistory(None),
        Navigation(),  # type: ignore[arg-type]
    ).execute(action())

    assert not result.success
    assert result.error_code == "YOUTUBE_HISTORY_EMPTY"
    assert result.retry_safe
