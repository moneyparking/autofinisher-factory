from __future__ import annotations

from pathlib import Path
from typing import Any

from common import clean_text, read_json

REGISTRY_PATH = Path("/home/agent/autofinisher-factory/digital_product_factory/configs/product_family_registry.json")


def load_product_family_registry() -> dict[str, dict[str, Any]]:
    payload = read_json(REGISTRY_PATH)
    if not isinstance(payload, dict):
        raise ValueError("product_family_registry.json must contain a top-level object")
    return payload


def get_family_preset(product_family: str) -> dict[str, Any]:
    registry = load_product_family_registry()
    if product_family not in registry:
        raise KeyError(f"Unknown product family: {product_family}")
    preset = registry[product_family]
    if not isinstance(preset, dict):
        raise ValueError(f"Preset for {product_family} must be an object")
    return preset


def _normalize_tokens(values: list[str]) -> list[str]:
    return [clean_text(value).lower() for value in values if clean_text(value)]



def _rule_matches(rule: dict[str, Any], *, product_kind: str, niche: str, keyword: str, combined_text: str) -> bool:
    kinds = _normalize_tokens(rule.get("product_kinds") or [])
    if kinds and clean_text(product_kind).lower() not in kinds:
        return False
    niche_contains = _normalize_tokens(rule.get("niche_contains") or [])
    if niche_contains and not any(token in niche for token in niche_contains):
        return False
    keyword_contains = _normalize_tokens(rule.get("keyword_contains") or [])
    if keyword_contains and not any(token in keyword for token in keyword_contains):
        return False
    combined_contains = _normalize_tokens(rule.get("combined_contains") or [])
    if combined_contains and not any(token in combined_text for token in combined_contains):
        return False
    return True



def resolve_product_family(*, product_kind: str, niche_id: str, winner: dict[str, Any], sku_task: dict[str, Any]) -> str:
    registry = load_product_family_registry()
    niche = str(niche_id or "").lower()
    keyword = str(winner.get("niche_keyword") or sku_task.get("niche_keyword") or "").lower()
    combined_text = " ".join(
        part for part in [
            niche,
            keyword,
            str(((sku_task.get("cluster") or {}).get("core_skus") or [{}])[0].get("slug") or "").lower(),
            str((winner.get("thesis") or {}).get("solution") or "").lower(),
        ]
        if part
    )

    matches: list[tuple[int, str]] = []
    for family_name, preset in registry.items():
        if not isinstance(preset, dict):
            continue
        for rule in preset.get("match_rules") or []:
            if isinstance(rule, dict) and _rule_matches(rule, product_kind=product_kind, niche=niche, keyword=keyword, combined_text=combined_text):
                matches.append((int(rule.get("priority") or 100), family_name))
                break

    if matches:
        matches.sort(key=lambda item: item[0])
        return matches[0][1]

    default_family_by_kind = {
        "planner": "planner_base",
        "checklist": "checklist_base",
        "spreadsheet": "budget_sheet_base",
        "notion_companion": "notion_companion_base",
    }
    fallback_family = default_family_by_kind.get(clean_text(product_kind).lower())
    if fallback_family and fallback_family in registry:
        return fallback_family

    raise ValueError(f"Unable to resolve product family for niche_id={niche_id} product_kind={product_kind}")
