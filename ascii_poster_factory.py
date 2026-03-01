#!/usr/bin/env python3
import os
import json
import argparse
import pyfiglet
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

WORKSPACE = os.path.expanduser("~/autofinisher-factory")
OUTPUT_DIR = os.path.join(WORKSPACE, "ready_to_publish")

def generate_ascii_pdf(keyword):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"poster_{keyword.replace(' ', '-')}_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    title = f"{keyword.upper()} ASCII Art Poster"

    # Генерируем ASCII текст
    ascii_art = pyfiglet.figlet_format(keyword.upper(), font="slant")

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    # 1. Фон (Dark Mode: #1e1e1e)
    c.setFillColor(HexColor("#1e1e1e"))
    c.rect(0, 0, width, height, stroke=0, fill=1)

    # 2. Отрисовка ASCII (Claude Color: #d97757)
    c.setFillColor(HexColor("#d97757"))
    c.setFont("Courier-Bold", 10)

    # Рисуем каждую строку ASCII-арта
    y_pos = height - 150
    for line in ascii_art.split('\n'):
        c.drawString(50, y_pos, line)
        y_pos -= 12

    # 3. Декоративные элементы терминала
    c.setFillColor(HexColor("#858585"))
    c.setFont("Courier", 12)
    c.drawString(50, height - 50, f"root@autofinisher:~# ./generate_art --theme claude --text '{keyword}'")
    c.drawString(50, 50, f"[PROCESS COMPLETED] EXIT CODE 0")

    c.save()
    return title, filepath

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--price", type=float, default=9.99)
    args = parser.parse_args()

    title, pdf_path = generate_ascii_pdf(args.keyword)

    sgr_response = {
        "schema_version": "2.1",
        "status": "success",
        "keyword": args.keyword,
        "niche": {
            "keyword": args.keyword,
            "avg_price": args.price
        },
        "product": {
            "title": title,
            "price": args.price,
            "currency_code": "USD"
        },
        "api_request_ready": {
            "shop_id": "0",
            "payload": {
                "title": title,
                "description": f"Minimalist ASCII Art Poster for developers. Perfect for office decor. Theme: {args.keyword.upper()}.",
                "price": str(args.price),
                "quantity": 999,
                "type": "download"
            }
        },
        "pdf_path": pdf_path
    }

    print(json.dumps(sgr_response))

if __name__ == "__main__":
    main()
