from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output" / "SKILLA_개발동기_안전한_로컬_AI_비서_보고서.md"
OUTPUT = ROOT / "output" / "SKILLA_개발동기_안전한_로컬_AI_비서_보고서.docx"

FONT = "Malgun Gothic"
ACCENT = "1F4E79"
LIGHT = "EAF2F8"
GRID = "D9E2F3"


def set_run_font(run, size=None, bold=None, color=None):
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:ascii"), FONT)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_border(cell, color=GRID):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = qn(f"w:{edge}")
        element = borders.find(tag)
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "6")
        element.set(qn("w:color"), color)


def set_cell_margins(cell, top=90, start=110, bottom=90, end=110):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("페이지 ")
    set_run_font(run, 9, color="666666")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)


def add_text(paragraph, text, size=10.5, bold=False, color=None):
    parts = re.split(r"(\*\*.*?\*\*)", text)
    for part in parts:
        if not part:
            continue
        is_bold = part.startswith("**") and part.endswith("**")
        run = paragraph.add_run(part[2:-2] if is_bold else part)
        set_run_font(run, size, bold=(bold or is_bold), color=color)


def add_table(doc, rows):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = "Table Grid"
    table.autofit = True
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            cell = table.cell(r, c)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            set_cell_border(cell)
            if r == 0:
                set_cell_shading(cell, ACCENT)
            elif r % 2 == 0:
                set_cell_shading(cell, "F7FAFC")
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.05
            add_text(paragraph, value, size=9.3, bold=(r == 0), color=("FFFFFF" if r == 0 else None))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def parse_table(lines, index):
    raw = []
    while index < len(lines) and lines[index].strip().startswith("|"):
        raw.append(lines[index].strip())
        index += 1
    rows = []
    for line in raw:
        cells = [x.strip() for x in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", x.replace(" ", "")) for x in cells):
            continue
        rows.append(cells)
    return rows, index


def build():
    source = SOURCE.read_text(encoding="utf-8")
    lines = source.splitlines()
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.25)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.35)
    section.right_margin = Cm(2.35)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = FONT
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.42
    for name, size in (("Title", 20), ("Heading 1", 14), ("Heading 2", 11.5)):
        style = styles[name]
        style.font.name = FONT
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(16 if name != "Title" else 0)
        style.paragraph_format.space_after = Pt(7)

    footer = section.footer
    add_page_number(footer.paragraphs[0])

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("# "):
            paragraph = doc.add_paragraph(style="Title")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_text(paragraph, stripped[2:], size=20, bold=True)
            subtitle = doc.add_paragraph()
            subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
            subtitle.paragraph_format.space_after = Pt(22)
            add_text(subtitle, "대화형 로컬 AI 비서의 개발 동기와 안전 실행 구조", size=11, color="555555")
            i += 1
            continue
        if stripped.startswith("## "):
            p = doc.add_paragraph(style="Heading 1")
            p.paragraph_format.keep_with_next = True
            add_text(p, stripped[3:], size=14, bold=True)
            i += 1
            continue
        if stripped.startswith("### "):
            p = doc.add_paragraph(style="Heading 2")
            p.paragraph_format.keep_with_next = True
            add_text(p, stripped[4:], size=11.5, bold=True)
            i += 1
            continue
        if stripped.startswith("|"):
            rows, i = parse_table(lines, i)
            if rows:
                add_table(doc, rows)
            continue
        if stripped.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.65)
            p.paragraph_format.right_indent = Cm(0.65)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            run = p.add_run("\n".join(code))
            run.font.name = "Consolas"
            run.font.size = Pt(8.8)
            run._element.rPr.rFonts.set(qn("w:ascii"), "Consolas")
            set_cell = OxmlElement("w:shd")
            p_pr = p._p.get_or_add_pPr()
            set_cell.set(qn("w:fill"), "F2F2F2")
            p_pr.append(set_cell)
            i += 1
            continue
        if stripped.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.75)
            p.paragraph_format.right_indent = Cm(0.25)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(7)
            add_text(p, stripped[2:], size=10.5, color="404040")
            i += 1
            continue
        if re.match(r"^[-*] ", stripped):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            add_text(p, stripped[2:], size=10.5)
            i += 1
            continue
        if re.match(r"^\d+\. \*\*", stripped):
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_after = Pt(5)
            text = re.sub(r"^\d+\. ", "", stripped)
            add_text(p, text, size=10.2)
            i += 1
            continue
        p = doc.add_paragraph()
        add_text(p, stripped, size=10.5)
        i += 1

    # Avoid a blank final paragraph and set document metadata.
    doc.core_properties.title = "SKILLA 개발 동기와 안전한 로컬 AI 비서 설계 보고서"
    doc.core_properties.subject = "SKILLA 프로젝트 보고서"
    doc.core_properties.author = "YongE"
    doc.core_properties.comments = ""
    doc.save(OUTPUT)


if __name__ == "__main__":
    build()
