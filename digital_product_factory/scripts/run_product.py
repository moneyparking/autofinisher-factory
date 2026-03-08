from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from common import CONFIGS_DIR, OUTPUTS_DIR, clean_text, read_json, safe_slug

READY_TO_PUBLISH_DIR = Path("/home/agent/autofinisher-factory/ready_to_publish")
PUBLISH_PACKETS_DIR = Path("/home/agent/autofinisher-factory/publish_packets")


def stage_product_outputs(product_slug: str) -> None:
    product_dir = OUTPUTS_DIR / product_slug
    ready_dir = READY_TO_PUBLISH_DIR / product_slug
    packet_dir = PUBLISH_PACKETS_DIR / product_slug
    ready_dir.mkdir(parents=True, exist_ok=True)
    packet_dir.mkdir(parents=True, exist_ok=True)

    for filename in [
        "deliverable.pdf",
        "deliverable.xlsx",
        "deliverable_raw.pdf",
        "master.png",
        "mockup.png",
        "SEO.txt",
        "source_rows.csv",
        "preview.pdf",
        "page_manifest.json",
        "planner_link_map.csv",
        "listing_preview.html",
        "listing_image_plan.json",
    ]:
        source = product_dir / filename
        if source.exists():
            shutil.copyfile(source, ready_dir / filename)

    for filename in [
        "digital_product_spec.json",
        "artifact_manifest.json",
        "listing_packet_etsy.json",
    ]:
        source = product_dir / filename
        if source.exists():
            shutil.copyfile(source, packet_dir / filename)


def run_config_path(product_id: int) -> str:
    config_path = CONFIGS_DIR / f"product_{product_id}.json"
    subprocess.run(["python3", str(Path(__file__).with_name("spec_compiler.py")), str(config_path)], check=True)
    config = read_json(config_path)
    return str(config.get("name", f"product_{product_id}")).strip().lower().replace(" ", "-").replace("_", "-")


def run_source_path(*, niche_id: str | None, winner_path: str | None, sku_task_path: str | None, product_kind: str | None) -> str:
    command = ["python3", str(Path(__file__).with_name("spec_compiler.py"))]
    if niche_id:
        command.extend(["--niche-id", niche_id])
    if winner_path:
        command.extend(["--winner-path", winner_path])
    if sku_task_path:
        command.extend(["--sku-task-path", sku_task_path])
    if product_kind:
        command.extend(["--product-kind", product_kind])
    subprocess.run(command, check=True)

    if niche_id:
        inferred_winner_path = Path(winner_path) if winner_path else Path(f"/home/agent/autofinisher-factory/data/winners/{niche_id}.json")
        inferred_sku_task_path = Path(sku_task_path) if sku_task_path else Path(f"/home/agent/autofinisher-factory/data/sku_tasks/sku_task_{niche_id}.json")
        validated_direct = Path(f"/home/agent/autofinisher-factory/data/validated_niches/{niche_id}.json")
        validated_item = Path(f"/home/agent/autofinisher-factory/data/validated_niches/items/{niche_id}.json")
        validated_path = validated_direct if validated_direct.exists() else validated_item if validated_item.exists() else None
        if inferred_winner_path.exists() and inferred_sku_task_path.exists():
            winner_payload = read_json(inferred_winner_path)
            sku_payload = read_json(inferred_sku_task_path)
        elif validated_path is not None:
            validated_payload = read_json(validated_path)
            winner_payload = {
                "niche_id": clean_text(validated_payload.get("niche_id") or niche_id),
                "niche_keyword": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or niche_id),
                "recommended_sku_cluster": {"core_skus": [{"slug": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or niche_id)}]},
            }
            sku_payload = {
                "niche_id": clean_text(validated_payload.get("niche_id") or niche_id),
                "niche_keyword": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or niche_id),
                "cluster": {"core_skus": [{"slug": clean_text(validated_payload.get("niche_keyword") or validated_payload.get("niche") or niche_id)}]},
            }
        else:
            raise FileNotFoundError(f"No source payloads found for niche_id={niche_id}")
    else:
        winner_payload = read_json(Path(winner_path))
        sku_payload = read_json(Path(sku_task_path))
    core_skus = ((sku_payload.get("cluster") or {}).get("core_skus") or (winner_payload.get("recommended_sku_cluster") or {}).get("core_skus") or [])
    primary_sku = core_skus[0] if core_skus and isinstance(core_skus[0], dict) else {}
    sku_slug = str(primary_sku.get("slug") or winner_payload.get("niche_keyword") or sku_payload.get("niche_keyword") or niche_id or "product")
    inferred_kind = "planner"
    lowered_slug = sku_slug.lower()
    if "notion" in lowered_slug:
        inferred_kind = "notion_companion"
    elif any(token in lowered_slug for token in ["checklist", "cleaning", "chore"]):
        inferred_kind = "checklist"
    elif any(token in lowered_slug for token in ["spreadsheet", "budget", "sheet"]):
        inferred_kind = "spreadsheet"
    kind = product_kind or inferred_kind
    slug = sku_slug if kind in lowered_slug else f"{sku_slug}-{kind}"
    return safe_slug(slug)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_id", nargs="?", type=int)
    parser.add_argument("--niche-id")
    parser.add_argument("--winner-path")
    parser.add_argument("--sku-task-path")
    parser.add_argument("--product-kind", choices=["checklist", "planner", "spreadsheet", "notion_companion"])
    args = parser.parse_args()

    if args.niche_id or args.winner_path or args.sku_task_path:
        slug = run_source_path(
            niche_id=args.niche_id,
            winner_path=args.winner_path,
            sku_task_path=args.sku_task_path,
            product_kind=args.product_kind,
        )
    else:
        if args.product_id is None:
            raise ValueError("product_id is required when source-driven flags are not provided")
        slug = run_config_path(args.product_id)

    subprocess.run(["python3", str(Path(__file__).with_name("build_from_spec.py")), slug], check=True)
    subprocess.run(["python3", str(Path(__file__).with_name("artifact_manifest.py")), slug], check=True)
    subprocess.run(["python3", str(Path(__file__).with_name("listing_compiler.py")), slug, "--channel", "etsy"], check=True)
    subprocess.run(["python3", str(Path(__file__).with_name("render_listing_assets.py")), slug], check=True)
    subprocess.run(["python3", str(Path(__file__).with_name("qa_runner.py")), slug], check=True)
    stage_product_outputs(slug)


if __name__ == "__main__":
    main()
