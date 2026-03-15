from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path("/home/agent/autofinisher-factory")
BATCH_URLS_PATH = BASE_DIR / "batch_urls.txt"
OUTPUT_DIR = BASE_DIR / "youtube_output"
SUMMARY_PATH = BASE_DIR / "batch_logs" / "youtube_batch_summary.json"


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def video_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return query.get("v", [""])[0]


def build_summary() -> dict[str, object]:
    urls = load_lines(BATCH_URLS_PATH)
    rows: list[dict[str, object]] = []
    passed_total = 0
    output_total = 0

    for url in urls:
        video_id = video_id_from_url(url)
        quality_gate_path = OUTPUT_DIR / video_id / "quality_gate.json"
        validated_path = OUTPUT_DIR / video_id / "05_validated_ideas.json"

        quality_gate = load_json(quality_gate_path, {})
        validated = load_json(validated_path, {})

        if quality_gate:
            output_total += 1
        if bool(quality_gate.get("passed")):
            passed_total += 1

        top_items: list[dict[str, object]] = []
        for item in (validated.get("items") or [])[:5]:
            if not isinstance(item, dict):
                continue
            top_items.append(
                {
                    "title": item.get("title"),
                    "wedge": item.get("wedge"),
                    "fms_score": item.get("fms_score"),
                }
            )

        rows.append(
            {
                "video_id": video_id,
                "url": url,
                "has_output": bool(quality_gate),
                "passed": quality_gate.get("passed"),
                "idea_count": quality_gate.get("idea_count"),
                "top_fms_score": quality_gate.get("top_fms_score"),
                "top_bundle_power": quality_gate.get("top_bundle_power"),
                "top_items": top_items,
            }
        )

    return {
        "batch_size": len(urls),
        "outputs_ready": output_total,
        "passed_total": passed_total,
        "rows": rows,
    }


def main() -> None:
    summary = build_summary()
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"batch_size={summary['batch_size']}")
    print(f"outputs_ready={summary['outputs_ready']}")
    print(f"passed_total={summary['passed_total']}")
    print("---")
    for row in summary["rows"]:
        print(
            f"{row['video_id']}\tpassed={row['passed']}\tideas={row['idea_count']}\t"
            f"top_fms={row['top_fms_score']}\tbundle={row['top_bundle_power']}"
        )


if __name__ == "__main__":
    main()
