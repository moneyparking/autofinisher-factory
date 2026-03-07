from __future__ import annotations

import argparse
import json
import os

from common import CONFIGS_DIR, write_json

SYSTEM_PROMPT = (
    "You are an expert digital product architect. Return strict JSON for a semi-automatic digital product config. "
    "Keep it simple, practical, and buildable. Include: name, type, layout_profile, families, themes, linking_profile, "
    "canva_template_key when relevant, pages, page_rules, metadata."
)


def generate_with_openai(prompt: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_object"}},
    )
    text = getattr(response, "output_text", "")
    return json.loads(text)


def generate_fallback(prompt: str) -> dict:
    safe_name = prompt.strip().replace(" ", "_")[:80] or "digital_product"
    return {
        "name": safe_name,
        "type": "canva_pdf",
        "layout_profile": "planner_daily",
        "families": ["planner_base"],
        "themes": ["Default"],
        "linking_profile": "default",
        "pages": [
            {
                "page_id": "core_page",
                "page_type": "planner",
                "title_template": safe_name.replace("_", " "),
                "repeat": {"mode": "single"},
            }
        ],
        "page_rules": {},
        "metadata": {
            "benefit_statement": "Provides a practical digital product with clear structure.",
            "user_problem": "Buyer needs a usable digital system.",
            "intended_user": "Digital product buyer",
            "usage_outcome": "Gets a ready-to-use file set.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("product_id", type=int)
    args = parser.parse_args()

    try:
        config = generate_with_openai(args.prompt)
        source = "openai"
    except Exception:
        config = generate_fallback(args.prompt)
        source = "fallback"

    config["id"] = args.product_id
    config.setdefault("metadata", {})["generated_by"] = source
    out_path = CONFIGS_DIR / f"product_{args.product_id}.json"
    write_json(out_path, config)
    print(out_path)


if __name__ == "__main__":
    main()
