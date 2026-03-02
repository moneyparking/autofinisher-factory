#!/usr/bin/env python3
import argparse
import json
import sys
import os
import requests

GUMROAD_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload_file", required=True)
    args = parser.parse_args()

    if not GUMROAD_TOKEN:
        print(json.dumps({"status": "error", "error_details": "GUMROAD_ACCESS_TOKEN is missing in environment"}))
        sys.exit(1)

    try:
        with open(args.payload_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        payload = data.get("api_request_ready", {}).get("payload")
        if not payload:
            raise ValueError("Invalid payload format. Missing 'api_request_ready.payload'")

        payload["access_token"] = GUMROAD_TOKEN
        
        url = "https://gumroad.com/api/v2/products"
        response = requests.post(url, data=payload, timeout=20)
        response.raise_for_status()
        
        result_data = response.json()
        print(json.dumps({
            "schema_version": "2.1",
            "module": "gumroad_publisher",
            "status": "success",
            "product_id": result_data.get("product", {}).get("id", ""),
            "short_url": result_data.get("product", {}).get("short_url", "")
        }, indent=2))

    except Exception as e:
        print(json.dumps({"status": "error", "error_details": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
