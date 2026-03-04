from __future__ import annotations

import math
import re
from typing import Any

from performance_intel import performance_feedback_score

HIGH_INTENT_TOKENS = {
    "planner": 12,
    "tracker": 12,
    "checklist": 11,
    "spreadsheet": 12,
    "template": 10,
    "printable": 9,
    "binder": 10,
    "journal": 9,
    "budget": 10,
    "log": 9,
    "worksheet": 8,
    "goodnotes": 8,
    "notion": 7,
    "pdf": 6,
    "digital": 6,
}

PREMIUM_TOKENS = {
    "small business": 12,
    "bookkeeping": 12,
    "wedding": 10,
    "adhd": 10,
    "rental": 11,
    "inventory": 11,
    "client": 9,
    "productivity": 8,
    "emergency": 8,
    "fitness": 7,
    "medication": 10,
}

MARKETPLACE_FIT = {
    "etsy": {
        "printable": 10,
        "planner": 9,
        "binder": 8,
        "checklist": 8,
        "journal": 7,
        "wedding": 8,
        "adhd": 7,
    },
    "gumroad": {
        "spreadsheet": 10,
        "small business": 10,
        "bookkeeping": 10,
        "template": 8,
        "inventory": 9,
        "rental": 9,
        "tracker": 7,
    },
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def keyword_score(text: str, weights: dict[str, int]) -> float:
    text_n = normalize(text)
    score = 0.0
    for token, weight in weights.items():
        if token in text_n:
            score += weight
    return score


def infer_vertical(text: str) -> str:
    text_n = normalize(text)
    if "adhd" in text_n:
        return "adhd_productivity"
    if any(token in text_n for token in ["bookkeeping", "inventory", "rental", "invoice", "client", "small business"]):
        return "small_business_ops"
    if any(token in text_n for token in ["wedding", "bridal"]):
        return "wedding_systems"
    if any(token in text_n for token in ["cleaning", "house", "home", "chore", "emergency"]):
        return "home_organization"
    if any(token in text_n for token in ["fitness", "habit", "meal", "medication", "wellness", "sleep"]):
        return "wellness_trackers"
    if "pet" in text_n or "dog" in text_n or "cat" in text_n or "vet" in text_n:
        return "pet_household_records"
    return "general_utility"


def marketplace_fit_score(text: str, marketplace: str) -> float:
    weights = MARKETPLACE_FIT.get(marketplace, {})
    return min(100.0, keyword_score(text, weights) * 2.5)


def production_ease_score(text: str) -> float:
    text_n = normalize(text)
    score = 70.0
    if "spreadsheet" in text_n:
        score += 10
    if any(token in text_n for token in ["planner", "tracker", "checklist", "log"]):
        score += 10
    if any(token in text_n for token in ["poster", "wall art", "portrait"]):
        score -= 20
    return max(0.0, min(100.0, score))


def price_power_score(text: str) -> float:
    base = 45.0 + keyword_score(text, PREMIUM_TOKENS)
    if "bundle" in normalize(text):
        base += 8
    if "spreadsheet" in normalize(text):
        base += 10
    return max(0.0, min(100.0, base))


def demand_score(metrics: dict[str, Any]) -> float:
    sold = float(metrics.get("sold_listings") or metrics.get("sold") or 0)
    return max(0.0, min(100.0, sold / 5.0))


def liquidity_score(metrics: dict[str, Any]) -> float:
    str_value = float(metrics.get("sell_through_rate") or 0)
    active = float(metrics.get("active_listings") or metrics.get("active") or 0)
    active_component = 0.0 if active <= 0 else min(30.0, math.log10(active + 1) * 10)
    return max(0.0, min(100.0, str_value + active_component))


def monetization_score(name: str, metrics: dict[str, Any], context: dict[str, Any] | None = None) -> float:
    context = context or {}
    ds = demand_score(metrics)
    ls = liquidity_score(metrics)
    ps = price_power_score(name)
    es = production_ease_score(name)
    etsy_fit = marketplace_fit_score(name, "etsy")
    gumroad_fit = marketplace_fit_score(name, "gumroad")
    distribution_fit = max(etsy_fit, gumroad_fit)
    trend_score = float(context.get("trend_score", 50.0) or 50.0)
    review_opportunity_score = float(context.get("review_opportunity_score", 50.0) or 50.0)
    competition_profile_score = float(context.get("competition_profile_score", 50.0) or 50.0)
    performance_score = float(context.get("performance_feedback_score", 50.0) or 50.0)
    score = (
        (0.22 * ds)
        + (0.20 * ls)
        + (0.16 * ps)
        + (0.12 * es)
        + (0.10 * distribution_fit)
        + (0.06 * trend_score)
        + (0.06 * review_opportunity_score)
        + (0.04 * competition_profile_score)
        + (0.04 * performance_score)
    )
    return round(max(0.0, min(100.0, score)), 2)


def suggested_price(name: str, metrics: dict[str, Any], context: dict[str, Any] | None = None) -> float:
    score = monetization_score(name, metrics, context)
    base = 4.99
    if "spreadsheet" in normalize(name) or "bookkeeping" in normalize(name) or "rental" in normalize(name):
        base = 9.99
    elif "bundle" in normalize(name) or "binder" in normalize(name):
        base = 7.99
    price = base + (score / 100.0) * 4.0
    return round(min(price, 14.99), 2)


def ranking_payload(item: dict[str, Any]) -> dict[str, Any]:
    name = item.get("niche") or item.get("query") or item.get("title") or ""
    metrics = item.get("metrics") or item.get("market_metrics") or {}
    vertical = item.get("vertical") or infer_vertical(name)
    intel = item.get("intel") or {}
    context = {
        "trend_score": float(item.get("trend_score") or intel.get("trend_score") or 50.0),
        "review_opportunity_score": float(intel.get("review_opportunity_score") or 50.0),
        "competition_profile_score": float(intel.get("competition_profile_score") or 50.0),
        "performance_feedback_score": float(intel.get("performance_feedback_score") or performance_feedback_score(name, vertical)),
    }
    return {
        "niche": name,
        "vertical": vertical,
        "monetization_score": monetization_score(name, metrics, context),
        "suggested_price": suggested_price(name, metrics, context),
        "etsy_fit": round(marketplace_fit_score(name, "etsy"), 2),
        "gumroad_fit": round(marketplace_fit_score(name, "gumroad"), 2),
        "production_ease": round(production_ease_score(name), 2),
        "price_power": round(price_power_score(name), 2),
        "trend_score": round(context["trend_score"], 2),
        "review_opportunity_score": round(context["review_opportunity_score"], 2),
        "competition_profile_score": round(context["competition_profile_score"], 2),
        "performance_feedback_score": round(context["performance_feedback_score"], 2),
    }
