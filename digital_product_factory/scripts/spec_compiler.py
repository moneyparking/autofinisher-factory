from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import OUTPUTS_DIR, clean_text, read_json, safe_slug, write_json
from product_family_registry import get_family_preset, resolve_product_family


WINNERS_DIR = Path("/home/agent/autofinisher-factory/data/winners")
SKU_TASKS_DIR = Path("/home/agent/autofinisher-factory/data/sku_tasks")
VALIDATED_NICHES_DIR = Path("/home/agent/autofinisher-factory/data/validated_niches")
NICHE_OVERRIDES_PATH = Path("/home/agent/autofinisher-factory/digital_product_factory/configs/niche_overrides.json")



def load_niche_overrides() -> dict[str, Any]:
    if NICHE_OVERRIDES_PATH.exists():
        return read_json(NICHE_OVERRIDES_PATH)
    return {}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def infer_product_type(raw_type: str, layout_profile: str) -> str:
    profile = clean_text(layout_profile).lower()
    if "planner" in profile:
        return "digital_planner"
    if "budget" in profile or raw_type == "sheet_pdf":
        return "budget_system"
    if "checklist" in profile:
        return "printable_checklist"
    return "digital_product"


def infer_product_kind_from_text(*values: str) -> str:
    text = " ".join(clean_text(value).lower() for value in values if clean_text(value))
    if "notion" in text:
        return "notion_companion"
    if "checklist" in text or "cleaning" in text or "chore" in text:
        return "checklist"
    if "spreadsheet" in text or "budget" in text or "sheet" in text:
        return "spreadsheet"
    return "planner"


def infer_artifact_paths(niche_id: str) -> tuple[Path, Path, Path | None]:
    winner_path = WINNERS_DIR / f"{niche_id}.json"
    sku_task_path = SKU_TASKS_DIR / f"sku_task_{niche_id}.json"
    direct_validated_niche_path = VALIDATED_NICHES_DIR / f"{niche_id}.json"
    item_validated_niche_path = VALIDATED_NICHES_DIR / "items" / f"{niche_id}.json"
    validated_niche_path: Path | None = None
    if direct_validated_niche_path.exists():
        validated_niche_path = direct_validated_niche_path
    elif item_validated_niche_path.exists():
        validated_niche_path = item_validated_niche_path
    return winner_path, sku_task_path, validated_niche_path


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


def compile_spec_from_sources(*, winner: dict[str, Any], sku_task: dict[str, Any], winner_path: Path, sku_task_path: Path, validated_niche_path: Path | None = None, product_kind: str | None = None) -> dict[str, Any]:
    niche_id = clean_text(winner.get("niche_id") or sku_task.get("niche_id"))
    niche_keyword = clean_text(winner.get("niche_keyword") or sku_task.get("niche_keyword") or niche_id)
    core_skus = ((sku_task.get("cluster") or {}).get("core_skus") or (winner.get("recommended_sku_cluster") or {}).get("core_skus") or [])
    primary_sku = core_skus[0] if core_skus and isinstance(core_skus[0], dict) else {}
    sku_slug = clean_text(primary_sku.get("slug") or niche_keyword or niche_id)
    kind = product_kind or infer_product_kind_from_text(niche_keyword, sku_slug, winner.get("thesis", {}).get("solution", ""))
    product_family = resolve_product_family(product_kind=kind, niche_id=niche_id, winner=winner, sku_task=sku_task)
    family_preset = get_family_preset(product_family)
    slug = safe_slug(f"{sku_slug}-{kind}") if kind not in sku_slug else safe_slug(sku_slug)
    product_name = clean_text(primary_sku.get("slug") or niche_keyword).replace("-", " ").title()
    if kind == "checklist" and "checklist" not in product_name.lower():
        product_name = f"{product_name} Checklist"
    if kind == "spreadsheet" and "spreadsheet" not in product_name.lower() and "sheet" not in product_name.lower():
        product_name = f"{product_name} Spreadsheet"
    if kind == "notion_companion" and "notion" not in product_name.lower():
        product_name = f"{product_name} Notion Companion"
    thesis = winner.get("thesis") or {}
    design = winner.get("design_guidelines") or {}
    seo = winner.get("seo_and_copy_hints") or {}
    listing_defaults = family_preset.get("listing_defaults") or {}
    price_anchor = ((winner.get("validation_metrics") or {}).get("etsy") or {}).get("avg_price")
    listing_title = f"{product_name} | Digital Download"
    if kind == "checklist":
        listing_title = f"{product_name} Printable Bundle | Digital Download"
    if kind == "planner":
        listing_title = f"{product_name} | Hyperlinked GoodNotes Planner | Daily Weekly Monthly | iPad Planner"
    if kind == "spreadsheet":
        listing_title = f"{product_name} | Budget Spreadsheet | Finance Tracker | Digital Download"
    if kind == "notion_companion":
        listing_title = f"{product_name} | Notion Template Guide | Setup Checklist | Digital Download"
    csv_output_name = f"{safe_slug(slug).replace('-', '_').upper()}_FULL_UNIQUE"

    spec = {
        "spec_version": "v1",
        "product_id": niche_id or slug,
        "product_slug": slug,
        "product_name": product_name,
        "product_family": product_family,
        "product_type": family_preset["product_type"],
        "product_kind": family_preset["product_kind"],
        "benefit_statement": clean_text(thesis.get("solution") or f"A {kind} product that is practical, printable, and ready to use immediately."),
        "user_problem": clean_text(thesis.get("problem") or f"The buyer needs a low-friction {kind} system that reduces decision fatigue."),
        "intended_user": clean_text(thesis.get("buyer_intent") or "Buyers looking for a structured digital download they can use immediately."),
        "usage_outcome": clean_text(f"Receives an Etsy-ready {kind} product with generated CSV, printable PDF, preview assets, and listing packet."),
        "content_modules": family_preset.get("content_modules") or [],
        "pages": [],
        "page_rules": family_preset.get("page_rules") or {},
        "variants": [{"theme": theme} for theme in ["Dark Rainbow", "Pastel Calm", "Bright ADHD", "Monochrome", "Custom"]],
        "build_backend": "sheet_pdf" if family_preset["product_kind"] == "spreadsheet" else "canva_pdf",
        "layout_profile": clean_text(family_preset.get("default_layout_profile") or "default_layout"),
        "theme": clean_text((design.get("style") or "clean minimal")[:80]),
        "master_template_refs": [],
        "linking_profile": clean_text(family_preset.get("default_linking_profile") or "default"),
        "required_artifacts": family_preset.get("required_artifacts") or [],
        "delivery_format": clean_text(family_preset.get("delivery_format") or "pdf"),
        "preview_assets_required": family_preset.get("preview_assets_required") or [],
        "qa_checks": family_preset.get("qa_checks") or [],
        "qa_thresholds": family_preset.get("qa_thresholds") or {},
        "must_have_sections": family_preset.get("must_have_sections") or [],
        "must_have_files": family_preset.get("must_have_files") or [],
        "dated": bool(family_preset.get("dated", False)),
        "year": family_preset.get("year"),
        "hyperlinked": bool(family_preset.get("supports_hyperlinks", False)),
        "hyperlinked_ready": False,
        "hyperlink_stage": {
            "engine": "pdf_linkr_cli",
            "profile": clean_text(family_preset.get("default_linking_profile") or "default"),
            "status": "pending" if family_preset["product_kind"] == "planner" and family_preset.get("supports_hyperlinks", False) else "not_applicable",
        },
        "planner_structure": family_preset.get("planner_structure"),
        "hyperlink_model": family_preset.get("hyperlink_model"),
        "preview_sampling": family_preset.get("preview_sampling") or {},
        "source_assets": {
            "winner_path": str(winner_path),
            "sku_task_path": str(sku_task_path),
            "validated_niche_path": str(validated_niche_path) if validated_niche_path else None,
        },
        "csv_output_name": csv_output_name,
        "render_plan": family_preset.get("render_plan") or {},
        "listing_inputs": {
            "listing_title": listing_title,
            "primary_keyword": clean_text((seo.get("core_keywords") or [niche_keyword])[0] if (seo.get("core_keywords") or [niche_keyword]) else niche_keyword),
            "secondary_keywords": [clean_text(item) for item in (seo.get("angles") or [])[:10]],
            "tags": [clean_text(item) for item in listing_defaults.get("tags") or [] if clean_text(item)],
            "category": clean_text(listing_defaults.get("category")),
            "format_hint": clean_text(listing_defaults.get("format_hint")),
            "price_anchor": price_anchor,
        },
        "design_hints": {
            "style": clean_text(design.get("style")),
            "layout": [clean_text(item) for item in design.get("layout") or []],
            "accessibility": [clean_text(item) for item in design.get("accessibility") or []],
        },
        "provenance": {
            "source_type": "winner_and_sku_task",
            "niche_id": niche_id,
            "winner_id": clean_text(winner.get("niche_id") or niche_id),
            "sku_task_id": clean_text(sku_task.get("task_id")),
        },
    }

    overrides = load_niche_overrides()
    niche_override_all = overrides.get(niche_id, {}) if isinstance(overrides, dict) else {}
    kind_override = niche_override_all.get(kind, {}) if isinstance(niche_override_all, dict) else {}
    if isinstance(kind_override, dict) and kind_override:
        spec = deep_merge(spec, kind_override)
        listing_title_template = clean_text(kind_override.get("listing_title_template"))
        if listing_title_template:
            spec.setdefault("listing_inputs", {})["listing_title"] = listing_title_template
        seo_boost_keywords = kind_override.get("seo_boost_keywords") or []
        if seo_boost_keywords:
            existing_keywords = spec.setdefault("listing_inputs", {}).get("secondary_keywords") or []
            spec["listing_inputs"]["secondary_keywords"] = existing_keywords + [
                clean_text(item) for item in seo_boost_keywords if clean_text(item)
            ]

    return spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_path", nargs="?")
    parser.add_argument("--niche-id")
    parser.add_argument("--winner-path")
    parser.add_argument("--sku-task-path")
    parser.add_argument("--product-kind", choices=["checklist", "planner", "spreadsheet", "notion_companion"])
    args = parser.parse_args()

    if args.niche_id or args.winner_path or args.sku_task_path:
        if args.niche_id:
            inferred_winner_path, inferred_sku_task_path, validated_niche_path = infer_artifact_paths(args.niche_id)
            winner_path = Path(args.winner_path) if args.winner_path else inferred_winner_path
            sku_task_path = Path(args.sku_task_path) if args.sku_task_path else inferred_sku_task_path
        else:
            winner_path = Path(args.winner_path) if args.winner_path else None
            sku_task_path = Path(args.sku_task_path) if args.sku_task_path else None
            validated_niche_path = None
        if validated_niche_path and (not winner_path.exists() or not sku_task_path.exists()):
            validated_payload = read_json(validated_niche_path)
            winner = {
                "niche_id": clean_text(validated_payload.get("niche_id") or args.niche_id),
                "niche_keyword": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or args.niche_id),
                "thesis": validated_payload.get("thesis") or {},
                "design_guidelines": validated_payload.get("design_guidelines") or {},
                "seo_and_copy_hints": validated_payload.get("seo_and_copy_hints") or {},
                "validation_metrics": validated_payload.get("validation_metrics") or {},
                "recommended_sku_cluster": {"core_skus": [{"slug": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or args.niche_id)}]},
            }
            sku_task = {
                "task_id": f"validated_{clean_text(validated_payload.get('niche_id') or args.niche_id)}",
                "niche_id": clean_text(validated_payload.get("niche_id") or args.niche_id),
                "niche_keyword": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or args.niche_id),
                "cluster": {"core_skus": [{"slug": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or args.niche_id)}]},
            }
            winner_path = validated_niche_path
            sku_task_path = validated_niche_path
        else:
            if winner_path is None or sku_task_path is None:
                raise ValueError("winner_path and sku_task_path are required for source-driven spec compilation")
            winner = read_json(winner_path)
            sku_task = read_json(sku_task_path)
        spec = compile_spec_from_sources(
            winner=winner,
            sku_task=sku_task,
            winner_path=winner_path,
            sku_task_path=sku_task_path,
            validated_niche_path=validated_niche_path,
            product_kind=args.product_kind,
        )
    else:
        if not args.config_path:
            raise ValueError("config_path is required when source-driven flags are not provided")
        config = read_json(Path(args.config_path))
        spec = compile_spec(config)
    out_path = OUTPUTS_DIR / spec["product_slug"] / "digital_product_spec.json"
    write_json(out_path, spec)
    print(out_path)


if __name__ == "__main__":
    main()
