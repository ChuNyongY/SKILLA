from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from javis_core import SkillRetrievalDecision, SkillSearchOutcome, load_skill_search_cases
from tools.run_skill_search_pilot import (
    CATALOG_FILENAME,
    DEFAULT_CASES,
    MANIFEST_FILENAME,
    PILOT_SKILLS,
    REPORT_FILENAME,
    _prepare_empty_output,
    main,
)

HOLDOUT_CASES = DEFAULT_CASES.with_name("skill_search_holdout_cases.json")
HOLDOUT_SHA256 = "8dd0bc9e090efbaf3e3f72a9f3e3f4a041a5770f92ffcc31eae02ce3d14721fd"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_cases_cover_positive_negative_and_ambiguity() -> None:
    cases = load_skill_search_cases(DEFAULT_CASES)

    assert len(cases) >= 20
    assert any(case.case_id.startswith("positive.") for case in cases)
    assert any(case.case_id.startswith("negative.") for case in cases)
    assert any(case.case_id.startswith("ambiguous.") for case in cases)
    assert any(
        case.expected_skill_key is None and case.case_id.startswith("negative.")
        for case in cases
    )


def test_holdout_cases_are_frozen_and_do_not_copy_development_queries() -> None:
    development = load_skill_search_cases(DEFAULT_CASES)
    holdout = load_skill_search_cases(HOLDOUT_CASES)

    assert len(holdout) == 25
    assert _sha256(HOLDOUT_CASES) == HOLDOUT_SHA256
    assert {case.query for case in development}.isdisjoint(case.query for case in holdout)
    assert sum(case.expected_skill_key is None for case in holdout) == 5
    assert len({case.case_id for case in holdout}) == len(holdout)


def test_pilot_writes_auditable_outputs_without_recording_uses(tmp_path: Path) -> None:
    output = (tmp_path / "pilot").resolve()

    assert main((str(output),)) == 0

    report_path = output / REPORT_FILENAME
    catalog_path = output / CATALOG_FILENAME
    manifest = json.loads((output / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert manifest["scope"].startswith("developer-labeled retrieval pilot")
    assert manifest["cases"] == len(load_skill_search_cases(DEFAULT_CASES))
    assert manifest["catalog_skills"] == len(PILOT_SKILLS)
    assert manifest["verified_skills"] == len(PILOT_SKILLS)
    assert manifest["skill_uses"] == 0
    assert {
        name: report[name]
        for name in (
            "total",
            "correct",
            "false_positive",
            "false_negative",
            "wrong_skill",
            "ambiguous",
        )
    } == {
        "total": 22,
        "correct": 19,
        "false_positive": 0,
        "false_negative": 1,
        "wrong_skill": 0,
        "ambiguous": 2,
    }
    assert manifest["sha256"] == {
        "cases": _sha256(DEFAULT_CASES),
        "report": _sha256(report_path),
        "catalog": _sha256(catalog_path),
    }
    ambiguous = [
        item for item in report["results"] if item["case_id"].startswith("ambiguous.")
    ]
    assert ambiguous
    assert all(
        item["retrieval_decision"] == SkillRetrievalDecision.AMBIGUOUS.value
        and item["outcome"] == SkillSearchOutcome.AMBIGUOUS.value
        for item in ambiguous
    )
    with sqlite3.connect(catalog_path) as database:
        assert database.execute("SELECT COUNT(*) FROM skill_uses").fetchone()[0] == 0
        assert database.execute(
            "SELECT COUNT(*) FROM skills WHERE status != 'VERIFIED'"
        ).fetchone()[0] == 0


def test_output_validation_rejects_relative_nonempty_and_rerun(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        _prepare_empty_output("relative")

    nonempty = (tmp_path / "nonempty").resolve()
    nonempty.mkdir()
    (nonempty / "owned-by-user.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        _prepare_empty_output(str(nonempty))

    output = (tmp_path / "pilot").resolve()
    assert main((str(output),)) == 0
    with pytest.raises(ValueError, match="empty"):
        main((str(output),))
