from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "SKILLA_THESIS_DRAFT.md"
OUTPUT = ROOT / "output" / "SKILLA_스킬기반_Windows_PC에이전트_졸업논문_초안.docx"
FONT = "Malgun Gothic"
TEXT_COLOR = "111111"
ACCENT = "17365D"
LIGHT = "EAF1F8"
GRID = "9EADBA"


def set_font(run, size: float, *, bold: bool = False, color: str = TEXT_COLOR) -> None:
    run.font.name = FONT
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), FONT)
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("- ")
    set_font(run, 9, color="666666")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)
    run = paragraph.add_run(" -")
    set_font(run, 9, color="666666")


def shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    el = OxmlElement("w:shd")
    el.set(qn("w:fill"), fill)
    props.append(el)


def margins(cell, value: int = 90) -> None:
    props = cell._tc.get_or_add_tcPr()
    tc_mar = props.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        props.append(tc_mar)
    for side in ("top", "start", "bottom", "end"):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        tc_mar.append(node)


def no_split(row) -> None:
    props = row._tr.get_or_add_trPr()
    props.append(OxmlElement("w:cantSplit"))


def repeat_header(row) -> None:
    props = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    props.append(el)


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            rows.append(cells)
        index += 1
    return rows, index


def add_table(doc: Document, rows: list[list[str]]) -> None:
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = True
    for r_idx, values in enumerate(rows):
        row = table.rows[r_idx]
        no_split(row)
        if r_idx == 0:
            repeat_header(row)
        for c_idx, value in enumerate(values):
            cell = row.cells[c_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            margins(cell)
            if r_idx == 0:
                shade(cell, ACCENT)
            elif r_idx % 2 == 0:
                shade(cell, "F6F8FA")
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if r_idx == 0 or c_idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
            set_font(p.add_run(value), 8.6, bold=r_idx == 0, color="FFFFFF" if r_idx == 0 else TEXT_COLOR)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def add_body(doc: Document, text: str, *, size: float = 10.2, spacing: float = 1.55) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0.75)
    p.paragraph_format.line_spacing = spacing
    p.paragraph_format.space_after = Pt(6)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    set_font(p.add_run(text), size)


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Cm(0.75)
    p.paragraph_format.first_line_indent = Cm(-0.3)
    p.paragraph_format.line_spacing = 1.35
    p.paragraph_format.space_after = Pt(3)
    set_font(p.add_run(text), 10.0)


def build(output: Path = OUTPUT, *, cover_subtitle: str = "SKILLA 연구 보고서", subject: str = "SKILLA 졸업논문 초안") -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.3)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(1.0)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
    normal.font.size = Pt(10.2)
    for style_name, size, before, after in (
        ("Heading 1", 15, 16, 9),
        ("Heading 2", 12.5, 13, 7),
        ("Heading 3", 11, 10, 5),
    ):
        style = doc.styles[style_name]
        style.font.name = FONT
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(ACCENT if style_name != "Heading 3" else TEXT_COLOR)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    add_page_number(section.footer.paragraphs[0])
    doc.core_properties.title = "Windows PC 반복 작업을 위한 스킬 생성·재사용·개정형 AI 에이전트의 설계 및 평가"
    doc.core_properties.subject = subject
    doc.core_properties.author = "SKILLA 프로젝트"

    index = 0
    cover_mode = True
    abstract_mode = False
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if stripped == "<!--PAGEBREAK-->":
            doc.add_page_break()
            cover_mode = False
            abstract_mode = False
            index += 1
            continue
        if stripped.startswith("# "):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(145)
            p.paragraph_format.space_after = Pt(25)
            set_font(p.add_run(stripped[2:]), 22, bold=True, color=ACCENT)
            index += 1
            continue
        if cover_mode and not stripped.startswith("#"):
            if stripped == "SKILLA 연구 보고서":
                stripped = cover_subtitle
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(18)
            set_font(p.add_run(stripped), 12, bold=False, color="444444")
            index += 1
            continue
        if stripped.startswith("## "):
            p = doc.add_paragraph(style="Heading 1")
            p.paragraph_format.keep_with_next = True
            set_font(p.add_run(stripped[3:]), 15, bold=True, color=ACCENT)
            abstract_mode = stripped == "## 초록"
            index += 1
            continue
        if stripped.startswith("### "):
            p = doc.add_paragraph(style="Heading 2")
            set_font(p.add_run(stripped[4:]), 12.5, bold=True, color=ACCENT)
            index += 1
            continue
        if stripped.startswith("|"):
            rows, index = parse_table(lines, index)
            add_table(doc, rows)
            continue
        if stripped.startswith("- "):
            add_bullet(doc, stripped[2:])
            index += 1
            continue
        if re.match(r"^\d+\. ", stripped) and index < 30:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.0)
            p.paragraph_format.space_after = Pt(5)
            set_font(p.add_run(stripped), 10.5)
            index += 1
            continue
        if abstract_mode:
            add_body(doc, stripped, size=9.35, spacing=1.35)
        else:
            add_body(doc, stripped)
        index += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--cover-subtitle", default="SKILLA 연구 보고서")
    parser.add_argument("--subject", default="SKILLA 졸업논문 초안")
    args = parser.parse_args()
    build(args.output, cover_subtitle=args.cover_subtitle, subject=args.subject)
