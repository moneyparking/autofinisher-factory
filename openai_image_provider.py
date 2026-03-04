from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class OpenAIImageProvider:
    def __init__(self, model: str = "dall-e-3", size: str = "1024x1024", quality: str = "standard") -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_IMAGE_MODEL", model)
        self.size = os.getenv("OPENAI_IMAGE_SIZE", size)
        self.quality = os.getenv("OPENAI_IMAGE_QUALITY", quality)
        self.client = OpenAI(api_key=self.api_key) if self.api_key and OpenAI is not None else None

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, output_path: Path, fallback_title: str = "") -> dict:
        if self.client is None:
            self._fallback_image(output_path, fallback_title or prompt)
            return {"provider": "fallback", "status": "ok", "path": str(output_path)}

        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=self.size,
                quality=self.quality,
                n=1,
                response_format="b64_json",
            )
            item = response.data[0]
            if getattr(item, "b64_json", None):
                output_path.write_bytes(base64.b64decode(item.b64_json))
                return {
                    "provider": "openai",
                    "status": "ok",
                    "path": str(output_path),
                    "revised_prompt": getattr(item, "revised_prompt", ""),
                }
            if getattr(item, "url", None):
                image_bytes = requests.get(item.url, timeout=60).content
                output_path.write_bytes(image_bytes)
                return {
                    "provider": "openai",
                    "status": "ok",
                    "path": str(output_path),
                    "revised_prompt": getattr(item, "revised_prompt", ""),
                }
        except Exception as exc:
            self._fallback_image(output_path, fallback_title or prompt)
            return {"provider": "fallback", "status": f"fallback_after_error: {exc}", "path": str(output_path)}

        self._fallback_image(output_path, fallback_title or prompt)
        return {"provider": "fallback", "status": "fallback_empty_response", "path": str(output_path)}

    def _fallback_image(self, output_path: Path, text: str) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1024, 1024), "#111827")
        draw = ImageDraw.Draw(image)
        accent = "#7c3aed"
        draw.rectangle((80, 80, 944, 944), outline=accent, width=12)
        draw.rectangle((120, 120, 904, 220), fill=accent)
        font_big = self._font(68)
        font_small = self._font(40)
        wrapped = self._wrap(text.upper(), 16)
        y = 300
        for line in wrapped[:6]:
            box = draw.textbbox((0, 0), line, font=font_big)
            x = (1024 - (box[2] - box[0])) // 2
            draw.text((x, y), line, fill="white", font=font_big)
            y += 90
        draw.text((210, 150), "PREMIUM DIGITAL DOWNLOAD", fill="white", font=font_small)
        image.save(output_path, format="PNG")

    def _font(self, size: int):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        return ImageFont.load_default()

    def _wrap(self, text: str, width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            test = " ".join(current + [word])
            if len(test) <= width:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines or [text]
