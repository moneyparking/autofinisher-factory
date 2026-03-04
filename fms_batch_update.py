from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fms_engine import compute_fms_components, compute_fms_score
from fms_reference import compute_reference_ratios, etsy_quality_band_for

BASE_DIR = Path("/home/agent/autofinisher-factory")
VALIDATED_DIR = BASE_DIR / "data" / "validated_niches" / "items"
REAL_PERFORMANCE_DIR = BASE_DIR / "data" / "real_performance"
MIN_MONETIZATION_SCORE = 42.0
MIN_STR = 15.0
MIN_SOLD = 20


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_real_performance_for_niche(niche_id: str) -> dict[str, Any]:
    return load_json(REAL_PERFORMANCE_DIR / f"{niche_id}.json", {})


def recompute_status(fms_score: float, ebay_metrics: dict[str, Any]) -> dict[str, str]:
    str_percent = float(ebay_metrics.get("str_percent") or 0.0)
    sold_count = int(ebay_metrics.get("sold_count") or 0)

    if fms_score >= MIN_MONETIZATION_SCORE and str_percent >= MIN_STR and sold_count >= MIN_SOLD:
        return {"status": "winner", "reason": "fms_ok_and_ebay_liquidity_strong"}
    if fms_score >= MIN_MONETIZATION_SCORE:
        if sold_count < MIN_SOLD:
            return {"status": "candidate", "reason": "fms_ok_but_ebay_sold_below_threshold"}
        if str_percent < MIN_STR:
            return {"status": "candidate", "reason": "fms_ok_but_ebay_str_below_threshold"}
        return {"status": "candidate", "reason": "fms_ok_but_liquidity_mixed"}
    return {"status": "low_fms", "reason": "fms_below_min_score"}


def update_validated_niche(path: Path) -> dict[str, Any]:
    data = load_json(path, {})
    niche_id = str(data.get("niche_id") or path.stem)
    etsy_metrics = data.get("etsy_metrics") or {}
    ebay_metrics = data.get("ebay_metrics") or {}
    real_performance = load_real_performance_for_niche(niche_id)

    components = compute_fms_components(
        etsy_metrics=etsy_metrics,
        ebay_metrics=ebay_metrics,
        real_performance=real_performance,
    )
    fms_score = compute_fms_score(components)
    decision = recompute_status(fms_score, ebay_metrics)

    data["fms_components"] = components
    data["fms_score"] = fms_score
    data["real_performance"] = real_performance
    data["etsy_quality_band"] = etsy_quality_band_for((etsy_metrics or {}).get("digital_share"))
    data["vs_reference"] = compute_reference_ratios(fms_score, ebay_metrics)
    validation = data.get("validation") or {}
    validation.update(
        {
            "status": decision["status"],
            "reason": decision["reason"],
            "niche_id": niche_id,
            "validated_path": str(path.resolve()),
            "updated_at": now_iso(),
        }
    )
    data["status"] = decision["status"]
    data["reason"] = decision["reason"]
    data["validation"] = validation
    write_json(path, data)
    return data


def batch_update_all_validated() -> list[dict[str, Any]]:
    VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for path in sorted(VALIDATED_DIR.glob("*.json")):
        results.append(update_validated_niche(path))
    return results


if __name__ == "__main__":
    updated = batch_update_all_validated()
    print(json.dumps({"updated_count": len(updated)}, ensure_ascii=False))