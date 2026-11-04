from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from javis_core import (
    LocalSkillCatalog,
    SkillAwarePlanner,
    SkillProposal,
    SkillRetrievalDecision,
    SkillSearchCase,
    SkillSearchEvaluationError,
    SkillSearchOutcome,
    SkillStatus,
    evaluate_skill_search,
    load_skill_search_cases,
)
from javis_core.cli import main
from javis_core.models import Action, Plan
from javis_core.registry import default_registry


def _catalog(tmp_path: Path) -> LocalSkillCatalog:
    return LocalSkillCatalog((tmp_path / "skills.sqlite3").resolve(), default_registry())


def _add_skill(
    catalog: LocalSkillCatalog,
    key: str,
    title: str,
    triggers: tuple[str, ...],
    *,
    description: str | None = None,
) -> None:
    draft = catalog.propose(
        SkillProposal(
            key=key,
            title=title,
            description=description or title,
            triggers=triggers,
            procedure=("현재 상태를 확인한다.",),
            allowed_capabilities=("system.info.read",),
        )
    )
    catalog.approve(draft.skill_id)


class _Planner:
    def __init__(self) -> None:
        self.context: Mapping[str, object] | None = None

    def plan(
        self,
        goal: str,
        *,
        trusted_context: Mapping[str, object] | None = None,
        untrusted_context: str | None = None,
    ) -> Plan:
        self.context = trusted_context
        return Plan(
            goal=goal,
            steps=(Action(capability_id="system.info.read", purpose="fallback"),),
        )


def test_exact_trigger_phrase_outranks_loose_token_overlap(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    _add_skill(catalog, "meeting-files", "회의 파일", ("회의 자료",))
    _add_skill(
        catalog,
        "meeting-notes",
        "회의록",
        ("회의록 작성",),
        description="회의 자료 정리 기록",
    )

    result = catalog.retrieve("회의 자료 정리해 줘")

    assert result.decision is SkillRetrievalDecision.MATCHED
    assert result.selected_skill is not None
    assert result.selected_skill.key == "meeting-files"


def test_tied_retrieval_is_deterministic_and_planner_falls_back(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    _add_skill(catalog, "alpha-sort", "자료 정리", ("자료 정리",))
    _add_skill(catalog, "beta-sort", "자료 정리", ("자료 정리",))
    before = catalog.list(status=SkillStatus.VERIFIED)

    first = catalog.retrieve("자료 정리해 줘")
    second = catalog.retrieve("자료 정리해 줘")
    ranked = catalog.search("자료 정리해 줘")
    planner = _Planner()
    SkillAwarePlanner(planner, catalog).plan("자료 정리해 줘")

    assert first == second
    assert first.decision is SkillRetrievalDecision.AMBIGUOUS
    assert first.tied_skill_keys == ("alpha-sort", "beta-sort")
    assert tuple(item.key for item in ranked) == ("alpha-sort", "beta-sort")
    assert planner.context is None
    assert catalog.list(status=SkillStatus.VERIFIED) == before


def test_no_match_uses_base_planner(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    _add_skill(catalog, "volume-control", "볼륨", ("소리 조절",))
    planner = _Planner()

    result = catalog.retrieve("날씨 알려 줘")
    SkillAwarePlanner(planner, catalog).plan("날씨 알려 줘")

    assert result.decision is SkillRetrievalDecision.NO_MATCH
    assert planner.context is None


def test_registered_korean_particles_match_without_one_character_noise(
    tmp_path: Path,
) -> None:
    catalog = _catalog(tmp_path)
    _add_skill(
        catalog,
        "volume-control",
        "컴퓨터 음량 조절",
        ("소리 크기",),
        description="기본 출력 장치의 볼륨과 소리를 변경한다.",
    )
    _add_skill(
        catalog,
        "system-check",
        "시스템 정보 확인",
        ("컴퓨터 상태",),
        description="컴퓨터의 운영체제와 시스템 상태를 읽는다.",
    )

    volume = catalog.retrieve("스피커 음량을 줄여 줘")
    irrelevant = catalog.retrieve("이 수학 문제를 설명해 줘")

    assert volume.decision is SkillRetrievalDecision.MATCHED
    assert volume.selected_skill is not None
    assert volume.selected_skill.key == "volume-control"
    assert irrelevant.decision is SkillRetrievalDecision.NO_MATCH


def test_registered_korean_location_particle_matches_browser_skill(
    tmp_path: Path,
) -> None:
    catalog = _catalog(tmp_path)
    _add_skill(
        catalog,
        "browser-navigation",
        "웹사이트 열기",
        ("사이트 접속",),
        description="허용된 주소를 브라우저에서 연다.",
    )

    result = catalog.retrieve("주소를 브라우저에서 열어 줘")

    assert result.decision is SkillRetrievalDecision.MATCHED
    assert result.selected_skill is not None
    assert result.selected_skill.key == "browser-navigation"


def test_unknown_or_too_short_suffix_stems_do_not_match(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    _add_skill(catalog, "alpha-skill", "이가", ("이가",))

    assert catalog.retrieve("이를 알려 줘").decision is SkillRetrievalDecision.NO_MATCH


def test_particle_vocabulary_is_not_limited_by_query_token_budget(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    filler = " ".join(f"단어{index}" for index in range(20))
    _add_skill(
        catalog,
        "late-vocabulary",
        "후반 어휘",
        ("최종단어",),
        description=filler,
    )

    result = catalog.retrieve("최종단어를 실행해 줘")

    assert result.decision is SkillRetrievalDecision.MATCHED
    assert result.selected_skill is not None
    assert result.selected_skill.key == "late-vocabulary"


def test_search_evaluator_classifies_every_outcome(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    _add_skill(catalog, "volume-control", "볼륨 조절", ("볼륨",))
    _add_skill(catalog, "system-check", "시스템 확인", ("시스템 정보",))
    _add_skill(catalog, "alpha-sort", "자료 정리", ("자료 정리",))
    _add_skill(catalog, "beta-sort", "자료 정리", ("자료 정리",))
    cases = (
        SkillSearchCase(
            case_id="correct-match",
            query="볼륨 알려 줘",
            expected_skill_key="volume-control",
        ),
        SkillSearchCase(case_id="correct-empty", query="날씨", expected_skill_key=None),
        SkillSearchCase(case_id="false-positive", query="볼륨", expected_skill_key=None),
        SkillSearchCase(
            case_id="false-negative",
            query="날씨",
            expected_skill_key="volume-control",
        ),
        SkillSearchCase(
            case_id="wrong-skill",
            query="볼륨",
            expected_skill_key="system-check",
        ),
        SkillSearchCase(
            case_id="ambiguous",
            query="자료 정리",
            expected_skill_key="alpha-sort",
        ),
    )

    report = evaluate_skill_search(catalog, cases)

    assert report.total == 6
    assert report.correct == 2
    assert report.false_positive == 1
    assert report.false_negative == 1
    assert report.wrong_skill == 1
    assert report.ambiguous == 1
    assert report.accuracy == pytest.approx(2 / 6)
    assert tuple(item.outcome for item in report.results) == (
        SkillSearchOutcome.CORRECT,
        SkillSearchOutcome.CORRECT,
        SkillSearchOutcome.FALSE_POSITIVE,
        SkillSearchOutcome.FALSE_NEGATIVE,
        SkillSearchOutcome.WRONG_SKILL,
        SkillSearchOutcome.AMBIGUOUS,
    )


def test_case_loader_rejects_duplicate_keys_and_extra_fields(tmp_path: Path) -> None:
    duplicate = (tmp_path / "duplicate.json").resolve()
    duplicate.write_text(
        '[{"case_id":"one","case_id":"two","query":"q",'
        '"expected_skill_key":null}]',
        encoding="utf-8",
    )
    with pytest.raises(SkillSearchEvaluationError, match="invalid"):
        load_skill_search_cases(duplicate)

    with pytest.raises(ValidationError):
        SkillSearchCase.model_validate(
            {
                "case_id": "one",
                "query": "q",
                "expected_skill_key": None,
                "unexpected": True,
            }
        )


def test_evaluate_skill_search_cli_uses_labeled_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog_path = (tmp_path / "skills.sqlite3").resolve()
    catalog = LocalSkillCatalog(catalog_path, default_registry())
    _add_skill(catalog, "volume-control", "볼륨 조절", ("볼륨",))
    cases_path = (tmp_path / "cases.json").resolve()
    cases_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "match",
                    "query": "볼륨 알려 줘",
                    "expected_skill_key": "volume-control",
                },
                {
                    "case_id": "none",
                    "query": "날씨 알려 줘",
                    "expected_skill_key": None,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert main(("evaluate-skill-search", str(catalog_path), str(cases_path))) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["total"] == 2
    assert report["accuracy"] == 1.0
