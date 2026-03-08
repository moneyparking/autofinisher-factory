from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from common import OUTPUTS_DIR

try:
    from run_product import run_source_path
except Exception:  # pragma: no cover - import path fallback for tests
    from scripts.run_product import run_source_path  # type: ignore

CONFIG_PATH = Path("configs/canonical_products.json")
SUMMARY_PATH = OUTPUTS_DIR / "_integration_summary.json"
SCHEMA_SPEC = Path("contracts/digital_product_spec.schema.json")
SCHEMA_MANIFEST = Path("contracts/artifact_manifest.schema.json")
SCHEMA_PACKET = Path("contracts/listing_packet.schema.json")


def load_canonical_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def validate_schema(file_path: Path, schema_path: Path) -> None:
    instance = json.loads(file_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for required_key in schema.get("required", []):
        if required_key not in instance:
            raise ValueError(f"Missing required field '{required_key}' in {file_path.name}")


def _parse_qa_output(stdout: str) -> dict:
    payload = stdout.strip()
    if not payload:
        raise ValueError("QA output is empty")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(payload)
    if not isinstance(parsed, dict):
        raise ValueError("QA output did not parse to a dict")
    return parsed


def _run_case(niche_id: str, product_kind: str) -> str:
    slug = run_source_path(
        niche_id=niche_id,
        winner_path=None,
        sku_task_path=None,
        product_kind=product_kind,
    )

    subprocess.run(
        ["python3", "scripts/run_product.py", "--niche-id", niche_id, "--product-kind", product_kind],
        check=True,
    )

    base_path = OUTPUTS_DIR / slug
    for filename in ["digital_product_spec.json", "artifact_manifest.json", "listing_packet_etsy.json"]:
        candidate = base_path / filename
        if not candidate.exists():
            raise FileNotFoundError(f"Missing {filename} for {slug}")

    validate_schema(base_path / "digital_product_spec.json", SCHEMA_SPEC)
    validate_schema(base_path / "artifact_manifest.json", SCHEMA_MANIFEST)
    validate_schema(base_path / "listing_packet_etsy.json", SCHEMA_PACKET)

    qa_result = subprocess.run(
        ["python3", "scripts/qa_runner.py", slug],
        capture_output=True,
        text=True,
        check=True,
    )
    qa_output = _parse_qa_output(qa_result.stdout)
    if not qa_output.get("checks_passed"):
        raise AssertionError(f"QA failed for {slug}: {qa_output}")
    return slug


def main() -> None:
    config = load_canonical_config()
    results: dict[str, dict] = {}
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    for case in config.get("cases", []):
        niche_id = str(case["niche_id"])
        product_kind = str(case["product_kind"])
        try:
            slug = _run_case(niche_id=niche_id, product_kind=product_kind)
            results[slug] = {
                "status": "PASSED",
                "niche_id": niche_id,
                "product_kind": product_kind,
            }
            print(f"{slug} ({product_kind}): PASSED")
        except Exception as exc:
            failed_slug = f"{niche_id}:{product_kind}"
            results[failed_slug] = {
                "status": "FAILED",
                "niche_id": niche_id,
                "product_kind": product_kind,
                "error": str(exc),
            }
            print(f"{failed_slug}: FAILED - {exc}")
            SUMMARY_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            raise SystemExit(1)

    SUMMARY_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Integration check completed. Summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
