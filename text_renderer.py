#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WORKSPACE = os.path.expanduser('~/autofinisher-factory')
OUTPUT_DIR = Path(WORKSPACE) / 'ready_to_publish'
OUTPUT_PATH = OUTPUT_DIR / 'TEXT_LAYER.png'
CANVAS_SIZE = (2200, 3200)
TEXT = "YOU'RE ABSOLUTELY RIGHT!"
R = getattr(Image, 'Resampling', Image)

FONT_CANDIDATES = [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf',
]


def pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, lines: list[str], max_width: int, max_height: int):
    chosen = pick_font(120)
    for size in range(260, 70, -6):
        font = pick_font(size)
        bbox = draw.multiline_textbbox((0, 0), '\n'.join(lines), font=font, spacing=int(size * 0.18), stroke_width=max(2, size // 28))
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width <= max_width and height <= max_height:
            chosen = font
            break
    return chosen


def build_text_layer(text: str = TEXT) -> Image.Image:
    canvas = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 0))
    work = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(work)

    lines = ["YOU'RE", 'ABSOLUTELY', 'RIGHT!']
    font = fit_font(draw, lines, max_width=int(CANVAS_SIZE[0] * 0.82), max_height=int(CANVAS_SIZE[1] * 0.42))
    spacing = int(font.size * 0.18) if hasattr(font, 'size') else 24
    stroke = max(2, getattr(font, 'size', 80) // 24)

    bbox = draw.multiline_textbbox((0, 0), '\n'.join(lines), font=font, spacing=spacing, stroke_width=stroke)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (CANVAS_SIZE[0] - text_w) / 2 - bbox[0]
    y = (CANVAS_SIZE[1] - text_h) / 2 - bbox[1]

    for blur, alpha, color in [
        (46, 52, (255, 74, 18, alpha := 52)),
        (24, 82, (255, 96, 28, 82)),
        (10, 120, (255, 130, 44, 120)),
    ]:
        glow = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.multiline_text((x, y), '\n'.join(lines), font=font, fill=color, spacing=spacing, align='center', stroke_width=stroke)
        glow = glow.filter(ImageFilter.GaussianBlur(blur))
        canvas = Image.alpha_composite(canvas, glow)

    shadow = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    depth_steps = 12
    for offset in range(depth_steps, 0, -1):
        strength = int(22 + (offset / depth_steps) * 80)
        sdraw.multiline_text((x + offset * 5, y + offset * 7), '\n'.join(lines), font=font, fill=(96, 12, 8, strength), spacing=spacing, align='center', stroke_width=stroke)
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    canvas = Image.alpha_composite(canvas, shadow)

    face = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(face)
    fdraw.multiline_text((x - 4, y - 6), '\n'.join(lines), font=font, fill=(255, 51, 102, 132), spacing=spacing, align='center', stroke_width=stroke)
    fdraw.multiline_text((x + 5, y + 3), '\n'.join(lines), font=font, fill=(255, 69, 0, 168), spacing=spacing, align='center', stroke_width=stroke)
    fdraw.multiline_text((x, y), '\n'.join(lines), font=font, fill=(255, 122, 50, 255), spacing=spacing, align='center', stroke_width=stroke, stroke_fill=(84, 10, 6, 210))
    fdraw.multiline_text((x - 2, y - 3), '\n'.join(lines), font=font, fill=(255, 212, 188, 210), spacing=spacing, align='center')
    canvas = Image.alpha_composite(canvas, face)

    pixels = Image.new('RGBA', CANVAS_SIZE, (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pixels)
    block = max(6, getattr(font, 'size', 120) // 28)
    for yy in range(int(y), int(y + text_h), block * 2):
        pdraw.rectangle((x - 40, yy, x + text_w + 40, yy + 2), fill=(255, 180, 120, 20))
    canvas = Image.alpha_composite(canvas, pixels)

    alpha = canvas.getchannel('A')
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.4))
    canvas.putalpha(alpha)
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description='Raster text renderer with transparent background.')
    parser.add_argument('--text', default=TEXT)
    parser.add_argument('--output', default=str(OUTPUT_PATH))
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image = build_text_layer(args.text)
    out_path = Path(args.output)
    image.save(out_path, format='PNG')
    print(json.dumps({'status': 'success', 'text_layer_path': str(out_path), 'text': args.text}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
