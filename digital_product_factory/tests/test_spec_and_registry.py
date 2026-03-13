from __future__ import annotations

import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / "digital_product_factory" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from product_family_registry import resolve_product_family
from spec_compiler import compile_spec_from_sources


def test_resolve_product_family_budget_sheet() -> None:
    winner = {
        "niche_keyword": "budget spreadsheet",
        "thesis": {"solution": "Budget dashboard and tracker"},
    }
    sku_task = {
        "niche_keyword": "budget spreadsheet",
        "cluster": {"core_skus": [{"slug": "budget-spreadsheet"}]},
    }
    family = resolve_product_family(
        product_kind="spreadsheet",
        niche_id="budget_spreadsheet_v1",
        winner=winner,
        sku_task=sku_task,
    )
    assert family == "budget_sheet_base"



def test_compile_spec_from_sources_for_spreadsheet() -> None:
    winner = {
        "niche_id": "budget_spreadsheet_v1",
        "niche_keyword": "budget spreadsheet",
        "thesis": {
            "buyer_intent": "Budgeting buyers",
            "problem": "Need a usable money tracker",
            "solution": "Spreadsheet system",
        },
        "design_guidelines": {
            "style": "clean minimal",
            "layout": ["sections"],
            "accessibility": ["clear headings"],
        },
        "seo_and_copy_hints": {
            "core_keywords": ["budget spreadsheet"],
            "angles": ["finance tracker"],
        },
        "validation_metrics": {"etsy": {"avg_price": 9.5}},
        "recommended_sku_cluster": {"core_skus": [{"slug": "budget-spreadsheet"}]},
    }
    sku_task = {
        "task_id": "sku_task_budget_spreadsheet_v1",
        "niche_id": "budget_spreadsheet_v1",
        "niche_keyword": "budget spreadsheet",
        "cluster": {"core_skus": [{"slug": "budget-spreadsheet"}]},
    }
    spec = compile_spec_from_sources(
        winner=winner,
        sku_task=sku_task,
        winner_path=Path("/tmp/winner.json"),
        sku_task_path=Path("/tmp/sku_task.json"),
        validated_niche_path=None,
        product_kind="spreadsheet",
    )
    assert spec["product_kind"] == "spreadsheet"
    assert spec["product_family"] == "budget_sheet_base"
    assert spec["build_backend"] == "sheet_pdf"
    assert spec["hyperlink_stage"]["status"] == "not_applicable"
    assert spec["delivery_format"] == "sheet_pdf"


def test_resolve_product_family_notion_companion() -> None:
    winner = {
        "niche_keyword": "notion business dashboard template",
        "thesis": {"solution": "Notion workspace guide and onboarding checklist"},
    }
    sku_task = {
        "niche_keyword": "notion business dashboard template",
        "cluster": {"core_skus": [{"slug": "notion-business-dashboard-template"}]},
    }
    family = resolve_product_family(
        product_kind="notion_companion",
        niche_id="notion_business_dashboard_template_v1",
        winner=winner,
        sku_task=sku_task,
    )
    assert family == "notion_companion_base"



def test_compile_spec_from_sources_for_notion_companion() -> None:
    winner = {
        "niche_id": "notion_business_dashboard_template_v1",
        "niche_keyword": "notion business dashboard template",
        "thesis": {
            "buyer_intent": "Small business buyers",
            "problem": "Need help understanding and setting up a Notion system",
            "solution": "A Notion companion guide with setup steps and workflow checklists",
        },
        "design_guidelines": {
            "style": "clean minimal",
            "layout": ["sections"],
            "accessibility": ["clear headings"],
        },
        "seo_and_copy_hints": {
            "core_keywords": ["notion business dashboard template"],
            "angles": ["notion setup guide"],
        },
        "validation_metrics": {"etsy": {"avg_price": 12.0}},
        "recommended_sku_cluster": {"core_skus": [{"slug": "notion-business-dashboard-template"}]},
    }
    sku_task = {
        "task_id": "validated_notion_business_dashboard_template_v1",
        "niche_id": "notion_business_dashboard_template_v1",
        "niche_keyword": "notion business dashboard template",
        "cluster": {"core_skus": [{"slug": "notion-business-dashboard-template"}]},
    }
    spec = compile_spec_from_sources(
        winner=winner,
        sku_task=sku_task,
        winner_path=Path("/tmp/validated_notion.json"),
        sku_task_path=Path("/tmp/validated_notion.json"),
        validated_niche_path=Path("/tmp/validated_notion.json"),
        product_kind="notion_companion",
    )
    assert spec["product_kind"] == "notion_companion"
    assert spec["product_family"] == "notion_companion_base"
    assert spec["build_backend"] == "canva_pdf"
    assert spec["hyperlink_stage"]["status"] == "not_applicable"
    assert spec["delivery_format"] == "pdf"
