from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "SKILLA_RELATED_WORK_METHODS.md"
OUTPUT = ROOT / "output" / "SKILLA_스킬_관련논문_방법론과_적용범위.docx"
FONT = "Malgun Gothic"
BLACK = "000000"
NAVY = "1F4E79"


def set_font(run, size: float, bold: bool = False, color: str = BLACK) -> None:
    run.font.name = FONT
    fonts = run._element.get_or_add_rPr().rFonts
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        fonts.set(qn(key), FONT)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def set_cell_margins(cell, value: int = 100) -> None:
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


def shade(cell, fill: str) -> None:
    element = OxmlElement("w:shd")
    element.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(element)


def repeat_header(row) -> None:
    element = OxmlElement("w:tblHeader")
    element.set(qn("w:val"), "true")
    row._tr.get_or_add_trPr().append(element)


def no_split(row) -> None:
    row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    before = paragraph.add_run("- ")
    set_font(before, 9, color="666666")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)
    after = paragraph.add_run(" -")
    set_font(after, 9, color="666666")


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        values = [value.strip() for value in lines[index].strip().strip("|").split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", value.replace(" ", "")) for value in values):
            rows.append(values)
        index += 1
    return rows, index


def add_table(doc: Document, rows: list[list[str]]) -> None:
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for r_idx, values in enumerate(rows):
        row = table.rows[r_idx]
        no_split(row)
        if r_idx == 0:
            repeat_header(row)
        for c_idx, value in enumerate(values):
            cell = row.cells[c_idx]
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if r_idx == 0:
                shade(cell, NAVY)
            elif r_idx % 2 == 0:
                shade(cell, "F3F6F9")
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.1
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if r_idx == 0 else WD_ALIGN_PARAGRAPH.LEFT
            set_font(paragraph.add_run(value), 8.4, bold=r_idx == 0, color="FFFFFF" if r_idx == 0 else BLACK)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_body(doc: Document, text: str, *, references: bool = False) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT if references else WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.first_line_indent = Cm(-0.75) if references and text.startswith("[") else (Cm(0) if references else Cm(0.75))
    paragraph.paragraph_format.left_indent = Cm(0.75) if references else Cm(0)
    paragraph.paragraph_format.line_spacing = 1.3 if references else 1.5
    paragraph.paragraph_format.space_after = Pt(6)
    set_font(paragraph.add_run(text), 9.3 if references else 10.2)


def build() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.3)
    add_page_number(section.footer.paragraphs[0])

    for name, size in (("Title", 20), ("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11)):
        style = doc.styles[name]
        style.font.name = FONT
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), FONT)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.space_before = Pt(14 if name != "Title" else 0)
        style.paragraph_format.space_after = Pt(8)
        if name == "Title":
            p_pr = style._element.get_or_add_pPr()
            border = p_pr.find(qn("w:pBdr"))
            if border is not None:
                p_pr.remove(border)

    doc.core_properties.title = "SKILLA에 반영한 스킬 관련 논문의 방법론"
    doc.core_properties.subject = "관련 연구 방법과 SKILLA 적용 범위"
    doc.core_properties.author = "SKILLA 프로젝트"

    index = 0
    references_mode = False
    while index < len(lines):
        text = lines[index].strip()
        if not text:
            index += 1
            continue
        if text.startswith("# "):
            paragraph = doc.add_paragraph(style="Title")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_before = Pt(30)
            paragraph.paragraph_format.space_after = Pt(20)
            set_font(paragraph.add_run(text[2:]), 20, bold=True)
            index += 1
            continue
        if text.startswith("## "):
            paragraph = doc.add_paragraph(style="Heading 1")
            set_font(paragraph.add_run(text[3:]), 15, bold=True)
            references_mode = text == "## 참고문헌"
            index += 1
            continue
        if text.startswith("### "):
            paragraph = doc.add_paragraph(style="Heading 2")
            set_font(paragraph.add_run(text[4:]), 12.5, bold=True)
            index += 1
            continue
        if text.startswith("|"):
            rows, index = parse_table(lines, index)
            add_table(doc, rows)
            continue
        if text.startswith("- "):
            paragraph = doc.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.left_indent = Cm(0.8)
            paragraph.paragraph_format.space_after = Pt(4)
            set_font(paragraph.add_run(text[2:]), 10.0)
            index += 1
            continue
        if re.match(r"^\d+\. ", text):
            paragraph = doc.add_paragraph(style="List Number")
            paragraph.paragraph_format.left_indent = Cm(0.8)
            paragraph.paragraph_format.space_after = Pt(4)
            set_font(paragraph.add_run(re.sub(r"^\d+\. ", "", text)), 10.0)
            index += 1
            continue
        add_body(doc, text, references=references_mode)
        index += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
