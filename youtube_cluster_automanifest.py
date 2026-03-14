#!/usr/bin/env python3
from __future__ import annotations

"""
YouTube Cluster Auto-Manifest Generator
Автоматически собирает и аннотирует видео для regression-кластера Etsy Ads.
Совместим с file-oriented layout Autofinisher и пишет output в
fixtures/regression/<cluster_id>/cluster_manifest.autogen.json.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from youtube_transcript_api import YouTubeTranscriptApi

BASE_DIR = Path("/home/agent/autofinisher-factory")
FIXTURES_DIR = BASE_DIR / "fixtures" / "regression"
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

DECISION_PATTERNS = (
    "pause the losers",
    "keep the winners",
    "turn off losers",
    "scale this up",
    "scale winners",
    "pause losers",
    "after 2 to 4 weeks",
    "after 2-4 weeks",
    "let it run for",
    "per listing",
    "listing level",
    "listing-level",
)

SCREEN_SHARE_PATTERNS = (
    "screen share",
    "as you can see",
    "on my screen",
    "here on screen",
    "share my screen",
    "look at my screen",
)

MARKETPLACE_UI_PATTERNS = (
    "etsy ads dashboard",
    "shop manager",
    "promoted listings",
    "campaigns panel",
    "marketing tab",
    "etsy ads",
)

METRIC_PATTERNS = (
    "roas",
    "ctr",
    "cpc",
    "conversion rate",
    "impressions",
    "acos",
    "ad spend",
    "profitability",
)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def get_video_id(url_or_id: str) -> str:
    value = normalize_space(url_or_id)
    if not value:
        raise ValueError("Empty video id or URL")
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    parsed = urlparse(value)
    if parsed.netloc.endswith("youtu.be"):
        candidate = parsed.path.strip("/").split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
    query_value = parse_qs(parsed.query).get("v", [""])[0]
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", query_value):
        return query_value
    if "/shorts/" in parsed.path:
        candidate = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
            return candidate
    match = re.search(r"([A-Za-z0-9_-]{11})", value)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract video id from: {url_or_id}")


def load_or_fetch_transcript(video_id: str) -> str:
    local_path = TRANSCRIPTS_DIR / f"{video_id}.txt"
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=["en"])
        pieces: list[str] = []
        for item in transcript:
            text = item.get("text") if isinstance(item, dict) else getattr(item, "text", "")
            cleaned = normalize_space(text)
            if cleaned:
                pieces.append(cleaned)
        joined = " ".join(pieces)
        if joined:
            local_path.write_text(joined + "\n", encoding="utf-8")
        return joined
    except Exception:
        return ""


def get_metadata(video_id: str) -> dict[str, Any]:
    query = urlencode(
        {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "format": "json",
        }
    )
    endpoint = f"https://www.youtube.com/oembed?{query}"
    try:
        with urlopen(endpoint, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "title": payload.get("title", ""),
            "channel_title": payload.get("author_name", ""),
            "published_at": "",
            "duration_minutes": 0,
        }
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "title": "",
            "channel_title": "",
            "published_at": "",
            "duration_minutes": 0,
        }


def contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in patterns)


def extract_decision_examples(transcript: str, *, limit: int = 3) -> list[str]:
    windows: list[str] = []
    lowered = transcript.lower()
    for pattern in DECISION_PATTERNS:
        start = 0
        while True:
            idx = lowered.find(pattern, start)
            if idx == -1:
                break
            raw = transcript[max(0, idx - 80) : min(len(transcript), idx + len(pattern) + 80)]
            cleaned = normalize_space(raw)
            if cleaned and cleaned not in windows:
                windows.append(cleaned)
            start = idx + len(pattern)
            if len(windows) >= limit:
                return windows
    return windows[:limit]


def annotate_video(video_id: str, topic_cluster: str, *, language_hint: str = "en", default_tier: str = "B") -> dict[str, Any]:
    transcript = load_or_fetch_transcript(video_id)
    metadata = get_metadata(video_id)
    transcript_lower = transcript.lower()

    has_screen_share = contains_any(transcript_lower, SCREEN_SHARE_PATTERNS)
    shows_marketplace_ui = contains_any(transcript_lower, MARKETPLACE_UI_PATTERNS)
    shows_specific_listings = bool(
        re.search(r"\b(this listing|this product|these listings|these products|that listing)\b", transcript_lower)
    )
    contains_metrics = contains_any(transcript_lower, METRIC_PATTERNS)
    contains_decision_layer_signals = contains_any(transcript_lower, DECISION_PATTERNS)
    decision_examples = extract_decision_examples(transcript)

    if contains_decision_layer_signals and contains_metrics:
        tier = default_tier
    elif contains_metrics:
        tier = "B"
    else:
        tier = "C"

    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "language": language_hint,
        "topic_cluster": topic_cluster,
        "tier": tier,
        "notes": f"Auto-annotated for {topic_cluster} cluster",
        "duration_minutes": int(metadata.get("duration_minutes", 0) or 0),
        "has_screen_share": has_screen_share,
        "shows_marketplace_ui": shows_marketplace_ui,
        "shows_specific_listings": shows_specific_listings,
        "contains_metrics": contains_metrics,
        "contains_decision_layer_signals": contains_decision_layer_signals,
        "decision_layer_signal_examples": decision_examples,
        "published_at": metadata.get("published_at", "") or "",
        "source_metadata": {
            "title": metadata.get("title", "") or "",
            "channel_title": metadata.get("channel_title", "") or "",
            "published_at_raw": metadata.get("published_at_raw", "") or "",
            "duration_iso8601": metadata.get("duration_iso8601", "") or "",
        },
        "annotation_confidence": {
            "has_screen_share": 0.85 if has_screen_share else 0.40,
            "shows_marketplace_ui": 0.90 if shows_marketplace_ui else 0.30,
            "contains_metrics": 0.95 if contains_metrics else 0.50,
            "contains_decision_layer_signals": 0.92 if contains_decision_layer_signals else 0.40,
        },
    }


def generate_automanifest(input_data: dict[str, Any]) -> dict[str, Any]:
    cluster_id = input_data["cluster_id"]
    topic_cluster = input_data["topic_cluster"]
    raw_video_ids = input_data.get("video_ids") or [get_video_id(url) for url in input_data.get("video_urls", [])]
    language_hint = input_data.get("language_hint", "en")
    default_tier = input_data.get("default_tier", "A")

    target_dir = FIXTURES_DIR / cluster_id
    target_dir.mkdir(parents=True, exist_ok=True)

    videos: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_video_id in raw_video_ids:
        video_id = get_video_id(raw_video_id)
        if video_id in seen:
            continue
        seen.add(video_id)
        videos.append(
            annotate_video(
                video_id,
                topic_cluster,
                language_hint=language_hint,
                default_tier=default_tier,
            )
        )

    output = {
        "cluster_id": cluster_id,
        "topic_cluster": topic_cluster,
        "generated_at": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "videos": videos,
    }

    out_path = target_dir / "cluster_manifest.autogen.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✅ Auto-manifest saved: {out_path}")
    print(f"   Videos processed: {len(videos)}")
    return output


def load_input_data(argv: list[str]) -> dict[str, Any]:
    if len(argv) > 1 and argv[1].endswith(".json"):
        return json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    return {
        "cluster_id": "etsy_ads_cluster_v2",
        "topic_cluster": "etsy_ads_v2",
        "video_ids": ["AC1zd_TTVf0"],
        "language_hint": "en",
    }


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv
    data = load_input_data(args)
    generate_automanifest(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
