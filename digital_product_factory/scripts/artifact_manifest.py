from __future__ import annotations

import argparse
from pathlib import Path

try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None

try:
    import fitz  # type: ignore
except Exception:
    fitz = None

from common import OUTPUTS_DIR, read_json, write_json

ARTIFACT_MAP = {
    "deliverable_pdf": "deliverable.pdf",
    "deliverable_xlsx": "deliverable.xlsx",
    "deliverable_raw_pdf": "deliverable_raw.pdf",
    "master_png": "master.png",
    "mockup_png": "mockup.png",
    "seo_txt": "SEO.txt",
    "source_csv": "source_rows.csv",
    "preview_pdf": "preview.pdf",
    "page_manifest": "page_manifest.json",
    "planner_link_map": "planner_link_map.csv",
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

    required_filenames = [ARTIFACT_MAP[item] for item in spec.get("required_artifacts", []) if item in ARTIFACT_MAP]
    preview_filenames = [ARTIFACT_MAP[item] for item in spec.get("preview_assets_required", []) if item in ARTIFACT_MAP]
    required_ready = all((product_dir / filename).exists() for filename in required_filenames)
    preview_ready = all((product_dir / filename).exists() for filename in preview_filenames)
    broken_links = validate_links(product_dir / "deliverable.pdf")
    notes = [] if fitz is not None else ["link_validation_skipped_no_pymupdf"]
    hyperlink_stage = spec.get("hyperlink_stage") or {}
    hyperlink_status = str(hyperlink_stage.get("status") or "not_applicable")
    if spec.get("product_kind") == "planner":
        thresholds = spec.get("qa_thresholds") or {}
        deliverable_pdf = product_dir / "deliverable.pdf"
        raw_pdf = product_dir / "deliverable_raw.pdf"
        link_map = product_dir / "planner_link_map.csv"
        page_manifest = product_dir / "page_manifest.json"
        if PdfReader is not None and deliverable_pdf.exists():
            try:
                page_count = len(PdfReader(str(deliverable_pdf)).pages)
                min_page_count = int(thresholds.get("min_page_count") or 0)
                if min_page_count and page_count < min_page_count:
                    notes.append("page_count_below_threshold")
            except Exception:
                notes.append("page_count_check_failed")
        if not raw_pdf.exists():
            notes.append("planner_raw_pdf_missing")
        if not link_map.exists():
            notes.append("planner_link_map_missing")
        if not page_manifest.exists():
            notes.append("page_manifest_missing")
        if spec.get("hyperlinked"):
            if spec.get("hyperlinked_ready", False) and hyperlink_status == "done":
                pass
            elif hyperlink_status == "failed":
                notes.append("hyperlink_stage_failed")
            else:
                notes.append("hyperlink_stage_not_completed")
    if spec.get("product_kind") == "spreadsheet":
        xlsx_path = product_dir / "deliverable.xlsx"
        if not xlsx_path.exists():
            notes.append("spreadsheet_deliverable_missing")

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
            "checks_passed": required_ready and broken_links == 0 and "hyperlink_stage_failed" not in notes,
            "broken_links": broken_links,
            "hyperlink_stage_status": hyperlink_status,
            "notes": notes,
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
