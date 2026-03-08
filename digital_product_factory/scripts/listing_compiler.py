from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import OUTPUTS_DIR, clean_text, read_json, write_json

BANNED_COPY_PHRASES = {
    "buyer receives",
    "product family",
    "artifact",
    "etsy-ready",
    "etsy ready",
    "ready for etsy upload",
    "listing packet",
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = clean_text(item)
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _title_case_phrase(value: str) -> str:
    text = clean_text(value).replace("_", " ").replace("-", " ")
    words = [part.capitalize() if part.islower() else part for part in text.split()]
    return clean_text(" ".join(words))


def _trim_phrase(value: str, limit: int = 20) -> str:
    text = clean_text(value)
    if len(text) <= limit:
        return text
    trimmed = text[:limit].rsplit(" ", 1)[0].strip()
    return trimmed or text[:limit].strip()


def _distinct_phrase(base: str, candidate: str) -> str:
    base_words = set(re.findall(r"[a-z0-9]+", clean_text(base).lower()))
    candidate_words = set(re.findall(r"[a-z0-9]+", clean_text(candidate).lower()))
    if not candidate_words or candidate_words.issubset(base_words):
        return ""
    return clean_text(candidate)


def _sanitize_buyer_copy(value: str, fallback: str = "") -> str:
    text = clean_text(value)
    lowered = text.lower()
    if any(phrase in lowered for phrase in BANNED_COPY_PHRASES):
        return clean_text(fallback)
    return text



def _product_label(spec: dict) -> str:
    product_name = clean_text(spec.get("product_name"))
    if product_name:
        return product_name
    return _title_case_phrase(spec.get("product_slug") or "Digital Download")


def _compatibility_text(spec: dict, format_hint: str) -> str:
    delivery_format = clean_text(spec.get("delivery_format"))
    kind = clean_text(spec.get("product_kind"))
    if kind == "spreadsheet":
        return clean_text(format_hint or "Works with spreadsheet apps that open .xlsx files and includes a PDF preview for reference.")
    if kind == "notion_companion":
        return clean_text(format_hint or "Designed for buyers using Notion and delivered as a PDF companion guide with setup help.")
    return clean_text(format_hint or f"Delivered as a digital {kind or 'download'} file for instant access after purchase.")


def _build_title(spec: dict, listing_inputs: dict) -> str:
    product_label = _product_label(spec)
    primary_keyword = _sanitize_buyer_copy(clean_text(listing_inputs.get("primary_keyword")))
    audience = _sanitize_buyer_copy(clean_text(spec.get("intended_user")), "busy buyers")
    outcome = _sanitize_buyer_copy(clean_text(spec.get("usage_outcome")))
    title_parts = [product_label]
    keyword_part = _distinct_phrase(product_label, primary_keyword)
    if keyword_part:
        title_parts.append(keyword_part)
    outcome_part = _distinct_phrase(product_label, outcome)
    if outcome_part:
        title_parts.append(outcome_part)
    elif audience:
        title_parts.append(f"for {audience}")
    title_parts.append("Instant Download")
    title = " | ".join(_dedupe(title_parts[:4]))
    return clean_text(title)


def _build_tags(spec: dict, listing_inputs: dict, title: str) -> list[str]:
    product_label = _product_label(spec)
    product_kind = clean_text(spec.get("product_kind")).replace("_", " ")
    primary_keyword = clean_text(listing_inputs.get("primary_keyword"))
    modules = [_title_case_phrase(item) for item in spec.get("content_modules") or []]
    kind_specific: list[str]
    if product_kind == "spreadsheet":
        kind_specific = [
            "budget spreadsheet",
            "monthly budget",
            "finance tracker",
            "money planner",
            "expense tracker",
            "savings tracker",
            "cash flow sheet",
        ]
    elif product_kind == "planner":
        kind_specific = [
            "digital planner",
            "printable planner",
            "daily planner",
            "weekly planner",
            "monthly planner",
            "organizer pages",
            "planner bundle",
        ]
    elif product_kind == "checklist":
        kind_specific = [
            "printable checklist",
            "cleaning checklist",
            "home routine",
            "task tracker",
            "adhd checklist",
            "weekly reset",
            "household planner",
        ]
    else:
        kind_specific = [
            "notion template",
            "business planner",
            "client tracker",
            "project tracker",
            "workflow system",
            "digital organizer",
            "productivity tool",
        ]
    candidates = _dedupe(
        [
            *[clean_text(tag) for tag in listing_inputs.get("tags") or []],
            primary_keyword,
            product_label,
            title,
            *modules,
            *kind_specific,
            _title_case_phrase(spec.get("product_type") or "digital download"),
            "instant download",
            "digital download",
            clean_text(spec.get("layout_profile")).replace("_", " "),
        ]
    )
    tags: list[str] = []
    for candidate in candidates:
        value = _trim_phrase(candidate.lower())
        if not value:
            continue
        if value in tags:
            continue
        tags.append(value)
        if len(tags) == 13:
            return tags
    fallback_seed = [product_kind or "digital", "template", "planner", "download", "printable"]
    index = 1
    while len(tags) < 13:
        fallback = _trim_phrase(f"{fallback_seed[(index - 1) % len(fallback_seed)]} {index}")
        if fallback not in tags:
            tags.append(fallback)
        index += 1
    return tags[:13]


def _build_feature_bullets(spec: dict, format_hint: str) -> list[str]:
    kind = clean_text(spec.get("product_kind"))
    bullets = [
        f"Instant digital download with {kind.replace('_', ' ')} files ready to open right away",
        clean_text(spec.get("benefit_statement")) or "Designed to save setup time and make the workflow easier to follow",
        _compatibility_text(spec, format_hint),
    ]
    if kind == "planner":
        structure = spec.get("planner_structure") or {}
        bullets.extend(
            [
                clean_text(f"Includes {structure.get('monthly_pages') or 0} monthly pages and {structure.get('weekly_pages') or 0} weekly pages"),
                clean_text(f"Includes {structure.get('daily_pages') or 0} daily pages for detailed planning"),
            ]
        )
    elif kind == "spreadsheet":
        required_sheets = ", ".join((spec.get("qa_thresholds") or {}).get("must_have_sheets") or [])
        if required_sheets:
            bullets.append(f"Workbook tabs include {required_sheets}")
    elif kind == "notion_companion":
        bullets.append("Setup guide and workflow checklist included for a smoother first-time setup")
    else:
        bullets.append("Simple checklist pages make routines easier to follow and repeat")
    return _dedupe(bullets)[:8]


def _build_benefit_bullets(spec: dict) -> list[str]:
    audience = _sanitize_buyer_copy(clean_text(spec.get("intended_user") or "busy buyers"), "busy buyers")
    problem = _sanitize_buyer_copy(clean_text(spec.get("user_problem") or "reduce setup time and decision fatigue"), "reduce setup time and decision fatigue")
    outcome = _sanitize_buyer_copy(clean_text(spec.get("usage_outcome") or "start using the product in minutes"), "start using the product in minutes")
    bullets = [
        _sanitize_buyer_copy(clean_text(spec.get("benefit_statement") or "A practical digital tool designed to feel easy to use from day one"), "A practical digital tool designed to feel easy to use from day one"),
        f"Made for {audience}",
        f"Created to help with {problem}",
        outcome,
    ]
    return _dedupe(bullets)[:6]


def _build_what_is_included(spec: dict, format_hint: str, deliverable_files: list[str], preview_files: list[str]) -> list[str]:
    kind = clean_text(spec.get("product_kind"))
    main_item = _product_label(spec)
    deliverable_label = "Printable PDF"
    if kind == "spreadsheet":
        deliverable_label = "Editable spreadsheet workbook"
    elif kind == "notion_companion":
        deliverable_label = "PDF setup guide and companion pages"
    included = [
        main_item,
        deliverable_label,
        f"{len(deliverable_files)} downloadable file(s)",
        f"{len(preview_files)} preview asset(s)",
        format_hint or "Instant digital download",
    ]
    return _dedupe(included)


def _build_seo_aeo(spec: dict, format_hint: str, what_is_included: list[str]) -> dict:
    audience = clean_text(spec.get("intended_user") or "buyers who want an easy-to-use digital tool")
    product_label = _product_label(spec)
    return {
        "what_is_it": clean_text(f"{product_label} is a digital download designed to be useful immediately after purchase."),
        "who_is_it_for": clean_text(f"Best for {audience}."),
        "what_do_i_get": clean_text("Included: " + ", ".join(what_is_included[:4]) + "."),
        "how_do_i_use_it": clean_text(f"Download the files, open them in the recommended format, and start with the first page or dashboard right away."),
        "compatibility": _compatibility_text(spec, format_hint),
    }


def _build_listing_image_plan(spec: dict, packet: dict) -> list[dict]:
    product_label = _product_label(spec)
    promise = clean_text(packet.get("buyer_promise") or packet.get("short_description"))
    compatibility = clean_text(packet.get("description_compatibility"))
    included = packet.get("what_is_included") or []
    return [
        {"slot": 1, "headline": product_label, "purpose": "thumbnail", "detail": promise or "Clear hero cover with the main product promise", "asset_hint": "master.png"},
        {"slot": 2, "headline": "What It Helps You Do", "purpose": "benefit", "detail": clean_text(packet.get("short_description") or "Show the main result the buyer can expect"), "asset_hint": "mockup.png"},
        {"slot": 3, "headline": "What Is Included", "purpose": "included", "detail": ", ".join(included[:4]), "asset_hint": "preview.pdf page 1"},
        {"slot": 4, "headline": "How It Works", "purpose": "usage", "detail": clean_text(packet.get("description_how_it_works")), "asset_hint": "preview.pdf page 2"},
        {"slot": 5, "headline": "Compatibility", "purpose": "compatibility", "detail": compatibility, "asset_hint": "listing_preview.html compatibility block"},
        {"slot": 6, "headline": "Preview The Layout", "purpose": "layout", "detail": "Show a clean page, dashboard, or worksheet spread.", "asset_hint": "preview.pdf page 3"},
        {"slot": 7, "headline": "Designed For Real Use", "purpose": "audience", "detail": clean_text((packet.get("seo_aeo") or {}).get("who_is_it_for") or "Show the buyer type and use case."), "asset_hint": "listing_preview.html audience block"},
        {"slot": 8, "headline": "Inside The Download", "purpose": "deliverables", "detail": clean_text(packet.get("description_what_youll_get")), "asset_hint": "listing_preview.html included block"},
        {"slot": 9, "headline": "Instant Digital Download", "purpose": "terms", "detail": clean_text(packet.get("description_terms")), "asset_hint": "listing_preview.html terms block"},
        {"slot": 10, "headline": "Ready To Start Today", "purpose": "cta", "detail": "Use the final image as a concise call to action with the best outcome and file format reminder.", "asset_hint": "listing_preview.html final CTA"},
    ]


def _build_listing_html(packet: dict) -> str:
    image_plan = packet.get("listing_image_plan") or []
    seo_aeo = packet.get("seo_aeo") or {}
    image_cards = "\n".join(
        [
            (
                f"<section class='image-card'><h3>Image {item['slot']}: {item['headline']}</h3>"
                f"<p><strong>Purpose:</strong> {item['purpose']}</p>"
                f"<p>{item['detail']}</p><p class='hint'>{item['asset_hint']}</p></section>"
            )
            for item in image_plan
        ]
    )
    included = "".join([f"<li>{item}</li>" for item in packet.get("what_is_included") or []])
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <title>{packet['title']}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; background: #f8fafc; }}
    .wrap {{ max-width: 980px; margin: 0 auto; }}
    .hero, .card, .image-card {{ background: #ffffff; border-radius: 16px; padding: 24px; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08); }}
    h1, h2, h3 {{ margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }}
    .hint {{ color: #64748b; font-size: 14px; }}
    ul {{ padding-left: 20px; }}
  </style>
</head>
<body>
  <div class='wrap'>
    <section class='hero'>
      <h1>{packet['title']}</h1>
      <p>{packet['description_intro']}</p>
      <p><strong>Best for:</strong> {seo_aeo.get('who_is_it_for', '')}</p>
    </section>
    <div class='grid'>
      <section class='card'><h2>What it is</h2><p>{seo_aeo.get('what_is_it', '')}</p></section>
      <section class='card'><h2>How to use it</h2><p>{seo_aeo.get('how_do_i_use_it', '')}</p></section>
      <section class='card'><h2>Compatibility</h2><p>{seo_aeo.get('compatibility', '')}</p></section>
      <section class='card'><h2>What you get</h2><ul>{included}</ul></section>
    </div>
    {image_cards}
  </div>
</body>
</html>
"""


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
    title = _build_title(spec, listing_inputs)
    tags = _build_tags(spec, listing_inputs, title)
    what_is_included = _build_what_is_included(spec, format_hint, deliverable_files, preview_files)
    seo_aeo = _build_seo_aeo(spec, format_hint, what_is_included)
    feature_bullets = _build_feature_bullets(spec, format_hint)
    benefit_bullets = _build_benefit_bullets(spec)
    buyer_promise = _sanitize_buyer_copy(clean_text(spec.get("benefit_statement") or benefit_bullets[0]), benefit_bullets[0])
    short_description = _sanitize_buyer_copy(clean_text(spec.get("usage_outcome") or seo_aeo["how_do_i_use_it"]), seo_aeo["how_do_i_use_it"])
    long_description = clean_text(
        f"{seo_aeo['what_is_it']} {seo_aeo['who_is_it_for']} {seo_aeo['what_do_i_get']} {seo_aeo['how_do_i_use_it']}"
    )
    primary_deliverable_path = deliverable_files[0] if deliverable_files else str(product_dir / "deliverable.pdf")
    if spec.get("product_kind") == "spreadsheet":
        primary_deliverable_path = artifact_lookup.get("deliverable_xlsx", primary_deliverable_path)
    listing_html_path = product_dir / "listing_preview.html"
    listing_plan_path = product_dir / "listing_image_plan.json"
    listing_image_paths = [str(product_dir / f"listing_image_{index:02d}.png") for index in range(1, 11)]
    artifacts = {
        "deliverable_path": primary_deliverable_path,
        "preview_path": artifact_lookup.get("preview_pdf", str(product_dir / "preview.pdf")),
        "master_path": artifact_lookup.get("master_png", str(product_dir / "master.png")),
        "mockup_path": artifact_lookup.get("mockup_png", str(product_dir / "mockup.png")),
        "seo_path": artifact_lookup.get("seo_txt", str(product_dir / "SEO.txt")),
        "source_csv_path": artifact_lookup.get("source_csv", str(product_dir / "source_rows.csv")),
        "rendered_listing_html_path": str(listing_html_path),
        "listing_image_plan_path": str(listing_plan_path),
        "extra_assets": [
            path
            for artifact_type, path in artifact_lookup.items()
            if artifact_type not in {"deliverable_pdf", "deliverable_xlsx", "preview_pdf", "master_png", "mockup_png", "seo_txt", "source_csv"}
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

    packet = {
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
        "listing_title": title,
        "title": title,
        "buyer_promise": buyer_promise,
        "short_description": short_description,
        "long_description": long_description,
        "description": long_description,
        "feature_bullets": feature_bullets,
        "benefit_bullets": benefit_bullets,
        "primary_keyword": clean_text(listing_inputs.get("primary_keyword") or tags[0]) or None,
        "secondary_keywords": _dedupe([clean_text(item) for item in listing_inputs.get("secondary_keywords") or spec.get("content_modules", [])[:10] if clean_text(item)]),
        "tags": tags,
        "category": clean_text(listing_inputs.get("category") or spec["product_family"]) or None,
        "price_anchor": listing_inputs.get("price_anchor"),
        "format_hint": format_hint,
        "deliverable_files": deliverable_files,
        "preview_files": preview_files,
        "thumbnail_files": preview_files[:2],
        "license_note": "Personal use unless otherwise stated.",
        "license_hint": "Personal use unless otherwise stated.",
        "what_is_included": what_is_included,
        "artifacts": artifacts,
        "source_provenance": source_provenance,
        "qa_summary": qa_summary,
        "manual_steps": [
            "Review the title and the first image headline for readability",
            "Upload the downloadable file first, then attach preview assets",
            "Use the image plan to build all 10 listing images in order",
            "Check tags, compatibility notes, and personal-use terms before publish",
        ],
        "review_checks": [
            "No internal factory language appears in buyer-facing copy",
            "Exactly 13 tags are present",
            "All 10 listing image slots are planned",
            "SEO and AEO sections clearly answer what it is, who it is for, what is included, how to use it, and compatibility",
        ],
        "publish_status": "draft",
        "description_intro": clean_text(f"{buyer_promise} Instant digital download for buyers who want a practical result without a long setup."),
        "description_whats_included": "\n".join([f"• {item}" for item in what_is_included]),
        "description_how_it_works": clean_text(f"1. Download instantly → 2. Open in the recommended format → 3. Start with the first page, dashboard, or setup step right away."),
        "description_what_youll_get": clean_text(f"You will get {len(deliverable_files)} downloadable file(s) and a 10-image listing plan, plus preview assets to show the product clearly."),
        "description_terms": "Instant digital download. Personal use only. No commercial resale or redistribution.",
        "description_compatibility": seo_aeo["compatibility"],
        "photo_sequence_hint": "1: cover promise → 2: main benefit → 3: what is included → 4: how it works → 5: compatibility → 6-10: real previews and CTA",
        "thumbnail_angle": "front_cover",
        "upload_order_hint": "Upload deliverable first, then preview PDF and image assets, then finish with the thumbnail image.",
        "seo_aeo": seo_aeo,
        "listing_image_paths": listing_image_paths,
    }
    packet["listing_image_plan"] = _build_listing_image_plan(spec, packet)
    packet["market_readiness"] = {
        "buyer_facing_copy": not any(phrase in long_description.lower() for phrase in BANNED_COPY_PHRASES),
        "seo_aeo_complete": all(clean_text(value) for value in seo_aeo.values()),
        "title_readable": len(re.findall(r"[A-Za-z0-9]+", title)) >= 4,
        "tags_ready": len(tags) == 13,
        "image_plan_ready": len(packet["listing_image_plan"]) == 10,
    }
    return packet


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
    write_json(product_dir / "listing_image_plan.json", {"product_slug": args.product_slug, "images": packet["listing_image_plan"]})
    (product_dir / "listing_preview.html").write_text(_build_listing_html(packet), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
