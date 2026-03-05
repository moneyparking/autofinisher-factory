from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from money_niche_hunter.config.settings import SANITY_OUTPUT_PATH, SHORTLIST_PATH
from money_niche_hunter.utils.storage import load_json, save_json

load_dotenv()

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


MODEL = os.getenv("MONEY_NICHE_HUNTER_LLM_MODEL", "gpt-4o-mini")
PROMPT_TEMPLATE = """
Ты — эксперт по цифровым продуктам на Etsy (planners, templates, checklists, trackers).

Ниша: \"{seed}\"

Верни только JSON без пояснений:
{{
  \"product_formats\": [\"формат 1\", \"формат 2\", \"формат 3\"],
  \"difficulty\": \"low\" | \"medium\" | \"high\",
  \"differentiators\": [\"дифференциатор 1\", \"дифференциатор 2\"],
  \"toxicity_flags\": [\"флаг 1\"] или [],
  \"sanity_verdict\": \"go\" | \"maybe\" | \"reject\",
  \"reason\": \"короткое обоснование (1-2 предложения)\"
}}
""".strip()


def _build_client() -> Any:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key, base_url=base_url)


def calculate_final_score(item: dict[str, Any]) -> float:
    base = float(item.get("composite_score") or 0.0)
    verdict = str(item.get("sanity_verdict") or "maybe")
    multiplier = {
        "go": 1.6,
        "maybe": 1.0,
        "reject": 0.2,
        "error": 0.5,
    }.get(verdict, 0.8)
    return round(base * multiplier, 6)


def review_with_llm(item: dict[str, Any], client: Any) -> dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(seed=item["seed"])
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        item.update(
            {
                "product_formats": result.get("product_formats", []),
                "difficulty": result.get("difficulty", "medium"),
                "differentiators": result.get("differentiators", []),
                "toxicity_flags": result.get("toxicity_flags", []),
                "sanity_verdict": result.get("sanity_verdict", "maybe"),
                "sanity_reason": result.get("reason", ""),
                "reviewed_at": datetime.now().isoformat(),
            }
        )
        item["final_score"] = calculate_final_score(item)
        return item
    except Exception as e:  # pragma: no cover
        item["sanity_verdict"] = "error"
        item["sanity_reason"] = str(e)[:200]
        item["final_score"] = calculate_final_score(item)
        return item


def run_sanity_check(shortlist_path: str = SHORTLIST_PATH, output_path: str = SANITY_OUTPUT_PATH) -> list[dict[str, Any]]:
    shortlist = load_json(shortlist_path, default=[])
    if not shortlist:
        return []
    client = _build_client()
    reviewed: list[dict[str, Any]] = []
    for item in shortlist:
        reviewed_item = review_with_llm(dict(item), client)
        reviewed.append(reviewed_item)
    reviewed.sort(key=lambda x: float(x.get("final_score") or 0.0), reverse=True)
    save_json(reviewed, output_path)
    return reviewed
