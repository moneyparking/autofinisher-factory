#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw, ImageFilter

WORKSPACE = os.path.expanduser('~/autofinisher-factory')
ASSETS_DIR = os.path.join(WORKSPACE, 'assets')
OUTPUT_PATH = os.path.join(ASSETS_DIR, 'app_icon.jpg')
SIZE = 1024


def build_logo() -> Image.Image:
    img = Image.new('RGB', (SIZE, SIZE), '#111111')
    draw = ImageDraw.Draw(img)

    # soft vignette / premium depth
    vignette = Image.new('L', (SIZE, SIZE), 0)
    vdraw = ImageDraw.Draw(vignette)
    for inset, alpha in [(28, 14), (64, 22), (112, 34), (164, 48)]:
        vdraw.rounded_rectangle((inset, inset, SIZE - inset, SIZE - inset), radius=200, outline=alpha, width=8)
    vignette = vignette.filter(ImageFilter.GaussianBlur(26))
    img.paste(Image.new('RGB', img.size, '#000000'), mask=vignette)

    # geometric F mark
    mark = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mark)
    orange = '#FF6A1A'
    orange_hot = '#FF9A3C'
    glow = '#FF4A12'

    stem = (372, 224, 498, 800)
    arm_top = [(474, 224), (742, 224), (704, 332), (474, 332)]
    arm_mid = [(474, 430), (646, 430), (612, 534), (474, 534)]
    notch = [(498, 666), (642, 666), (610, 748), (498, 748)]

    for blur, alpha in [(52, 44), (28, 68), (14, 92)]:
        glow_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow_layer)
        color = (255, 92, 28, alpha)
        gdraw.rounded_rectangle(stem, radius=28, fill=color)
        gdraw.polygon(arm_top, fill=color)
        gdraw.polygon(arm_mid, fill=color)
        gdraw.polygon(notch, fill=color)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(blur))
        mark = Image.alpha_composite(mark, glow_layer)

    mdraw = ImageDraw.Draw(mark)
    mdraw.rounded_rectangle(stem, radius=28, fill=orange)
    mdraw.polygon(arm_top, fill=orange)
    mdraw.polygon(arm_mid, fill=orange)
    mdraw.polygon(notch, fill='#D63B11')

    # inner highlight
    mdraw.rounded_rectangle((392, 244, 430, 780), radius=18, fill=orange_hot)
    mdraw.polygon([(488, 246), (700, 246), (682, 288), (488, 288)], fill=orange_hot)
    mdraw.polygon([(488, 450), (608, 450), (592, 490), (488, 490)], fill=orange_hot)

    # subtle diagonal shard for modernity
    mdraw.polygon([(626, 590), (762, 706), (708, 764), (574, 646)], fill=glow)

    img = Image.alpha_composite(img.convert('RGBA'), mark)

    # micro grain
    grain = Image.effect_noise((SIZE, SIZE), 8).convert('L')
    grain = grain.point(lambda p: 118 if p < 118 else 136 if p > 136 else p)
    img = Image.blend(img.convert('RGB'), Image.merge('RGB', (grain, grain, grain)), 0.04)
    return img


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    image = build_logo()
    image.save(OUTPUT_PATH, format='JPEG', quality=97, subsampling=0)
    print(f'✅ App icon created: {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
