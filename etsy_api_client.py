import json
import os
import time
from typing import Any, Dict, Optional

import requests

BASE_URL = "https://openapi.etsy.com/v3/application"
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 1.0
TIMEOUT_SECONDS = 30


def _build_headers() -> Dict[str, str]:
    api_key = os.environ.get("ETSY_API_KEY", "")
    access_token = os.environ.get("ETSY_ACCESS_TOKEN", "")
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["x-api-key"] = api_key
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _request_with_backoff(method: str, url: str, *, params: Optional[Dict[str, Any]] = None, json_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    headers = _build_headers()
    if "x-api-key" not in headers:
        return {"error": "Missing ETSY_API_KEY"}

    last_error: Dict[str, Any] = {"error": "Unknown Etsy API failure"}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_payload,
                timeout=TIMEOUT_SECONDS,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                sleep_seconds = float(retry_after) if retry_after else BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                last_error = {
                    "error": "HTTP 429 Too Many Requests",
                    "status_code": 429,
                    "attempt": attempt,
                }
                if attempt < MAX_RETRIES:
                    time.sleep(sleep_seconds)
                    continue
                return last_error

            if response.status_code >= 400:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"raw_text": response.text[:1000]}
                return {
                    "error": "Etsy API request failed",
                    "status_code": response.status_code,
                    "details": payload,
                }

            try:
                return response.json()
            except ValueError:
                return {
                    "error": "Invalid JSON response from Etsy API",
                    "status_code": response.status_code,
                    "raw_text": response.text[:1000],
                }
        except requests.RequestException as exc:
            last_error = {
                "error": "Network error while calling Etsy API",
                "details": str(exc),
                "attempt": attempt,
            }
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
                continue
            return last_error

    return last_error


def search_listings(keyword: str, limit: int = 100) -> Dict[str, Any]:
    safe_limit = max(1, min(int(limit), 100))
    url = f"{BASE_URL}/listings/active"
    return _request_with_backoff(
        "GET",
        url,
        params={"keywords": keyword, "limit": safe_limit},
    )


def create_draft(shop_id: str, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    if not shop_id:
        return {"error": "Missing shop_id"}
    url = f"{BASE_URL}/shops/{shop_id}/listings"
    return _request_with_backoff("POST", url, json_payload=payload_dict)


if __name__ == "__main__":
    print(json.dumps({"status": "ok", "module": "etsy_api_client"}))
