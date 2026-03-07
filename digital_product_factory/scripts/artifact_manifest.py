from __future__ import annotations

import argparse
from pathlib import Path

try:
    import fitz  # type: ignore
except Exception:
    fitz = None

from common import OUTPUTS_DIR, read_json, write_json

ARTIFACT_MAP = {
    "deliverable_pdf": "deliverable.pdf",
    "master_png": "master.png",
    "mockup_png": "mockup.png",
    "seo_txt": "SEO.txt",
}


def validate_links(pdf_path: Path) -> int:
    if fitz is None:
        return 0
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return 0
    broken = 0
    doc = fitz.open(str(pdf_path))
    for page in doc:
        for link in page.get_links():
            if not link.get("uri") and link.get("page") is None:
                broken += 1
    return broken


def build_manifest(spec: dict, product_dir: Path) -> dict:
    artifacts = []
    for artifact_type, filename in ARTIFACT_MAP.items():
        path = product_dir / filename
        artifacts.append(
            {
                "artifact_type": artifact_type,
                "path": str(path),
                "exists": path.exists(),
                "is_primary": artifact_type == "deliverable_pdf",
            }
        )

    required_ready = all((product_dir / filename).exists() for filename in ["deliverable.pdf", "master.png"])
    preview_ready = all((product_dir / filename).exists() for filename in ["master.png", "mockup.png"])
    broken_links = validate_links(product_dir / "deliverable.pdf")

    return {
        "manifest_version": "v1",
        "product_slug": spec["product_slug"],
        "product_spec_path": str(product_dir / "digital_product_spec.json"),
        "build_status": "ready" if required_ready else "incomplete",
        "artifacts": artifacts,
        "completeness": {
            "required_artifacts_ready": required_ready,
            "preview_assets_ready": preview_ready,
        },
        "qa": {
            "checks_passed": required_ready and broken_links == 0,
            "broken_links": broken_links,
            "notes": [] if fitz is not None else ["link_validation_skipped_no_pymupdf"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_slug")
    args = parser.parse_args()

    product_dir = OUTPUTS_DIR / args.product_slug
    spec = read_json(product_dir / "digital_product_spec.json")
    manifest = build_manifest(spec, product_dir)
    out_path = product_dir / "artifact_manifest.json"
    write_json(out_path, manifest)
    print(out_path)


if __name__ == "__main__":
    main()
