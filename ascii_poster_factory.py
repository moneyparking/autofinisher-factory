#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

WORKSPACE = os.path.expanduser("~/autofinisher-factory")
OUTPUT_DIR = os.path.join(WORKSPACE, "ready_to_publish")


def generate_ascii_pdf(keyword: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"poster_{keyword.replace(' ', '-')}_{timestamp}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    bg = HexColor("#0A0A0B")
    grid = HexColor("#111115")
    glow_dark = HexColor("#61110F")
    glow_mid = HexColor("#B62518")
    glow_hot = HexColor("#FF4500")
    glow_neon = HexColor("#FF6A3D")
    glow_pink = HexColor("#FF3366")
    meta = HexColor("#85858C")
    meta_soft = HexColor("#63636A")
    accent = HexColor("#FFD0B5")

    c.setFillColor(bg)
    c.rect(0, 0, width, height, stroke=0, fill=1)

    c.setStrokeColor(grid)
    c.setLineWidth(0.35)
    for y in range(28, int(height), 16):
        c.line(0, y, width, y)

    phrase_lines = ["YOU'RE", "ABSOLUTELY", "RIGHT!"]
    font_size = 31
    leading = 45
    center_x = width / 2
    start_y = (height / 2) + 66

    for idx, line in enumerate(phrase_lines):
        y = start_y - (idx * leading)
        c.setFont("Courier-Bold", font_size)

        for offset in range(12, 0, -2):
            c.setFillColor(glow_dark)
            c.drawCentredString(center_x + offset, y - offset * 0.92, line)

        c.setFillColor(glow_mid)
        c.drawCentredString(center_x + 5.2, y - 3.5, line)
        c.drawCentredString(center_x + 2.8, y - 1.8, line)

        c.setFillColor(glow_pink)
        c.drawCentredString(center_x - 1.4, y + 0.8, line)
        c.setFillColor(glow_hot)
        c.drawCentredString(center_x + 1.5, y - 0.2, line)

        c.setFillColor(glow_neon)
        c.drawCentredString(center_x, y, line)

        c.setFillColor(accent)
        c.drawCentredString(center_x - 0.7, y + 0.9, line)

    c.setStrokeColor(HexColor("#1C1C22"))
    c.setLineWidth(1)
    c.line(42, height - 44, width - 42, height - 44)
    c.line(42, 36, width - 42, 36)

    rendered_at = datetime.now()
    c.setFillColor(meta)
    c.setFont("Helvetica", 9)
    c.drawString(42, height - 28, "AUTOFINISHER FACTORY // PREMIUM ASCII DROP")
    c.drawRightString(width - 42, height - 28, rendered_at.strftime("RENDERED %Y-%m-%d"))

    c.setFont("Helvetica", 8)
    c.setFillColor(meta_soft)
    c.drawString(42, 22, f"TOKEN {keyword.upper()} // EDITION 01")
    c.drawCentredString(center_x, 22, "MATTE BLACK // NEON GLITCH // DISPLAY PRINT")
    c.drawRightString(width - 42, 22, rendered_at.strftime("CODE %H%M%S"))

    c.save()
    return filepath


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--price", type=float, default=9.99)
    args = parser.parse_args()

    pdf_path = generate_ascii_pdf(args.keyword)
    print(json.dumps({
        "status": "success",
        "keyword": args.keyword,
        "price": args.price,
        "pdf_path": pdf_path,
        "slogan": "YOU'RE ABSOLUTELY RIGHT!"
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
