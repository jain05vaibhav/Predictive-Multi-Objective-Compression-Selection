"""
Converts the Markdown Invention Disclosure Document (IDF-B) into a formatted
Microsoft Word (.docx) file with embedded figures, styled tables, and captions.
"""

import os
import re
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

MD_PATH = "docs/INVENTION_DISCLOSURE_DOCUMENT_IDF_B.md"
DOCX_PATH = "docs/INVENTION_DISCLOSURE_DOCUMENT_IDF_B.docx"
ASSETS_DIR = "docs/idf_assets"

def set_cell_background(cell, fill_hex):
    """Sets background color of a table cell."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tc_pr.append(shd)

def set_table_borders(table, color="D3D3D3"):
    """Applies clean subtle borders to a table."""
    tbl_pr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), color)
        tblBorders.append(border)
    v_border = OxmlElement('w:insideV')
    v_border.set(qn('w:val'), 'none')
    tblBorders.append(v_border)
    tbl_pr.append(tblBorders)

def parse_markdown_table(table_lines):
    """Parses markdown table lines into list of lists."""
    rows = []
    for line in table_lines:
        line = line.strip()
        if not line.startswith('|'):
            continue
        # Split by | and strip
        parts = [p.strip() for p in line.split('|')[1:-1]]
        # Skip separator line (e.g. |---|---|)
        if all(re.match(r'^:?-+:?$', p) for p in parts if p):
            continue
        rows.append(parts)
    return rows

def build_docx():
    doc = docx.Document()

    # Set page margins to 1 inch
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Base normal style font
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(30, 41, 59)

    with open(MD_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_table = False
    table_buffer = []

    i = 0
    total_lines = len(lines)

    while i < total_lines:
        line = lines[i].rstrip('\r\n')
        stripped = line.strip()

        # Table detection
        if stripped.startswith('|') and '|' in stripped[1:]:
            in_table = True
            table_buffer.append(stripped)
            i += 1
            continue
        elif in_table:
            # End of table encountered
            in_table = False
            rows = parse_markdown_table(table_buffer)
            table_buffer = []
            if rows:
                col_count = max(len(r) for r in rows)
                t = doc.add_table(rows=len(rows), cols=col_count)
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                set_table_borders(t)

                for r_idx, row in enumerate(rows):
                    for c_idx, cell_text in enumerate(row):
                        if c_idx < col_count:
                            cell = t.cell(r_idx, c_idx)
                            # Clean markdown bold/italics
                            clean_txt = cell_text.replace('**', '').replace('*', '').replace('`', '')
                            cell.text = clean_txt
                            # Styling
                            p = cell.paragraphs[0]
                            p.paragraph_format.space_before = Pt(3)
                            p.paragraph_format.space_after = Pt(3)
                            p.paragraph_format.line_spacing = 1.15
                            if r_idx == 0:
                                set_cell_background(cell, "0F172A")
                                for run in p.runs:
                                    run.font.bold = True
                                    run.font.size = Pt(9.5)
                                    run.font.color.rgb = RGBColor(255, 255, 255)
                            else:
                                if r_idx % 2 == 1:
                                    set_cell_background(cell, "F8FAFC")
                                else:
                                    set_cell_background(cell, "FFFFFF")
                                for run in p.runs:
                                    run.font.size = Pt(9)
                doc.add_paragraph()  # Spacing after table

        # Empty lines
        if not stripped:
            i += 1
            continue

        # Horizontal Rule
        if stripped in ('---', '***', '___'):
            i += 1
            continue

        # Image detection: ![Caption](path)
        img_match = re.match(r'!\[(.*?)\]\((.*?)\)', stripped)
        if img_match:
            caption = img_match.group(1)
            img_rel_path = img_match.group(2)
            # Normalize path
            img_path = os.path.normpath(os.path.join("docs", img_rel_path))
            if not os.path.exists(img_path):
                # Try directly in ASSETS_DIR
                base = os.path.basename(img_rel_path)
                img_path = os.path.join(ASSETS_DIR, base)

            if os.path.exists(img_path):
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(2)
                run = p_img.add_run()
                # Set width to 6.0 inches max
                run.add_picture(img_path, width=Inches(6.0))

                # Caption
                p_cap = doc.add_paragraph()
                p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_cap.paragraph_format.space_before = Pt(2)
                p_cap.paragraph_format.space_after = Pt(10)
                run_cap = p_cap.add_run(caption)
                run_cap.font.size = Pt(9.5)
                run_cap.font.italic = True
                run_cap.font.color.rgb = RGBColor(71, 85, 105)
            else:
                p = doc.add_paragraph(f"[Image missing: {img_path}]")
            i += 1
            continue

        # Headings
        if stripped.startswith('# '):
            h = doc.add_heading(level=0)
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = h.add_run(stripped[2:])
            run.font.name = 'Calibri'
            run.font.size = Pt(20)
            run.font.bold = True
            run.font.color.rgb = RGBColor(15, 23, 42)
            h.paragraph_format.space_after = Pt(12)
        elif stripped.startswith('## '):
            h = doc.add_heading(level=1)
            run = h.add_run(stripped[3:])
            run.font.name = 'Calibri'
            run.font.size = Pt(14)
            run.font.bold = True
            run.font.color.rgb = RGBColor(30, 58, 138)
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after = Pt(6)
        elif stripped.startswith('### '):
            h = doc.add_heading(level=2)
            run = h.add_run(stripped[4:])
            run.font.name = 'Calibri'
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = RGBColor(15, 118, 110)
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after = Pt(4)
        elif stripped.startswith('#### '):
            h = doc.add_heading(level=3)
            run = h.add_run(stripped[5:])
            run.font.name = 'Calibri'
            run.font.size = Pt(11)
            run.font.bold = True
            run.font.color.rgb = RGBColor(71, 85, 105)
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(3)

        # Bullet list item
        elif stripped.startswith('* ') or stripped.startswith('- '):
            bullet_text = stripped[2:]
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_before = Pt(1.5)
            p.paragraph_format.space_after = Pt(1.5)
            p.paragraph_format.line_spacing = 1.15
            _add_formatted_text(p, bullet_text)

        # Numbered list item
        elif re.match(r'^\d+\.\s+', stripped):
            num_text = re.sub(r'^\d+\.\s+', '', stripped)
            p = doc.add_paragraph(style='List Number')
            p.paragraph_format.space_before = Pt(1.5)
            p.paragraph_format.space_after = Pt(1.5)
            p.paragraph_format.line_spacing = 1.15
            _add_formatted_text(p, num_text)

        # Blockquote / Note / Monospace box
        elif stripped.startswith('> '):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.4)
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run(stripped[2:])
            run.font.italic = True
            run.font.color.rgb = RGBColor(71, 85, 105)

        # Code block marker
        elif stripped.startswith('```'):
            # Collect code lines until closing ```
            code_lines = []
            i += 1
            while i < total_lines and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i].rstrip('\r\n'))
                i += 1
            code_block_text = "\n".join(code_lines)
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(code_block_text)
            run.font.name = 'Consolas'
            run.font.size = Pt(8.5)
            run.font.color.rgb = RGBColor(30, 41, 59)

        # Standard paragraph
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.15
            _add_formatted_text(p, stripped)

        i += 1

    # Final table check
    if in_table and table_buffer:
        rows = parse_markdown_table(table_buffer)
        if rows:
            col_count = max(len(r) for r in rows)
            t = doc.add_table(rows=len(rows), cols=col_count)
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            set_table_borders(t)
            for r_idx, row in enumerate(rows):
                for c_idx, cell_text in enumerate(row):
                    if c_idx < col_count:
                        t.cell(r_idx, c_idx).text = cell_text.replace('**', '').replace('*', '')

    doc.save(DOCX_PATH)
    print(f"Successfully generated Word Document at: {DOCX_PATH}")

def _add_formatted_text(paragraph, text):
    """Parses bold, italic, code spans and adds runs."""
    # Split by bold (**...**) and inline code (`...`)
    tokens = re.split(r'(\*\*.*?\*\*|`.*?`|\*.*?\*)', text)
    for token in tokens:
        if not token:
            continue
        if token.startswith('**') and token.endswith('**'):
            r = paragraph.add_run(token[2:-2])
            r.font.bold = True
        elif token.startswith('*') and token.endswith('*'):
            r = paragraph.add_run(token[1:-1])
            r.font.italic = True
        elif token.startswith('`') and token.endswith('`'):
            r = paragraph.add_run(token[1:-1])
            r.font.name = 'Consolas'
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(190, 24, 93)
        else:
            paragraph.add_run(token)

if __name__ == "__main__":
    build_docx()
