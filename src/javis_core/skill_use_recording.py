from __future__ import annotations

import hashlib
import json
from typing import Protocol
from uuid import UUID

from pydantic import JsonValue

from .models import ActionStatus, Plan
from .registry import CapabilityRegistry
from .runtime_models import TaskOutcome
from .skill_runtime import LocalSkillCatalog, SkillOutcome, SkillPlanSelection


class SelectedSkillSource(Protocol):
    def claim_selected_skill(self, task_id: UUID) -> SkillPlanSelection | None: ...


class CatalogSkillUseRecorder:
    """Bind one completed top-level plan to its exact selected skill version."""

    def __init__(
        self,
        catalog: LocalSkillCatalog,
        selections: SelectedSkillSource,
        *,
        model_configuration_sha256: str,
        tool_surface_sha256: str,
    ) -> None:
        if not _is_sha256(model_configuration_sha256) or not _is_sha256(
            tool_surface_sha256
        ):
            raise ValueError("skill use environment hashes must be lowercase SHA-256")
        self._catalog = catalog
        self._selections = selections
        self._model_configuration_sha256 = model_configuration_sha256
        self._tool_surface_sha256 = tool_surface_sha256

    def observe(self, plan: Plan, outcome: TaskOutcome, *, elapsed_ms: int) -> bool:
        if outcome.task_id != plan.task_id:
            raise ValueError("skill use outcome did not match the selected plan")
        selection = self._selections.claim_selected_skill(plan.task_id)
        if selection is None:
            return False
        if outcome.status is ActionStatus.SUCCEEDED:
            skill_outcome = SkillOutcome.SUCCEEDED
        elif outcome.status is ActionStatus.FAILED:
            skill_outcome = SkillOutcome.FAILED
        else:
            skill_outcome = SkillOutcome.ABORTED
        self._catalog.record_use(
            selection.skill,
            skill_outcome,
            outcome.reason.upper()[:80],
            elapsed_ms=min(max(elapsed_ms, 0), 86_400_000),
            llm_calls=selection.usage.llm_calls,
            input_tokens=selection.usage.input_tokens,
            output_tokens=selection.usage.output_tokens,
            model_configuration_sha256=self._model_configuration_sha256,
            tool_surface_sha256=self._tool_surface_sha256,
            planner_usage_complete=selection.usage.complete,
            planner_responses_without_usage=(
                selection.usage.responses_without_usage
            ),
        )
        return True


def product_model_configuration_sha256(model_id: str) -> str:
    if not model_id or len(model_id) > 128 or "\0" in model_id:
        raise ValueError("invalid model identifier")
    document: dict[str, JsonValue] = {
        "schema_version": "1.0",
        "provider": "nvidia-nim",
        "model_id": model_id,
        "nim_chat": {
            "temperature": 0.1,
            "max_tokens": 3_000,
            "reasoning_effort": "low",
            "clear_thinking": True,
        },
        "typed_planner": {
            "max_steps": 20,
            "max_plan_characters": 100_000,
            "max_goal_characters": 4_000,
            "max_untrusted_context_characters": 20_000,
            "max_user_prompt_bytes": 100_000,
            "max_repair_attempts": 1,
        },
    }
    return _canonical_sha256(document)


def product_tool_surface_sha256(registry: CapabilityRegistry) -> str:
    capabilities = [
        capability.model_dump(mode="json") for capability in registry.list()
    ]
    capabilities.sort(key=lambda item: str(item["capability_id"]))
    return _canonical_sha256(
        {
            "schema_version": "1.0",
            "capabilities": capabilities,
        }
    )


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
