from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import OUTPUTS_DIR, read_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay mode — shows current product state without rebuilding artifacts."
    )
    parser.add_argument(
        "--product-slug",
        required=True,
        help="Real product_slug, e.g. budget-spreadsheet",
    )
    args = parser.parse_args()

    base = OUTPUTS_DIR / args.product_slug
    if not base.exists():
        print(f"ERROR: Output directory not found: {base}")
        raise SystemExit(1)

    artifacts = [str(path.relative_to(base)) for path in sorted(base.glob("*")) if path.is_file()]

    qa_summary: dict = {}
    manifest_path = base / "artifact_manifest.json"
    if manifest_path.exists():
        try:
            manifest = read_json(manifest_path)
            qa_summary = manifest.get("qa") or {}
        except Exception as exc:  # pragma: no cover - defensive fallback
            qa_summary = {"error": str(exc)}

    packet: dict = {}
    packet_path = base / "listing_packet_etsy.json"
    if packet_path.exists():
        try:
            packet = read_json(packet_path)
        except Exception as exc:  # pragma: no cover - defensive fallback
            packet = {"error": str(exc)}

    packet_summary = {
        "title": packet.get("title"),
        "description_preview": (
            packet.get("description", "")[:150] + "..."
            if packet.get("description")
            else None
        ),
        "new_fields_present": [
            key
            for key in packet
            if key.startswith("description_")
            or key in {"photo_sequence_hint", "thumbnail_angle", "upload_order_hint"}
        ],
    }

    publish_packet_paths = [
        str(base / filename)
        for filename in [
            "listing_packet_etsy.json",
            "digital_product_spec.json",
            "artifact_manifest.json",
        ]
        if (base / filename).exists()
    ]

    output = {
        "product_slug": args.product_slug,
        "artifacts": artifacts,
        "qa_summary": qa_summary,
        "listing_packet_summary": packet_summary,
        "publish_packet_paths": publish_packet_paths,
    }
    print(json.dumps(output, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
