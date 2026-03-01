import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SCHEMA_VERSION = "2.1"
DB_PATH = "factory.db"
OUTPUT_DIR = Path("ready_to_publish")


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ebay_niches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            sold_count INTEGER NOT NULL,
            avg_sold_price REAL NOT NULL,
            opportunity_score REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ebay_runs (
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


def generate_pdf(keyword: str, product_title: str, avg_sold_price: float, opportunity_score: float) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = OUTPUT_DIR / f"ebay_{keyword.replace(' ', '-').lower()}_{timestamp}.pdf"
    c = canvas.Canvas(str(filename), pagesize=letter)
    width, height = letter
    sections = [
        (40, height - 110, width - 80, 70, f"Keyword: {keyword}"),
        (40, height - 200, width - 80, 70, f"Product: {product_title}"),
        (40, height - 290, width - 80, 70, f"Average Sold Price: {avg_sold_price:.2f}"),
        (40, height - 380, width - 80, 70, f"Opportunity Score: {opportunity_score:.2f}"),
        (40, height - 470, width - 80, 70, "Status: eBay demo artifact"),
    ]
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, height - 50, "Autofinisher Factory eBay Report")
    c.setFont("Helvetica", 12)
    for x, y, w, h, text in sections:
        c.rect(x, y, w, h)
        c.drawString(x + 12, y + h - 28, text[:120])
    c.showPage()
    c.save()
    return str(filename)


def main() -> int:
    parser = argparse.ArgumentParser(description="eBay analytical executor")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--price", required=False, type=float, default=0.0)
    args = parser.parse_args()

    keyword = args.keyword.strip()
    sold_count = 0
    avg_sold_price = max(args.price, 0.0)
    opportunity_score = sold_count * avg_sold_price
    product_title = f"{keyword.title()} Demo Product"
    pdf_path = generate_pdf(keyword, product_title, avg_sold_price, opportunity_score)

    conn = init_db()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO ebay_niches (keyword, sold_count, avg_sold_price, opportunity_score, created_at) VALUES (?, ?, ?, ?, ?)",
            (keyword, sold_count, avg_sold_price, opportunity_score, now),
        )
        conn.execute(
            "INSERT INTO ebay_runs (keyword, status, pdf_path, created_at) VALUES (?, ?, ?, ?)",
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
            "sold_count": sold_count,
            "avg_sold_price": round(avg_sold_price, 2),
            "opportunity_score": round(opportunity_score, 2),
        },
        "product": {
            "title": product_title,
            "price": max(args.price, 0.0),
            "currency_code": "USD",
        },
        "api_requests_ready": {
            "inventory_item": {
                "sku": f"SKU-{keyword.replace(' ', '-').upper()}",
                "product": {
                    "title": product_title,
                    "description": f"Auto-generated eBay inventory item for {keyword}",
                },
                "condition": "NEW"
            },
            "offer": {
                "sku": f"SKU-{keyword.replace(' ', '-').upper()}",
                "availableQuantity": 1,
                "marketplaceId": "EBAY_US",
                "format": "FIXED_PRICE",
                "listingDescription": f"Offer generated for {keyword}",
                "pricingSummary": {
                    "price": {
                        "value": f"{max(args.price, 0.99):.2f}",
                        "currency": "USD"
                    }
                }
            }
        },
        "pdf_path": pdf_path,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
