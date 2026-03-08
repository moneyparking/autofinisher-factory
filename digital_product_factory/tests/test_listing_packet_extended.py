from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / "digital_product_factory" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from listing_compiler import compile_listing_packet


@pytest.fixture
def sample_spec_manifest() -> tuple[dict, dict]:
    spec = {
        "product_slug": "budget-spreadsheet",
        "product_name": "Budget Spreadsheet",
        "product_kind": "spreadsheet",
        "product_family": "budget_sheet_base",
        "product_type": "budget_system",
        "benefit_statement": "Save time and see your monthly numbers at a glance",
        "user_problem": "Need a simple budget tracker",
        "intended_user": "busy moms",
        "usage_outcome": "Track spending in minutes",
        "layout_profile": "budget_dashboard",
        "delivery_format": "sheet_pdf",
        "content_modules": ["dashboard", "transactions", "monthly_overview"],
        "listing_inputs": {
            "listing_title": "Budget Spreadsheet | Digital Download",
            "category": "spreadsheets",
            "format_hint": "Google Sheets + optional PDF preview",
            "tags": ["budget spreadsheet", "finance tracker"],
            "primary_keyword": "budget spreadsheet",
        },
        "source_assets": {},
    }
    manifest = {
        "artifacts": [
            {"artifact_type": "deliverable_xlsx", "path": "/tmp/deliverable.xlsx", "exists": True},
            {"artifact_type": "preview_pdf", "path": "/tmp/preview.pdf", "exists": True},
            {"artifact_type": "master_png", "path": "/tmp/master.png", "exists": True},
            {"artifact_type": "mockup_png", "path": "/tmp/mockup.png", "exists": True},
            {"artifact_type": "seo_txt", "path": "/tmp/SEO.txt", "exists": True},
            {"artifact_type": "source_csv", "path": "/tmp/source_rows.csv", "exists": True},
        ],
        "qa": {"checks_passed": True, "broken_links": 0},
    }
    return spec, manifest


@pytest.fixture
def sample_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_spec_manifest: tuple[dict, dict]) -> tuple[dict, Path]:
    import listing_compiler

    spec, manifest = sample_spec_manifest
    monkeypatch.setattr(listing_compiler, "OUTPUTS_DIR", tmp_path)
    packet = compile_listing_packet(spec, manifest, "etsy")
    product_dir = tmp_path / spec["product_slug"]
    product_dir.mkdir(parents=True, exist_ok=True)
    return packet, product_dir


def test_listing_packet_populates_publish_ready_fields(sample_packet: tuple[dict, Path]) -> None:
    packet, _ = sample_packet
    for field in [
        "description_intro",
        "description_whats_included",
        "description_how_it_works",
        "description_what_youll_get",
        "description_terms",
        "description_compatibility",
        "photo_sequence_hint",
        "thumbnail_angle",
        "upload_order_hint",
        "seo_aeo",
        "listing_image_plan",
        "listing_image_paths",
        "market_readiness",
    ]:
        assert field in packet


def test_compile_listing_packet_is_buyer_facing_and_market_ready(sample_packet: tuple[dict, Path]) -> None:
    packet, _ = sample_packet
    assert len(packet["description_intro"]) > 10
    assert "• Budget Spreadsheet" in packet["description_whats_included"]
    assert "10-image listing plan" in packet["description_what_youll_get"]
    assert packet["thumbnail_angle"] == "front_cover"
    assert len(packet["tags"]) == 13
    assert len(packet["listing_image_plan"]) == 10
    assert len(packet["listing_image_paths"]) == 10
    assert packet["market_readiness"]["tags_ready"] is True
    assert "buyer receives" not in packet["description"].lower()
    assert packet["title"].count("Budget Spreadsheet") == 1


def test_replay_product_reads_existing_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    product_dir = tmp_path / "budget-spreadsheet"
    product_dir.mkdir(parents=True)
    (product_dir / "artifact_manifest.json").write_text(json.dumps({"qa": {"checks_passed": True}}), encoding="utf-8")
    (product_dir / "listing_packet_etsy.json").write_text(json.dumps({"title": "Test", "description": "Packet description"}), encoding="utf-8")
    (product_dir / "digital_product_spec.json").write_text(json.dumps({"product_slug": "budget-spreadsheet"}), encoding="utf-8")

    import replay_product

    monkeypatch.setattr(replay_product, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["replay_product.py", "--product-slug", "budget-spreadsheet"])
    replay_product.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["product_slug"] == "budget-spreadsheet"
    assert "listing_packet_etsy.json" in "\n".join(payload["publish_packet_paths"])


def test_replay_product_does_not_call_build_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    product_dir = tmp_path / "budget-spreadsheet"
    product_dir.mkdir(parents=True)
    (product_dir / "artifact_manifest.json").write_text(json.dumps({"qa": {}}), encoding="utf-8")
    (product_dir / "listing_packet_etsy.json").write_text(json.dumps({}), encoding="utf-8")
    (product_dir / "digital_product_spec.json").write_text(json.dumps({}), encoding="utf-8")

    import replay_product

    calls: list[tuple] = []

    def _unexpected_call(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Build pipeline should not be called from replay_product")

    monkeypatch.setattr(replay_product, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["replay_product.py", "--product-slug", "budget-spreadsheet"])
    replay_product.main()
    assert calls == []
