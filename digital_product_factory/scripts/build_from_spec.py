from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

try:
    from pypdf import PdfReader, PdfWriter  # type: ignore
except Exception:
    PdfReader = None
    PdfWriter = None

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SCRIPT_DIR = Path(__file__).resolve().parent
FACTORY_DIR = SCRIPT_DIR.parent
REPO_DIR = FACTORY_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from common import OUTPUTS_DIR, clean_text, read_json
from digital_product_factory.generate_full_unique import (
    generate_full_adhd_planner_csv,
    generate_full_cleaning_checklist_csv,
)
from planner_postprocess import (
    build_planner_page_manifest,
    execute_hyperlink_stage,
    select_preview_pages,
    write_page_manifest,
    write_planner_link_map,
)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Title2", parent=styles["Title"], fontSize=22, leading=26, alignment=TA_CENTER, textColor=colors.HexColor("#2b2d42")))
styles.add(ParagraphStyle(name="Subtle", parent=styles["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#555555")))
styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontSize=15, leading=19, textColor=colors.HexColor("#1d3557"), spaceAfter=8))
styles.add(ParagraphStyle(name="Card", parent=styles["BodyText"], fontSize=10.5, leading=14))

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def get_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    if Path(path).exists():
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_table(data: list[list[str]], col_widths: list[float]) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d3557")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#eef4fb")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#a8b5c5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def extract_room_name(page_title: str) -> str:
    normalized = page_title.replace("–", "-")
    parts = normalized.split(" - ", 1)
    if len(parts) == 2:
        return parts[1].replace(" Cleaning Checklist", "").strip()
    return page_title.replace("Cleaning Checklist", "").strip()


def build_checklist_pdf(rows: list[dict[str, str]], spec: dict, path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = []
    story += [Paragraph(clean_text(spec.get("product_name") or "Checklist Product"), styles["Title2"]), Spacer(1, 6)]
    story += [Paragraph(clean_text(spec.get("benefit_statement") or "Printable checklist system for ADHD-friendly task completion."), styles["Subtle"]), Spacer(1, 12)]

    themes = sorted({r["Theme"] for r in rows})
    rooms = sorted({extract_room_name(r["Page_Title"]) for r in rows})
    overview_data = [
        ["Metric", "Value"],
        ["CSV rows", str(len(rows))],
        ["Themes", ", ".join(themes)],
        ["Rooms", ", ".join(rooms)],
        ["Weeks per room", "4"],
        ["Delivery format", clean_text(spec.get("delivery_format") or "pdf")],
    ]
    story += [Paragraph("Overview", styles["Section"]), build_table(overview_data, [55 * mm, 110 * mm]), Spacer(1, 12)]

    sample = [r for r in rows if r["Theme"] == rows[0]["Theme"]][:12] if rows else []
    if sample:
        data = [["Theme", "Page title", "Text", "Link target"]]
        for row in sample:
            data.append([row["Theme"], row["Page_Title"], row["Text_Main"], row["Link_Target_LogicalID"]])
        story += [Paragraph("Representative checklist rows", styles["Section"]), build_table(data, [24 * mm, 52 * mm, 74 * mm, 31 * mm]), PageBreak()]

        story += [Paragraph("Printable pages", styles["Section"])]
        for row in sample[:4]:
            tasks = [part.strip() for part in row["Text_Main"].split("+") if part.strip()]
            checklist_data = [["Done", "Task / Prompt"]]
            for task in tasks:
                checklist_data.append(["□", task])
            story += [
                Paragraph(f"<font size=16><b>{clean_text(row['Page_Title'])}</b></font>", styles["Card"]),
                Spacer(1, 6),
                build_table(checklist_data, [18 * mm, 150 * mm]),
                Spacer(1, 12),
            ]

    doc.build(story)


def build_notion_companion_pdf(spec: dict, path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = []
    title = clean_text(spec.get("product_name") or "Notion Companion Guide")
    benefit = clean_text(spec.get("benefit_statement") or "A buyer-facing setup guide and workflow companion for a Notion template.")
    format_hint = clean_text((spec.get("listing_inputs") or {}).get("format_hint") or "PDF setup guide + companion checklist for a Notion template")
    modules = [clean_text(item).replace("_", " ").title() for item in spec.get("content_modules") or [] if clean_text(item)]

    story += [Paragraph(title, styles["Title2"]), Spacer(1, 6)]
    story += [Paragraph(benefit, styles["Subtle"]), Spacer(1, 12)]

    overview_rows = [
        ["What the buyer gets", "Value"],
        ["Main deliverable", "Buyer-facing PDF companion guide"],
        ["Best use", "Open the guide first, then set up or duplicate the Notion workspace"],
        ["Format hint", format_hint],
        ["Included sections", ", ".join(modules or ["Start Here", "Setup Steps", "Workflow Checklists", "Buyer Guidance"])],
    ]
    story += [Paragraph("What buyer gets", styles["Section"]), build_table(overview_rows, [55 * mm, 110 * mm]), Spacer(1, 12)]

    setup_rows = [
        ["Step", "Action"],
        ["1", "Duplicate the Notion template into the buyer's workspace or open the shared template link."],
        ["2", "Use the Start Here page to understand the dashboard, databases, and daily workflow."],
        ["3", "Complete the setup checklist before adding live projects, clients, or content plans."],
        ["4", "Review the workflow pages weekly so the system stays useful after the first download."],
    ]
    story += [Paragraph("Start Here workflow", styles["Section"]), build_table(setup_rows, [15 * mm, 150 * mm]), Spacer(1, 12)]

    checklist_rows = [
        ["Checklist", "Why it matters"],
        ["Workspace duplicated", "Confirms the buyer has their own editable copy"],
        ["Core databases reviewed", "Prevents confusion on first open"],
        ["Tags / statuses customised", "Makes the template match the buyer's workflow"],
        ["Weekly reset reviewed", "Helps the system stay in use after setup"],
    ]
    story += [Paragraph("Companion checklist preview", styles["Section"]), build_table(checklist_rows, [55 * mm, 110 * mm]), Spacer(1, 12), PageBreak()]

    what_you_get_rows = [
        ["Included", "Why it matters"],
        ["PDF setup guide", "Explains how the buyer should open, duplicate, and use the Notion system"],
        ["Workflow checklists", "Turns setup into simple action steps"],
        ["Preview assets", "Supports Etsy listing creation and buyer expectations"],
        ["SEO helper text", "Speeds up listing operations"],
    ]
    story += [Paragraph("What the buyer gets in the download", styles["Section"]), build_table(what_you_get_rows, [55 * mm, 110 * mm])]
    doc.build(story)


def _xlsx_col_name(index: int) -> str:
    value = ""
    current = index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        value = chr(65 + remainder) + value
    return value


XLSX_STYLE_DEFAULT = 0
XLSX_STYLE_TITLE = 1
XLSX_STYLE_SECTION = 2
XLSX_STYLE_HEADER = 3
XLSX_STYLE_CURRENCY = 4
XLSX_STYLE_WRAP = 5
XLSX_STYLE_NOTE = 6
XLSX_STYLE_DATE = 7
XLSX_STYLE_STRONG = 8


def _xlsx_style_id(sheet: dict, row_index: int, column_index: int, value: object) -> int:
    if row_index in set(sheet.get("title_rows") or []):
        return XLSX_STYLE_TITLE
    if row_index in set(sheet.get("section_rows") or []):
        return XLSX_STYLE_SECTION
    if row_index in set(sheet.get("strong_rows") or []):
        if column_index in set(sheet.get("currency_columns") or []):
            return XLSX_STYLE_CURRENCY
        return XLSX_STYLE_STRONG
    if row_index in set(sheet.get("header_rows") or [1]):
        return XLSX_STYLE_HEADER
    if column_index in set(sheet.get("date_columns") or []) and row_index > 1:
        return XLSX_STYLE_DATE
    if column_index in set(sheet.get("currency_columns") or []) and row_index > 1:
        return XLSX_STYLE_CURRENCY
    if column_index in set(sheet.get("wrap_columns") or []):
        return XLSX_STYLE_WRAP
    if column_index in set(sheet.get("note_columns") or []):
        return XLSX_STYLE_NOTE
    return XLSX_STYLE_DEFAULT



def _xlsx_cell_xml(column_index: int, row_index: int, value: object, *, style_id: int = XLSX_STYLE_DEFAULT) -> str:
    cell_ref = f"{_xlsx_col_name(column_index)}{row_index}"
    style_attr = "" if style_id == XLSX_STYLE_DEFAULT else f' s="{style_id}"'
    if isinstance(value, (int, float)):
        return f'<c r="{cell_ref}"{style_attr}><v>{value}</v></c>'
    text = str(value)
    if text.startswith("="):
        return f'<c r="{cell_ref}"{style_attr}><f>{xml_escape(text[1:])}</f></c>'
    return (
        f'<c r="{cell_ref}" t="inlineStr"{style_attr}>'
        f'<is><t>{xml_escape(text)}</t></is>'
        f'</c>'
    )



def _xlsx_sheet_xml(sheet: dict) -> str:
    rows = sheet["rows"]
    row_xml = []
    max_cols = max((len(row) for row in rows), default=1)
    row_heights = sheet.get("row_heights") or {}
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            _xlsx_cell_xml(
                column_index,
                row_index,
                value,
                style_id=_xlsx_style_id(sheet, row_index, column_index, value),
            )
            for column_index, value in enumerate(row, start=1)
        )
        row_attrs = ""
        if row_index in row_heights:
            row_attrs = f' ht="{row_heights[row_index]}" customHeight="1"'
        row_xml.append(f'<row r="{row_index}"{row_attrs}>{cells}</row>')
    dimension = f"A1:{_xlsx_col_name(max_cols)}{max(len(rows), 1)}"
    col_widths = sheet.get("col_widths") or []
    cols_xml = ""
    if col_widths:
        cols_xml = '<cols>' + ''.join(
            f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
            for index, width in enumerate(col_widths, start=1)
        ) + '</cols>'
    pane_xml = ""
    freeze_cell = clean_text(sheet.get("freeze_cell"))
    if freeze_cell and freeze_cell != "A1":
        pane_xml = (
            '<sheetViews><sheetView workbookViewId="0">'
            f'<pane topLeftCell="{freeze_cell}" state="frozen"/>'
            f'<selection pane="topLeft" activeCell="{freeze_cell}" sqref="{freeze_cell}"/>'
            '</sheetView></sheetViews>'
        )
    else:
        pane_xml = '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
    merge_ranges = sheet.get("merged_ranges") or []
    merge_xml = ""
    if merge_ranges:
        merge_xml = '<mergeCells count="{count}">{items}</mergeCells>'.format(
            count=len(merge_ranges),
            items=''.join(f'<mergeCell ref="{xml_escape(item)}"/>' for item in merge_ranges),
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/>'
        + pane_xml
        + cols_xml
        + '<sheetFormatPr defaultRowHeight="18"/>'
        + '<sheetData>'
        + ''.join(row_xml)
        + '</sheetData>'
        + merge_xml
        + '</worksheet>'
    )



def _xlsx_styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="2">'
        '<numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00;[Red](&quot;$&quot;#,##0.00)"/>'
        '<numFmt numFmtId="165" formatCode="yyyy-mm-dd"/>'
        '</numFmts>'
        '<fonts count="5">'
        '<font><sz val="11"/><color rgb="FF111827"/><name val="Calibri"/><family val="2"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>'
        '<font><b/><sz val="16"/><color rgb="FF0F172A"/><name val="Calibri"/><family val="2"/></font>'
        '<font><i/><sz val="11"/><color rgb="FF6B7280"/><name val="Calibri"/><family val="2"/></font>'
        '<font><b/><sz val="11"/><color rgb="FF111827"/><name val="Calibri"/><family val="2"/></font>'
        '</fonts>'
        '<fills count="6">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFE0F2FE"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF0F766E"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1D3557"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF3F4F6"/><bgColor indexed="64"/></patternFill></fill>'
        '</fills>'
        '<borders count="2">'
        '<border><left/><right/><top/><bottom/><diagonal/></border>'
        '<border><left style="thin"><color rgb="FFD1D5DB"/></left><right style="thin"><color rgb="FFD1D5DB"/></right><top style="thin"><color rgb="FFD1D5DB"/></top><bottom style="thin"><color rgb="FFD1D5DB"/></bottom><diagonal/></border>'
        '</borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="9">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>'
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>'
        '<xf numFmtId="0" fontId="4" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )



def build_budget_sheet_workbook(spec: dict, path: Path) -> None:
    title = clean_text(spec.get("product_name") or "Budget Spreadsheet")
    sheets = [
        {
            "name": "Start Here",
            "rows": [
                [title, "", ""],
                [clean_text(spec.get("benefit_statement") or "A clean spreadsheet system for budgeting, tracking spend, and reviewing your monthly buffer."), "", ""],
                ["Quick Start", "", ""],
                ["1", "Open Dashboard", "See planned income, expenses, and current buffer at a glance."],
                ["2", "Update Monthly Budget", "Change the planned amounts to fit the buyer's real month."],
                ["3", "Log Transactions", "Add every income or expense entry in the tracker as it happens."],
                ["4", "Review Category Summary", "Check which categories are under or over budget in seconds."],
                ["Access Template", "", ""],
                ["Paste your live template link before delivery.", "https://your-template-link-here", "Buyers can bookmark this link for fast access."],
                ["What buyer gets", "", ""],
                ["Editable workbook (.xlsx)", "Formula-driven budget tabs", "Dashboard, Monthly Budget, Transactions, Category Summary"],
                ["Buyer-facing PDF preview", "Listing-ready support file", "Start Here, Dashboard, Transactions, and inclusions overview"],
                ["Works in common apps", "Excel, Google Sheets, Numbers-compatible apps", "No macros required"],
                ["Included Tabs", "", ""],
                ["Start Here", "Dashboard", "Monthly Budget"],
                ["Transactions", "Category Summary", "Instructions"],
            ],
            "col_widths": [28, 38, 44],
            "freeze_cell": "A4",
            "merged_ranges": ["A1:C1", "A2:C2", "A3:C3", "A8:C8", "A10:C10", "A14:C14"],
            "title_rows": [1],
            "section_rows": [3, 8, 10, 14],
            "strong_rows": [15, 16],
            "wrap_columns": [2, 3],
            "note_columns": [1],
            "row_heights": {1: 28, 2: 26, 3: 22, 8: 22, 10: 22, 14: 22},
        },
        {
            "name": "Dashboard",
            "rows": [
                ["KPI", "Value", "What it means"],
                ["Planned Income", "='Monthly Budget'!B2", "Main monthly income target from the budget sheet"],
                ["Planned Fixed Costs", "='Monthly Budget'!B3", "Rent, utilities, subscriptions, and other set costs"],
                ["Planned Variable Costs", "='Monthly Budget'!B4", "Flexible spending categories such as food and transport"],
                ["Savings Goal", "='Monthly Budget'!B5", "Target amount to keep aside each month"],
                ["Planned Leftover", "=B2-B3-B4-B5", "Expected amount left after the budget plan"],
                ["Actual Income Logged", "=SUMIFS(Transactions!$D$2:$D$500,Transactions!$E$2:$E$500,\"Income\")", "Live total pulled from the Transactions tab"],
                ["Actual Expenses Logged", "=SUMIFS(Transactions!$D$2:$D$500,Transactions!$E$2:$E$500,\"Expense\")", "Only expense rows from the Transactions tab"],
                ["Actual Net Cash Flow", "=B7-B8", "Actual income minus actual expenses logged so far"],
                ["Budget Buffer vs Plan", "=B6-B9", "Positive means the buyer is ahead of the current plan"],
            ],
            "col_widths": [28, 18, 46],
            "freeze_cell": "A2",
            "currency_columns": [2],
            "wrap_columns": [3],
        },
        {
            "name": "Monthly Budget",
            "rows": [
                ["Metric", "Planned Amount", "Notes"],
                ["Income", 2500.00, "Salary, freelance work, or business income"],
                ["Fixed Costs", 1100.00, "Rent, utilities, internet, and subscriptions"],
                ["Variable Costs", 650.00, "Food, fuel, dining, and flexible spending"],
                ["Savings Goal", 350.00, "Emergency fund, debt payoff, or sinking funds"],
                ["Leftover", "=B2-B3-B4-B5", "Remaining amount after the monthly plan"],
            ],
            "col_widths": [24, 18, 48],
            "freeze_cell": "A2",
            "currency_columns": [2],
            "wrap_columns": [3],
            "strong_rows": [6],
        },
        {
            "name": "Transactions",
            "rows": [
                ["Date", "Category", "Description", "Amount", "Type", "Month"],
                ["2026-01-01", "Groceries", "Weekly food shop", 54.20, "Expense", "Jan"],
                ["2026-01-03", "Salary", "Primary income", 2500.00, "Income", "Jan"],
                ["2026-01-04", "Transport", "Monthly pass", 35.00, "Expense", "Jan"],
                ["2026-01-05", "Housing", "Monthly rent", 900.00, "Expense", "Jan"],
                ["2026-01-08", "Utilities", "Electricity bill", 72.40, "Expense", "Jan"],
                ["2026-01-10", "Dining", "Coffee and lunch", 18.50, "Expense", "Jan"],
            ],
            "col_widths": [14, 18, 34, 14, 14, 10],
            "freeze_cell": "A2",
            "currency_columns": [4],
            "date_columns": [1],
            "wrap_columns": [3],
        },
        {
            "name": "Category Summary",
            "rows": [
                ["Category", "Budgeted", "Actual Spend", "Difference"],
                ["Groceries", 400.00, "=SUMIFS(Transactions!$D$2:$D$500,Transactions!$B$2:$B$500,$A2,Transactions!$E$2:$E$500,\"Expense\")", "=B2-C2"],
                ["Transport", 120.00, "=SUMIFS(Transactions!$D$2:$D$500,Transactions!$B$2:$B$500,$A3,Transactions!$E$2:$E$500,\"Expense\")", "=B3-C3"],
                ["Utilities", 180.00, "=SUMIFS(Transactions!$D$2:$D$500,Transactions!$B$2:$B$500,$A4,Transactions!$E$2:$E$500,\"Expense\")", "=B4-C4"],
                ["Housing", 900.00, "=SUMIFS(Transactions!$D$2:$D$500,Transactions!$B$2:$B$500,$A5,Transactions!$E$2:$E$500,\"Expense\")", "=B5-C5"],
                ["Dining", 100.00, "=SUMIFS(Transactions!$D$2:$D$500,Transactions!$B$2:$B$500,$A6,Transactions!$E$2:$E$500,\"Expense\")", "=B6-C6"],
                ["Total", "=SUM(B2:B6)", "=SUM(C2:C6)", "=SUM(D2:D6)"],
            ],
            "col_widths": [20, 16, 16, 16],
            "freeze_cell": "A2",
            "currency_columns": [2, 3, 4],
            "strong_rows": [7],
        },
        {
            "name": "Instructions",
            "rows": [
                ["Topic", "Guidance"],
                ["Best use", "Open Start Here first, then update Monthly Budget and track real entries in Transactions."],
                ["Dashboard workflow", "Review the Dashboard weekly to compare the planned leftover against the actual cash flow."],
                ["Category review", "Use Category Summary to see which expense categories are under or over plan."],
                ["New month setup", "Duplicate the workbook or save a new copy for each month to keep records tidy."],
            ],
            "col_widths": [22, 70],
            "freeze_cell": "A2",
            "wrap_columns": [2],
        },
    ]

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<bookViews><workbookView xWindow="0" yWindow="0" windowWidth="18000" windowHeight="9600"/></bookViews>'
        '<sheets>'
        + ''.join(
            f'<sheet name="{xml_escape(sheet["name"])}" sheetId="{index}" r:id="rId{index}"/>'
            for index, sheet in enumerate(sheets, start=1)
        )
        + '</sheets>'
        '</workbook>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + ''.join(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
            for index, _sheet in enumerate(sheets, start=1)
        )
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        + '</Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + ''.join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for index, _sheet in enumerate(sheets, start=1)
        )
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '</Types>'
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        '</Relationships>'
    )
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{xml_escape(title)}</dc:title>'
        '<dc:creator>Autofinisher</dc:creator>'
        '</cp:coreProperties>'
    )
    app_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Autofinisher</Application>'
        '<TitlesOfParts><vt:vector size="6" baseType="lpstr">'
        + ''.join(f'<vt:lpstr>{xml_escape(sheet["name"])}</vt:lpstr>' for sheet in sheets)
        + '</vt:vector></TitlesOfParts>'
        '</Properties>'
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/styles.xml", _xlsx_styles_xml())
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("docProps/app.xml", app_xml)
        for index, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _xlsx_sheet_xml(sheet))



def build_budget_sheet_pdf(spec: dict, path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = []
    listing_inputs = spec.get("listing_inputs") or {}
    modules = [clean_text(item) for item in spec.get("content_modules") or [] if clean_text(item)]
    required_sheet_names = [clean_text(item) for item in (spec.get("qa_thresholds") or {}).get("must_have_sheets") or [] if clean_text(item)]
    title = clean_text(spec.get("product_name") or "Budget Spreadsheet")
    format_hint = clean_text(listing_inputs.get("format_hint") or "Excel / Google Sheets compatible workbook")
    included_sheets = ["Start Here", "Dashboard", "Monthly Budget", "Transactions", "Category Summary", "Instructions"]

    story += [Paragraph(title, styles["Title2"]), Spacer(1, 6)]
    story += [Paragraph(clean_text(spec.get("benefit_statement") or "A clean spreadsheet system for budgeting and finance tracking."), styles["Subtle"]), Spacer(1, 12)]

    overview_data = [
        ["Metric", "Value"],
        ["What the buyer receives", "Formula-driven .xlsx workbook plus a buyer-facing PDF preview"],
        ["Included workbook tabs", ", ".join(included_sheets)],
        ["Format hint", format_hint],
        ["Template setup", "Start Here onboarding + Access Template handoff area"],
        ["Best fit", clean_text(spec.get("intended_user") or "Buyers who want low-friction budgeting")],
    ]
    story += [Paragraph("What the buyer gets", styles["Section"]), build_table(overview_data, [55 * mm, 110 * mm]), Spacer(1, 12)]

    onboarding_rows = [
        ["Step", "Action"],
        ["1", "Open Start Here and follow the quick-start checklist before editing anything else."],
        ["2", "Use the Access Template area to paste the live workbook link if delivery happens through Google Sheets or cloud storage."],
        ["3", "Review Dashboard for the live budget snapshot: planned leftover, actual expenses, actual income, and current buffer."],
        ["4", "Update Monthly Budget and Transactions, then use Category Summary to review categories without manual math."],
    ]
    story += [Paragraph("Start Here + Access Template workflow", styles["Section"]), build_table(onboarding_rows, [15 * mm, 150 * mm]), Spacer(1, 12)]

    module_rows = [["Included tab", "Purpose"]]
    purpose_map = {
        "Start Here": "Onboarding, access instructions, tab map, and buyer handoff guidance",
        "Dashboard": "Live KPI snapshot for planned vs actual budget performance",
        "Monthly Budget": "Main planning tab for income, costs, savings, and leftover",
        "Transactions": "Real-world money log used by workbook formulas",
        "Category Summary": "Automatic category roll-up using workbook formulas",
        "Instructions": "Simple usage notes for monthly workflow and template reuse",
    }
    combined = included_sheets if modules or required_sheet_names else included_sheets
    for item in combined:
        label = clean_text(item)
        module_rows.append([label, purpose_map.get(label, f"Structured {label.lower()} worksheet")])
    story += [Paragraph("Included worksheets", styles["Section"]), build_table(module_rows, [52 * mm, 113 * mm]), Spacer(1, 12)]

    dashboard_rows = [
        ["KPI", "Example value", "Explanation"],
        ["Planned Income", "$2,500.00", "Target monthly income from the Monthly Budget tab"],
        ["Actual Expenses Logged", "$1,080.10", "Pulled from transaction entries marked as Expense"],
        ["Actual Net Cash Flow", "$1,419.90", "Income logged minus expenses logged"],
        ["Planned Leftover", "$400.00", "Expected amount left after planned costs and savings"],
        ["Budget Buffer vs Plan", "($1,019.90)", "Quick signal showing whether actual cash flow is ahead or behind the plan"],
    ]
    story += [Paragraph("Dashboard preview", styles["Section"]), Paragraph("The Dashboard is designed for a fast buyer read: one tab, core KPIs, and meaningful formulas rather than placeholder math.", styles["Card"]), Spacer(1, 8), build_table(dashboard_rows, [40 * mm, 35 * mm, 90 * mm]), Spacer(1, 12)]

    transactions_rows = [
        ["Date", "Category", "Description", "Amount", "Type"],
        ["2026-01-01", "Groceries", "Weekly food shop", "$54.20", "Expense"],
        ["2026-01-03", "Salary", "Primary income", "$2,500.00", "Income"],
        ["2026-01-05", "Housing", "Monthly rent", "$900.00", "Expense"],
        ["2026-01-08", "Utilities", "Electricity bill", "$72.40", "Expense"],
        ["2026-01-10", "Dining", "Coffee and lunch", "$18.50", "Expense"],
    ]
    story += [Paragraph("Transactions preview", styles["Section"]), Paragraph("This is the buyer's main update tab. Every income and expense entry feeds the Dashboard and Category Summary automatically.", styles["Card"]), Spacer(1, 8), build_table(transactions_rows, [28 * mm, 32 * mm, 55 * mm, 25 * mm, 25 * mm]), Spacer(1, 12), PageBreak()]

    category_rows = [
        ["Category", "Budgeted", "Actual Spend", "Difference"],
        ["Groceries", "$400.00", "$54.20", "$345.80"],
        ["Transport", "$120.00", "$35.00", "$85.00"],
        ["Utilities", "$180.00", "$72.40", "$107.60"],
        ["Housing", "$900.00", "$900.00", "$0.00"],
        ["Dining", "$100.00", "$18.50", "$81.50"],
    ]
    story += [Paragraph("Category Summary preview", styles["Section"]), Paragraph("The buyer does not need to total categories manually. The workbook rolls up actual expenses by category and compares them against the planned budget.", styles["Card"]), Spacer(1, 8), build_table(category_rows, [38 * mm, 32 * mm, 32 * mm, 38 * mm]), Spacer(1, 12)]

    what_you_get_rows = [
        ["Included", "Why it matters"],
        ["Editable workbook (.xlsx)", "Main customer deliverable with formatting, freeze panes, and formulas already in place"],
        ["Start Here tab", "Improves first-open clarity and reduces buyer confusion"],
        ["Dashboard + Transactions + Category Summary", "Lets the buyer budget, track, and review from one workbook"],
        ["Buyer-facing PDF preview", "Shows the key workbook views and what is included before purchase"],
        ["Listing support assets", "Preview PDF, mockups, and SEO helper text for Etsy workflow"],
    ]
    story += [Paragraph("What buyer gets in the download", styles["Section"]), build_table(what_you_get_rows, [55 * mm, 110 * mm])]
    doc.build(story)



def build_planner_pdf(
    rows: list[dict[str, str]],
    spec: dict,
    path: Path,
    *,
    page_manifest: list[dict] | None = None,
    enable_links: bool = False,
) -> list[dict]:
    page_manifest = page_manifest or build_planner_page_manifest(spec, rows)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = []
    for index, page in enumerate(page_manifest):
        page_type = clean_text(page.get("page_type"))
        page_id = clean_text(page.get("page_id"))
        title = clean_text(page.get("title") or spec.get("product_name") or "Planner")
        subtitle = clean_text(page.get("subtitle"))
        body = clean_text(page.get("body"))
        target = clean_text(page.get("target_page_id"))
        anchor_markup = f'<a name="{page_id}"/>' if page_id else ""
        meta_rows = [["Field", "Value"], ["Page #", str(page.get("page_number"))], ["Page type", page_type], ["Page ID", page_id]]
        if page.get("month"):
            meta_rows.append(["Month", str(page.get("month"))])
        if page.get("week"):
            meta_rows.append(["Week", str(page.get("week"))])
        if page.get("date"):
            meta_rows.append(["Date", clean_text(page.get("date"))])
        if target:
            meta_rows.append(["Nav target", target])

        if page_type == "cover":
            story += [Paragraph(f"{anchor_markup}{title}", styles["Title2"]), Spacer(1, 12), Paragraph(clean_text(spec.get("benefit_statement") or subtitle), styles["Subtle"]), Spacer(1, 18)]
        else:
            story += [Paragraph(f"{anchor_markup}<font size=18><b>{title}</b></font>", styles["Card"]), Spacer(1, 6)]
            if subtitle:
                story += [Paragraph(subtitle, styles["Subtle"]), Spacer(1, 10)]

        story += [build_table(meta_rows, [42 * mm, 123 * mm]), Spacer(1, 10)]
        if enable_links and target:
            target_label = target.replace("_", " ")
            story += [Paragraph(f'<a href="#{target}">Jump to {target_label}</a>', styles["Subtle"]), Spacer(1, 8)]
        if body:
            story += [Paragraph("Content", styles["Section"]), Paragraph(body, styles["Card"]), Spacer(1, 10)]

        if page_type in {"monthly_overview", "weekly_page", "daily_page", "extra_template"}:
            prompt_rows = [["Block", "Prompt"]]
            if page_type == "monthly_overview":
                prompt_rows.extend([["Top 3", "Monthly priorities and appointments"], ["Wins", "Track progress and momentum"], ["Habits", "Focus on repeatable anchors"]])
            elif page_type == "weekly_page":
                prompt_rows.extend([["Focus", "What matters most this week"], ["Schedule", "Key appointments and deadlines"], ["Reset", "Low-friction recovery actions"]])
            elif page_type == "daily_page":
                prompt_rows.extend([["Top 3", "Three important tasks"], ["Notes", "Brain dump / reminders"], ["Care", "Meals, movement, and decompression"]])
            else:
                prompt_rows.extend([["Template use", "Reusable worksheet area"], ["Notes", "Custom prompts and lists"], ["Follow-up", "Action items and review"]])
            story += [build_table(prompt_rows, [35 * mm, 130 * mm])]

        if index < len(page_manifest) - 1:
            story += [PageBreak()]
    doc.build(story)
    return page_manifest


def draw_multiline_centered(draw: ImageDraw.ImageDraw, text: str, *, y_start: int, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, fill: str, max_width: int = 960) -> None:
    words = clean_text(text).split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        left, top, right, bottom = draw.textbbox((0, 0), candidate, font=font)
        if (right - left) <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    y = y_start
    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
        draw.text(((1200 - (right - left)) // 2, y), line, fill=fill, font=font)
        y += (bottom - top) + 18


def build_cover_assets(spec: dict, product_dir: Path) -> None:
    listing_inputs = spec.get("listing_inputs") or {}
    title = clean_text(spec.get("product_name") or spec.get("product_slug") or "Digital Product")
    subtitle = clean_text(listing_inputs.get("format_hint") or spec.get("usage_outcome") or spec.get("benefit_statement") or "Instant digital download")
    accent = "#4f46e5" if spec.get("product_kind") == "planner" else "#0f766e"

    master = Image.new("RGB", (1200, 1200), "white")
    draw = ImageDraw.Draw(master)
    draw.rectangle((0, 0, 1200, 220), fill=accent)
    draw_multiline_centered(draw, title, y_start=320, font=get_font(72, bold=True), fill="#111827")
    draw_multiline_centered(draw, subtitle, y_start=700, font=get_font(34), fill="#374151")
    draw.rounded_rectangle((120, 920, 1080, 1040), radius=18, outline=accent, width=6)
    draw_multiline_centered(draw, "Printable PDF • Etsy-ready package", y_start=945, font=get_font(28, bold=True), fill=accent)
    master.save(product_dir / "master.png")

    mockup = Image.new("RGB", (1200, 1200), accent)
    mockup_draw = ImageDraw.Draw(mockup)
    mockup_draw.rounded_rectangle((120, 120, 1080, 1080), radius=36, fill="white")
    draw_multiline_centered(mockup_draw, title, y_start=250, font=get_font(62, bold=True), fill="#111827")
    bullets = [
        clean_text(spec.get("benefit_statement") or "Fast to use"),
        clean_text(spec.get("user_problem") or "Structured workflow"),
        clean_text(spec.get("usage_outcome") or "Ready to print"),
    ]
    y = 560
    for bullet in bullets:
        draw_multiline_centered(mockup_draw, f"• {bullet}", y_start=y, font=get_font(28), fill="#374151", max_width=820)
        y += 120
    mockup.save(product_dir / "mockup.png")


def build_seo_text(spec: dict, product_dir: Path) -> None:
    tags = spec.get("listing_inputs", {}).get("tags") or []
    if not tags:
        tags = [spec.get("product_slug", "digital product").replace("-", " "), spec.get("product_family", "digital product"), spec.get("product_type", "digital product")]
    title = clean_text(spec.get("listing_inputs", {}).get("listing_title") or spec.get("product_name") or spec.get("product_slug"))
    description = clean_text(spec.get("benefit_statement") or spec.get("usage_outcome") or "Digital download.")
    payload = [
        f"TITLE: {title}",
        f"TAGS: {', '.join(clean_text(tag) for tag in tags[:13] if clean_text(tag))}",
        f"DESC: {description}",
    ]
    (product_dir / "SEO.txt").write_text("\n".join(payload), encoding="utf-8")


def infer_product_kind(spec: dict) -> str:
    explicit = clean_text(spec.get("product_kind")).lower()
    if explicit in {"checklist", "planner", "spreadsheet", "notion_companion"}:
        return explicit
    product_type = clean_text(spec.get("product_type")).lower()
    if "notion" in product_type:
        return "notion_companion"
    if "checklist" in product_type:
        return "checklist"
    if "spreadsheet" in product_type or "budget" in product_type or "sheet" in product_type:
        return "spreadsheet"
    return "planner"


def build_csv_for_spec(spec: dict, product_dir: Path) -> Path:
    product_kind = infer_product_kind(spec)
    csv_output_name = clean_text(spec.get("csv_output_name") or f"{spec['product_slug'].replace('-', '_').upper()}_FULL_UNIQUE")
    if product_kind == "checklist":
        generated_path = generate_full_cleaning_checklist_csv(output_name=csv_output_name)
        destination = product_dir / "source_rows.csv"
        shutil.copyfile(generated_path, destination)
        return destination
    if product_kind == "spreadsheet":
        destination = product_dir / "source_rows.csv"
        rows = [
            {"Sheet_Name": "Start Here", "Column": "Section", "Example": "Quick Start"},
            {"Sheet_Name": "Dashboard", "Column": "KPI", "Example": "Budget Buffer vs Plan"},
            {"Sheet_Name": "Monthly Budget", "Column": "Planned Amount", "Example": "2500.00"},
            {"Sheet_Name": "Transactions", "Column": "Date", "Example": "2026-01-01"},
            {"Sheet_Name": "Transactions", "Column": "Category", "Example": "Groceries"},
            {"Sheet_Name": "Transactions", "Column": "Amount", "Example": "54.20"},
            {"Sheet_Name": "Category Summary", "Column": "Difference", "Example": "345.80"},
        ]
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return destination
    if product_kind == "notion_companion":
        destination = product_dir / "source_rows.csv"
        rows = [
            {"Section": "Start Here", "Prompt": "Duplicate the Notion workspace or open the template link"},
            {"Section": "Setup Steps", "Prompt": "Review dashboard, core databases, and statuses"},
            {"Section": "Workflow Checklists", "Prompt": "Complete the onboarding checklist before live use"},
            {"Section": "Buyer Guidance", "Prompt": "Use the weekly reset to keep the template useful"},
        ]
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return destination
    structure = spec.get("planner_structure") or {}
    _ = structure.get("yearly_pages", 1)
    _ = structure.get("monthly_pages", 12)
    _ = structure.get("weekly_pages", 52)
    _ = structure.get("daily_pages", 365)
    generated_path = generate_full_adhd_planner_csv(output_name=csv_output_name)
    destination = product_dir / "source_rows.csv"
    shutil.copyfile(generated_path, destination)
    return destination



def build_preview_from_deliverable(deliverable_path: Path, preview_path: Path, *, preview_pages: list[int]) -> None:
    if PdfReader is None or PdfWriter is None:
        shutil.copyfile(deliverable_path, preview_path)
        return
    reader = PdfReader(str(deliverable_path))
    writer = PdfWriter()
    total_pages = len(reader.pages)
    added = 0
    for page_number in preview_pages:
        index = page_number - 1
        if 0 <= index < total_pages:
            writer.add_page(reader.pages[index])
            added += 1
    if added == 0:
        for index in range(min(total_pages, 8)):
            writer.add_page(reader.pages[index])
    with preview_path.open("wb") as handle:
        writer.write(handle)


def build_artifacts(spec: dict, product_dir: Path) -> dict[str, str]:
    product_dir.mkdir(parents=True, exist_ok=True)
    csv_path = build_csv_for_spec(spec, product_dir)
    rows = read_rows(csv_path)
    deliverable_path = product_dir / "deliverable.pdf"
    deliverable_xlsx_path = product_dir / "deliverable.xlsx"
    preview_path = product_dir / "preview.pdf"
    raw_deliverable_path = product_dir / "deliverable_raw.pdf"
    page_manifest_path = product_dir / "page_manifest.json"
    link_map_path = product_dir / "planner_link_map.csv"
    product_kind = infer_product_kind(spec)
    if product_kind == "checklist":
        build_checklist_pdf(rows, spec, deliverable_path)
        shutil.copyfile(deliverable_path, preview_path)
    elif product_kind == "spreadsheet":
        build_budget_sheet_workbook(spec, deliverable_xlsx_path)
        build_budget_sheet_pdf(spec, deliverable_path)
        build_budget_sheet_pdf(spec, preview_path)
        spec_path = product_dir / "digital_product_spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    elif product_kind == "notion_companion":
        build_notion_companion_pdf(spec, deliverable_path)
        build_notion_companion_pdf(spec, preview_path)
        spec_path = product_dir / "digital_product_spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        page_manifest = build_planner_page_manifest(spec, rows)
        build_planner_pdf(rows, spec, raw_deliverable_path, page_manifest=page_manifest, enable_links=False)
        page_manifest_path = write_page_manifest(page_manifest, product_dir)
        link_map_path = write_planner_link_map(page_manifest, product_dir)
        if spec.get("hyperlinked"):
            build_planner_pdf(rows, spec, deliverable_path, page_manifest=page_manifest, enable_links=True)
            execute_hyperlink_stage(
                spec=spec,
                product_dir=product_dir,
                raw_pdf_path=raw_deliverable_path,
                final_pdf_path=deliverable_path,
                link_map_path=link_map_path,
            )
        else:
            shutil.copyfile(raw_deliverable_path, deliverable_path)
        preview_pages = select_preview_pages(page_manifest, spec.get("preview_sampling") or {})
        preview_manifest = [page for page in page_manifest if int(page.get("page_number") or 0) in set(preview_pages)]
        build_planner_pdf(rows, spec, preview_path, page_manifest=preview_manifest, enable_links=False)
        spec_path = product_dir / "digital_product_spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    build_cover_assets(spec, product_dir)
    build_seo_text(spec, product_dir)
    base_result = {
        "source_csv": str(csv_path),
        "preview_pdf": str(preview_path),
        "master_png": str(product_dir / "master.png"),
        "mockup_png": str(product_dir / "mockup.png"),
        "seo_txt": str(product_dir / "SEO.txt"),
    }
    if product_kind == "spreadsheet":
        return {
            **base_result,
            "deliverable_xlsx": str(deliverable_xlsx_path),
            "deliverable_pdf": str(deliverable_path),
        }
    return {
        **base_result,
        "deliverable_pdf": str(deliverable_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_slug")
    args = parser.parse_args()

    product_dir = OUTPUTS_DIR / args.product_slug
    spec = read_json(product_dir / "digital_product_spec.json")
    result = build_artifacts(spec, product_dir)
    print(result)


if __name__ == "__main__":
    main()
