from __future__ import annotations

from skilla_core.models import Action, VerificationResult
from skilla_core.runtime_models import ExecutionResult
from skilla_core.user_visible_result import UserVisibleResultStore


def test_system_information_is_rendered_with_allowlisted_korean_labels() -> None:
    action = Action(capability_id="system.info.read", purpose="시스템 정보 확인")
    result = ExecutionResult(
        action_id=action.action_id,
        executor="native",
        success=True,
        observed={
            "system": "Windows",
            "release": "11",
            "version": "10.0.26100",
            "machine": "AMD64",
            "hostname": "MY-PC",
            "private_token": "must-not-appear",
        },
        duration_ms=1,
    )
    store = UserVisibleResultStore()

    store.observe(
        action,
        result,
        VerificationResult(success=True, reason="POSTCONDITIONS_VERIFIED"),
    )

    rendered = store.snapshot()
    assert rendered is not None
    serialized = rendered.model_dump_json()
    assert "운영체제: Windows" in serialized
    assert "컴퓨터 이름: MY-PC" in serialized
    assert "private_token" not in serialized
    assert "must-not-appear" not in serialized


def test_unrecognized_capability_does_not_expose_observed_values() -> None:
    action = Action(capability_id="browser.open", purpose="페이지 열기")
    store = UserVisibleResultStore()
    store.observe(
        action,
        ExecutionResult(
            action_id=action.action_id,
            executor="mock",
            success=True,
            observed={"url": "https://private.example/secret"},
            duration_ms=1,
        ),
        VerificationResult(success=True, reason="POSTCONDITIONS_VERIFIED"),
    )

    rendered = store.snapshot()
    assert rendered is not None
    assert "private.example" not in rendered.model_dump_json()


def test_mismatched_or_unverified_result_is_rejected() -> None:
    action = Action(capability_id="system.info.read", purpose="시스템 정보 확인")
    other = Action(capability_id="system.info.read", purpose="다른 시스템 정보 확인")
    store = UserVisibleResultStore()
    result = ExecutionResult(
        action_id=other.action_id,
        executor="native",
        success=True,
        observed={"system": "Windows"},
        duration_ms=1,
    )

    try:
        store.observe(
            action,
            result,
            VerificationResult(success=True, reason="POSTCONDITIONS_VERIFIED"),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("mismatched result was accepted")
    assert store.snapshot() is None
