from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path("/home/agent/autofinisher-factory")
RUNS_DIR = BASE_DIR / "data" / "keyword_runs"
CANDIDATES_DIR = BASE_DIR / "niche_engine" / "candidates"
CONTRACT_PATH = BASE_DIR / "niche_engine" / "contracts" / "niche_candidate.json"


def _normalize(text: str | None) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_slug(value: str, *, max_length: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _normalize(value))
    slug = slug.strip("_")
    if not slug:
        slug = "keyword"
    return slug[:max_length]


def resolve_run_id(run_id: str | None = None) -> str | None:
    if run_id and str(run_id).strip():
        return str(run_id).strip()
    marker = RUNS_DIR / "latest_run.txt"
    if marker.exists():
        value = marker.read_text(encoding="utf-8").strip()
        return value or None
    return None


def shortlist_path_for_run(run_id: str) -> Path:
    return RUNS_DIR / run_id / "money_shortlist.csv"


def _load_contract() -> dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise FileNotFoundError(f"Missing contract file: {CONTRACT_PATH}")
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _build_candidate(contract: dict[str, Any], row: dict[str, Any], run_id: str) -> dict[str, Any]:
    keyword = _normalize(row.get("keyword"))
    if not keyword:
        raise ValueError("keyword missing")
    candidate = json.loads(json.dumps(contract))
    candidate["seed_query"] = keyword
    candidate["candidate_query"] = keyword
    candidate["normalized_query"] = keyword
    candidate["source"] = {
        "provider": "keyword_discovery",
        "expansion_query": keyword,
        "run_id": run_id,
        "sources": (row.get("sources") or "").split("|") if row.get("sources") else [],
    }
    candidate.setdefault("semantic_atoms", {})
    candidate.setdefault("scores", {})
    candidate.setdefault("reason_codes", [])
    candidate["scores"]["demand_score"] = round(_safe_float(row.get("money_score")) * 100, 2)
    candidate["scores"]["profitability_score"] = round(_safe_float(row.get("money_score")) * 100, 2)
    candidate["reason_codes"] = list(candidate.get("reason_codes") or []) + [
        "keyword_discovery_import",
        f"source_hits_{row.get('source_hits') or 0}",
        f"support_hits_{row.get('support_hits') or 0}",
    ]
    candidate["status"] = "accepted"
    candidate["market_query_pack"] = {"etsy": [keyword], "google": [f"{keyword} etsy"]}
    candidate["money_score"] = _safe_float(row.get("money_score"))
    candidate["evidence"] = {
        "keyword_money_score": _safe_float(row.get("money_score")),
        "seed_examples": (row.get("seed_examples") or "").split("|") if row.get("seed_examples") else [],
        "support_types": (row.get("support_types") or "").split("|") if row.get("support_types") else [],
        "max_result_count": row.get("max_result_count"),
    }
    candidate["origin"] = {
        "primary_source": "keyword_inferred",
        "run_id": run_id,
    }
    return candidate


def to_niche_candidates(run_id: str | None = None) -> dict[str, Any]:
    resolved = resolve_run_id(run_id)
    if not resolved:
        return {"status": "skipped", "reason": "run_id_missing", "count": 0}
    shortlist_path = shortlist_path_for_run(resolved)
    if not shortlist_path.exists():
        return {"status": "skipped", "reason": "shortlist_missing", "count": 0, "run_id": resolved}

    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    contract = _load_contract()
    written = 0
    keywords: list[str] = []
    with shortlist_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            keyword = _normalize(row.get("keyword"))
            if not keyword:
                continue
            keywords.append(keyword)
            candidate = _build_candidate(contract, row, resolved)
            filename = f"keyword_{resolved}_{_safe_slug(keyword)}.json"
            (CANDIDATES_DIR / filename).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
            written += 1
    index_path = CANDIDATES_DIR / "keyword_discovery_index.json"
    index_payload = {"run_id": resolved, "count": written, "keywords": keywords}
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "done", "run_id": resolved, "count": written, "index": str(index_path)}


def import_keyword_run_to_verticals(run_id: str | None = None, *, max_candidates: int = 50) -> list[dict[str, Any]]:
    resolved = resolve_run_id(run_id)
    if not resolved:
        return []
    shortlist_path = shortlist_path_for_run(resolved)
    if not shortlist_path.exists():
        return []
    seeds: list[dict[str, Any]] = []
    with shortlist_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            keyword = _normalize(row.get("keyword"))
            if not keyword:
                continue
            seeds.append({"seed": keyword, "bucket": "keyword_discovery"})
            if len(seeds) >= max_candidates:
                break
    if not seeds:
        return []
    return [{"name": f"keyword_discovery_{resolved}", "seed_keywords": seeds}]
