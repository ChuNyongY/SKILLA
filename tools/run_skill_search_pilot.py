"""Run the frozen, developer-labeled skill retrieval pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from skilla_core import (
    LocalSkillCatalog,
    SkillProposal,
    SkillStatus,
    evaluate_skill_search,
    load_skill_search_cases,
)
from skilla_core.registry import default_registry

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = (_ROOT / "evaluation" / "skill_search_pilot_cases.json").resolve()
CATALOG_FILENAME = "skills.sqlite3"
REPORT_FILENAME = "report.json"
MANIFEST_FILENAME = "manifest.json"


def _proposal(
    key: str,
    title: str,
    description: str,
    triggers: tuple[str, ...],
    capability: str,
) -> SkillProposal:
    return SkillProposal(
        key=key,
        title=title,
        description=description,
        triggers=triggers,
        procedure=("현재 상태와 필요한 입력을 확인한다.", "작업 후 결과를 확인한다."),
        dynamic_inputs=("현재 작업 대상",),
        verification_rules=("요청한 결과가 실제 상태에 반영되었는지 확인한다.",),
        allowed_capabilities=(capability,),
    )


PILOT_SKILLS = (
    _proposal(
        "weekly-file-sort",
        "주간 과제 파일 정리",
        "다운로드 폴더의 이번 주 과제 파일을 파일명과 내용 기준으로 과목별 폴더에 이동한다.",
        ("과제 자료 정리", "이번 주 파일 정리", "과목별 정리"),
        "file.move",
    ),
    _proposal(
        "meeting-pdf-open",
        "회의 자료 PDF 열기",
        "회의 자료 폴더에서 요청한 PDF 문서를 찾아 등록된 프로그램으로 연다.",
        ("회의 자료 열기", "회의 PDF", "회의 문서 열기"),
        "file.open",
    ),
    _proposal(
        "volume-control",
        "컴퓨터 음량 조절",
        "기본 출력 장치의 현재 볼륨을 읽거나 요청한 소리 크기로 변경한다.",
        ("볼륨 조절", "소리 크기", "음량 변경"),
        "audio.volume.set",
    ),
    _proposal(
        "system-check",
        "시스템 정보 확인",
        "운영체제와 컴퓨터 시스템 사양 및 PC 정보를 읽어 확인한다.",
        ("시스템 정보", "컴퓨터 상태", "PC 정보"),
        "system.info.read",
    ),
    _proposal(
        "browser-navigation",
        "등록 웹사이트 열기",
        "허용된 웹사이트 주소에 브라우저로 접속하여 페이지를 연다.",
        ("웹사이트 열기", "브라우저로 열기", "사이트 접속"),
        "browser.navigate",
    ),
    _proposal(
        "work-bundle-archive",
        "업무 묶음 처리",
        "업무 묶음을 처리한다.",
        ("업무 묶음 처리",),
        "file.list",
    ),
    _proposal(
        "work-bundle-share",
        "업무 묶음 처리",
        "업무 묶음을 처리한다.",
        ("업무 묶음 처리",),
        "file.list",
    ),
)


def _prepare_empty_output(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError("output directory must be absolute")
    if path.exists():
        if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
            raise ValueError("output directory must be an empty regular directory")
        return path.resolve(strict=True)
    parent = path.parent.resolve(strict=True)
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("output directory parent must be a regular directory")
    created = parent / path.name
    created.mkdir()
    return created.resolve(strict=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_exclusive(path: Path, document: Any) -> None:
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists() or temporary.is_symlink() or path.exists():
        raise ValueError("pilot output already exists")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    except OSError as error:
        raise ValueError("pilot output could not be written exclusively") from error
    finally:
        if temporary.exists():
            temporary.unlink()


def _catalog_counts(path: Path) -> tuple[int, int, int]:
    with sqlite3.connect(path) as database:
        total = int(database.execute("SELECT COUNT(*) FROM skills").fetchone()[0])
        verified = int(
            database.execute(
                "SELECT COUNT(*) FROM skills WHERE status=?",
                (SkillStatus.VERIFIED.value,),
            ).fetchone()[0]
        )
        uses = int(database.execute("SELECT COUNT(*) FROM skill_uses").fetchone()[0])
    return total, verified, uses


def run_pilot(output: Path, cases_path: Path = DEFAULT_CASES) -> dict[str, object]:
    catalog_path = output / CATALOG_FILENAME
    output_names = (CATALOG_FILENAME, REPORT_FILENAME, MANIFEST_FILENAME)
    if any((output / name).exists() for name in output_names):
        raise ValueError("pilot output already exists")
    cases = load_skill_search_cases(cases_path)
    catalog = LocalSkillCatalog(catalog_path, default_registry())
    for proposal in PILOT_SKILLS:
        catalog.approve(catalog.propose(proposal).skill_id)

    report = evaluate_skill_search(catalog, cases)
    total_skills, verified_skills, skill_uses = _catalog_counts(catalog_path)
    if total_skills != len(PILOT_SKILLS) or verified_skills != total_skills:
        raise RuntimeError("pilot catalog contains a non-verified or missing skill")
    if skill_uses != 0:
        raise RuntimeError("retrieval pilot unexpectedly recorded a skill use")

    report_path = output / REPORT_FILENAME
    _write_json_exclusive(report_path, report.model_dump(mode="json"))
    manifest: dict[str, object] = {
        "schema_version": 1,
        "scope": "developer-labeled retrieval pilot; not a general-user performance claim",
        "cases": len(cases),
        "catalog_skills": total_skills,
        "verified_skills": verified_skills,
        "skill_uses": skill_uses,
        "skill_keys": sorted(proposal.key for proposal in PILOT_SKILLS),
        "sha256": {
            "cases": _sha256(cases_path),
            "report": _sha256(report_path),
            "catalog": _sha256(catalog_path),
        },
    }
    _write_json_exclusive(output / MANIFEST_FILENAME, manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    arguments = parser.parse_args(argv)
    output = _prepare_empty_output(arguments.output_directory)
    cases_path = Path(arguments.cases)
    if not cases_path.is_absolute():
        raise ValueError("case path must be absolute")
    manifest = run_pilot(output, cases_path)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
