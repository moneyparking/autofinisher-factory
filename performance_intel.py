from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path("/home/agent/autofinisher-factory")
PERFORMANCE_PATH = BASE_DIR / "sales_feedback.json"


def load_performance_feedback() -> dict[str, Any]:
    if not PERFORMANCE_PATH.exists():
        return {"sku_feedback": {}, "family_feedback": {}}
    try:
        payload = json.loads(PERFORMANCE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {"sku_feedback": {}, "family_feedback": {}}


def performance_feedback_score(niche: str, vertical: str) -> float:
    payload = load_performance_feedback()
    sku_feedback = payload.get("sku_feedback", {})
    family_feedback = payload.get("family_feedback", {})
    niche_key = str(niche or "").strip().lower()
    vertical_key = str(vertical or "").strip().lower()

    sku_score = sku_feedback.get(niche_key)
    family_score = family_feedback.get(vertical_key)

    if isinstance(sku_score, (int, float)):
        return round(max(0.0, min(100.0, float(sku_score))), 2)
    if isinstance(family_score, (int, float)):
        return round(max(0.0, min(100.0, float(family_score))), 2)
    return 50.0
