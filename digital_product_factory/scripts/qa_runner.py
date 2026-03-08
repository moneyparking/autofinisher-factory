from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None

from common import OUTPUTS_DIR, read_json

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _safe_read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return read_json(path)



def _pdf_page_count(pdf_path: Path) -> int | None:
    if PdfReader is None or not pdf_path.exists():
        return None
    try:
        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        return None



def _check_csv_rows(csv_path: Path) -> list[str]:
    notes: list[str] = []
    if not csv_path.exists():
        return ["source_rows_missing"]

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    if not rows:
        return ["source_rows_empty"]

    header, *data_rows = rows
    if not any(str(cell).strip() for cell in header):
        notes.append("source_rows_header_empty")

    seen: set[tuple[str, ...]] = set()
    has_data = False
    for index, row in enumerate(data_rows, start=2):
        normalized = tuple(str(cell).strip() for cell in row)
        if not any(normalized):
            notes.append(f"source_rows_empty_row_{index}")
            continue
        has_data = True
        if normalized in seen:
            notes.append(f"source_rows_duplicate_row_{index}")
        seen.add(normalized)

    if not has_data:
        notes.append("source_rows_no_data")
    return notes



def _required_sheet_notes(xlsx_path: Path, required_sheets: list[str]) -> list[str]:
    if not xlsx_path.exists():
        return ["spreadsheet_deliverable_missing"]
    if not required_sheets:
        return []

    try:
        with zipfile.ZipFile(xlsx_path) as archive:
            workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    except Exception:
        return ["spreadsheet_sheet_check_failed"]

    found = [sheet.attrib.get("name", "") for sheet in workbook_root.findall("main:sheets/main:sheet", NS)]
    missing = [sheet for sheet in required_sheets if sheet not in found]
    if not missing:
        return []
    return [f"spreadsheet_missing_sheets:{','.join(missing)}"]



def run_qa(product_slug: str) -> dict:
    product_dir = OUTPUTS_DIR / product_slug
    spec_path = product_dir / "digital_product_spec.json"
    manifest_path = product_dir / "artifact_manifest.json"
    packet_path = product_dir / "listing_packet_etsy.json"

    if not spec_path.exists() or not manifest_path.exists():
        return {
            "product_slug": product_slug,
            "contract_checks_passed": False,
            "product_checks_passed": False,
            "commercial_checks_passed": False,
            "checks_passed": False,
            "missing_files": [
                name
                for name, path in [("digital_product_spec.json", spec_path), ("artifact_manifest.json", manifest_path)]
                if not path.exists()
            ],
            "broken_links": 0,
            "notes": ["missing_spec_or_manifest"],
        }

    spec = read_json(spec_path)
    manifest = read_json(manifest_path)
    packet = _safe_read_json(packet_path)

    product_kind = str(spec.get("product_kind") or "")
    missing_files = [
        required
        for required in spec.get("must_have_files", [])
        if not (product_dir / required).exists()
    ]
    broken_links = int((manifest.get("qa") or {}).get("broken_links", 0))
    notes = list((manifest.get("qa") or {}).get("notes") or [])

    contract_checks_passed = (
        not missing_files and bool((manifest.get("completeness") or {}).get("required_artifacts_ready", False))
    )
    product_checks_passed = True
    commercial_checks_passed = bool((manifest.get("completeness") or {}).get("preview_assets_ready", False))

    deliverable_pdf = product_dir / "deliverable.pdf"
    deliverable_xlsx = product_dir / "deliverable.xlsx"
    preview_pdf = product_dir / "preview.pdf"
    source_rows = product_dir / "source_rows.csv"
    thresholds = spec.get("qa_thresholds") or {}

    if packet is None:
        notes.append("listing_packet_missing")
        commercial_checks_passed = False

    if product_kind == "planner":
        page_count = _pdf_page_count(deliverable_pdf)
        min_page_count = int(thresholds.get("min_page_count") or 0)
        if min_page_count and page_count is not None and page_count < min_page_count:
            notes.append("planner_page_count_below_threshold")
            product_checks_passed = False
        required_months = int(thresholds.get("required_months") or 0)
        if required_months and int((spec.get("planner_structure") or {}).get("monthly_pages") or 0) < required_months:
            notes.append("planner_required_months_missing")
            product_checks_passed = False
        required_daily_pages = int(thresholds.get("required_daily_pages") or 0)
        if required_daily_pages and int((spec.get("planner_structure") or {}).get("daily_pages") or 0) < required_daily_pages:
            notes.append("planner_required_daily_pages_missing")
            product_checks_passed = False
        hyperlink_status = str((spec.get("hyperlink_stage") or {}).get("status") or "not_applicable")
        if spec.get("hyperlinked") and hyperlink_status not in {"done", "failed", "not_applicable"}:
            notes.append("planner_hyperlink_status_invalid")
            product_checks_passed = False
        if spec.get("hyperlinked") and hyperlink_status == "failed":
            notes.append("planner_hyperlink_stage_failed")
            product_checks_passed = False

    elif product_kind == "checklist":
        if not deliverable_pdf.exists():
            notes.append("checklist_deliverable_missing")
            contract_checks_passed = False
        page_count = _pdf_page_count(deliverable_pdf)
        if page_count is not None and page_count < 1:
            notes.append("checklist_page_count_below_threshold")
            product_checks_passed = False
        csv_notes = _check_csv_rows(source_rows)
        if csv_notes:
            notes.extend(csv_notes)
            product_checks_passed = False
            if any(note.startswith("source_rows_missing") for note in csv_notes):
                contract_checks_passed = False

    elif product_kind == "spreadsheet":
        if not deliverable_xlsx.exists():
            notes.append("spreadsheet_deliverable_missing")
            contract_checks_passed = False
        if not preview_pdf.exists():
            notes.append("spreadsheet_preview_missing")
            commercial_checks_passed = False
        if packet is not None and not str((packet.get("artifacts") or {}).get("deliverable_path") or "").endswith(".xlsx"):
            notes.append("spreadsheet_packet_deliverable_not_xlsx")
            contract_checks_passed = False
        sheet_notes = _required_sheet_notes(deliverable_xlsx, list(thresholds.get("must_have_sheets") or []))
        if sheet_notes:
            notes.extend(sheet_notes)
            if any(note == "spreadsheet_deliverable_missing" for note in sheet_notes):
                contract_checks_passed = False
            else:
                product_checks_passed = False

    elif product_kind == "notion_companion":
        if not deliverable_pdf.exists():
            notes.append("notion_companion_deliverable_missing")
            contract_checks_passed = False
        if not preview_pdf.exists():
            notes.append("notion_companion_preview_missing")
            commercial_checks_passed = False
        if not source_rows.exists():
            notes.append("notion_companion_source_rows_missing")
            contract_checks_passed = False
        page_count = _pdf_page_count(deliverable_pdf)
        min_page_count = int(thresholds.get("min_page_count") or 4)
        if page_count is not None and page_count < min_page_count:
            notes.append("notion_companion_page_count_below_threshold")
            product_checks_passed = False

    checks_passed = (
        contract_checks_passed and product_checks_passed and commercial_checks_passed and broken_links == 0
    )

    return {
        "product_slug": product_slug,
        "contract_checks_passed": contract_checks_passed,
        "product_checks_passed": product_checks_passed,
        "commercial_checks_passed": commercial_checks_passed,
        "checks_passed": checks_passed,
        "missing_files": missing_files,
        "broken_links": broken_links,
        "notes": notes,
    }



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_slug")
    args = parser.parse_args()
    print(json.dumps(run_qa(args.product_slug), indent=4))


if __name__ == "__main__":
    main()
