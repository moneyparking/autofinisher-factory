from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from monetization_scorer import ranking_payload
from openai_image_provider import OpenAIImageProvider

BASE_DIR = Path("/home/agent/autofinisher-factory")
INPUT_PATH = BASE_DIR / "niche_engine" / "accepted" / "niche_package.json"
OUTPUT_ROOT = BASE_DIR / "ready_to_publish"
PUBLISH_ROOT = BASE_DIR / "publish_packets"
CSV_PATH = OUTPUT_ROOT / "etsy_mass_import.csv"
TARGET_COUNT = 50


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "untitled-niche"


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def ensure_dirs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    PUBLISH_ROOT.mkdir(parents=True, exist_ok=True)


def read_items() -> list[dict[str, Any]]:
    if not INPUT_PATH.exists():
        return []
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("niches") or []
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def sorted_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for item in items:
        niche = item.get("niche") or item.get("query") or item.get("title")
        if not niche:
            continue
        rank = ranking_payload(item)
        item_copy = dict(item)
        item_copy["ranking"] = rank
        item_copy["suggested_price"] = rank["suggested_price"]
        item_copy["vertical"] = rank["vertical"]
        enriched.append(item_copy)
    enriched.sort(key=lambda x: (-float(x["ranking"]["monetization_score"]), -float(x["ranking"]["etsy_fit"]), x.get("niche", "")))
    return enriched[:TARGET_COUNT]


def load_font(size: int, bold: bool = True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        test = " ".join(current + [word])
        box = draw.textbbox((0, 0), test, font=font)
        if (box[2] - box[0]) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [text]


def generate_deliverable_pdf(title: str, output_path: Path) -> None:
    pages = []
    for idx in range(3):
        img = Image.new("RGB", (2480, 3508), "white")
        draw = ImageDraw.Draw(img)
        accent = ["#7c3aed", "#0f766e", "#1d4ed8"][idx % 3]
        draw.rectangle((180, 180, 2300, 3300), outline=accent, width=12)
        draw.rectangle((180, 180, 2300, 420), fill=accent)
        draw.text((260, 250), title.upper()[:42], fill="white", font=load_font(78, True))
        body_font = load_font(42, False)
        for row in range(10):
            y1 = 650 + row * 230
            draw.rectangle((250, y1, 2230, y1 + 140), outline="#cbd5e1", width=3)
            draw.text((300, y1 + 32), f"Section {row + 1}", fill="#334155", font=body_font)
        pages.append(img)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(output_path, save_all=True, append_images=pages[1:])


def generate_mockup(title: str, output_path: Path, provider: OpenAIImageProvider) -> dict[str, Any]:
    prompt = (
        f"Premium Etsy marketplace hero image for a digital download product titled '{title}'. "
        f"Minimal clean composition, elegant stationery aesthetic, premium lighting, marketplace-ready, no watermark, no extra text."
    )
    return provider.generate(prompt=prompt, output_path=output_path, fallback_title=title)


def generate_master_cover(title: str, output_path: Path) -> None:
    img = Image.new("RGB", (2000, 2500), "#0f172a")
    draw = ImageDraw.Draw(img)
    accent = "#7c3aed"
    draw.rounded_rectangle((120, 120, 1880, 2380), radius=42, outline=accent, width=10)
    draw.rounded_rectangle((160, 160, 1840, 360), radius=26, fill=accent)
    title_font = load_font(130, True)
    subtitle_font = load_font(56, True)
    lines = wrap_lines(draw, title.upper(), title_font, 1500)
    y = 780
    for line in lines[:5]:
        box = draw.textbbox((0, 0), line, font=title_font)
        x = (2000 - (box[2] - box[0])) // 2
        draw.text((x, y), line, fill="white", font=title_font)
        y += 170
    draw.text((430, 240), "DIGITAL DOWNLOAD BUNDLE", fill="white", font=subtitle_font)
    draw.text((560, 2200), "INSTANT ACCESS", fill="#cbd5e1", font=subtitle_font)
    img.save(output_path, format="PNG")


def tags_for(title: str) -> list[str]:
    base = clean_text(title).lower()
    tags = [
        base[:20],
        "digital download",
        "printable template",
        "instant download",
        "planner printable",
        "tracker template",
        "pdf planner",
        "etsy digital",
        "home organization",
        "productivity tool",
        "editable printable",
        "download bundle",
        "premium template",
    ]
    deduped = []
    seen = set()
    for tag in tags:
        norm = tag.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            deduped.append(tag[:32])
    return deduped[:13]


def build_listing_packet(item: dict[str, Any], sku_dir: Path) -> dict[str, Any]:
    title = clean_text(item.get("niche") or item.get("query") or item.get("title"))
    ranking = item["ranking"]
    price = float(item.get("suggested_price") or ranking["suggested_price"])
    slug = safe_slug(title)
    seo_title = f"{title.title()} Printable Bundle | Digital Download"
    description = (
        f"{title.title()} is a premium digital download designed for fast use and clean presentation. "
        f"Includes professionally formatted printable pages and marketplace-ready preview assets. "
        f"No physical item will be shipped."
    )
    packet = {
        "created_at": now_iso(),
        "slug": slug,
        "title": seo_title[:140],
        "niche": title,
        "vertical": ranking["vertical"],
        "price": price,
        "tags": tags_for(title),
        "description": description,
        "materials": ["digital download", "pdf", "printable"],
        "who_made": "i_did",
        "when_made": "made_to_order",
        "is_supply": False,
        "etsy_category_hint": ranking["vertical"],
        "gumroad_summary": description,
        "metrics": item.get("metrics", {}),
        "ranking": ranking,
        "files": {
            "deliverable_pdf": str((sku_dir / "deliverable.pdf").resolve()),
            "master_png": str((sku_dir / "master.png").resolve()),
            "mockup_png": str((sku_dir / "mockup.png").resolve()),
            "seo_txt": str((sku_dir / "SEO.txt").resolve()),
        },
        "manual_upload_checklist": [
            "Upload primary mockup as cover image",
            "Upload master cover as secondary listing image",
            "Attach deliverable PDF file",
            "Paste title, description, and tags",
            "Set digital download and price",
            "Review category and attributes before publishing"
        ]
    }
    return packet


def append_etsy_csv(row: dict[str, Any]) -> None:
    exists = CSV_PATH.exists()
    fieldnames = [
        "slug",
        "title",
        "price",
        "tags",
        "description",
        "deliverable_pdf",
        "mockup_png",
        "master_png",
        "vertical",
        "monetization_score",
    ]
    with CSV_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def build_all(limit: int = TARGET_COUNT) -> dict[str, Any]:
    ensure_dirs()
    items = sorted_candidates(read_items())[:limit]
    provider = OpenAIImageProvider()
    results = []

    for item in items:
        title = clean_text(item.get("niche") or item.get("query") or item.get("title"))
        slug = safe_slug(title)
        sku_dir = OUTPUT_ROOT / slug
        packet_dir = PUBLISH_ROOT / slug
        sku_dir.mkdir(parents=True, exist_ok=True)
        packet_dir.mkdir(parents=True, exist_ok=True)

        generate_deliverable_pdf(title, sku_dir / "deliverable.pdf")
        generate_master_cover(title, sku_dir / "master.png")
        image_meta = generate_mockup(title, sku_dir / "mockup.png", provider)

        packet = build_listing_packet(item, sku_dir)
        packet["image_generation"] = image_meta

        (sku_dir / "SEO.txt").write_text(
            f"TITLE: {packet['title']}\n"
            f"PRICE: {packet['price']}\n"
            f"TAGS: {', '.join(packet['tags'])}\n"
            f"DESCRIPTION: {packet['description']}\n",
            encoding="utf-8",
        )
        (packet_dir / "etsy_listing.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        (packet_dir / "gumroad_listing.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        (packet_dir / "manual_upload_checklist.txt").write_text("\n".join(packet["manual_upload_checklist"]), encoding="utf-8")

        append_etsy_csv({
            "slug": packet["slug"],
            "title": packet["title"],
            "price": packet["price"],
            "tags": ", ".join(packet["tags"]),
            "description": packet["description"],
            "deliverable_pdf": packet["files"]["deliverable_pdf"],
            "mockup_png": packet["files"]["mockup_png"],
            "master_png": packet["files"]["master_png"],
            "vertical": packet["vertical"],
            "monetization_score": packet["ranking"]["monetization_score"],
        })
        results.append(packet)
        print(f"[premium_sku_factory] built packet for {title}")

    summary = {
        "created_at": now_iso(),
        "target_count": limit,
        "built_count": len(results),
        "output_root": str(OUTPUT_ROOT),
        "publish_root": str(PUBLISH_ROOT),
        "csv_path": str(CSV_PATH),
        "items": results,
    }
    (PUBLISH_ROOT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    build_all()
