from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import OUTPUTS_DIR, clean_text, read_json, safe_slug, write_json


def infer_product_type(raw_type: str, layout_profile: str) -> str:
    profile = clean_text(layout_profile).lower()
    if "planner" in profile:
        return "digital_planner"
    if "budget" in profile or raw_type == "sheet_pdf":
        return "budget_system"
    if "checklist" in profile:
        return "printable_checklist"
    return "digital_product"


def compile_spec(config: dict[str, Any]) -> dict[str, Any]:
    name = clean_text(config.get("name") or f"product_{config.get('id', 'unknown')}")
    slug = safe_slug(name)
    raw_type = clean_text(config.get("type") or "canva_pdf")
    themes = config.get("themes") or ["Default"]
    theme = clean_text(themes[0])
    pages = config.get("pages") or []
    families = config.get("families") or []
    page_types = [clean_text(page.get("page_type")) for page in pages if isinstance(page, dict)]
    content_modules = [p for p in page_types if p]
    product_type = infer_product_type(raw_type, clean_text(config.get("layout_profile")))

    return {
        "spec_version": "v1",
        "product_id": str(config.get("id") or slug),
        "product_slug": slug,
        "product_name": name,
        "product_family": clean_text(families[0]) if families else "general",
        "product_type": product_type,
        "benefit_statement": clean_text(config.get("metadata", {}).get("benefit_statement") or f"Helps the buyer use {name} quickly and consistently."),
        "user_problem": clean_text(config.get("metadata", {}).get("user_problem") or f"The buyer needs a structured {product_type.replace('_', ' ')}."),
        "intended_user": clean_text(config.get("metadata", {}).get("intended_user") or "Digital product buyer"),
        "usage_outcome": clean_text(config.get("metadata", {}).get("usage_outcome") or "Gets a ready-to-use digital system with clear structure."),
        "content_modules": content_modules,
        "pages": pages,
        "page_rules": config.get("page_rules") or {},
        "variants": [{"theme": t} for t in themes],
        "build_backend": raw_type,
        "layout_profile": clean_text(config.get("layout_profile") or "default_layout"),
        "theme": theme,
        "master_template_refs": [clean_text(config.get("canva_template_key"))] if config.get("canva_template_key") else [],
        "linking_profile": clean_text(config.get("linking_profile") or "default"),
        "required_artifacts": ["deliverable_pdf", "master_png"],
        "delivery_format": "pdf",
        "preview_assets_required": ["master_png", "mockup_png"],
        "qa_checks": ["required_files_present", "titles_not_empty", "links_valid_if_present"],
        "must_have_sections": content_modules[:10],
        "must_have_files": ["deliverable.pdf", "master.png"],
        "provenance": {
            "source_type": "manual_or_llm_config",
            "niche_id": clean_text(config.get("metadata", {}).get("niche_id")),
            "winner_id": clean_text(config.get("metadata", {}).get("winner_id")),
            "sku_task_id": clean_text(config.get("metadata", {}).get("sku_task_id"))
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path")
    args = parser.parse_args()

    config = read_json(Path(args.config_path))
    spec = compile_spec(config)
    out_path = OUTPUTS_DIR / spec["product_slug"] / "digital_product_spec.json"
    write_json(out_path, spec)
    print(out_path)


if __name__ == "__main__":
    main()
