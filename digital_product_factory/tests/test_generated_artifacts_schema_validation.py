from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / "digital_product_factory" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from common import CONTRACTS_DIR, OUTPUTS_DIR, read_json

RUN_PRODUCT = REPO_DIR / "digital_product_factory" / "scripts" / "run_product.py"
PRODUCT_CASES = [
    ("2026_adhd_digital_planner_v1", "planner", "2026-adhd-digital-planner"),
    ("2026_adhd_digital_planner_v1", "checklist", "2026-adhd-digital-planner-checklist"),
    ("budget_spreadsheet_v1", "spreadsheet", "budget-spreadsheet"),
]


def load_schema(name: str) -> dict:
    path = CONTRACTS_DIR / name
    assert path.exists(), f"Schema not found: {path}"
    return read_json(path)


@pytest.fixture(scope="session")
def built_product_slugs() -> list[str]:
    slugs: list[str] = []
    for niche_id, product_kind, slug in PRODUCT_CASES:
        subprocess.run(
            [
                "python3",
                str(RUN_PRODUCT),
                "--niche-id",
                niche_id,
                "--product-kind",
                product_kind,
            ],
            check=True,
            cwd=REPO_DIR,
        )
        slugs.append(slug)
    return slugs


@pytest.mark.parametrize(
    "schema_name, artifact_name",
    [
        ("digital_product_spec.schema.json", "digital_product_spec.json"),
        ("artifact_manifest.schema.json", "artifact_manifest.json"),
        ("listing_packet.schema.json", "listing_packet_etsy.json"),
    ],
)
def test_generated_artifacts_match_schema(built_product_slugs: list[str], schema_name: str, artifact_name: str) -> None:
    schema = load_schema(schema_name)
    for slug in built_product_slugs:
        artifact_path = OUTPUTS_DIR / slug / artifact_name
        assert artifact_path.exists(), f"Missing artifact: {artifact_path}"
        jsonschema.validate(instance=read_json(artifact_path), schema=schema)


def test_generated_listing_packets_exist_for_all_families(built_product_slugs: list[str]) -> None:
    for slug in built_product_slugs:
        packet_path = OUTPUTS_DIR / slug / "listing_packet_etsy.json"
        assert packet_path.exists(), f"Missing listing packet: {packet_path}"
