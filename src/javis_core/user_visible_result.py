from __future__ import annotations

from threading import Lock

from pydantic import Field

from .models import Action, FrozenModel, VerificationResult
from .runtime_models import ExecutionResult


class UserVisibleResultSnapshot(FrozenModel):
    capability_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    lines: tuple[str, ...] = Field(min_length=1, max_length=8)


class UserVisibleResultStore:
    """Retain only an allowlisted, verified result summary for the local UI."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot: UserVisibleResultSnapshot | None = None

    def clear(self) -> None:
        with self._lock:
            self._snapshot = None

    def snapshot(self) -> UserVisibleResultSnapshot | None:
        with self._lock:
            return (
                None if self._snapshot is None else self._snapshot.model_copy(deep=True)
            )

    def observe(
        self,
        action: Action,
        execution: ExecutionResult,
        verification: VerificationResult,
    ) -> None:
        if execution.action_id != action.action_id or not verification.success:
            raise ValueError("only matching verified results may be displayed")
        snapshot = _summarize(action.capability_id, execution)
        with self._lock:
            self._snapshot = snapshot


class ChainedVerifiedResultObserver:
    """Deliver one verified result to multiple fail-closed observers."""

    def __init__(self, *observers: object) -> None:
        self._observers = observers

    def observe(
        self,
        action: Action,
        execution: ExecutionResult,
        verification: VerificationResult,
    ) -> None:
        for observer in self._observers:
            callback = getattr(observer, "observe", None)
            if not callable(callback):
                raise TypeError("verified result observer is invalid")
            callback(action, execution, verification)


def _summarize(
    capability_id: str,
    execution: ExecutionResult,
) -> UserVisibleResultSnapshot:
    if capability_id == "system.info.read":
        labels = (
            ("system", "운영체제"),
            ("release", "운영체제 릴리스"),
            ("version", "운영체제 버전"),
            ("machine", "시스템 종류"),
            ("hostname", "컴퓨터 이름"),
        )
        lines = tuple(
            f"{label}: {value}"
            for key, label in labels
            if (value := _safe_scalar(execution.observed.get(key))) is not None
        )
        return UserVisibleResultSnapshot(
            capability_id=capability_id,
            title="확인된 컴퓨터 시스템 정보",
            lines=lines or ("시스템 정보를 확인했지만 표시할 항목이 없습니다.",),
        )
    if capability_id == "file.list":
        count = execution.observed.get("count")
        truncated = execution.observed.get("truncated") is True
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            suffix = "(표시 한도까지 확인)" if truncated else ""
            return UserVisibleResultSnapshot(
                capability_id=capability_id,
                title="폴더 확인 결과",
                lines=(f"파일과 폴더 {count}개를 확인했습니다. {suffix}".strip(),),
            )
    return UserVisibleResultSnapshot(
        capability_id=capability_id,
        title="검증된 작업 결과",
        lines=("요청한 작업을 마쳤고 결과 검증도 통과했습니다.",),
    )


def _safe_scalar(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized or any(ord(character) < 32 for character in normalized):
        return None
    return normalized[:160]
