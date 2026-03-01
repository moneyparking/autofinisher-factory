import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from etsy_api_client import search_listings

SCHEMA_VERSION = "2.1"
DB_PATH = "factory.db"
OUTPUT_DIR = Path("ready_to_publish")


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS niches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            listing_count INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            opportunity_score REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            status TEXT NOT NULL,
            pdf_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _extract_results(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = api_response.get("results")
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]
    return []


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_etsy_payload(keyword: str, price: float, opportunity_score: float) -> Dict[str, Any]:
    safe_price = max(price, 0.2)
    payload = {
        "title": f"{keyword.title()} Demo Product",
        "description": (
            f"Auto-generated Etsy draft for keyword '{keyword}'. "
            f"Opportunity score: {opportunity_score:.2f}. "
            "This draft is for a digital download and should be reviewed before publication."
        ),
        "price": f"{safe_price:.2f}",
        "quantity": 999,
        "who_made": "i_did",
        "when_made": "made_to_order",
        "taxonomy_id": 1,
        "type": "download",
        "is_supply": False,
    }
    return payload


def generate_pdf(keyword: str, product_title: str, avg_price: float, opportunity_score: float) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = OUTPUT_DIR / f"etsy_{keyword.replace(' ', '-').lower()}_{timestamp}.pdf"
    c = canvas.Canvas(str(filename), pagesize=letter)
    width, height = letter

    sections = [
        (40, height - 110, width - 80, 70, f"Keyword: {keyword}"),
        (40, height - 200, width - 80, 70, f"Product: {product_title}"),
        (40, height - 290, width - 80, 70, f"Average Price: {avg_price:.2f}"),
        (40, height - 380, width - 80, 70, f"Opportunity Score: {opportunity_score:.2f}"),
        (40, height - 470, width - 80, 70, "Status: Ready to publish review artifact"),
    ]

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, height - 50, "Autofinisher Factory Etsy Report")
    c.setFont("Helvetica", 12)
    for x, y, w, h, text in sections:
        c.rect(x, y, w, h)
        c.drawString(x + 12, y + h - 28, text[:120])
    c.showPage()
    c.save()
    return str(filename)


def main() -> int:
    parser = argparse.ArgumentParser(description="Etsy analytical executor")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--price", required=True, type=float)
    args = parser.parse_args()

    keyword = args.keyword.strip()
    input_price = args.price
    api_response = search_listings(keyword)
    results = _extract_results(api_response if isinstance(api_response, dict) else {})

    count = len(results)
    prices = []
    views_values = []
    for item in results:
        prices.append(_to_float(item.get("price", item.get("price_amount", 0.0)), 0.0))
        views_values.append(_to_float(item.get("views", 0), 0.0))

    avg_price = mean(prices) if prices else max(input_price, 0.0)
    views_total = sum(views_values)
    opportunity_score = ((views_total / count) * avg_price) if count > 0 else 0.0

    payload = build_etsy_payload(keyword, input_price, opportunity_score)
    assert payload["type"] == "download", "Payload type must be digital download"

    product_title = payload["title"]
    pdf_path = generate_pdf(keyword, product_title, avg_price, opportunity_score)

    conn = init_db()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO niches (keyword, listing_count, avg_price, opportunity_score, created_at) VALUES (?, ?, ?, ?, ?)",
            (keyword, count, avg_price, opportunity_score, now),
        )
        conn.execute(
            "INSERT INTO products (keyword, title, price, created_at) VALUES (?, ?, ?, ?)",
            (keyword, product_title, max(input_price, 0.0), now),
        )
        conn.execute(
            "INSERT INTO runs (keyword, status, pdf_path, created_at) VALUES (?, ?, ?, ?)",
            (keyword, "success", pdf_path, now),
        )
        conn.commit()
    finally:
        conn.close()

    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "success",
        "keyword": keyword,
        "niche": {
            "keyword": keyword,
            "listing_count": count,
            "views_total": views_total,
            "avg_price": round(avg_price, 2),
            "opportunity_score": round(opportunity_score, 2),
            "api_status": "degraded" if isinstance(api_response, dict) and api_response.get("error") else "ok",
        },
        "product": {
            "title": product_title,
            "price": max(input_price, 0.0),
            "currency_code": "USD",
        },
        "api_request_ready": {
            "shop_id": os.environ.get("ETSY_SHOP_ID", "0"),
            "payload": payload,
        },
        "pdf_path": pdf_path,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
