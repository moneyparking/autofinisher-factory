import argparse
import json
from pathlib import Path
from typing import Any, Dict

from etsy_api_client import create_draft

SCHEMA_VERSION = "2.1"


def _load_payload_file(payload_file: str) -> Dict[str, Any]:
    path = Path(payload_file)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"error": f"Payload file not found: {payload_file}"}
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON in payload file: {exc}"}
    except OSError as exc:
        return {"error": f"Unable to read payload file: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish an Etsy draft from a local JSON payload file.")
    parser.add_argument("--payload_file", required=True, help="Path to local JSON payload file")
    args = parser.parse_args()

    loaded = _load_payload_file(args.payload_file)
    if "error" in loaded:
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "response": loaded,
        }))
        return 1

    shop_id = str(loaded.get("shop_id", ""))
    payload = loaded.get("payload")
    if not shop_id or not isinstance(payload, dict):
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "response": {"error": "payload_file must contain shop_id and payload object"},
        }))
        return 1

    response = create_draft(shop_id, payload)
    status = "error" if isinstance(response, dict) and response.get("error") else "success"
    print(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "response": response,
    }))
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
