import json
from pathlib import Path

import pytest

from javis_core.registry import default_registry
from javis_core.skill_authoring import (
    SkillAuthoringError,
    SkillDraftAuthor,
    SkillExecutionTrace,
    SkillTraceStep,
)
from javis_core.skill_runtime import LocalSkillCatalog, SkillOutcome, SkillProposal, SkillStatus


class Transport:
    def __init__(self, response: str) -> None:
        self.response = response
        self.system_prompt = ""
        self.user_prompt = ""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


class SequenceTransport:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def proposal(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "key": "weekly-file-sort",
        "title": "주간 파일 정리",
        "description": "새 파일을 분류해 해당 폴더로 옮기고 결과를 확인한다.",
        "triggers": ["이번 주 자료 정리"],
        "procedure": ["대상 파일을 확인한다.", "분류한 뒤 옮긴다.", "결과를 확인한다."],
        "dynamic_inputs": ["이번 실행의 파일 목록", "대상 폴더"],
        "decision_rules": ["파일명과 확인 가능한 내용으로 분류한다."],
        "verification_rules": ["각 파일이 목표 폴더에 있는지 확인한다."],
        "allowed_capabilities": ["file.move"],
    }
    value.update(updates)
    return value


def trace(
    *,
    outcome: SkillOutcome = SkillOutcome.SUCCEEDED,
    verified: bool = True,
) -> SkillExecutionTrace:
    return SkillExecutionTrace(
        goal_summary="매주 내려받은 과제 자료를 과목 폴더로 분류",
        outcome=outcome,
        steps=(
            SkillTraceStep(
                sequence=1,
                capability_id="file.move",
                outcome=outcome,
                detail_code="FILE_MOVED" if outcome is SkillOutcome.SUCCEEDED else "TARGET_MISSING",
                independently_verified=verified,
            ),
        ),
        dynamic_input_labels=("이번 주 파일 목록",),
        decision_notes=("파일명과 확인 가능한 내용으로 과목을 판정",),
        verification_notes=("이동 뒤 대상 위치를 재확인",),
    )


def catalog(tmp_path: Path) -> LocalSkillCatalog:
    return LocalSkillCatalog((tmp_path / "skills.sqlite3").resolve(), default_registry())


def author(tmp_path: Path, value: dict[str, object]) -> tuple[SkillDraftAuthor, Transport]:
    transport = Transport(json.dumps(value, ensure_ascii=False))
    return SkillDraftAuthor(transport, catalog(tmp_path)), transport


def test_verified_success_trace_creates_only_a_draft(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    transport = Transport(json.dumps(proposal(), ensure_ascii=False))
    writer = SkillDraftAuthor(transport, store)
    artifact = writer.draft_initial(trace())
    assert artifact.draft.status is SkillStatus.DRAFT
    assert artifact.reason_code == "VERIFIED_SUCCESS_TRACE"
    assert len(artifact.source_trace_sha256) == 64
    assert "untrusted data" in transport.system_prompt
    assert artifact.draft.key not in {item.key for item in store.search("과제")}


@pytest.mark.parametrize(
    ("outcome", "verified"),
    [(SkillOutcome.FAILED, True), (SkillOutcome.SUCCEEDED, False)],
)
def test_initial_draft_rejects_untrustworthy_evidence(
    tmp_path: Path,
    outcome: SkillOutcome,
    verified: bool,
) -> None:
    writer, _ = author(tmp_path, proposal())
    with pytest.raises(SkillAuthoringError):
        writer.draft_initial(trace(outcome=outcome, verified=verified))


def test_generated_skill_cannot_invent_a_capability(tmp_path: Path) -> None:
    writer, _ = author(tmp_path, proposal(allowed_capabilities=["file.delete.trash"]))
    with pytest.raises(SkillAuthoringError, match="absent from the evidence"):
        writer.draft_initial(trace())


def test_invalid_envelope_gets_one_strict_format_repair(tmp_path: Path) -> None:
    raw = json.dumps(proposal(), ensure_ascii=False)
    transport = SequenceTransport([f"```json\n{raw}\n```", raw])
    writer = SkillDraftAuthor(transport, catalog(tmp_path))

    artifact = writer.draft_initial(trace())

    assert artifact.draft.status is SkillStatus.DRAFT
    assert len(transport.calls) == 2
    repair = json.loads(transport.calls[1][1])
    assert repair["task"].startswith("FORMAT_REPAIR_ONLY")
    assert repair["invalid_output_data_only"].startswith("```json")


def test_format_repair_can_be_disabled(tmp_path: Path) -> None:
    raw = json.dumps(proposal(), ensure_ascii=False)
    transport = SequenceTransport([f"```json\n{raw}\n```"])
    writer = SkillDraftAuthor(transport, catalog(tmp_path), max_repair_attempts=0)

    with pytest.raises(SkillAuthoringError):
        writer.draft_initial(trace())

    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "response",
    ["```json\n{}\n```", '{"key":"a","key":"b"}', '{"key":NaN}'],
)
def test_authoring_parser_rejects_noncanonical_json(tmp_path: Path, response: str) -> None:
    transport = Transport(response)
    writer = SkillDraftAuthor(transport, catalog(tmp_path))
    with pytest.raises(SkillAuthoringError):
        writer.draft_initial(trace())


def test_revision_requires_policy_signal_and_never_expands_authority(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    current = store.approve(store.propose(SkillProposal.model_validate(proposal())).skill_id)
    transport = Transport(json.dumps(proposal(), ensure_ascii=False))
    writer = SkillDraftAuthor(transport, store)
    with pytest.raises(SkillAuthoringError, match="policy does not permit"):
        writer.draft_revision(current.skill_id, trace(outcome=SkillOutcome.FAILED))

    for _ in range(2):
        store.record_use(current, SkillOutcome.FAILED, "TARGET_MISSING")
    store.record_use(current, SkillOutcome.SUCCEEDED, "FILE_MOVED")
    transport.response = json.dumps(
        proposal(allowed_capabilities=["file.move", "file.delete.trash"]),
        ensure_ascii=False,
    )
    with pytest.raises(SkillAuthoringError, match="expand capability"):
        writer.draft_revision(current.skill_id, trace(outcome=SkillOutcome.FAILED))
    assert store.require(current.skill_id).status is SkillStatus.VERIFIED


def test_permitted_revision_stays_draft_until_human_approval(tmp_path: Path) -> None:
    store = catalog(tmp_path)
    current = store.approve(store.propose(SkillProposal.model_validate(proposal())).skill_id)
    for _ in range(2):
        store.record_use(current, SkillOutcome.FAILED, "TARGET_MISSING")
    store.record_use(current, SkillOutcome.SUCCEEDED, "FILE_MOVED")
    writer = SkillDraftAuthor(Transport(json.dumps(proposal(), ensure_ascii=False)), store)
    artifact = writer.draft_revision(current.skill_id, trace(outcome=SkillOutcome.FAILED))
    assert artifact.draft.status is SkillStatus.DRAFT
    assert artifact.draft.version == 2
    assert artifact.reason_code == "REPEATED_FAILURE"
    assert store.require(current.skill_id).status is SkillStatus.VERIFIED
