import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, letter
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
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"product_{keyword.replace(' ', '-')}_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    title = f"{keyword.title()}"

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    # 1. Эстетичный фон (Soft Beige / Off-White)
    bg_color = HexColor("#FAF9F6")
    c.setFillColor(bg_color)
    c.rect(0, 0, width, height, stroke=0, fill=1)

    # 2. Заголовок (Элегантный контраст)
    text_color = HexColor("#2C3E50")
    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(50, height - 70, title)

    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#7F8C8D"))
    c.drawString(50, height - 90, "Daily Productivity & Mindfulness Tracker")

    # 3. Блок: Top 3 Priorities
    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 140, "Top 3 Priorities")
    c.setLineWidth(0.5)
    c.setStrokeColor(HexColor("#BDC3C7"))
    for i in range(3):
        y_pos = height - 170 - (i * 30)
        c.circle(60, y_pos + 4, 8, stroke=1, fill=0)
        c.line(80, y_pos, 280, y_pos)

    # 4. Блок: Time Blocking (Schedule)
    c.drawString(50, height - 280, "Daily Schedule")
    time_start_y = height - 310
    c.setFont("Helvetica", 11)
    for i, hour in enumerate(range(7, 21)):
        y_pos = time_start_y - (i * 25)
        c.drawString(50, y_pos, f"{hour}:00")
        c.line(90, y_pos - 2, 280, y_pos - 2)

    # 5. Блок: Habits & Wellness (Правая колонка)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(320, height - 140, "Wellness & Habits")
    c.setFont("Helvetica", 11)
    c.drawString(320, height - 170, "Water Intake:")
    for i in range(8):
        c.circle(410 + (i * 15), height - 166, 5, stroke=1, fill=0)

    c.drawString(320, height - 210, "Daily Habits:")
    for i in range(4):
        y_pos = height - 240 - (i * 25)
        c.rect(320, y_pos, 12, 12, stroke=1, fill=0)
        c.line(340, y_pos + 2, 530, y_pos + 2)

    # 6. Блок: Notes / Brain Dump (Dotted Grid)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(320, height - 360, "Brain Dump / Notes")

    c.setFillColor(HexColor("#ECF0F1"))
    c.rect(320, 50, 220, height - 430, stroke=0, fill=1)

    c.setFillColor(HexColor("#BDC3C7"))
    for x in range(330, 540, 15):
        for y_dot in range(60, int(height - 380), 15):
            c.circle(x, y_dot, 0.7, stroke=0, fill=1)

    c.save()
    return filepath


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
