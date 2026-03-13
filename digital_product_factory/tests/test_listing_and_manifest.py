from __future__ import annotations

import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / "digital_product_factory" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from artifact_manifest import build_manifest
from listing_compiler import compile_listing_packet



def test_build_manifest_for_spreadsheet(tmp_path: Path) -> None:
    spec = {
        "product_slug": "budget-spreadsheet",
        "product_kind": "spreadsheet",
        "required_artifacts": [
            "deliverable_xlsx",
            "deliverable_pdf",
            "master_png",
            "mockup_png",
            "seo_txt",
            "preview_pdf",
            "source_csv",
        ],
        "preview_assets_required": ["preview_pdf", "master_png", "mockup_png"],
        "qa_thresholds": {"must_have_sheets": ["Transactions", "Dashboard"]},
        "hyperlink_stage": {"status": "not_applicable"},
    }
    for filename in [
        "deliverable.xlsx",
        "deliverable.pdf",
        "preview.pdf",
        "master.png",
        "mockup.png",
        "SEO.txt",
        "source_rows.csv",
        "digital_product_spec.json",
    ]:
        (tmp_path / filename).write_text("ok", encoding="utf-8")
    manifest = build_manifest(spec, tmp_path)
    assert manifest["build_status"] == "ready"
    assert manifest["completeness"]["required_artifacts_ready"] is True
    assert manifest["qa"]["checks_passed"] is True
    assert "spreadsheet_deliverable_missing" not in manifest["qa"]["notes"]



def test_compile_listing_packet_includes_xlsx_for_spreadsheet() -> None:
    spec = {
        "product_slug": "budget-spreadsheet",
        "product_name": "Budget Spreadsheet",
        "product_family": "budget_sheet_base",
        "product_type": "budget_system",
        "product_kind": "spreadsheet",
        "layout_profile": "budget_dashboard",
        "benefit_statement": "Structured money tracking",
        "intended_user": "Budget-conscious buyer",
        "usage_outcome": "Ready-to-use budget system",
        "user_problem": "Needs a low-friction finance template",
        "content_modules": ["transactions", "monthly_overview", "dashboard"],
        "listing_inputs": {
            "listing_title": "Budget Spreadsheet | Budget Spreadsheet | Finance Tracker | Digital Download",
            "format_hint": "Google Sheets + optional PDF preview",
            "category": "spreadsheets",
            "tags": ["budget spreadsheet"],
            "primary_keyword": "budget spreadsheet",
            "secondary_keywords": ["finance tracker"],
            "price_anchor": 9.5,
        },
        "source_assets": {},
        "qa_thresholds": {"must_have_sheets": ["Transactions", "Dashboard"]},
    }
    manifest = {
        "artifacts": [
            {"artifact_type": "deliverable_xlsx", "path": "/tmp/deliverable.xlsx", "exists": True},
            {"artifact_type": "deliverable_pdf", "path": "/tmp/deliverable.pdf", "exists": True},
            {"artifact_type": "preview_pdf", "path": "/tmp/preview.pdf", "exists": True},
            {"artifact_type": "master_png", "path": "/tmp/master.png", "exists": True},
            {"artifact_type": "mockup_png", "path": "/tmp/mockup.png", "exists": True},
        ]
    }
    packet = compile_listing_packet(spec, manifest, "etsy")
    assert "/tmp/deliverable.xlsx" in packet["deliverable_files"]
    assert "/tmp/deliverable.pdf" in packet["deliverable_files"]
    assert "Spreadsheet workbook + PDF preview" in packet["what_is_included"]
