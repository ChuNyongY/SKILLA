from pathlib import Path

import pytest

from javis_core import LocalSkillCatalog, SkillStatus
from tools.run_safe_file_sort_pilot import _pilot_registry
from tools.run_skill_revision_candidate_pilot import (
    FileSortRevisionRunner,
    _initial_proposal,
    _load_or_create_pair,
    _output_directory,
    _revised_proposal,
)
from tools.run_skill_study_pilot import _canonical_sha256


def test_revision_pilot_proposals_keep_key_and_capability_authority() -> None:
    initial = _initial_proposal()
    revised = _revised_proposal()

    assert revised.key == initial.key
    assert set(revised.allowed_capabilities) <= set(initial.allowed_capabilities)
    assert any("섞지 않음" in rule for rule in revised.decision_rules)


def test_pair_metadata_is_stable_and_keeps_candidate_draft(tmp_path: Path) -> None:
    output = tmp_path.resolve()
    catalog = LocalSkillCatalog(output / "skills.sqlite3", _pilot_registry())
    first = _load_or_create_pair(output, catalog)
    second = _load_or_create_pair(output, catalog)

    assert first == second
    assert catalog.require(first[0]).status is SkillStatus.VERIFIED
    assert catalog.require(first[1]).status is SkillStatus.DRAFT


def test_output_directory_rejects_foreign_entry(tmp_path: Path) -> None:
    assert _output_directory(str(tmp_path.resolve())) == tmp_path.resolve()
    (tmp_path / "foreign.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown or unsafe"):
        _output_directory(str(tmp_path.resolve()))


def test_revision_runner_initial_state_hash_matches_fixture_definition(
    tmp_path: Path,
) -> None:
    runner = FileSortRevisionRunner(tmp_path)
    expected = _canonical_sha256(
        {
            "directories": ["english", "math"],
            "files": {
                "english_week1.txt": (
                    "4231a97ecfd74fdbdde4d4306d6624330dadf659b3cd1e9b5ae35b0be2f46206"
                ),
                "math_week1.txt": (
                    "ec752d1d10b6d764a0e397c93efbaa03fd30ce08b8cbde407683936427c59368"
                ),
            },
        }
    )
    assert runner._initial_state_sha256 == expected
