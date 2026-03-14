from __future__ import annotations

import json
from pathlib import Path

import youtube_cluster_automanifest as yca


def test_get_video_id_from_plain_id() -> None:
    assert yca.get_video_id("xLmnJYWHQ34") == "xLmnJYWHQ34"


def test_get_video_id_from_watch_url() -> None:
    assert yca.get_video_id("https://www.youtube.com/watch?v=xLmnJYWHQ34") == "xLmnJYWHQ34"


def test_get_video_id_from_short_url() -> None:
    assert yca.get_video_id("https://youtu.be/xLmnJYWHQ34") == "xLmnJYWHQ34"


def test_extract_decision_examples_respects_limit() -> None:
    text = (
        "We pause the losers after enough spend. "
        "Then we keep the winners once the budget is fully utilized. "
        "Finally we scale this up per listing when the campaign is stable."
    )
    examples = yca.extract_decision_examples(text, limit=2)
    assert len(examples) == 2
    assert any("pause the losers" in item.lower() for item in examples)


def test_generate_automanifest_writes_expected_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(yca, "FIXTURES_DIR", tmp_path)

    transcript = (
        "As you can see on my screen in the Etsy ads dashboard, this listing has ROAS and CTR data. "
        "We pause the losers and keep the winners after 2 to 4 weeks per listing."
    )

    monkeypatch.setattr(yca, "load_or_fetch_transcript", lambda video_id: transcript)
    monkeypatch.setattr(
        yca,
        "get_metadata",
        lambda video_id: {
            "title": "Test Etsy Ads Video",
            "channel_title": "Test Channel",
            "published_at": "2025-01-01",
            "duration_minutes": 14,
            "published_at_raw": "2025-01-01T00:00:00Z",
            "duration_iso8601": "PT14M",
        },
    )

    payload = yca.generate_automanifest(
        {
            "cluster_id": "etsy_ads_cluster_v2",
            "topic_cluster": "etsy_ads_v2",
            "video_ids": ["xLmnJYWHQ34", "xLmnJYWHQ34"],
            "language_hint": "en",
            "default_tier": "A",
        }
    )

    output_path = tmp_path / "etsy_ads_cluster_v2" / "cluster_manifest.autogen.json"
    assert output_path.exists()

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["cluster_id"] == "etsy_ads_cluster_v2"
    assert written["topic_cluster"] == "etsy_ads_v2"
    assert len(written["videos"]) == 1

    video = written["videos"][0]
    assert video["video_id"] == "xLmnJYWHQ34"
    assert video["tier"] == "A"
    assert video["has_screen_share"] is True
    assert video["shows_marketplace_ui"] is True
    assert video["shows_specific_listings"] is True
    assert video["contains_metrics"] is True
    assert video["contains_decision_layer_signals"] is True
    assert video["published_at"] == "2025-01-01"
    assert video["source_metadata"]["title"] == "Test Etsy Ads Video"
    assert video["annotation_confidence"]["contains_metrics"] == 0.95
    assert payload["videos"][0]["decision_layer_signal_examples"]
