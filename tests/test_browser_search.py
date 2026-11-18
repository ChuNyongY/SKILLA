from __future__ import annotations

import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest

from skilla_core.browser_search import BrowserSearchExecutor, BrowserSearchVerifier
from skilla_core.models import Action, Postcondition, VerificationResult
from skilla_core.runtime_models import ExecutionResult


class Navigation:
    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.actions: list[Action] = []

    def execute(self, action: Action, cancellation=None) -> ExecutionResult:  # type: ignore[no-untyped-def]
        del cancellation
        self.actions.append(action)
        return ExecutionResult(
            action_id=action.action_id,
            executor="native",
            success=self.success,
            error_code=None if self.success else "NAVIGATION_FAILED",
            error_message=None if self.success else "Navigation failed",
            retry_safe=False,
            duration_ms=1,
            observed={
                "host": "www.google.com",
                "scheme": "https",
                "pid": 101,
                "hwnd": 202,
            },
        )


class NavigationVerifier:
    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.actions: list[Action] = []
        self.results: list[ExecutionResult] = []

    def verify(self, action: Action, result: ExecutionResult) -> VerificationResult:
        self.actions.append(action)
        self.results.append(result)
        return VerificationResult(
            success=self.success,
            reason="BROWSER_NAVIGATION_VERIFIED" if self.success else "WINDOW_MISSING",
            recoverable=False,
        )


def action(query: str = "스킬라 확장 기능") -> Action:
    return Action(
        capability_id="browser.search.web",
        arguments={"browser_id": "chrome", "query": query},
        purpose="search the web",
        target_identity="browser-search:chrome:www.google.com",
        expected_postconditions=(Postcondition(predicate="browser.search.opened"),),
    )


def test_korean_query_is_encoded_and_only_its_hash_is_exposed() -> None:
    navigation = Navigation()
    request = action()

    result = BrowserSearchExecutor(navigation).execute(request)  # type: ignore[arg-type]

    assert result.success
    nested = navigation.actions[0]
    parsed = urlsplit(nested.arguments["url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.google.com"
    assert parse_qs(parsed.query) == {"q": ["스킬라 확장 기능"]}
    assert nested.target_identity == "browser:chrome:www.google.com"
    assert result.observed["query_sha256"] == hashlib.sha256(
        "스킬라 확장 기능".encode()
    ).hexdigest()
    assert "스킬라 확장 기능" not in result.model_dump_json()


@pytest.mark.parametrize("query", ["", "  ", "줄바꿈\n검색", "x" * 201, "검색\0어"])
def test_invalid_or_oversized_queries_fail_before_navigation(query: str) -> None:
    navigation = Navigation()

    result = BrowserSearchExecutor(navigation).execute(action(query))  # type: ignore[arg-type]

    assert not result.success
    assert result.error_code == "INVALID_ARGUMENTS"
    assert navigation.actions == []


def test_exact_target_and_postcondition_are_required() -> None:
    navigation = Navigation()
    executor = BrowserSearchExecutor(navigation)  # type: ignore[arg-type]
    wrong_target = action().model_copy(
        update={"target_identity": "browser-search:edge:www.google.com"}
    )
    wrong_postcondition = action().model_copy(
        update={"expected_postconditions": (Postcondition(predicate="process.exists"),)}
    )

    assert executor.execute(wrong_target).error_code == "TARGET_IDENTITY_MISMATCH"
    assert executor.execute(wrong_postcondition).error_code == "INVALID_POSTCONDITION"
    assert navigation.actions == []


def test_verifier_rebinds_query_and_uses_navigation_verifier() -> None:
    navigation = Navigation()
    request = action("  스킬라   확장  ")
    result = BrowserSearchExecutor(navigation).execute(request)  # type: ignore[arg-type]
    verifier = NavigationVerifier()

    verified = BrowserSearchVerifier(verifier).verify(request, result)  # type: ignore[arg-type]

    assert verified.success
    assert verifier.actions[0].capability_id == "browser.navigate"
    assert "query_sha256" not in verifier.results[0].observed
    assert "search_engine" not in verifier.results[0].observed
    assert "스킬라 확장" not in verified.model_dump_json()


def test_forged_query_binding_and_failed_navigation_are_rejected() -> None:
    navigation = Navigation()
    request = action()
    result = BrowserSearchExecutor(navigation).execute(request)  # type: ignore[arg-type]
    forged = result.model_copy(
        update={"observed": {**result.observed, "query_sha256": "0" * 64}}
    )
    verifier = NavigationVerifier()

    assert BrowserSearchVerifier(verifier).verify(request, forged).reason == (
        "BROWSER_SEARCH_QUERY_MISMATCH"
    )
    assert not BrowserSearchExecutor(Navigation(success=False)).execute(request).success  # type: ignore[arg-type]
