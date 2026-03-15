from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

BASE_DIR = Path("/home/agent/autofinisher-factory")
CONFIG_PATH = BASE_DIR / "config" / "keyword_discovery.yaml"
RUNS_DIR = BASE_DIR / "data" / "keyword_runs"
DEFAULT_CONFIG: dict[str, Any] = {
    "min_search": 20,
    "min_money_score": 0.65,
    "profiles": {
        "default": {
            "min_search": 20,
            "min_money_score": 0.65,
        },
        "etsy_seller_b2b_tools": {
            "min_search": 10,
            "min_money_score": 0.55,
        },
    },
}


def _normalize_keyword(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _safe_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(value))
    except Exception:
        return 0


def load_keyword_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()
    raw = CONFIG_PATH.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            loaded = yaml.safe_load(raw) or {}
            if isinstance(loaded, dict):
                merged = DEFAULT_CONFIG.copy()
                merged.update(loaded)
                profiles = dict(DEFAULT_CONFIG.get("profiles") or {})
                profiles.update(loaded.get("profiles") or {})
                merged["profiles"] = profiles
                return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def _iter_raw_records(raw_dirs: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for directory in raw_dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            seed = _normalize_keyword(payload.get("seed") or path.stem.replace("_", " "))
            source = str(payload.get("source") or directory.parent.name or "unknown")
            result_count = _safe_int(payload.get("result_count"))
            keyword = _normalize_keyword(payload.get("keyword") or seed)
            if keyword:
                records.append(
                    {
                        "keyword": keyword,
                        "seed": seed,
                        "source": source,
                        "source_type": payload.get("source_type") or "raw",
                        "result_count": result_count,
                        "support_type": "seed",
                    }
                )
            seen_supports: set[str] = set()
            for field_name, support_type in (
                ("suggestions", "suggestion"),
                ("related_searches", "related_search"),
                ("niche_candidates", "niche_candidate"),
            ):
                for item in payload.get(field_name) or []:
                    normalized = _normalize_keyword(item)
                    if not normalized or normalized in seen_supports:
                        continue
                    seen_supports.add(normalized)
                    records.append(
                        {
                            "keyword": normalized,
                            "seed": seed,
                            "source": source,
                            "source_type": payload.get("source_type") or "raw",
                            "result_count": result_count,
                            "support_type": support_type,
                        }
                    )
    return records


def _money_score(row: dict[str, Any], max_result_count: int) -> float:
    result_count = _safe_int(row.get("max_result_count"))
    source_hits = _safe_int(row.get("source_hits"))
    seed_hits = _safe_int(row.get("seed_hits"))
    support_hits = _safe_int(row.get("support_hits"))
    normalized_volume = 0.0 if max_result_count <= 0 else min(1.0, result_count / max_result_count)
    source_component = min(1.0, source_hits / 2.0)
    support_component = min(1.0, support_hits / 4.0)
    seed_component = min(1.0, seed_hits / 3.0)
    support_boost = min(0.5, (0.10 * source_hits) + (0.05 * seed_hits) + (0.05 * support_hits))
    if max_result_count <= 0:
        score = support_boost
    else:
        score = (0.45 * normalized_volume) + (0.20 * source_component) + (0.20 * support_component) + (0.15 * seed_component) + (0.10 * support_boost)
    return round(max(0.0, min(1.0, score)), 4)


def compile_keywords(raw_dirs: list[Path], run_id: str, *, profile: str = "default") -> dict[str, str]:
    config = load_keyword_config()
    profile_cfg = dict(config.get("profiles") or {}).get(profile, {}) or {}
    min_search = _safe_int(profile_cfg.get("min_search", config.get("min_search", 20)))
    min_money_score = float(profile_cfg.get("min_money_score", config.get("min_money_score", 0.65)))
    raw_records = _iter_raw_records(raw_dirs)
    aggregates: dict[str, dict[str, Any]] = {}
    for record in raw_records:
        keyword = _normalize_keyword(record.get("keyword"))
        if not keyword:
            continue
        entry = aggregates.setdefault(
            keyword,
            {
                "keyword": keyword,
                "source_hits": 0,
                "support_hits": 0,
                "seed_hits": 0,
                "max_result_count": 0,
                "sources": set(),
                "support_types": set(),
                "seed_examples": set(),
            },
        )
        source = str(record.get("source") or "unknown")
        support_type = str(record.get("support_type") or "support")
        seed = _normalize_keyword(record.get("seed"))
        entry["sources"].add(source)
        entry["support_types"].add(support_type)
        if seed:
            entry["seed_examples"].add(seed)
        entry["max_result_count"] = max(entry["max_result_count"], _safe_int(record.get("result_count")))
    for entry in aggregates.values():
        entry["source_hits"] = len(entry["sources"])
        entry["support_hits"] = len(entry["support_types"])
        entry["seed_hits"] = len(entry["seed_examples"])
    max_result_count = max((entry["max_result_count"] for entry in aggregates.values()), default=0)

    rows: list[dict[str, Any]] = []
    for entry in aggregates.values():
        score = _money_score(entry, max_result_count=max_result_count)
        row = {
            "keyword": entry["keyword"],
            "money_score": score,
            "max_result_count": entry["max_result_count"],
            "source_hits": entry["source_hits"],
            "support_hits": entry["support_hits"],
            "seed_hits": entry["seed_hits"],
            "sources": "|".join(sorted(entry["sources"])),
            "support_types": "|".join(sorted(entry["support_types"])),
            "seed_examples": "|".join(sorted(entry["seed_examples"])),
        }
        rows.append(row)
    rows.sort(key=lambda x: (-float(x["money_score"]), -int(x["max_result_count"]), x["keyword"]))
    shortlist = [row for row in rows if int(row["max_result_count"]) >= min_search and float(row["money_score"]) >= min_money_score]

    out_dir = RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "keyword",
        "money_score",
        "max_result_count",
        "source_hits",
        "support_hits",
        "seed_hits",
        "sources",
        "support_types",
        "seed_examples",
    ]
    for filename, data_rows in (("master_keywords.csv", rows), ("money_shortlist.csv", shortlist)):
        with (out_dir / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data_rows)

    summary = {
        "run_id": run_id,
        "profile": profile,
        "min_search": min_search,
        "min_money_score": min_money_score,
        "master_count": len(rows),
        "shortlist_count": len(shortlist),
        "raw_dirs": [str(p) for p in raw_dirs],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUNS_DIR / "latest_run.txt").write_text(run_id, encoding="utf-8")
    return {
        "master": str(out_dir / "master_keywords.csv"),
        "shortlist": str(out_dir / "money_shortlist.csv"),
        "summary": str(out_dir / "summary.json"),
    }
