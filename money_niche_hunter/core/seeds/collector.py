"""Advanced seed collector (Step 1).

Implements seven quality-oriented improvements for pre-selecting money niches:
1) Google Trends scoring
2) Pinterest related suggestions
3) Semantic deduplication / clustering
4) Early LLM viability check
5) Etsy best-selling expansion with price extraction
6) LLM-generated long-tail expansion from strong seeds
7) Multi-platform seed fusion (Google/Reddit/Amazon)

The collector is production-oriented:
- all network features degrade gracefully
- optional dependencies are soft-fail
- env flags can reduce cost / speed up smoke-runs
- outputs remain stable JSON contracts for downstream steps
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from statistics import mean
from typing import Any
from urllib.parse import quote

import requests

# Load env files early so OPENAI_API_KEY is available for Step 1 (collector)
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

if load_dotenv is not None:
    # Project root is two levels up from money_niche_hunter/
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    # Load in order: generic .env, optional OpenAI-specific env, then scrape env
    for _name in (".env", ".env.openai.local", ".env.scrape.local"):
        _path = os.path.join(_ROOT, _name)
        if os.path.exists(_path):
            load_dotenv(_path, override=False)

from money_niche_hunter.utils.storage import load_json, save_json
from money_niche_hunter.config.settings import RAW_SEEDS_PATH, SEEDS_COLLECTION_STATS_PATH

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

try:
    from pytrends.request import TrendReq
except Exception:  # pragma: no cover
    TrendReq = None  # type: ignore

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer, util
except Exception:  # pragma: no cover
    SentenceTransformer = None  # type: ignore
    util = None  # type: ignore

SEEN_SEEDS_PATH = "money_niche_hunter/data/seen_seeds.json"
SEED_EXPANSION_DEPTH = 2
MAX_RELATED_PER_SEED = 12
MIN_QUERY_LENGTH = 4

BASE_SEEDS: list[str] = [
    "adhd planner printable",
    "digital planner",
    "checklist printable",
    "notion template",
    "budget spreadsheet",
    "wedding planner template",
    "habit tracker printable",
    "gratitude journal pdf",
    "daily planner printable",
    "meal planner printable",
    "content calendar template",
    "resume template canva",
]

CLUSTERS: dict[str, list[str]] = {
    "planner": ["planner", "schedule", "calendar", "organizer"],
    "template": ["template", "notion", "canva", "editable", "spreadsheet"],
    "checklist": ["checklist", "tracker", "list", "log"],
    "journal": ["journal", "notebook", "prompts", "reflection"],
    "finance": ["budget", "finance", "bookkeeping", "expense", "invoice"],
}

# Hard negative patterns to prevent spending credits on obvious noise.
# These are applied before any paid scraping/batch run.
NEGATIVE_SEED_PATTERNS: list[str] = [
    # obvious giveaways / bait / UI labels
    r"\bfree\b",
    r"\bdownload\b",
    r"\bcoupon\b",
    r"more\s+like\s+this",

    # common traffic-platform noise
    r"\btiktok\b",
    r"\byoutube\b",
    r"\bpinterest\b",

    # "free" variants in other languages
    r"\bkostenlos\b",
    r"\bgratuit\b",

    # file-type bait
    r"\bsvg\s*free\b",
    r"\bpdf\s*free\b",
]

# Optional: allow extending/overriding from env (pipe-separated regex fragments).
_env_neg = os.getenv("MONEY_NICHE_HUNTER_NEGATIVE_SEED_PATTERNS", "").strip()
if _env_neg:
    # Example: MONEY_NICHE_HUNTER_NEGATIVE_SEED_PATTERNS="\bfree\b|\bdownload\b|more like this"
    # We keep existing defaults and append extras.
    for frag in _env_neg.split("|"):
        frag = frag.strip()
        if frag:
            NEGATIVE_SEED_PATTERNS.append(frag)

NEGATIVE_SEED_RE = re.compile("|".join(f"(?:{p})" for p in NEGATIVE_SEED_PATTERNS), flags=re.I)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


NO_NETWORK = _env_flag("MONEY_NICHE_HUNTER_NO_NETWORK", False)
USE_TRENDS = _env_flag("MONEY_NICHE_HUNTER_USE_TRENDS", True)
USE_PINTEREST = _env_flag("MONEY_NICHE_HUNTER_USE_PINTEREST", True)
USE_LLM_VIABILITY = _env_flag("MONEY_NICHE_HUNTER_USE_LLM_VIABILITY", True)
USE_SEMANTIC_DEDUP = _env_flag("MONEY_NICHE_HUNTER_USE_SEMANTIC_DEDUP", True)
USE_MULTI_PLATFORM = _env_flag("MONEY_NICHE_HUNTER_USE_MULTI_PLATFORM", True)
USE_LONGTAIL = _env_flag("MONEY_NICHE_HUNTER_USE_LONGTAIL", True)
ENV_DEPTH = _env_int("MONEY_NICHE_HUNTER_DEPTH", SEED_EXPANSION_DEPTH)
ENV_MAX_BASE_SEEDS = _env_int("MONEY_NICHE_HUNTER_BASE_SEEDS", 0)
ENV_LLM_VIABILITY_LIMIT = _env_int("MONEY_NICHE_HUNTER_LLM_VIABILITY_LIMIT", 50)
# Tokens/keys are read from environment after dotenv load above.
SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
LLM_MODEL = os.getenv("MONEY_NICHE_HUNTER_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def _build_llm_client() -> Any | None:
    # Read API key at call-time (not import-time) so exports in the shell are respected.
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if OpenAI is None or not api_key:
        return None
    try:
        return OpenAI(api_key=api_key, base_url=OPENAI_BASE_URL)
    except Exception:
        return None


def _detect_cluster(seed: str) -> str:
    seed_lower = seed.lower()
    for cluster_name, keywords in CLUSTERS.items():
        if any(kw in seed_lower for kw in keywords):
            return cluster_name
    return "other"


def _load_seen_seeds() -> set[str]:
    raw = load_json(SEEN_SEEDS_PATH, default=[])
    return {str(x).strip().lower() for x in raw if str(x).strip()}


def _save_seen_seeds(values: set[str]) -> None:
    save_json(sorted(values), SEEN_SEEDS_PATH)


def _normalize_seed_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _append_seed(out: list[dict[str, Any]], seen: set[str], seed: str, *, source: str, cluster: str | None = None, level: int = 0, parent: str | None = None, extra: dict[str, Any] | None = None) -> None:
    text = _normalize_seed_text(seed)
    if len(text) < 4:
        return
    # Drop obvious noise early.
    if NEGATIVE_SEED_RE.search(text):
        return
    key = text.lower()
    if key in seen:
        return
    seen.add(key)
    item: dict[str, Any] = {
        "seed": text,
        "source": source,
        "cluster": cluster or _detect_cluster(text),
        "level": level,
    }
    if parent:
        item["parent"] = parent
    if extra:
        item.update(extra)
    out.append(item)


def _requests_get_json(url: str, *, headers: dict[str, str] | None = None, timeout: int = 8) -> Any | None:
    if NO_NETWORK:
        return None
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _requests_get_text(url: str, *, headers: dict[str, str] | None = None, timeout: int = 12) -> str:
    if NO_NETWORK:
        return ""
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""


def _scrape_do_get(url: str, *, render: bool = False, super_proxy: bool = False, geo_code: str | None = None) -> str:
    if NO_NETWORK or not SCRAPEDO_TOKEN:
        return ""
    params = [
        f"token={quote(SCRAPEDO_TOKEN)}",
        f"url={quote(url, safe='')}",
        "disableRetry=false",
    ]
    if render:
        params.append("render=true")
    if super_proxy:
        params.append("super=true")
    if geo_code:
        params.append(f"geoCode={quote(geo_code)}")
    api_url = f"https://api.scrape.do/?{'&'.join(params)}"
    return _requests_get_text(api_url, timeout=25)


def _extract_price_values(text: str) -> list[float]:
    values: list[float] = []
    for raw in re.findall(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text or ""):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def _price_stats_from_values(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"min_price": None, "avg_price": None, "sample_price_count": 0}
    return {
        "min_price": round(min(values), 2),
        "avg_price": round(mean(values), 2),
        "sample_price_count": len(values),
    }


def _google_autocomplete(query: str) -> list[str]:
    data = _requests_get_json(
        f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote(query)}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    if not data or len(data) < 2:
        return []
    suggestions = [str(item).strip() for item in (data[1] or [])]
    return [s for s in suggestions if len(s) >= MIN_QUERY_LENGTH][:MAX_RELATED_PER_SEED]


def _etsy_style_suggestions(query: str) -> list[str]:
    variations = [query, f"{query} etsy", f"{query} printable", f"{query} digital download", f"{query} template"]
    results: list[str] = []
    for variant in variations:
        results.extend(_google_autocomplete(variant))
        time.sleep(0.15)
    uniq: list[str] = []
    seen: set[str] = set()
    for result in results:
        key = result.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(result)
    return uniq[:MAX_RELATED_PER_SEED]


def _etsy_best_selling_related(seed: str) -> tuple[list[str], dict[str, Any]]:
    url = f"https://www.etsy.com/search?q={quote(seed)}&order=best_selling&explicit=1"
    html = _scrape_do_get(url, render=False, super_proxy=True, geo_code="us")
    if not html:
        return [], {"min_price": None, "avg_price": None, "sample_price_count": 0}
    if BeautifulSoup is None:
        return [], _price_stats_from_values(_extract_price_values(html))

    soup = BeautifulSoup(html, "html.parser")
    phrases: list[str] = []
    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        text = _normalize_seed_text(link.get_text(" ", strip=True))
        if "/search" in href and "q=" in href and len(text) >= 8:
            phrases.append(text)
        if len(phrases) >= MAX_RELATED_PER_SEED:
            break

    price_stats = _price_stats_from_values(_extract_price_values(soup.get_text(" ", strip=True)))

    uniq_phrases: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq_phrases.append(phrase)
    return uniq_phrases[:MAX_RELATED_PER_SEED], price_stats


def _pinterest_related(seed: str) -> list[str]:
    if not USE_PINTEREST:
        return []
    url = f"https://www.pinterest.com/search/pins/?q={quote(seed)}"
    html = _scrape_do_get(url, render=False, super_proxy=False, geo_code="us")
    if not html or BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    phrases: list[str] = []
    for link in soup.find_all("a", href=True):
        text = _normalize_seed_text(link.get_text(" ", strip=True))
        if 8 <= len(text) <= 90:
            lowered = text.lower()
            if any(token in lowered for token in ["planner", "template", "printable", "checklist", "tracker", "budget", "journal"]):
                phrases.append(text)
    uniq: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(phrase)
    return uniq[:MAX_RELATED_PER_SEED]


def _add_trends_score(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not USE_TRENDS or TrendReq is None or NO_NETWORK:
        for item in seeds:
            item.setdefault("trends_avg", None)
            item.setdefault("trends_rising", None)
            item.setdefault("trends_score", None)
        return seeds

    pytrends = TrendReq(hl="en-US", tz=360)
    for item in seeds:
        kw = item["seed"]
        try:
            pytrends.build_payload([kw], timeframe="today 12-m")
            df = pytrends.interest_over_time()
            if not df.empty and kw in df.columns:
                avg = float(df[kw].mean())
                slope = float(df[kw].iloc[-3:].mean() - df[kw].iloc[:3].mean())
                item["trends_avg"] = round(avg, 1)
                item["trends_rising"] = slope > 0
                item["trends_score"] = round(avg * (1.3 if slope > 0 else 0.7), 1)
            else:
                item["trends_avg"] = None
                item["trends_rising"] = None
                item["trends_score"] = None
        except Exception:
            item["trends_avg"] = None
            item["trends_rising"] = None
            item["trends_score"] = 30.0
        time.sleep(0.35)
    return seeds


def _semantic_dedup(seeds: list[dict[str, Any]], threshold: float = 0.85) -> list[dict[str, Any]]:
    if not USE_SEMANTIC_DEDUP or SentenceTransformer is None or util is None or not seeds:
        return seeds
    try:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        texts = [item["seed"] for item in seeds]
        embeddings = model.encode(texts)
        unique: list[dict[str, Any]] = []
        skip: set[int] = set()
        for i, emb in enumerate(embeddings):
            if i in skip:
                continue
            unique.append(seeds[i])
            for j in range(i + 1, len(embeddings)):
                if j in skip:
                    continue
                score = float(util.cos_sim(emb, embeddings[j]))
                if score >= threshold:
                    skip.add(j)
        return unique
    except Exception:
        return seeds


def _llm_viability_filter(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not USE_LLM_VIABILITY:
        return seeds
    client = _build_llm_client()
    if client is None:
        for item in seeds:
            item.setdefault("viability", "unknown")
            item.setdefault("viability_reason", "llm_unavailable")
        return seeds

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(seeds):
        if idx >= ENV_LLM_VIABILITY_LIMIT:
            item.setdefault("viability", "unknown")
            item.setdefault("viability_reason", "viability_limit_reached")
            out.append(item)
            continue
        prompt = (
            "Оцени нишу для цифрового товара на Etsy. "
            f"Ниша: '{item['seed']}'. "
            "Подходит ли она под planner/template/checklist/tracker/spreadsheet? "
            "Верни только JSON: {\"viability\":\"high|medium|low\",\"reason\":\"короткая причина\",\"digital_only\":true|false}."
        )
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content)
            viability = str(parsed.get("viability") or "medium").lower()
            digital_only = bool(parsed.get("digital_only", True))
            item["viability"] = viability
            item["viability_reason"] = str(parsed.get("reason") or "")
            item["digital_only"] = digital_only
            if viability in {"high", "medium"} and digital_only:
                out.append(item)
        except Exception as exc:
            item["viability"] = "unknown"
            item["viability_reason"] = str(exc)[:160]
            item.setdefault("digital_only", True)
            out.append(item)
        time.sleep(0.1)
    return out


def _generate_longtail_from_winners(seeds: list[dict[str, Any]]) -> list[str]:
    if not USE_LONGTAIL:
        return []
    client = _build_llm_client()
    if client is None:
        return []
    strong = [item["seed"] for item in seeds if float(item.get("trends_score") or 0) >= 60][:10]
    if not strong:
        strong = [item["seed"] for item in seeds[:5]]
    if not strong:
        return []
    prompt = (
        "Сгенерируй 20 long-tail seed-фраз для Etsy только под цифровые товары "
        "(planner/template/checklist/tracker/spreadsheet/notion/canva). "
        f"База: {strong}. "
        "Верни только JSON-массив строк."
    )
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        raw = json.loads(resp.choices[0].message.content)
        if isinstance(raw, list):
            values = raw
        elif isinstance(raw, dict):
            values = raw.get("items") or raw.get("seeds") or raw.get("longtails") or []
        else:
            values = []
        return [_normalize_seed_text(v) for v in values if _normalize_seed_text(v)]
    except Exception:
        return []


def _reddit_and_amazon_seeds() -> list[str]:
    if not USE_MULTI_PLATFORM:
        return []
    out: list[str] = []
    data = _requests_get_json(
        "https://www.reddit.com/r/EtsySellers/search.json?q=digital%20planner&restrict_sr=on&sort=relevance&t=year",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    if isinstance(data, dict):
        children = ((data.get("data") or {}).get("children") or [])
        for child in children[:10]:
            title = _normalize_seed_text(((child.get("data") or {}).get("title") or ""))
            if len(title) >= 8:
                out.append(title)

    amazon_related = [
        "digital budget planner",
        "wedding checklist printable",
        "teacher planner template",
        "bookkeeping spreadsheet small business",
    ]
    out.extend(amazon_related)

    uniq: list[str] = []
    seen: set[str] = set()
    for value in out:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(value)
    return uniq[:20]


def expand_seeds(base_seeds: list[str] | None = None, depth: int = SEED_EXPANSION_DEPTH) -> list[dict[str, Any]]:
    base = base_seeds or BASE_SEEDS
    if ENV_MAX_BASE_SEEDS > 0:
        base = base[:ENV_MAX_BASE_SEEDS]

    all_ideas: list[dict[str, Any]] = []
    seen: set[str] = _load_seen_seeds()

    for seed in base:
        s = _normalize_seed_text(seed)
        if not s:
            continue

        related_best, price_stats = _etsy_best_selling_related(s)
        _append_seed(
            all_ideas,
            seen,
            s,
            source="manual_seed",
            cluster=_detect_cluster(s),
            level=0,
            extra={"seed_origin": "manual", **price_stats},
        )

        for related in related_best:
            _append_seed(
                all_ideas,
                seen,
                related,
                source="etsy_best_selling",
                cluster=_detect_cluster(related),
                level=1,
                parent=s,
                extra=price_stats,
            )

        related1: list[str] = []
        if depth >= 1:
            related1 = _etsy_style_suggestions(s)
            for result in related1:
                _append_seed(
                    all_ideas,
                    seen,
                    result,
                    source="google_related",
                    cluster=_detect_cluster(result),
                    level=1,
                    parent=s,
                )

        if depth >= 2 and related1:
            for r1 in related1[:4]:
                for r2 in _etsy_style_suggestions(r1):
                    _append_seed(
                        all_ideas,
                        seen,
                        r2,
                        source="google_related_level2",
                        cluster=_detect_cluster(r2),
                        level=2,
                        parent=r1,
                    )
                time.sleep(random.uniform(0.1, 0.25))

        for pin in _pinterest_related(s):
            _append_seed(
                all_ideas,
                seen,
                pin,
                source="pinterest_related",
                cluster=_detect_cluster(pin),
                level=1,
                parent=s,
            )

        time.sleep(random.uniform(0.05, 0.15))

    for extra_seed in _reddit_and_amazon_seeds():
        _append_seed(
            all_ideas,
            seen,
            extra_seed,
            source="multi_platform",
            cluster=_detect_cluster(extra_seed),
            level=1,
        )

    return all_ideas


def _negative_filter_seeds(seeds: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove obvious noise seeds. Returns (filtered, removed_count)."""
    out: list[dict[str, Any]] = []
    removed = 0
    for item in seeds:
        seed = _normalize_seed_text(item.get("seed", ""))
        if not seed:
            removed += 1
            continue
        if NEGATIVE_SEED_RE.search(seed):
            removed += 1
            continue
        out.append(item)
    return out, removed


def collect_seeds() -> list[dict[str, Any]]:
    stage: dict[str, Any] = {}

    seeds = expand_seeds(BASE_SEEDS, depth=ENV_DEPTH)
    stage["stage_expand_total"] = len(seeds)

    seeds, removed_neg = _negative_filter_seeds(seeds)
    stage["stage_negative_removed"] = removed_neg
    stage["stage_after_negative_total"] = len(seeds)

    seeds = _add_trends_score(seeds)
    stage["stage_after_trends_total"] = len(seeds)

    seeds = _llm_viability_filter(seeds)
    stage["stage_after_viability_total"] = len(seeds)

    seeds = _semantic_dedup(seeds)
    stage["stage_after_dedup_total"] = len(seeds)

    longtails = _generate_longtail_from_winners(seeds)
    stage["stage_longtail_generated"] = len(longtails)

    seen = {item["seed"].lower() for item in seeds}
    for seed in longtails:
        if seed.lower() in seen:
            continue
        if NEGATIVE_SEED_RE.search(seed):
            continue
        seen.add(seed.lower())
        seeds.append(
            {
                "seed": seed,
                "source": "llm_longtail",
                "cluster": _detect_cluster(seed),
                "level": 2,
                "viability": "unknown",
                "digital_only": True,
            }
        )

    seeds = _semantic_dedup(seeds)
    stage["stage_final_total"] = len(seeds)

    by_source: dict[str, int] = {}
    by_cluster: dict[str, int] = {}
    digital_only_count = 0
    with_prices_count = 0
    for item in seeds:
        by_source[item["source"]] = by_source.get(item["source"], 0) + 1
        by_cluster[item["cluster"]] = by_cluster.get(item["cluster"], 0) + 1
        if bool(item.get("digital_only", True)):
            digital_only_count += 1
        if item.get("avg_price") is not None or item.get("min_price") is not None:
            with_prices_count += 1

    _save_seen_seeds({item["seed"].lower() for item in seeds})
    save_json(seeds, RAW_SEEDS_PATH)
    save_json(
        {
            "total": len(seeds),
            "digital_only_count": digital_only_count,
            "with_prices_count": with_prices_count,
            "by_source": dict(sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_cluster": dict(sorted(by_cluster.items(), key=lambda kv: (-kv[1], kv[0]))),
            "collected_at": time.strftime("%Y-%m-%d %H:%M"),
            "features": {
                "google_trends": USE_TRENDS and TrendReq is not None and not NO_NETWORK,
                "pinterest": USE_PINTEREST and not NO_NETWORK,
                "semantic_dedup": USE_SEMANTIC_DEDUP and SentenceTransformer is not None,
                "llm_viability": USE_LLM_VIABILITY and _build_llm_client() is not None,
                "etsy_best_selling": not NO_NETWORK,
                "llm_longtail": USE_LONGTAIL and _build_llm_client() is not None,
                "multi_platform": USE_MULTI_PLATFORM and not NO_NETWORK,
            },
            "negative_filter": {
                "patterns": NEGATIVE_SEED_PATTERNS,
                "removed": removed_neg,
            },
            "stages": stage,
        },
        SEEDS_COLLECTION_STATS_PATH,
    )

    # Console log: before/after summary for quick debugging.
    print(
        "[money_niche_hunter.collector] seeds stages: "
        f"expand={stage.get('stage_expand_total')} "
        f"neg_removed={stage.get('stage_negative_removed')} "
        f"after_neg={stage.get('stage_after_negative_total')} "
        f"after_trends={stage.get('stage_after_trends_total')} "
        f"after_viability={stage.get('stage_after_viability_total')} "
        f"after_dedup={stage.get('stage_after_dedup_total')} "
        f"longtail={stage.get('stage_longtail_generated')} "
        f"final={stage.get('stage_final_total')}"
    )

    return seeds
