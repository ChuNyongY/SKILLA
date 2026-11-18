from __future__ import annotations

import hashlib
from time import perf_counter_ns
from urllib.parse import urlencode

from .browser_navigation import BrowserNavigateExecutor, BrowserNavigationVerifier
from .cancellation import CancellationToken
from .models import Action, Postcondition, VerificationResult
from .runtime_models import ExecutionResult


class BrowserSearchExecutor:
    """Open one bounded user query in Google through a registered browser."""

    name = "native"

    def __init__(self, navigation: BrowserNavigateExecutor) -> None:
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
        browser_id, query = validated
        nested = _navigation_action(action, browser_id, query)
        result = self._navigation.execute(nested, cancellation)
        if not result.success:
            return result
        return result.model_copy(
            update={
                "observed": {
                    **result.observed,
                    "search_engine": "google",
                    "query_sha256": _query_hash(query),
                },
                "duration_ms": max(0, (perf_counter_ns() - started) // 1_000_000),
            }
        )

    @staticmethod
    def _validate(action: Action) -> tuple[str, str] | str:
        if action.capability_id != "browser.search.web":
            return "UNSUPPORTED_CAPABILITY"
        if set(action.arguments) != {"browser_id", "query"}:
            return "INVALID_ARGUMENTS"
        browser_id = action.arguments.get("browser_id")
        query = action.arguments.get("query")
        if (
            not isinstance(browser_id, str)
            or browser_id not in {"chrome", "edge"}
            or not isinstance(query, str)
        ):
            return "INVALID_ARGUMENTS"
        normalized = normalize_search_query(query)
        if normalized is None:
            return "INVALID_ARGUMENTS"
        if action.target_identity != f"browser-search:{browser_id}:www.google.com":
            return "TARGET_IDENTITY_MISMATCH"
        if len(action.expected_postconditions) != 1:
            return "INVALID_POSTCONDITION"
        postcondition = action.expected_postconditions[0]
        if postcondition.predicate != "browser.search.opened" or postcondition.arguments:
            return "INVALID_POSTCONDITION"
        return browser_id, normalized

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
            error_message="Registered browser search was not completed",
            retry_safe=retry_safe,
            duration_ms=max(0, (perf_counter_ns() - started) // 1_000_000),
        )


class BrowserSearchVerifier:
    def __init__(self, navigation: BrowserNavigationVerifier) -> None:
        self._navigation = navigation

    def verify(self, action: Action, result: ExecutionResult) -> VerificationResult:
        if result.action_id != action.action_id or result.executor != "native":
            return self._failure("BROWSER_SEARCH_BINDING_FAILED")
        if not result.success:
            return self._failure(result.error_code or "EXECUTION_FAILED")
        validated = BrowserSearchExecutor._validate(action)
        if isinstance(validated, str):
            return self._failure("BROWSER_SEARCH_CONTRACT_FAILED")
        browser_id, query = validated
        if (
            result.observed.get("search_engine") != "google"
            or result.observed.get("query_sha256") != _query_hash(query)
        ):
            return self._failure("BROWSER_SEARCH_QUERY_MISMATCH")
        nested = _navigation_action(action, browser_id, query)
        navigation_result = result.model_copy(
            update={
                "observed": {
                    key: value
                    for key, value in result.observed.items()
                    if key not in {"search_engine", "query_sha256"}
                }
            }
        )
        verified = self._navigation.verify(nested, navigation_result)
        if not verified.success:
            return self._failure(verified.reason)
        return VerificationResult(
            success=True,
            observed={
                "search_engine": "google",
                "query_sha256": _query_hash(query),
            },
            reason="BROWSER_SEARCH_OPENED_VERIFIED",
        )

    @staticmethod
    def _failure(reason: str) -> VerificationResult:
        return VerificationResult(success=False, reason=reason, recoverable=False)


def _navigation_action(action: Action, browser_id: str, query: str) -> Action:
    url = "https://www.google.com/search?" + urlencode({"q": query})
    return Action(
        action_id=action.action_id,
        capability_id="browser.navigate",
        arguments={"browser_id": browser_id, "url": url},
        purpose=action.purpose,
        target_identity=f"browser:{browser_id}:www.google.com",
        expected_postconditions=(Postcondition(predicate="browser.navigation.verified"),),
    )


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def normalize_search_query(query: str) -> str | None:
    """Return the one canonical query representation shared by policy and execution."""
    if "\0" in query or any(ord(character) < 0x20 for character in query):
        return None
    normalized = " ".join(query.split())
    return normalized if 1 <= len(normalized) <= 200 else None
