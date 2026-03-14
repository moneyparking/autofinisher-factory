from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_validator_v2_automanifest_prep(monkeypatch, tmp_path: Path) -> None:
    import scripts.validate_etsy_ads_regression_fixtures as validator

    fixture_name = "etsy_ads_cluster_v2"
    fixture_root = tmp_path / "fixtures" / "regression" / fixture_name
    fixture_root.mkdir(parents=True)
    (fixture_root / "inputs.json").write_text(
        json.dumps(
            {
                "videos": [
                    {"video_id": "xLmnJYWHQ34", "role": "batch"},
                    {"video_id": "WNQgc8NzLYc", "role": "control"},
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(validator, "FIXTURE_NAME", fixture_name)
    monkeypatch.setattr(validator, "FIXTURE_ROOT", fixture_root)

    calls: list[dict] = []

    def fake_generate_automanifest(payload: dict) -> dict:
        calls.append(payload)
        return {"videos": []}

    monkeypatch.setattr(validator.yca, "generate_automanifest", fake_generate_automanifest)

    validator.ensure_cluster_manifest_autogen()

    assert len(calls) == 1
    assert calls[0]["cluster_id"] == fixture_name
    assert calls[0]["topic_cluster"] == "etsy_ads_v2"
    assert calls[0]["video_ids"] == ["xLmnJYWHQ34"]


def test_aggregator_v2_automanifest_prep(monkeypatch, tmp_path: Path) -> None:
    import scripts.aggregate_etsy_ads_cluster_metrics as aggregator

    fixture_name = "etsy_ads_cluster_v2"
    fixture_root = tmp_path / "fixtures" / "regression" / fixture_name
    fixture_root.mkdir(parents=True)
    (fixture_root / "inputs.json").write_text(
        json.dumps(
            {
                "videos": [
                    {"video_id": "lhxcQLmrdhQ", "role": "batch"},
                    {"video_id": "y4I6vfdD68I", "role": "batch"},
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(aggregator, "FIXTURE_NAME", fixture_name)
    monkeypatch.setattr(aggregator, "FIXTURE_ROOT", fixture_root)

    calls: list[dict] = []

    def fake_generate_automanifest(payload: dict) -> dict:
        calls.append(payload)
        return {"videos": []}

    monkeypatch.setattr(aggregator.yca, "generate_automanifest", fake_generate_automanifest)

    aggregator.ensure_cluster_manifest_autogen()

    assert len(calls) == 1
    assert calls[0]["cluster_id"] == fixture_name
    assert calls[0]["topic_cluster"] == "etsy_ads_v2"
    assert calls[0]["video_ids"] == ["lhxcQLmrdhQ", "y4I6vfdD68I"]
