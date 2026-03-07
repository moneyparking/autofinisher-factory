from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path("/home/agent/autofinisher-factory/digital_product_factory")
CONFIGS_DIR = BASE_DIR / "configs"
OUTPUTS_DIR = BASE_DIR / "outputs"
CONTRACTS_DIR = BASE_DIR / "contracts"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-") or "untitled-product"


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
