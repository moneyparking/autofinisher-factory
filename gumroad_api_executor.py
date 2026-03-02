#!/usr/bin/env python3
import json
import os
import argparse
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

WORKSPACE = os.path.expanduser("~/autofinisher-factory")
OUTPUT_DIR = os.path.join(WORKSPACE, "ready_to_publish")

def generate_pdf(keyword):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"gumroad_{keyword.replace(' ', '-')}_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    title = f"{keyword.title()} Toolkit"
    
    c = canvas.Canvas(filepath, pagesize=A4)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, 800, title)
    c.setFont("Helvetica", 12)
    c.drawString(50, 770, "Auto-Generated Gumroad Digital Product")
    y = 740
    for i in range(1, 6):
        c.rect(50, y-20, 500, 18)
        c.drawString(60, y-16, f"Module {i}: {keyword.title()} Essentials")
        y -= 30
    c.save()
    return title, filepath

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--price", type=float, default=5.0)
    args = parser.parse_args()

    title, pdf_path = generate_pdf(args.keyword)
    price_cents = int((args.price if args.price > 0 else 5.0) * 100)

    sgr_response = {
        "schema_version": "2.1",
        "status": "success",
        "keyword": args.keyword,
        "platform": "gumroad",
        "product": {
            "title": title,
            "price_usd": args.price,
            "pdf_path": pdf_path
        },
        "api_request_ready": {
            "payload": {
                "name": title,
                "price": price_cents,
                "description": f"Instant digital download: {title}. High-quality PDF toolkit.",
                "published": "false"
            }
        }
    }
    print(json.dumps(sgr_response, indent=2))

if __name__ == "__main__":
    main()
