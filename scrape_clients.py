from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote_plus

import requests

from network_retry import fetch_with_retry

# Load env files early so provider tokens are available for all entrypoints.
# This repo uses .env.scrape.local as the source-of-truth for scraping provider keys.
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

if load_dotenv is not None:
    _ROOT = os.path.abspath(os.path.dirname(__file__))
    for _name in (".env", ".env.openai.local", ".env.scrape.local"):
        _path = os.path.join(_ROOT, _name)
        if os.path.exists(_path):
            # Do not override already-exported env vars.
            load_dotenv(_path, override=False)


class ScrapeClient:
    """Thin wrapper over different scraping providers.

    Provider selection is env-driven and tokens are never hardcoded.

    Supported providers:
      - scraperapi (legacy)
      - scrapedo (api mode)
      - scrapingbee (api mode)
      - zenrows (api mode)

    Use cases in this repo:
      - google SERP HTML fetch
      - etsy HTML fetch
      - ebay HTML fetch
    """

    def __init__(self, *, provider: str, timeout_s: int, max_retries: int, max_elapsed_s: float):
        self.provider = (provider or "").strip().lower()
        self.timeout_s = int(timeout_s)
        self.max_retries = int(max_retries)
        self.max_elapsed_s = float(max_elapsed_s)

    @staticmethod
    def from_env(*, default_provider: str, timeout_env: str, retries_env: str, elapsed_env: str) -> "ScrapeClient":
        provider = os.getenv("SCRAPE_PROVIDER", default_provider).strip().lower()
        timeout_s = int(os.getenv(timeout_env, "10"))
        max_retries = int(os.getenv(retries_env, "1"))
        max_elapsed_s = float(os.getenv(elapsed_env, "15"))
        return ScrapeClient(provider=provider, timeout_s=timeout_s, max_retries=max_retries, max_elapsed_s=max_elapsed_s)

    def _scraperapi_fetch(self, *, url: str, headers: dict[str, str]) -> tuple[str | None, dict[str, Any]]:
        api_key = os.getenv("SCRAPERAPI_KEY", "").strip()
        endpoint = os.getenv("SCRAPERAPI_ENDPOINT", "http://api.scraperapi.com").strip() or "http://api.scraperapi.com"
        params = {"api_key": api_key, "url": url, "keep_headers": "true"}

        def _do() -> str:
            resp = requests.get(endpoint, params=params, headers=headers, timeout=self.timeout_s)
            resp.raise_for_status()
            return resp.text

        return fetch_with_retry(
            _do,
            max_retries=self.max_retries,
            backoffs=[2, 4],
            retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
            stage="request",
            warnings_prefix="scraperapi",
            max_elapsed_s=self.max_elapsed_s,
        )

    def _scrapedo_fetch(
        self,
        *,
        url: str,
        headers: dict[str, str],
        extra_params: dict[str, Any] | None = None,
        send_headers: bool = True,
    ) -> tuple[str | None, dict[str, Any]]:
        token = os.getenv("SCRAPEDO_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "SCRAPEDO_TOKEN is missing. Ensure .env.scrape.local is loaded (python-dotenv installed) or export SCRAPEDO_TOKEN."
            )
        endpoint = os.getenv("SCRAPEDO_ENDPOINT", "https://api.scrape.do/").strip() or "https://api.scrape.do/"
        custom_headers = os.getenv("SCRAPEDO_CUSTOM_HEADERS", "false").strip().lower()
        # scrape.do api mode expects token + url; requests will handle URL encoding.
        params: dict[str, Any] = {"token": token, "url": url}
        if custom_headers in {"true", "false"}:
            params["customHeaders"] = custom_headers
        if extra_params:
            for key, value in extra_params.items():
                if value is None:
                    continue
                params[str(key)] = value

        def _do() -> str:
            request_headers = headers if send_headers else None
            resp = requests.get(endpoint, params=params, headers=request_headers, timeout=self.timeout_s)
            if resp.status_code >= 400:
                body = (resp.text or "").replace("\n", " ")[:800]
                raise requests.HTTPError(f"scrape.do HTTP {resp.status_code}: {body}", response=resp)
            return resp.text

        return fetch_with_retry(
            _do,
            max_retries=self.max_retries,
            backoffs=[2, 4],
            retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
            stage="request",
            warnings_prefix="scrapedo",
            max_elapsed_s=self.max_elapsed_s,
        )

    def _scrapingbee_fetch(self, *, url: str, headers: dict[str, str]) -> tuple[str | None, dict[str, Any]]:
        api_key = os.getenv("SCRAPINGBEE_API_KEY", "").strip()
        endpoint = os.getenv("SCRAPINGBEE_ENDPOINT", "https://app.scrapingbee.com/api/v1/").strip() or "https://app.scrapingbee.com/api/v1/"
        # ScrapingBee API: api_key=...&url=<encoded>
        params = {
            "api_key": api_key,
            "url": url,
            # keep the response as HTML
            "render_js": "false",
        }

        def _do() -> str:
            resp = requests.get(endpoint, params=params, headers=headers, timeout=self.timeout_s)
            resp.raise_for_status()
            return resp.text

        return fetch_with_retry(
            _do,
            max_retries=self.max_retries,
            backoffs=[2, 4],
            retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
            stage="request",
            warnings_prefix="scrapingbee",
            max_elapsed_s=self.max_elapsed_s,
        )

    def _zenrows_fetch(
        self,
        *,
        url: str,
        headers: dict[str, str],
        extra_params: dict[str, Any] | None = None,
        send_headers: bool = True,
    ) -> tuple[str | None, dict[str, Any]]:
        api_key = os.getenv("ZENROWS_API_KEY", "").strip()
        endpoint = os.getenv("ZENROWS_ENDPOINT", "https://api.zenrows.com/v1/").strip() or "https://api.zenrows.com/v1/"

        params: dict[str, Any] = {
            "apikey": api_key,
            "url": url,
        }
        if extra_params:
            for key, value in extra_params.items():
                if value is None:
                    continue
                params[str(key)] = value

        def _do() -> str:
            request_headers = headers if send_headers else None
            resp = requests.get(endpoint, params=params, headers=request_headers, timeout=self.timeout_s)
            resp.raise_for_status()
            return resp.text

        return fetch_with_retry(
            _do,
            max_retries=self.max_retries,
            backoffs=[2, 4],
            retry_on=(requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError),
            stage="request",
            warnings_prefix="zenrows",
            max_elapsed_s=self.max_elapsed_s,
        )

    def fetch_html_with_meta(
        self,
        *,
        url: str,
        headers: dict[str, str],
        extra_params: dict[str, Any] | None = None,
        send_headers: bool = True,
    ) -> tuple[str, dict[str, Any]]:
        """Fetch HTML and return (html, retry_meta). Raises RuntimeError if provider returns None."""
        if self.provider == "scrapedo":
            html, meta = self._scrapedo_fetch(url=url, headers=headers, extra_params=extra_params, send_headers=send_headers)
        elif self.provider == "scrapingbee":
            html, meta = self._scrapingbee_fetch(url=url, headers=headers)
        elif self.provider == "zenrows":
            html, meta = self._zenrows_fetch(url=url, headers=headers, extra_params=extra_params, send_headers=send_headers)
        else:
            # default to legacy scraperapi
            html, meta = self._scraperapi_fetch(url=url, headers=headers)

        if html is None:
            raise RuntimeError(meta.get("error") or "scrape_failed")
        return str(html), meta


def build_google_url(query: str, *, country: str, language: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(query)}&hl={quote_plus(language)}&gl={quote_plus(country)}"
