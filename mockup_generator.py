#!/usr/bin/env python3
import argparse
import json
import math
import os
import random

from PIL import Image, ImageOps

WORKSPACE = os.path.expanduser("~/autofinisher-factory")
OUTPUT_DIR = os.path.join(WORKSPACE, "ready_to_publish")
CONFIG_PATH = os.path.join(WORKSPACE, "templates.json")
R = getattr(Image, "Resampling", Image)


def load_templates_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"[!] Файл конфигурации не найден: {CONFIG_PATH}")
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def solve(pa, pb):
    matrix = []
    for (x, y), (u, v) in zip(pa, pb):
        matrix += [[x, y, 1, 0, 0, 0, -u * x, -u * y, u], [0, 0, 0, x, y, 1, -v * x, -v * y, v]]
    for i in range(8):
        pivot = max(range(i, 8), key=lambda row: abs(matrix[row][i]))
        matrix[i], matrix[pivot] = matrix[pivot], matrix[i]
        divisor = matrix[i][i]
        for j in range(i, 9):
            matrix[i][j] /= divisor
        for row in range(8):
            if row != i:
                factor = matrix[row][i]
                for j in range(i, 9):
                    matrix[row][j] -= factor * matrix[i][j]
    return [matrix[i][8] for i in range(8)]


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def quad_size(quad):
    tl, tr, br, bl = quad
    top = math.dist(tl, tr)
    bottom = math.dist(bl, br)
    left = math.dist(tl, bl)
    right = math.dist(tr, br)
    return int((top + bottom) / 2), int((left + right) / 2)


def inset_quad(frame, margin=0.033):
    tl, tr, br, bl = frame
    return (
        lerp(tl, br, margin),
        lerp(tr, bl, margin),
        lerp(br, tl, margin),
        lerp(bl, tr, margin),
    )


def fit_quad(frame, sw, sh, margin=0.033):
    itl, itr, ibr, ibl = inset_quad(frame, margin)
    aw, ah = quad_size((itl, itr, ibr, ibl))
    source_ratio = sw / sh
    area_ratio = aw / ah
    if source_ratio > area_ratio:
        left_gap = right_gap = 0
        top_gap = bottom_gap = (ah - aw / source_ratio) / (2 * ah)
    else:
        top_gap = bottom_gap = 0
        left_gap = right_gap = (aw - ah * source_ratio) / (2 * aw)
    top_l = lerp(itl, itr, left_gap)
    top_r = lerp(itr, itl, right_gap)
    bot_l = lerp(ibl, ibr, left_gap)
    bot_r = lerp(ibr, ibl, right_gap)
    return (
        lerp(top_l, bot_l, top_gap),
        lerp(top_r, bot_r, top_gap),
        lerp(bot_r, top_r, bottom_gap),
        lerp(bot_l, top_l, bottom_gap),
    )


def prepare_poster(png_path, target):
    poster = Image.open(png_path).convert("RGBA")
    return ImageOps.contain(poster, target, method=R.LANCZOS)


def warp_rgba_to_canvas(image, canvas_size, destination_quad):
    coeffs = solve(destination_quad, [(0, 0), (image.width, 0), (image.width, image.height), (0, image.height)])
    return image.transform(canvas_size, Image.Transform.PERSPECTIVE, coeffs, resample=R.BICUBIC)


def create_photorealistic_mockup(png_path, template_name=None, output_path=None):
    templates = load_templates_config()
    if not templates:
        return None
    if not template_name or template_name not in templates:
        available = [name for name in templates if os.path.exists(os.path.join(WORKSPACE, name))]
        if not available:
            print("[!] Нет доступных файлов шаблонов в директории.")
            return None
        template_name = random.choice(available)

    template_path = os.path.join(WORKSPACE, template_name)
    if not os.path.exists(template_path):
        print(f"[!] Файл шаблона не найден: {template_path}")
        return None
    if not os.path.exists(png_path):
        print(f"[!] PNG-мастер не найден: {png_path}")
        return None

    template_config = templates[template_name]
    corners = template_config["corners"]
    frame = [
        tuple(corners["top_left"]),
        tuple(corners["top_right"]),
        tuple(corners["bottom_right"]),
        tuple(corners["bottom_left"]),
    ]
    target_width, target_height = quad_size(frame)

    background = Image.open(template_path).convert("RGBA")
    poster = prepare_poster(png_path, (target_width, target_height))
    destination_quad = fit_quad(frame, poster.width, poster.height, 0.033)
    warped_poster = warp_rgba_to_canvas(poster, background.size, destination_quad)
    background.alpha_composite(warped_poster)

    if output_path:
        final_path = output_path
    else:
        base = os.path.splitext(os.path.basename(png_path))[0]
        template_stub = os.path.splitext(template_name)[0]
        final_path = os.path.join(OUTPUT_DIR, f"{base}_{template_stub}_REAL_PIN.jpg")
    background.convert("RGB").save(final_path, quality=100)
    print(f"✅ Мокап готов: {final_path}")
    return final_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--png", required=True)
    parser.add_argument("--template")
    parser.add_argument("--output")
    args = parser.parse_args()
    if not os.path.exists(args.png):
        print(f"[!] PNG-мастер не найден: {args.png}")
        return
    create_photorealistic_mockup(args.png, args.template, args.output)


if __name__ == "__main__":
    main()
