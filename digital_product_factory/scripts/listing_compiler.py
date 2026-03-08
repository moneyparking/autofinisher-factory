from __future__ import annotations

import argparse
from pathlib import Path

from common import OUTPUTS_DIR, clean_text, read_json, write_json


def compile_listing_packet(spec: dict, manifest: dict, channel: str) -> dict:
    listing_inputs = spec.get("listing_inputs") or {}
    source_assets = spec.get("source_assets") or {}
    deliverable_files = [
        a["path"]
        for a in manifest["artifacts"]
        if a["artifact_type"] in {"deliverable_pdf", "deliverable_xlsx"} and a["exists"]
    ]
    preview_files = [
        a["path"]
        for a in manifest["artifacts"]
        if a["artifact_type"] in {"master_png", "mockup_png", "preview_pdf"} and a["exists"]
    ]
    artifact_lookup = {item["artifact_type"]: item["path"] for item in manifest.get("artifacts", []) if item.get("exists")}
    product_dir = OUTPUTS_DIR / spec["product_slug"]
    format_hint = clean_text(listing_inputs.get("format_hint"))
    benefits = [
        clean_text(spec.get("benefit_statement")),
        clean_text(f"Built for {spec['intended_user']}"),
        clean_text(spec.get("usage_outcome")),
    ]
    features = [
        clean_text(f"Product family: {spec['product_family']}"),
        clean_text(f"Layout profile: {spec['layout_profile']}"),
        clean_text(f"Product kind: {spec.get('product_kind', spec['product_type'])}"),
    ] + [clean_text(f"Module: {m}") for m in spec.get("content_modules", [])[:5]]
    if spec.get("product_kind") == "planner":
        structure = spec.get("planner_structure") or {}
        features.extend([
            clean_text(f"Year: {spec.get('year') or ''}"),
            clean_text(f"Daily pages: {structure.get('daily_pages') or ''}"),
            clean_text(f"Monthly pages: {structure.get('monthly_pages') or ''}"),
            clean_text(f"Weekly pages: {structure.get('weekly_pages') or ''}"),
            clean_text(f"Hyperlinked: {'Yes' if spec.get('hyperlinked') else 'No'}"),
        ])
    if spec.get("product_kind") == "spreadsheet":
        thresholds = spec.get("qa_thresholds") or {}
        features.extend([
            clean_text(f"Required sheets: {', '.join(thresholds.get('must_have_sheets') or [])}"),
            clean_text(f"Delivery format: {spec.get('delivery_format') or ''}"),
            clean_text(f"Spreadsheet-ready: Yes"),
        ])
    if spec.get("product_kind") == "notion_companion":
        features.extend([
            clean_text(f"Delivery format: {spec.get('delivery_format') or ''}"),
            clean_text("Notion-ready: Yes"),
            clean_text("Buyer onboarding guide included"),
        ])
    long_description = clean_text(
        f"{spec['product_name']} helps solve: {spec['user_problem']}. "
        f"Buyer receives a structured digital product with clear sections, printable files, and preview assets ready for Etsy upload."
    )
    what_is_included = [
        clean_text(spec.get("product_name")),
        "Printable PDF deliverable",
        "Preview cover assets",
        "SEO helper text",
    ]
    if spec.get("product_kind") in {"planner", "spreadsheet", "notion_companion"}:
        if format_hint:
            what_is_included.append(format_hint)
    if spec.get("product_kind") == "spreadsheet":
        what_is_included[1] = "Spreadsheet workbook + PDF preview"
    if spec.get("product_kind") == "notion_companion":
        what_is_included[1] = "PDF setup guide + companion checklist"

    listing_title = clean_text(listing_inputs.get("listing_title") or f"{spec['product_name']} | Digital Download")
    description = long_description
    tags = [clean_text(item) for item in listing_inputs.get("tags") or [spec["product_slug"].replace("-", " "), spec["product_family"], spec["product_type"]] if clean_text(item)][:13]
    category = clean_text(listing_inputs.get("category") or spec["product_family"]) or None
    price_anchor = listing_inputs.get("price_anchor")
    license_note = "Personal use unless otherwise stated."
    primary_deliverable_path = deliverable_files[0] if deliverable_files else str(product_dir / "deliverable.pdf")
    if spec.get("product_kind") == "spreadsheet":
        primary_deliverable_path = artifact_lookup.get("deliverable_xlsx", primary_deliverable_path)
    artifacts = {
        "deliverable_path": primary_deliverable_path,
        "preview_path": artifact_lookup.get("preview_pdf", str(product_dir / "preview.pdf")),
        "master_path": artifact_lookup.get("master_png", str(product_dir / "master.png")),
        "mockup_path": artifact_lookup.get("mockup_png", str(product_dir / "mockup.png")),
        "seo_path": artifact_lookup.get("seo_txt", str(product_dir / "SEO.txt")),
        "source_csv_path": artifact_lookup.get("source_csv", str(product_dir / "source_rows.csv")),
        "extra_assets": [
            path for artifact_type, path in artifact_lookup.items() if artifact_type not in {"deliverable_pdf", "deliverable_xlsx", "preview_pdf", "master_png", "mockup_png", "seo_txt", "source_csv"}
        ],
    }
    source_provenance = {
        "niche_id": clean_text(spec.get("niche_id") or Path(str(source_assets.get("winner_path") or "")).stem.replace("sku_task_", "")) or spec["product_slug"],
        "winner_path": source_assets.get("winner_path") or "",
        "sku_task_path": source_assets.get("sku_task_path") or "",
        "validated_niche_path": source_assets.get("validated_niche_path") or "",
    }
    qa_summary = {
        "checks_passed": bool((manifest.get("qa") or {}).get("checks_passed", False)),
        "missing_files": [Path(item["path"]).name for item in manifest.get("artifacts", []) if not item.get("exists")],
        "broken_links": int((manifest.get("qa") or {}).get("broken_links", 0)),
    }

    return {
        "packet_version": "v1",
        "packet_id": f"{spec['product_slug']}-{channel}",
        "product_slug": spec["product_slug"],
        "product_kind": spec.get("product_kind", spec["product_type"]),
        "product_family": spec["product_family"],
        "channel": channel,
        "is_digital": True,
        "type": "download",
        "digital_product_spec_path": str(product_dir / "digital_product_spec.json"),
        "artifact_manifest_path": str(product_dir / "artifact_manifest.json"),
        "validated_niche_path": source_assets.get("validated_niche_path"),
        "winner_path": source_assets.get("winner_path"),
        "sku_task_path": source_assets.get("sku_task_path"),
        "listing_title": listing_title,
        "title": listing_title,
        "buyer_promise": clean_text(spec.get("benefit_statement")),
        "short_description": clean_text(spec.get("usage_outcome")),
        "long_description": long_description,
        "description": description,
        "feature_bullets": [item for item in features[:8] if item],
        "benefit_bullets": [item for item in benefits[:6] if item],
        "primary_keyword": clean_text(listing_inputs.get("primary_keyword") or spec["product_slug"].replace("-", " ")) or None,
        "secondary_keywords": [clean_text(item) for item in listing_inputs.get("secondary_keywords") or spec.get("content_modules", [])[:10] if clean_text(item)],
        "tags": tags,
        "category": category,
        "price_anchor": price_anchor,
        "format_hint": format_hint,
        "deliverable_files": deliverable_files,
        "preview_files": preview_files,
        "thumbnail_files": preview_files[:2],
        "license_note": license_note,
        "license_hint": license_note,
        "what_is_included": [item for item in what_is_included if item],
        "artifacts": artifacts,
        "source_provenance": source_provenance,
        "qa_summary": qa_summary,
        "manual_steps": [
            "Review Etsy title and description",
            "Confirm preview image order and thumbnail",
            "Upload deliverable files and preview assets",
            "Set price, category, and tags before publish",
        ],
        "review_checks": [
            "No empty bullets",
            "Required files attached",
            "Value proposition is clear",
            "Spec provenance paths are populated",
        ],
        "publish_status": "draft",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_slug")
    parser.add_argument("--channel", default="etsy")
    args = parser.parse_args()

    product_dir = OUTPUTS_DIR / args.product_slug
    spec = read_json(product_dir / "digital_product_spec.json")
    manifest = read_json(product_dir / "artifact_manifest.json")
    packet = compile_listing_packet(spec, manifest, args.channel)
    out_path = product_dir / f"listing_packet_{args.channel}.json"
    write_json(out_path, packet)
    print(out_path)


if __name__ == "__main__":
    main()
