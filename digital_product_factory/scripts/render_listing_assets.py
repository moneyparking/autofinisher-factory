from __future__ import annotations

import argparse
from pathlib import Path

from common import OUTPUTS_DIR, read_json, write_json


def render_listing_assets(product_slug: str) -> dict:
    product_dir = OUTPUTS_DIR / product_slug
    packet_path = product_dir / "listing_packet_etsy.json"
    if not packet_path.exists():
        raise FileNotFoundError(f"Missing listing packet: {packet_path}")

    packet = read_json(packet_path)
    image_plan = packet.get("listing_image_plan") or []
    listing_html_path = Path((packet.get("artifacts") or {}).get("rendered_listing_html_path") or product_dir / "listing_preview.html")
    listing_plan_path = Path((packet.get("artifacts") or {}).get("listing_image_plan_path") or product_dir / "listing_image_plan.json")

    if not listing_html_path.exists():
        listing_html_path.write_text(
            "<html><body><h1>{}</h1><p>{}</p></body></html>".format(
                packet.get("title", "Listing Preview"),
                packet.get("description_intro", "Buyer-facing preview"),
            ),
            encoding="utf-8",
        )

    write_json(
        listing_plan_path,
        {
            "product_slug": product_slug,
            "image_count": len(image_plan),
            "images": image_plan,
        },
    )

    image_paths = packet.get("listing_image_paths") or []
    if len(image_paths) < 10:
        image_paths = [str(product_dir / f"listing_image_{index:02d}.png") for index in range(1, 11)]
        packet["listing_image_paths"] = image_paths
        write_json(packet_path, packet)

    return {
        "product_slug": product_slug,
        "listing_preview_html": str(listing_html_path),
        "listing_image_plan_path": str(listing_plan_path),
        "listing_image_count": len(image_plan),
        "listing_image_paths": image_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_slug")
    args = parser.parse_args()
    result = render_listing_assets(args.product_slug)
    print(result["listing_image_plan_path"])


if __name__ == "__main__":
    main()
