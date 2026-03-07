from __future__ import annotations

import argparse

from common import OUTPUTS_DIR, read_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_slug")
    args = parser.parse_args()

    product_dir = OUTPUTS_DIR / args.product_slug
    spec = read_json(product_dir / "digital_product_spec.json")
    manifest = read_json(product_dir / "artifact_manifest.json")

    missing_files = [
        required
        for required in spec.get("must_have_files", [])
        if not (product_dir / required).exists()
    ]
    broken_links = int(manifest.get("qa", {}).get("broken_links", 0))
    checks_passed = (
        not missing_files
        and broken_links == 0
        and manifest.get("completeness", {}).get("required_artifacts_ready", False)
    )

    print(
        {
            "product_slug": args.product_slug,
            "checks_passed": checks_passed,
            "missing_files": missing_files,
            "broken_links": broken_links,
        }
    )


if __name__ == "__main__":
    main()
