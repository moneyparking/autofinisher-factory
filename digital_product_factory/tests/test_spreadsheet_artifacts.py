from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / "digital_product_factory" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from build_from_spec import build_artifacts
from common import OUTPUTS_DIR, read_json
from listing_compiler import compile_listing_packet
from artifact_manifest import build_manifest


EXPECTED_SHEETS = [
    "Start Here",
    "Dashboard",
    "Monthly Budget",
    "Transactions",
    "Category Summary",
    "Instructions",
]

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _load_budget_spec() -> dict:
    return read_json(OUTPUTS_DIR / "budget-spreadsheet" / "digital_product_spec.json")


def _read_workbook_parts(workbook_path: Path) -> tuple[list[str], dict[str, ET.Element], str]:
    with zipfile.ZipFile(workbook_path) as archive:
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        styles_xml = archive.read("xl/styles.xml").decode("utf-8")
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root.findall("rel:Relationship", REL_NS)
        }
        sheet_names: list[str] = []
        sheet_roots: dict[str, ET.Element] = {}
        for sheet in workbook_root.findall("main:sheets/main:sheet", NS):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rel_id]
            sheet_names.append(name)
            sheet_roots[name] = ET.fromstring(archive.read(f"xl/{target}"))
    return sheet_names, sheet_roots, styles_xml


def _sheet_cell_formula(sheet_root: ET.Element, cell_ref: str) -> str | None:
    cell = sheet_root.find(f"main:sheetData/main:row/main:c[@r='{cell_ref}']", NS)
    if cell is None:
        return None
    formula = cell.find("main:f", NS)
    return None if formula is None else f"={formula.text or ''}"


def _sheet_cell_style(sheet_root: ET.Element, cell_ref: str) -> str | None:
    cell = sheet_root.find(f"main:sheetData/main:row/main:c[@r='{cell_ref}']", NS)
    if cell is None:
        return None
    return cell.attrib.get("s")


def test_spreadsheet_workbook_structure_and_required_sheet_names(tmp_path: Path) -> None:
    spec = _load_budget_spec()
    spec["product_slug"] = "budget-spreadsheet-test"

    result = build_artifacts(spec, tmp_path)
    workbook_path = Path(result["deliverable_xlsx"])
    assert workbook_path.exists()

    sheet_names, sheet_roots, _styles_xml = _read_workbook_parts(workbook_path)
    assert sheet_names == EXPECTED_SHEETS

    dashboard = sheet_roots["Dashboard"]
    transactions = sheet_roots["Transactions"]
    start_here = sheet_roots["Start Here"]

    assert dashboard.find("main:sheetViews/main:sheetView/main:pane", NS).attrib.get("topLeftCell") == "A2"
    assert transactions.find("main:sheetViews/main:sheetView/main:pane", NS).attrib.get("topLeftCell") == "A2"
    assert start_here.find("main:sheetViews/main:sheetView/main:pane", NS).attrib.get("topLeftCell") == "A4"

    required_sheet_names = set((spec.get("qa_thresholds") or {}).get("must_have_sheets") or [])
    assert required_sheet_names.issubset(set(sheet_names))


def test_spreadsheet_formula_presence_and_formatting(tmp_path: Path) -> None:
    spec = _load_budget_spec()
    spec["product_slug"] = "budget-spreadsheet-test"

    result = build_artifacts(spec, tmp_path)
    sheet_names, sheet_roots, styles_xml = _read_workbook_parts(Path(result["deliverable_xlsx"]))

    dashboard = sheet_roots["Dashboard"]
    category_summary = sheet_roots["Category Summary"]
    monthly_budget = sheet_roots["Monthly Budget"]
    transactions = sheet_roots["Transactions"]
    start_here = sheet_roots["Start Here"]

    assert _sheet_cell_formula(dashboard, "B7") == '=SUMIFS(Transactions!$D$2:$D$500,Transactions!$E$2:$E$500,"Income")'
    assert _sheet_cell_formula(dashboard, "B8") == '=SUMIFS(Transactions!$D$2:$D$500,Transactions!$E$2:$E$500,"Expense")'
    assert _sheet_cell_formula(dashboard, "B10") == "=B6-B9"
    assert _sheet_cell_formula(category_summary, "C2") == '=SUMIFS(Transactions!$D$2:$D$500,Transactions!$B$2:$B$500,$A2,Transactions!$E$2:$E$500,"Expense")'
    assert _sheet_cell_formula(category_summary, "B7") == "=SUM(B2:B6)"
    assert _sheet_cell_formula(category_summary, "C7") == "=SUM(C2:C6)"
    assert _sheet_cell_formula(monthly_budget, "B6") == "=B2-B3-B4-B5"

    assert _sheet_cell_style(dashboard, "B2") == "4"
    assert _sheet_cell_style(category_summary, "C2") == "4"
    assert _sheet_cell_style(transactions, "A2") == "7"

    assert "formatCode=\"&quot;$&quot;#,##0.00;[Red](&quot;$&quot;#,##0.00)\"" in styles_xml
    assert "formatCode=\"yyyy-mm-dd\"" in styles_xml
    merge_cells = start_here.find("main:mergeCells", NS)
    assert merge_cells is not None
    assert len(merge_cells.findall("main:mergeCell", NS)) >= 1
    assert sheet_names == EXPECTED_SHEETS


def test_spreadsheet_packet_consistency_and_paths(tmp_path: Path) -> None:
    spec = _load_budget_spec()
    spec["product_slug"] = "budget-spreadsheet-test"

    build_artifacts(spec, tmp_path)
    manifest = build_manifest(spec, tmp_path)
    packet = compile_listing_packet(spec, manifest, "etsy")

    assert packet["artifacts"]["deliverable_path"].endswith("deliverable.xlsx")
    assert packet["artifacts"]["preview_path"].endswith("preview.pdf")
    assert any(path.endswith("deliverable.xlsx") for path in packet["deliverable_files"])
    assert any(path.endswith("deliverable.pdf") for path in packet["deliverable_files"])
    assert packet["qa_summary"]["checks_passed"] is True
