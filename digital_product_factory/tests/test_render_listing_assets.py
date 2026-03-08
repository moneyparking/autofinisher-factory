from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / "digital_product_factory" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import render_listing_assets


def test_render_listing_assets_writes_html_and_plan(tmp_path: Path, monkeypatch) -> None:
    product_dir = tmp_path / "budget-spreadsheet"
    product_dir.mkdir(parents=True)
    packet = {
        "title": "Budget Spreadsheet | Finance Tracker | Instant Download",
        "description_intro": "A practical spreadsheet download for faster money tracking.",
        "artifacts": {
            "rendered_listing_html_path": str(product_dir / "listing_preview.html"),
            "listing_image_plan_path": str(product_dir / "listing_image_plan.json"),
        },
        "listing_image_plan": [
            {
                "slot": index,
                "headline": f"Image {index}",
                "purpose": "preview",
                "detail": "Buyer-facing preview copy",
                "asset_hint": "preview.pdf",
            }
            for index in range(1, 11)
        ],
        "listing_image_paths": [str(product_dir / f"listing_image_{index:02d}.png") for index in range(1, 11)],
        "what_is_included": ["Budget Spreadsheet", "Editable spreadsheet workbook"],
        "seo_aeo": {
            "what_is_it": "A budgeting spreadsheet download.",
            "who_is_it_for": "Buyers who want a simple money tracker.",
            "what_do_i_get": "Workbook and preview assets.",
            "how_do_i_use_it": "Download, open, and start tracking.",
            "compatibility": "Works with apps that open .xlsx files.",
        },
    }
    (product_dir / "listing_packet_etsy.json").write_text(json.dumps(packet), encoding="utf-8")

    monkeypatch.setattr(render_listing_assets, "OUTPUTS_DIR", tmp_path)
    result = render_listing_assets.render_listing_assets("budget-spreadsheet")

    assert result["listing_image_count"] == 10
    assert Path(result["listing_preview_html"]).exists()
    assert Path(result["listing_image_plan_path"]).exists()
    plan_payload = json.loads(Path(result["listing_image_plan_path"]).read_text(encoding="utf-8"))
    assert plan_payload["image_count"] == 10
    assert len(plan_payload["images"]) == 10
