from __future__ import annotations

import argparse

from common import OUTPUTS_DIR, clean_text, read_json, write_json


def compile_listing_packet(spec: dict, manifest: dict, channel: str) -> dict:
    deliverable_files = [a["path"] for a in manifest["artifacts"] if a["artifact_type"] == "deliverable_pdf" and a["exists"]]
    preview_files = [a["path"] for a in manifest["artifacts"] if a["artifact_type"] in {"master_png", "mockup_png"} and a["exists"]]
    benefits = [
        spec["benefit_statement"],
        f"Built for {spec['intended_user']}",
        spec["usage_outcome"],
    ]
    features = [
        f"Product family: {spec['product_family']}",
        f"Layout profile: {spec['layout_profile']}",
        f"Theme: {spec['theme']}",
    ] + [f"Module: {m}" for m in spec.get("content_modules", [])[:5]]

    return {
        "packet_version": "v1",
        "packet_id": f"{spec['product_slug']}-{channel}",
        "product_slug": spec["product_slug"],
        "channel": channel,
        "digital_product_spec_path": str(OUTPUTS_DIR / spec["product_slug"] / "digital_product_spec.json"),
        "artifact_manifest_path": str(OUTPUTS_DIR / spec["product_slug"] / "artifact_manifest.json"),
        "validated_niche_path": None,
        "winner_path": None,
        "sku_task_path": None,
        "listing_title": clean_text(f"{spec['product_name'].replace('_', ' ').title()} | Digital Download"),
        "buyer_promise": spec["benefit_statement"],
        "short_description": clean_text(spec["usage_outcome"]),
        "long_description": clean_text(
            f"{spec['product_name']} helps solve: {spec['user_problem']}. "
            f"Buyer receives a structured digital product with clear sections and ready-to-use files."
        ),
        "feature_bullets": features[:8],
        "benefit_bullets": benefits[:6],
        "primary_keyword": spec["product_slug"].replace("-", " "),
        "secondary_keywords": spec.get("content_modules", [])[:10],
        "tags": [spec["product_slug"].replace("-", " "), spec["product_family"], spec["product_type"]][:13],
        "category": spec["product_family"],
        "deliverable_files": deliverable_files,
        "preview_files": preview_files,
        "thumbnail_files": preview_files[:1],
        "price_anchor": None,
        "license_note": "Personal use unless otherwise stated.",
        "what_is_included": spec.get("required_artifacts", []),
        "manual_steps": [
            "Review listing title and description",
            "Check cover image order",
            "Upload files to marketplace",
            "Confirm price and category"
        ],
        "review_checks": [
            "No empty bullets",
            "Required files attached",
            "Value proposition is clear"
        ],
        "publish_status": "draft"
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
