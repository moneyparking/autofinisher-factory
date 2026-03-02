#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/agent/autofinisher-factory")
PAYLOADS_DIR = ROOT / "render_engine" / "payloads"


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return text or "poster"


def build_payload(keyword: str, template_id: str) -> dict:
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if template_id == "swiss_brutalism":
        headline = keyword.upper()
        return {
            "schema_version": "1.0",
            "template_id": "swiss_brutalism",
            "template_version": "1.0.0",
            "render_mode": "master",
            "content": {
                "headline": headline,
                "subheadline": "Strict editorial poster for systems, startup and AI interiors",
                "kicker": "AUTOFINISHER SWISS SERIES",
                "body": "Deterministic HTML/CSS/SVG render path with modular grid and metadata rail architecture.",
                "footer_left": "EDITION 02",
                "footer_center": "SWISS BRUTALISM / PNG MASTER / DISPLAY PRINT",
                "footer_right": f"CODE {slugify(keyword).upper()[:12]}"
            },
            "style": {
                "family": "swiss_brutalism",
                "palette_id": "bone_signal",
                "font_pack": "inter_space_mono",
                "background_mode": "paper_flat",
                "texture_pack": [],
                "accent_mode": "signal_band",
                "density": "medium",
                "alignment": "left",
                "case_mode": "upper",
                "grid_mode": "modular_12",
                "spacing_preset": "editorial_rail",
                "metadata_color": "ink_neutral"
            },
            "layout": {
                "headline_max_lines": 4,
                "safe_margin_ratio": 0.06,
                "vertical_anchor": "center",
                "headline_width_ratio": 0.72,
                "overflow_strategy": "scale_down_only",
                "min_font_px": 78,
                "max_font_px": 300,
                "metadata_rail_width_ratio": 0.15
            },
            "output": {
                "profile_id": "master_4k_vertical",
                "width": 2160,
                "height": 3840,
                "format": "png",
                "dpi": 300,
                "background": "opaque"
            },
            "metadata": {
                "keyword": f"{keyword} poster",
                "collection_id": "systems_drop_01",
                "edition_id": "edition_02",
                "source": "factory_pipeline",
                "created_at": created_at
            }
        }

    return {
        "schema_version": "1.0",
        "template_id": "retro_neon_grid",
        "template_version": "1.0.0",
        "render_mode": "master",
        "content": {
            "headline": "YOU'RE ABSOLUTELY RIGHT!",
            "subheadline": "Statement poster for modern interior drop",
            "kicker": "AUTOFINISHER PREMIUM SERIES",
            "body": "Deterministic HTML/CSS/SVG render path with premium retro-tech hierarchy.",
            "footer_left": "EDITION 01",
            "footer_center": "MATTE BLACK / NEON GRID / DISPLAY PRINT",
            "footer_right": f"CODE {slugify(keyword).upper()[:12]}"
        },
        "style": {
            "family": "retro_neon_grid",
            "palette_id": "ember_signal",
            "font_pack": "orbitron_space_mono",
            "background_mode": "svg_grid_gradient",
            "texture_pack": ["film_grain_soft", "scanlines_subtle"],
            "accent_mode": "glow_high",
            "density": "medium",
            "alignment": "center",
            "case_mode": "preserve",
            "grid_mode": "horizon_signal",
            "spacing_preset": "poster_safe",
            "metadata_color": "cool_fog"
        },
        "layout": {
            "headline_max_lines": 3,
            "safe_margin_ratio": 0.08,
            "vertical_anchor": "center",
            "headline_width_ratio": 0.82,
            "overflow_strategy": "scale_down_then_track_tighter",
            "min_font_px": 84,
            "max_font_px": 320
        },
        "output": {
            "profile_id": "master_4k_vertical",
            "width": 2160,
            "height": 3840,
            "format": "png",
            "dpi": 300,
            "background": "opaque"
        },
        "metadata": {
            "keyword": f"{keyword.lower()} poster",
            "collection_id": "affirmation_drop_01",
            "edition_id": "edition_01",
            "source": "factory_pipeline",
            "created_at": created_at
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a factory-safe render payload.")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--template", default="retro_neon_grid", choices=["retro_neon_grid", "swiss_brutalism"])
    parser.add_argument("--out")
    args = parser.parse_args()

    payload = build_payload(args.keyword, args.template)
    default_name = f"generated_{args.template}_{slugify(args.keyword)}.json"
    output_path = Path(args.out) if args.out else PAYLOADS_DIR / default_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"status": "success", "payload_path": str(output_path), "template_id": args.template}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
