from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from common import CONFIGS_DIR, OUTPUTS_DIR, read_json


def ensure_placeholder_outputs(product_slug: str) -> None:
    product_dir = OUTPUTS_DIR / product_slug
    product_dir.mkdir(parents=True, exist_ok=True)
    for name in ["deliverable.pdf", "master.png", "mockup.png", "SEO.txt"]:
        path = product_dir / name
        if not path.exists():
            if name.endswith(".txt"):
                path.write_text("SEO placeholder", encoding="utf-8")
            else:
                path.touch()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product_id", type=int)
    args = parser.parse_args()

    config_path = CONFIGS_DIR / f"product_{args.product_id}.json"
    subprocess.run(["python3", str(Path(__file__).with_name("spec_compiler.py")), str(config_path)], check=True)
    config = read_json(config_path)
    slug = str(config.get("name", f"product_{args.product_id}")).strip().lower().replace(" ", "-").replace("_", "-")
    ensure_placeholder_outputs(slug)
    subprocess.run(["python3", str(Path(__file__).with_name("artifact_manifest.py")), slug], check=True)
    subprocess.run(["python3", str(Path(__file__).with_name("listing_compiler.py")), slug, "--channel", "etsy"], check=True)
    subprocess.run(["python3", str(Path(__file__).with_name("qa_runner.py")), slug], check=True)


if __name__ == "__main__":
    main()
