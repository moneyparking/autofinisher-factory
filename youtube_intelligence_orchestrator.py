#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

from etsy_mcp_scraper import inspect_listing, scan_keywords as etsy_scan_keywords
from fms_engine import compute_fms_components, compute_fms_score
from niche_profit_engine import evaluate_niche_profitability, get_ebay_metrics, normalize_ebay_query
from wedge_scoring import bundle_keep_status, calculate_bundle_power

BASE_DIR = Path("/home/agent/autofinisher-factory")
OUTPUT_DIR = BASE_DIR / "youtube_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
WEDGE_MATRIX_V2_PATH = BASE_DIR / "WEDGE_MATRIX_TOP_SET_V2.json"

QUALITY_MIN_IDEAS = int(os.getenv("YT_MIN_IDEAS", "10"))
QUALITY_MIN_FMS = float(os.getenv("YT_MIN_FMS", "45.0"))
MAX_RETRIES = int(os.getenv("YT_AGENT_RETRIES", "2"))
MAX_BATCH_VIDEOS = int(os.getenv("YT_MAX_BATCH_VIDEOS", "20"))
MAX_LISTINGS_PER_KEYWORD = int(os.getenv("YT_ETSY_MAX_LISTINGS", "10"))
MAX_INSPECT_LISTINGS = int(os.getenv("YT_ETSY_INSPECT_TOP", "3"))
WEDGE_MODE_DEFAULT = os.getenv("YT_WEDGE_MODE", "1").strip().lower() in {"1", "true", "yes", "on"}
TRANSCRIPT_USE_YTDLP = os.getenv("YT_USE_YTDLP_FALLBACK", "1").strip().lower() in {"1", "true", "yes", "on"}
YTDLP_BIN = os.getenv("YT_DLP_BIN", "yt-dlp").strip() or "yt-dlp"

TEMPLATED_ENABLED = os.getenv("YT_TEMPLATED_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
EXCALIDRAW_ENABLED = os.getenv("YT_EXCALIDRAW_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}

PRODUCT_TOKENS = {
    "template",
    "planner",
    "dashboard",
    "checklist",
    "workbook",
    "tracker",
    "calculator",
    "bundle",
    "kit",
    "worksheet",
    "prompt",
    "library",
    "course",
    "toolkit",
    "guide",
    "crm",
    "portal",
    "workspace",
    "calendar",
    "brand",
}

GENERIC_KILL_TOKENS = {
    "planner",
    "life planner",
    "productivity planner",
    "notion templates",
    "business planner",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_video_id(video_url: str) -> str:
    parsed = urlparse(video_url)
    if parsed.netloc.endswith("youtu.be"):
        value = parsed.path.strip("/")
        if value:
            return value
    qs = parse_qs(parsed.query)
    if qs.get("v"):
        return qs["v"][0]
    if parsed.path.startswith("/shorts/"):
        value = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0].strip()
        if value:
            return value
    fallback = re.sub(r"[^A-Za-z0-9_-]", "", parsed.path.split("/")[-1])
    if fallback:
        return fallback
    raise ValueError(f"Cannot extract video id from URL: {video_url}")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", normalize_space(text).lower()).strip("-")
    return value or "untitled"


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", normalize_space(text))
    out: list[str] = []
    seen = set()
    for chunk in chunks:
        cleaned = normalize_space(chunk)
        if len(cleaned) < 40:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def log_step(message: str) -> None:
    print(f"[{utc_now_iso()}] {message}", flush=True)


def ytdlp_available() -> bool:
    return shutil.which(YTDLP_BIN) is not None


def fetch_transcript_via_ytdlp(video_url: str) -> dict[str, Any] | None:
    if not TRANSCRIPT_USE_YTDLP or not ytdlp_available():
        return None
    cmd = [
        YTDLP_BIN,
        "--skip-download",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs",
        "en.*,en,ru.*",
        "--sub-format",
        "json3",
        "-o",
        "-",
        "--print",
        "requested_subtitles",
        video_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    except Exception as exc:
        return {"status": "unavailable", "error": f"yt-dlp invocation failed: {exc}", "chunks": [], "text": ""}

    output = (result.stdout or "").strip()
    if result.returncode != 0 or not output or output == "NA":
        err = (result.stderr or "").strip()
        return {"status": "unavailable", "error": f"yt-dlp could not fetch subtitles: {err or 'not available'}", "chunks": [], "text": ""}

    subtitle_url = None
    try:
        payload = json.loads(output)
        if isinstance(payload, dict):
            for _lang, meta in payload.items():
                if isinstance(meta, dict) and meta.get("url"):
                    subtitle_url = meta["url"]
                    break
    except Exception:
        subtitle_url = output if output.startswith("http") else None

    if not subtitle_url:
        return {"status": "unavailable", "error": "yt-dlp returned no subtitle URL", "chunks": [], "text": ""}

    try:
        import requests

        resp = requests.get(subtitle_url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"status": "unavailable", "error": f"subtitle download failed: {exc}", "chunks": [], "text": ""}

    events = data.get("events") if isinstance(data, dict) else []
    chunks: list[dict[str, Any]] = []
    for event in events or []:
        segs = event.get("segs") or []
        text = normalize_space("".join(str(seg.get("utf8", "")) for seg in segs))
        if not text:
            continue
        start = safe_float(event.get("tStartMs"), 0.0) / 1000.0
        duration = safe_float(event.get("dDurationMs"), 0.0) / 1000.0
        chunks.append({"text": text, "start": start, "duration": duration})

    transcript_text = " ".join(chunk["text"] for chunk in chunks if chunk["text"])
    return {"status": "ok", "language": "en", "chunks": chunks, "text": transcript_text, "source": "yt-dlp"}


def normalize_transcript_chunks(raw_chunks: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    current_start = 0.0
    for item in raw_chunks or []:
        if isinstance(item, str):
            text = normalize_space(item)
            if not text:
                continue
            normalized.append({"text": text, "start": round(current_start, 2), "duration": 0.0})
            continue
        if not isinstance(item, dict):
            continue
        text = normalize_space(
            item.get("text")
            or item.get("caption")
            or item.get("value")
            or item.get("utterance")
            or item.get("line")
            or item.get("content")
            or ""
        )
        if not text:
            continue
        start = safe_float(item.get("start", item.get("offset", item.get("tStartMs", current_start))), current_start)
        duration = safe_float(item.get("duration", item.get("dDurationMs", 0.0)), 0.0)
        if safe_float(item.get("tStartMs"), None) is not None:
            start = safe_float(item.get("tStartMs"), current_start) / 1000.0
        if safe_float(item.get("dDurationMs"), None) is not None:
            duration = safe_float(item.get("dDurationMs"), 0.0) / 1000.0
        normalized.append({"text": text, "start": round(start, 2), "duration": round(duration, 2)})
        current_start = max(current_start, start + max(duration, 0.0))
    return normalized


def build_transcript_payload_from_text(text: str, video_id: str, *, source: str, language: str | None = None) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines()):
        cleaned = normalize_space(line)
        if not cleaned:
            continue
        chunks.append({"text": cleaned, "start": float(idx * 5), "duration": 0.0})
    transcript_text = " ".join(chunk["text"] for chunk in chunks)
    return {
        "video_id": video_id,
        "status": "ok",
        "language": language,
        "chunks": chunks,
        "text": transcript_text,
        "source": source,
    }


def build_transcript_payload_from_json_payload(payload: Any, video_id: str, *, source: str) -> dict[str, Any]:
    if isinstance(payload, dict):
        chunks = normalize_transcript_chunks(payload.get("chunks") or payload.get("segments") or payload.get("events") or [])
        text = normalize_space(payload.get("text") or " ".join(chunk["text"] for chunk in chunks))
        if not chunks and text:
            return build_transcript_payload_from_text(text, video_id, source=source, language=payload.get("language"))
        return {
            "video_id": payload.get("video_id") or video_id,
            "status": payload.get("status") or ("ok" if text or chunks else "unavailable"),
            "language": payload.get("language"),
            "chunks": chunks,
            "text": text,
            "source": payload.get("source") or source,
        }
    if isinstance(payload, list):
        chunks = normalize_transcript_chunks(payload)
        return {
            "video_id": video_id,
            "status": "ok" if chunks else "unavailable",
            "language": None,
            "chunks": chunks,
            "text": " ".join(chunk["text"] for chunk in chunks),
            "source": source,
        }
    if isinstance(payload, str):
        return build_transcript_payload_from_text(payload, video_id, source=source)
    return {"video_id": video_id, "status": "unavailable", "language": None, "chunks": [], "text": "", "source": source}


def load_transcript_from_file(file_path: str | Path, video_id: str) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Transcript file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(raw)
        transcript_payload = build_transcript_payload_from_json_payload(payload, video_id, source=f"local_file:{path.name}")
    else:
        transcript_payload = build_transcript_payload_from_text(raw, video_id, source=f"local_file:{path.name}")
    transcript_payload["video_id"] = transcript_payload.get("video_id") or video_id
    transcript_payload["status"] = transcript_payload.get("status") or ("ok" if transcript_payload.get("text") else "unavailable")
    return transcript_payload


def clean_validation_query(text: str, *, preserve_brand_terms: bool = False) -> str:
    raw = normalize_space(text).lower()
    tokens = [tok for tok in re.sub(r"[^a-z0-9\s]+", " ", raw).split() if tok]
    banned = {
        "system",
        "execution",
        "workflow",
        "bottlenecks",
        "repeatable",
        "manual",
        "results",
        "simple",
        "os",
        "framework",
        "2026",
    }
    if preserve_brand_terms:
        banned -= {"notion", "canva", "etsy", "midjourney", "goodnotes", "adhd"}
    kept: list[str] = []
    for tok in tokens:
        if tok in banned:
            continue
        if tok not in kept:
            kept.append(tok)
    return " ".join(kept[:6]).strip()


def is_generic_query(text: str) -> bool:
    cleaned = clean_validation_query(text, preserve_brand_terms=True)
    if not cleaned:
        return True
    if cleaned in GENERIC_KILL_TOKENS:
        return True
    tokens = cleaned.split()
    return not any(tok in PRODUCT_TOKENS for tok in tokens)


def infer_buyer_from_text(text: str) -> str:
    low = normalize_space(text).lower()
    if "etsy" in low and "ads" in low:
        return "Etsy sellers scaling with paid traffic"
    if "freelancer" in low or "client" in low:
        return "Freelancers managing multiple clients"
    if "adhd" in low:
        return "ADHD knowledge workers"
    if "midjourney" in low or "ai art" in low:
        return "AI artists selling commercial creative assets"
    if "creator" in low or "brand" in low or "content" in low:
        return "Content creators building branded output"
    return "Digital operators with workflow pain"


def load_wedge_matrix_v2() -> list[dict[str, Any]]:
    if not WEDGE_MATRIX_V2_PATH.exists():
        return []
    try:
        return json.loads(WEDGE_MATRIX_V2_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def choose_matching_wedge_entry(buyer: str, pain: str, wedge: str) -> dict[str, Any] | None:
    buyer_low = normalize_space(buyer).lower()
    pain_low = normalize_space(pain).lower()
    wedge_low = normalize_space(wedge).lower()
    best_entry: dict[str, Any] | None = None
    best_score = -1
    for entry in load_wedge_matrix_v2():
        score = 0
        entry_buyer = normalize_space(entry.get("buyer", "")).lower()
        entry_pain = normalize_space(entry.get("pain", "")).lower()
        entry_wedge = normalize_space(entry.get("wedge", "")).lower()
        if entry_buyer and (entry_buyer in buyer_low or buyer_low in entry_buyer):
            score += 3
        if entry_wedge and (entry_wedge in wedge_low or wedge_low in entry_wedge):
            score += 3
        if entry_pain and any(token in pain_low for token in entry_pain.split()[:4]):
            score += 2
        if score > best_score:
            best_score = score
            best_entry = entry
    return best_entry if best_score >= 3 else None


def planner_only_idea(idea: dict[str, Any]) -> bool:
    artifact_stack = [str(x).strip().lower() for x in (idea.get("artifact_stack") or []) if str(x).strip()]
    if not artifact_stack:
        return False
    plannerish = {"planner", "notion template", "template", "workbook"}
    return len(artifact_stack) <= 2 and all(item in plannerish for item in artifact_stack)


def build_program_md(video_url: str, video_id: str) -> str:
    return textwrap.dedent(
        f"""
        # YouTube Intelligence Program

        Video URL: {video_url}
        Video ID: {video_id}
        Generated At: {utc_now_iso()}

        ## Goal
        Turn one YouTube video into validated digital-product ideas and a ready-to-package artifact set.

        ## Agent sequence
        1. Segment transcript into thematic blocks.
        2. Extract pains, desires, and quotable market language.
        3. Mine solution patterns, frameworks, and assets.
        4. Generate product concepts.
        5. Validate concepts through Etsy + eBay + FMS.
        6. Package outputs into seller-ready files and a ZIP archive.

        ## Quality gate
        - Minimum ideas: {QUALITY_MIN_IDEAS}
        - Minimum top FMS score: {QUALITY_MIN_FMS}
        - Retries allowed: {MAX_RETRIES}

        ## Keep / retry rule
        If idea count or top FMS score is below threshold, retry the product strategist with a broader product mix.
        """
    ).strip() + "\n"


async def get_transcript(video_url: str) -> dict[str, Any]:
    video_id = extract_video_id(video_url)
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "ru"])
        chunks: list[dict[str, Any]] = []
        for item in fetched:
            chunks.append(
                {
                    "text": normalize_space(getattr(item, "text", "")),
                    "start": safe_float(getattr(item, "start", 0.0)),
                    "duration": safe_float(getattr(item, "duration", 0.0)),
                }
            )
        transcript_text = " ".join(chunk["text"] for chunk in chunks if chunk["text"])
        return {
            "video_id": video_id,
            "status": "ok",
            "language": getattr(fetched, "language_code", None),
            "chunks": chunks,
            "text": transcript_text,
            "source": "youtube_transcript_api",
        }
    except Exception as exc:
        fallback = fetch_transcript_via_ytdlp(video_url)
        if fallback and fallback.get("status") == "ok":
            fallback["video_id"] = video_id
            return fallback
        fallback_error = fallback.get("error") if isinstance(fallback, dict) else None
        return {
            "video_id": video_id,
            "status": "unavailable",
            "language": None,
            "chunks": [],
            "text": "",
            "error": str(exc),
            "fallback_error": fallback_error,
        }


async def agent_segmenter(transcript_payload: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    chunks = transcript_payload.get("chunks") or []
    blocks: list[dict[str, Any]] = []
    current: list[str] = []
    current_start: float | None = None
    current_duration = 0.0

    for item in chunks:
        text = normalize_space(item.get("text", ""))
        if not text:
            continue
        if current_start is None:
            current_start = safe_float(item.get("start", 0.0))
        current.append(text)
        current_duration += safe_float(item.get("duration", 0.0))
        joined = " ".join(current)
        if len(joined) >= 900:
            blocks.append(
                {
                    "id": len(blocks) + 1,
                    "start": round(current_start or 0.0, 2),
                    "duration": round(current_duration, 2),
                    "summary": joined[:400],
                    "text": joined,
                }
            )
            current = []
            current_start = None
            current_duration = 0.0

    if current:
        joined = " ".join(current)
        blocks.append(
            {
                "id": len(blocks) + 1,
                "start": round(current_start or 0.0, 2),
                "duration": round(current_duration, 2),
                "summary": joined[:400],
                "text": joined,
            }
        )

    payload = {
        "generated_at": utc_now_iso(),
        "video_id": transcript_payload.get("video_id"),
        "block_count": len(blocks),
        "blocks": blocks[:20],
    }
    write_json(out_dir / "01_segmenter.json", payload)
    return payload


def infer_pains_and_desires(text: str) -> list[dict[str, Any]]:
    sentences = split_sentences(text)
    results: list[dict[str, Any]] = []
    pain_rules = [
        ("adhd", "attention and focus issues", "focus-friendly execution", "ADHD knowledge workers", "adhd execution workflow"),
        ("goodnotes", "generic planning overload", "clean digital planning", "Digital planner buyers", "goodnotes planning system"),
        ("freelancer", "chaotic client management", "zero-miss follow-ups", "Freelancers managing clients", "freelancer client management"),
        ("client", "chaotic client management", "zero-miss follow-ups", "Freelancers managing clients", "freelancer client management"),
        ("crm", "scattered lead tracking", "centralized client pipeline", "Freelancers and small agencies", "notion crm workflow"),
        ("etsy", "seller operations fragmentation", "higher ranking and cleaner operations", "Etsy sellers", "etsy seller operations"),
        ("seo", "listing optimization confusion", "search visibility gains", "Etsy sellers", "etsy seo workflow"),
        ("ads", "paid ads complexity", "profitable ad decisions", "Etsy sellers scaling with paid traffic", "etsy ad testing"),
        ("midjourney", "style inconsistency", "commercial-ready consistency", "AI artists and content creators", "midjourney consistency system"),
        ("brand", "inconsistent creative identity", "one-system brand consistency", "Content creators", "brand consistency engine"),
        ("content", "content production burden", "repeatable content engine", "Content creators", "creator content workflow"),
        ("legal", "compliance fear", "faster legal-safe drafting", "Solopreneurs and legal operators", "legal ai workflow"),
        ("finance", "scattered money tracking", "clear profit visibility", "Freelancers and solo operators", "freelancer finance workflow"),
        ("automation", "manual workflow overhead", "leveraged automation", "Digital operators", "automation workflow system"),
    ]
    for sentence in sentences[:100]:
        low = sentence.lower()
        for token, pain, outcome, buyer, wedge in pain_rules:
            if token in low:
                results.append({
                    "buyer": buyer,
                    "pain": pain,
                    "desire": outcome,
                    "outcome": outcome,
                    "wedge": wedge,
                    "quote": sentence,
                })
                break
    if not results:
        fallback_buyer = infer_buyer_from_text(text)
        results.append(
            {
                "buyer": fallback_buyer,
                "pain": "manual workflow complexity",
                "desire": "repeatable execution",
                "outcome": "repeatable execution",
                "wedge": "workflow execution system",
                "quote": "Fallback wedge generated because transcript signal was weak.",
            }
        )
    return results[:15]


async def agent_pain_extractor(segmenter_data: dict[str, Any], out_dir: Path) -> list[dict[str, Any]]:
    corpus = " ".join(block.get("text", "") for block in segmenter_data.get("blocks", []))
    pains = infer_pains_and_desires(corpus)
    write_json(out_dir / "02_pain_desire.json", pains)
    return pains


async def agent_solution_miner(pain_data: list[dict[str, Any]], out_dir: Path) -> list[dict[str, Any]]:
    solutions: list[dict[str, Any]] = []
    for entry in pain_data:
        pain = normalize_space(entry.get("pain", ""))
        desire = normalize_space(entry.get("desire", ""))
        quote = normalize_space(entry.get("quote", ""))
        buyer = normalize_space(entry.get("buyer", infer_buyer_from_text(pain + " " + desire)))
        wedge = normalize_space(entry.get("wedge", clean_validation_query(pain + " " + desire, preserve_brand_terms=True)))
        matched = choose_matching_wedge_entry(buyer, pain, wedge)
        if matched:
            artifact_stack = matched.get("artifact_stack") or []
            validation_queries = matched.get("validation_queries") or []
            primary_channel = matched.get("primary_channel")
            secondary_channel = matched.get("secondary_channel")
            bundle_power = matched.get("bundle_power")
            evidence_confidence = matched.get("evidence_confidence")
            claim_verification_status = matched.get("claim_verification_status")
            source_type = matched.get("source_type")
            priority = matched.get("priority")
            expected_bundle_tiers = matched.get("expected_bundle_tiers") or []
            avg_price_hint = matched.get("avg_price_hint")
            expansion_products = matched.get("expansion_products") or []
            gumroad_fit_hint = matched.get("gumroad_fit_hint")
            bundle_cohesion_hint = matched.get("bundle_cohesion_hint")
            artifact_diversity_hint = matched.get("artifact_diversity_hint")
            differentiation_angle = "Wedge matched against Top Set v2 schema and carried forward into production logic."
        else:
            low = (pain + " " + desire + " " + wedge).lower()
            if any(token in low for token in ["ads", "seo", "crm", "client", "finance"]):
                artifact_stack = ["dashboard", "calculator", "checklist", "mini-course"]
            elif any(token in low for token in ["midjourney", "prompt", "brand", "content", "art"]):
                artifact_stack = ["prompt library", "bundle", "swipe file", "mini-course"]
            else:
                artifact_stack = ["workspace", "checklist", "workbook", "bundle"]
            validation_queries = [
                clean_validation_query(f"{buyer} {wedge} {artifact_stack[0]}", preserve_brand_terms=True),
                clean_validation_query(f"{wedge} {artifact_stack[1]}", preserve_brand_terms=True),
                clean_validation_query(f"{pain} {artifact_stack[0]}", preserve_brand_terms=True),
            ]
            validation_queries = [q for q in validation_queries if q]
            primary_channel = "gumroad"
            secondary_channel = "etsy"
            evidence_confidence = "low"
            claim_verification_status = "unverified"
            source_type = "transcript_signal"
            priority = 3
            expected_bundle_tiers = [49, 79]
            avg_price_hint = 49
            expansion_products = ["free checklist"]
            gumroad_fit_hint = "medium"
            bundle_cohesion_hint = "medium"
            artifact_diversity_hint = min(len(artifact_stack) * 2, 10)
            bundle_power = calculate_bundle_power(
                {
                    "artifact_stack": artifact_stack,
                    "expected_bundle_tiers": expected_bundle_tiers,
                    "avg_price_hint": avg_price_hint,
                    "expansion_products": expansion_products,
                    "gumroad_fit_hint": gumroad_fit_hint,
                    "bundle_cohesion_hint": bundle_cohesion_hint,
                    "artifact_diversity_hint": artifact_diversity_hint,
                }
            )
            differentiation_angle = "Built from transcript-derived wedge signal and packaged as a bundle-first concept."
        solutions.append(
            {
                "buyer": buyer,
                "pain": pain,
                "desire": desire,
                "outcome": entry.get("outcome") or desire,
                "wedge": wedge,
                "framework": f"{normalize_space(wedge).title()} Framework",
                "artifact_stack": artifact_stack,
                "artifact_candidates": artifact_stack,
                "asset_type": str(artifact_stack[0]).title() if artifact_stack else "Bundle",
                "validation_queries": validation_queries,
                "differentiation_angle": differentiation_angle,
                "source_quote": quote,
                "primary_channel": primary_channel,
                "secondary_channel": secondary_channel,
                "bundle_power": bundle_power,
                "evidence_confidence": evidence_confidence,
                "claim_verification_status": claim_verification_status,
                "source_type": source_type,
                "priority": priority,
                "expected_bundle_tiers": expected_bundle_tiers,
                "avg_price_hint": avg_price_hint,
                "expansion_products": expansion_products,
                "gumroad_fit_hint": gumroad_fit_hint,
                "bundle_cohesion_hint": bundle_cohesion_hint,
                "artifact_diversity_hint": artifact_diversity_hint,
                "bundle_status": bundle_keep_status(float(bundle_power)),
            }
        )
    if not solutions:
        fallback = {
            "buyer": "Digital operators with workflow pain",
            "pain": "manual business bottlenecks",
            "desire": "repeatable execution",
            "outcome": "repeatable execution",
            "wedge": "workflow execution system",
            "framework": "Workflow Execution Framework",
            "artifact_stack": ["dashboard", "checklist", "mini-course", "bundle"],
            "artifact_candidates": ["dashboard", "checklist", "mini-course", "bundle"],
            "asset_type": "Dashboard",
            "validation_queries": ["workflow dashboard template", "execution checklist bundle"],
            "differentiation_angle": "Fallback wedge for low-signal transcripts.",
            "source_quote": "No transcript available.",
            "primary_channel": "gumroad",
            "secondary_channel": "etsy",
            "bundle_power": 7.6,
            "evidence_confidence": "low",
            "claim_verification_status": "unverified",
            "source_type": "fallback_signal",
            "priority": 3,
            "expected_bundle_tiers": [39, 79],
            "avg_price_hint": 49,
            "expansion_products": ["free checklist"],
            "gumroad_fit_hint": "medium",
            "bundle_cohesion_hint": "medium",
            "artifact_diversity_hint": 8,
            "bundle_status": "keep",
        }
        solutions.append(fallback)
    write_json(out_dir / "03_solutions.json", solutions)
    return solutions


def build_idea_candidates(solutions: list[dict[str, Any]], retry_index: int, *, wedge_mode: bool = False) -> list[dict[str, Any]]:
    base_formats = [
        ("KPI Dashboard", 59),
        ("Mini Course", 79),
        ("Prompt Library", 49),
        ("Bundle", 69),
        ("Checklist Kit", 35),
        ("Swipe File", 39),
        ("Workspace", 89),
        ("Calculator", 45),
        ("Workbook", 39),
    ]
    if not wedge_mode:
        base_formats = [
            ("Notion Dashboard", 49),
            ("Prompt Pack", 29),
            ("Workbook", 39),
            ("Mini Course", 79),
            ("Checklist Bundle", 29),
            ("Swipe File", 35),
        ]
    ideas: list[dict[str, Any]] = []
    for idx, solution in enumerate(solutions):
        if wedge_mode and bundle_keep_status(float(solution.get("bundle_power", 0.0))) == "kill":
            continue
        desire = normalize_space(solution.get("desire", "results"))
        pain = normalize_space(solution.get("pain", "workflow friction"))
        buyer = normalize_space(solution.get("buyer", "Digital operators"))
        wedge = normalize_space(solution.get("wedge", desire))
        artifact_stack = solution.get("artifact_stack") or solution.get("artifact_candidates") or []
        validation_queries = [q for q in (solution.get("validation_queries") or []) if q]
        primary_channel = solution.get("primary_channel")
        secondary_channel = solution.get("secondary_channel")
        evidence_confidence = solution.get("evidence_confidence")
        claim_verification_status = solution.get("claim_verification_status")
        source_type = solution.get("source_type")
        bundle_power = float(solution.get("bundle_power", 0.0))
        preferred_formats = []
        for artifact in artifact_stack:
            mapping = {
                "dashboard": ("KPI Dashboard", 59),
                "testing sheet": ("Checklist Kit", 35),
                "calculator": ("Calculator", 45),
                "checklist": ("Checklist Kit", 35),
                "mini-course": ("Mini Course", 79),
                "prompt library": ("Prompt Library", 49),
                "prompt pack": ("Prompt Library", 49),
                "bundle": ("Bundle", 69),
                "commercial bundle": ("Bundle", 69),
                "swipe file": ("Swipe File", 39),
                "workspace": ("Workspace", 89),
                "workbook": ("Workbook", 39),
                "brand kit": ("Bundle", 69),
                "content operating system": ("Workspace", 89),
                "style guide": ("Workbook", 39),
                "automation pack": ("Bundle", 69),
                "compliance kit": ("Checklist Kit", 35),
                "tax checklist bundle": ("Checklist Kit", 35),
                "onboarding kit": ("Bundle", 69),
                "mini-course bundle": ("Mini Course", 79),
                "sop pack": ("Bundle", 69),
                "ops kit": ("Bundle", 69),
                "ai prompt pack": ("Prompt Library", 49),
            }
            choice = mapping.get(str(artifact).lower())
            if choice and choice not in preferred_formats:
                preferred_formats.append(choice)
        formats = preferred_formats + [item for item in base_formats if item not in preferred_formats]
        if wedge_mode and len({str(a).strip().lower() for a in artifact_stack if str(a).strip()}) >= 3:
            formats = [item for item in formats if item[0] != "Workbook"]
        for offset, (fmt, price) in enumerate(formats[: 4 + retry_index]):
            raw_title_core = wedge.title() if wedge else desire.title()
            title = f"{raw_title_core} {fmt}" if raw_title_core else fmt
            idea = {
                "id": len(ideas) + 1,
                "format": fmt,
                "title": title[:110],
                "price": price,
                "priority": int(solution.get("priority", max(1, 10 - (idx % 4) - offset // 2))),
                "buyer": buyer,
                "pain": pain,
                "desire": desire,
                "outcome": solution.get("outcome") or desire,
                "wedge": wedge,
                "framework": solution.get("framework"),
                "artifact_stack": artifact_stack,
                "artifact_candidates": artifact_stack,
                "differentiation_angle": solution.get("differentiation_angle"),
                "source_quote": solution.get("source_quote"),
                "niche_query": clean_validation_query(
                    validation_queries[min(offset, max(0, len(validation_queries) - 1))] if validation_queries else f"{buyer} {wedge} {fmt}",
                    preserve_brand_terms=True,
                ),
                "validation_queries": validation_queries,
                "primary_channel": primary_channel,
                "secondary_channel": secondary_channel,
                "bundle_power": bundle_power,
                "bundle_status": bundle_keep_status(bundle_power),
                "evidence_confidence": evidence_confidence,
                "claim_verification_status": claim_verification_status,
                "source_type": source_type,
            }
            if planner_only_idea(idea):
                continue
            if any(token in title.lower() for token in GENERIC_KILL_TOKENS):
                continue
            ideas.append(idea)
            if len(ideas) >= max(QUALITY_MIN_IDEAS + 4, 16):
                return ideas
    return ideas


async def agent_product_strategist(solutions: list[dict[str, Any]], out_dir: Path, retry_index: int = 0, *, wedge_mode: bool = False) -> list[dict[str, Any]]:
    ideas = build_idea_candidates(solutions, retry_index, wedge_mode=wedge_mode)
    write_json(out_dir / "04_product_ideas.json", ideas)
    return ideas


def build_etsy_metrics_from_scan(scan_result: dict[str, Any]) -> dict[str, Any]:
    first = (scan_result.get("results") or [{}])[0]
    aggregates = first.get("aggregates") or {}
    search_metadata = first.get("search_metadata") or {}
    return {
        "total_results": search_metadata.get("total_results"),
        "digital_share": aggregates.get("digital_share", search_metadata.get("digital_share")),
        "avg_reviews_top": aggregates.get("avg_reviews_top"),
        "avg_price": aggregates.get("avg_price", aggregates.get("median_price")),
    }


def build_ebay_metrics_for_fms(raw_metrics: dict[str, Any]) -> dict[str, Any]:
    active = safe_int(raw_metrics.get("active"), 0)
    sold = safe_int(raw_metrics.get("sold"), 0)
    return {
        "str_percent": evaluate_niche_profitability(raw_metrics),
        "active_count": active,
        "sold_count": sold,
    }


def inspect_top_listings(scan_result: dict[str, Any]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    first = (scan_result.get("results") or [{}])[0]
    listings = first.get("listings") or []
    seen_urls: set[str] = set()
    for listing in listings[: max(1, MAX_INSPECT_LISTINGS)]:
        url = normalize_space(listing.get("url", ""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            details = inspect_listing(url, max_reviews=3)
            enriched.append(
                {
                    "url": url,
                    "title": details.get("title"),
                    "price": details.get("price"),
                    "rating": details.get("rating"),
                    "reviews_count": details.get("reviews_count"),
                    "sales_count": details.get("sales_count"),
                    "is_digital": details.get("is_digital"),
                    "tags": details.get("tags") or [],
                }
            )
        except Exception as exc:
            enriched.append({"url": url, "error": str(exc)})
    return enriched


async def agent_validator(ideas: list[dict[str, Any]], video_id: str, out_dir: Path) -> dict[str, Any]:
    validated: list[dict[str, Any]] = []
    best_fms = 0.0
    for idx, idea in enumerate(ideas, start=1):
        keyword = normalize_space(idea.get("niche_query") or idea.get("title") or "")
        if not keyword:
            continue
        log_step(f"[validator] {video_id} idea {idx}/{len(ideas)} etsy_query='{keyword}'")
        try:
            etsy_scan = etsy_scan_keywords([keyword], max_listings_per_keyword=MAX_LISTINGS_PER_KEYWORD)
        except Exception as exc:
            etsy_scan = {"results": [{"keyword": keyword, "error": str(exc), "listings": [], "aggregates": {}, "search_metadata": {}}]}
        etsy_metrics = build_etsy_metrics_from_scan(etsy_scan)
        listing_insights = inspect_top_listings(etsy_scan)
        ebay_query = normalize_ebay_query(keyword) or keyword
        ebay_skipped = is_generic_query(keyword)
        if ebay_skipped:
            ebay_raw = {"active": 0, "sold": 0, "skipped": True, "reason": "generic_query"}
        else:
            try:
                ebay_raw = get_ebay_metrics(ebay_query)
            except Exception as exc:
                ebay_raw = {"active": 0, "sold": 0, "error": str(exc)}
        ebay_metrics = build_ebay_metrics_for_fms(ebay_raw)
        components = compute_fms_components(etsy_metrics=etsy_metrics, ebay_metrics=ebay_metrics, real_performance={})
        fms_score = compute_fms_score(components)
        best_fms = max(best_fms, fms_score)
        revenue_floor = max(500, int(round((fms_score * max(idea.get("price", 29), 19)) / 1.8)))
        validated.append(
            {
                **idea,
                "video_id": video_id,
                "etsy_keyword": keyword,
                "ebay_query": None if ebay_skipped else ebay_query,
                "etsy_metrics": etsy_metrics,
                "ebay_metrics": ebay_metrics,
                "ebay_status": "skipped_generic_query" if ebay_skipped else "queried",
                "listing_insights": listing_insights,
                "fms_components": components,
                "fms_score": fms_score,
                "revenue_potential": f"${revenue_floor}+/mo",
            }
        )
    validated.sort(
        key=lambda item: (
            -safe_float(item.get("bundle_power"), 0.0),
            -safe_int(item.get("priority"), 0),
            -safe_float(item.get("fms_score"), 0.0),
            item.get("title", ""),
        )
    )
    payload = {
        "generated_at": utc_now_iso(),
        "video_id": video_id,
        "idea_count": len(validated),
        "top_fms_score": best_fms,
        "items": validated,
    }
    write_json(out_dir / "05_validated_ideas.json", payload)
    return payload


def quality_gate(ideas: list[dict[str, Any]], validated_payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    idea_count = len(ideas)
    top_fms = safe_float(validated_payload.get("top_fms_score"), 0.0)
    top_bundle = max([safe_float(item.get("bundle_power"), 0.0) for item in (validated_payload.get("items") or [])] or [0.0])
    passed = idea_count >= QUALITY_MIN_IDEAS and top_fms >= QUALITY_MIN_FMS and top_bundle >= 7.5
    return passed, {
        "idea_count": idea_count,
        "top_fms_score": top_fms,
        "top_bundle_power": top_bundle,
        "min_ideas": QUALITY_MIN_IDEAS,
        "min_fms": QUALITY_MIN_FMS,
        "min_bundle_power": 7.5,
    }


def build_research_report(video_url: str, transcript_payload: dict[str, Any], segmenter_data: dict[str, Any], pains: list[dict[str, Any]], validated_items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append(f"# Research Report for {transcript_payload.get('video_id')}")
    lines.append("")
    lines.append(f"Video URL: {video_url}")
    lines.append(f"Generated At: {utc_now_iso()}")
    lines.append("")
    lines.append("## Pain / Desire Map")
    lines.append("")
    for item in pains[:10]:
        lines.append(f"- Pain: {item.get('pain')} | Desire: {item.get('desire')}")
        lines.append(f"  - Quote: {item.get('quote')}")
    lines.append("")
    lines.append("## Transcript Blocks")
    lines.append("")
    for block in segmenter_data.get("blocks", [])[:8]:
        lines.append(f"### Block {block.get('id')} @ {block.get('start')}s")
        lines.append(block.get("summary", ""))
        lines.append("")
    lines.append("## Top Validated Ideas")
    lines.append("")
    for item in validated_items[:8]:
        lines.append(
            f"- {item.get('title')} | {item.get('format')} | bundle {item.get('bundle_power')} | FMS {item.get('fms_score')} | {item.get('revenue_potential')} | {item.get('primary_channel')}->{item.get('secondary_channel')}"
        )
    return "\n".join(lines).strip() + "\n"


def build_etsy_listing_payload(idea: dict[str, Any]) -> dict[str, Any]:
    title = normalize_space(f"{idea.get('title')} | {idea.get('format')} | Instant Download")[:140]
    base_terms = [
        idea.get("format", "Digital Product"),
        idea.get("pain", "workflow"),
        idea.get("desire", "results"),
        idea.get("framework", "system"),
        "digital download",
        "etsy seller",
        "small business",
        "productivity",
        "template",
        "dashboard",
        "prompt pack",
        "workflow",
        "2026",
    ]
    tags: list[str] = []
    for term in base_terms:
        cleaned = normalize_space(str(term or ""))[:20]
        if cleaned and cleaned.lower() not in {x.lower() for x in tags}:
            tags.append(cleaned)
        if len(tags) >= 13:
            break
    bullets = [
        f"Built from a live market signal around: {idea.get('pain')}",
        f"Designed to help buyers achieve: {idea.get('desire')}",
        f"Format: {idea.get('format')}",
        f"Validation signal: FMS {idea.get('fms_score')}",
        "Instant digital delivery",
    ]
    description = textwrap.dedent(
        f"""
        {title}

        What you get:
        - A structured {idea.get('format')}
        - A framework based on the core theme: {idea.get('framework')}
        - A digital asset designed to reduce {idea.get('pain')} and increase {idea.get('desire')}

        Validation snapshot:
        - FMS score: {idea.get('fms_score')}
        - Revenue potential: {idea.get('revenue_potential')}

        This is a digital product. No physical item will be shipped.
        """
    ).strip()
    return {"title": title, "tags": tags, "bullets": bullets, "description": description}


def build_excalidraw_payload(video_id: str, pains: list[dict[str, Any]], validated_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "youtube_intelligence_orchestrator",
        "video_id": video_id,
        "maps": {
            "pain_map": [{"pain": item.get("pain"), "desire": item.get("desire")} for item in pains[:8]],
            "product_ladder": [
                {"tier": "entry", "title": item.get("title"), "price": item.get("price"), "fms_score": item.get("fms_score")}
                for item in validated_items[:6]
            ],
        },
    }


def build_templated_handoff(video_id: str, validated_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "generated_at": utc_now_iso(),
        "templates_requested": [
            "etsy_slide_01_hero_adhd_weekly_reset",
            "etsy_slide_02_whats_included_adhd_weekly_reset",
            "planner_cover_v2",
            "planner_daily_v2",
            "planner_weekly_v2",
            "planner_notes_v2_1",
        ],
        "items": [
            {
                "title": item.get("title"),
                "subtitle": item.get("format"),
                "price": item.get("price"),
                "fms_score": item.get("fms_score"),
                "bundle_power": item.get("bundle_power"),
                "primary_channel": item.get("primary_channel"),
                "secondary_channel": item.get("secondary_channel"),
                "evidence_confidence": item.get("evidence_confidence"),
                "claim_verification_status": item.get("claim_verification_status"),
                "revenue_potential": item.get("revenue_potential"),
            }
            for item in validated_items[:6]
        ],
    }


async def agent_packager(video_url: str, transcript_payload: dict[str, Any], segmenter_data: dict[str, Any], pains: list[dict[str, Any]], validated_payload: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    validated_items = validated_payload.get("items") or []
    listings_dir = out_dir / "etsy_listings"
    excalidraw_dir = out_dir / "excalidraw"
    listings_dir.mkdir(parents=True, exist_ok=True)
    excalidraw_dir.mkdir(parents=True, exist_ok=True)

    for idx, idea in enumerate(validated_items[:5], start=1):
        listing = build_etsy_listing_payload(idea)
        write_json(listings_dir / f"listing_{idx:02d}.json", listing)
        write_text(listings_dir / f"listing_{idx:02d}_title.txt", listing["title"] + "\n")

    research_report = build_research_report(video_url, transcript_payload, segmenter_data, pains, validated_items)
    write_text(out_dir / "research_report.md", research_report)
    write_text(out_dir / "course_outline.md", "# Course Outline\n\n1. Core pain\n2. Framework\n3. Implementation\n4. Monetization\n")
    write_text(out_dir / "prompt_pack.txt", "Prompt 1: Turn the core pain into a digital framework.\nPrompt 2: Create an Etsy listing from the top validated idea.\n")
    write_text(out_dir / "ready_to_sell.md", "# Ready to Sell\n\n1. Review top 3 validated ideas.\n2. Pick one Etsy listing JSON.\n3. Render slides in Templated.\n4. Publish to Etsy/Gumroad.\n")
    write_json(out_dir / "product_ideas.json", validated_items)
    write_json(out_dir / "validated_ideas.json", validated_payload)
    write_json(excalidraw_dir / "pain_map.excalidraw", build_excalidraw_payload(transcript_payload.get("video_id", "unknown"), pains, validated_items))
    write_json(out_dir / "notion_template.json", {"type": "notion_dashboard", "video_id": transcript_payload.get("video_id"), "items": validated_items[:10]})
    write_json(out_dir / "templated_handoff.json", build_templated_handoff(transcript_payload.get("video_id", "unknown"), validated_items))
    return {"status": "packaged", "listing_count": min(5, len(validated_items))}


def zip_output_dir(out_dir: Path, video_id: str) -> Path:
    zip_path = OUTPUT_DIR / f"YouTube_Intelligence_{video_id}_{datetime.now().strftime('%Y-%m-%d')}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(out_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(out_dir))
    return zip_path


async def run_youtube_intelligence(
    video_url: str,
    *,
    wedge_mode: bool = WEDGE_MODE_DEFAULT,
    transcript_file: str | None = None,
    transcript_json: str | None = None,
) -> Path:
    log_step(
        f"[start] processing video_url={video_url} wedge_mode={wedge_mode} "
        f"transcript_file={transcript_file or '-'} transcript_json={transcript_json or '-'}"
    )
    if transcript_json:
        transcript_payload = load_transcript_from_file(transcript_json, extract_video_id(video_url))
    elif transcript_file:
        transcript_payload = load_transcript_from_file(transcript_file, extract_video_id(video_url))
    else:
        transcript_payload = await get_transcript(video_url)
    video_id = transcript_payload.get("video_id") or extract_video_id(video_url)
    out_dir = OUTPUT_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    write_text(out_dir / "program.md", build_program_md(video_url, video_id))
    write_json(out_dir / "transcript.json", transcript_payload)
    write_text(out_dir / "transcript.md", (transcript_payload.get("text") or "Transcript not available") + "\n")
    log_step(f"[transcript] video={video_id} status={transcript_payload.get('status')} source={transcript_payload.get('source')} chunks={len(transcript_payload.get('chunks') or [])}")

    segmenter_data = await agent_segmenter(transcript_payload, out_dir)
    pain_data = await agent_pain_extractor(segmenter_data, out_dir)
    solutions = await agent_solution_miner(pain_data, out_dir)
    log_step(f"[signals] video={video_id} blocks={segmenter_data.get('block_count')} pain_signals={len(pain_data)} wedge_objects={len(solutions)}")

    attempt = 0
    ideas: list[dict[str, Any]] = []
    validated_payload: dict[str, Any] = {"items": [], "top_fms_score": 0.0}
    gate_report: dict[str, Any] = {}

    while attempt <= MAX_RETRIES:
        log_step(f"[strategist] video={video_id} attempt={attempt} wedge_mode={wedge_mode}")
        ideas = await agent_product_strategist(solutions, out_dir, retry_index=attempt, wedge_mode=wedge_mode)
        validated_payload = await agent_validator(ideas, video_id, out_dir)
        passed, gate_report = quality_gate(ideas, validated_payload)
        write_json(out_dir / "quality_gate.json", {"attempt": attempt, "passed": passed, **gate_report, "wedge_mode": wedge_mode})
        log_step(f"[quality_gate] video={video_id} passed={passed} ideas={gate_report.get('idea_count')} top_fms={gate_report.get('top_fms_score')}")
        if passed:
            break
        attempt += 1

    await agent_packager(video_url, transcript_payload, segmenter_data, pain_data, validated_payload, out_dir)
    zip_path = zip_output_dir(out_dir, video_id)
    log_step(f"[done] video={video_id} ideas={len(ideas)} top_fms={gate_report.get('top_fms_score', 0.0)} zip={zip_path}")
    return zip_path


async def run_batch(urls: list[str], *, wedge_mode: bool = WEDGE_MODE_DEFAULT) -> list[Path]:
    outputs: list[Path] = []
    total = min(len(urls), MAX_BATCH_VIDEOS)
    for idx, url in enumerate(urls[:MAX_BATCH_VIDEOS], start=1):
        log_step(f"[batch] {idx}/{total} start")
        outputs.append(await run_youtube_intelligence(url, wedge_mode=wedge_mode))
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YouTube Intelligence Orchestrator")
    parser.add_argument("--video", help="One video URL")
    parser.add_argument("--videos", help="Text file with video URLs, one per line")
    parser.add_argument("--transcript-file", help="Local transcript file path (.txt or .json)")
    parser.add_argument("--transcript-json", help="Local transcript JSON path")
    parser.add_argument("--wedge-mode", action="store_true", help="Use wedge-first product generation")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.video and not args.videos:
        raise SystemExit("Provide --video or --videos")
    if args.transcript_json and args.transcript_file:
        raise SystemExit("Use only one of --transcript-file or --transcript-json")
    if (args.transcript_file or args.transcript_json) and args.videos:
        raise SystemExit("Transcript file inputs currently support only --video")
    wedge_mode = args.wedge_mode or WEDGE_MODE_DEFAULT
    if args.video:
        asyncio.run(
            run_youtube_intelligence(
                args.video,
                wedge_mode=wedge_mode,
                transcript_file=args.transcript_file,
                transcript_json=args.transcript_json,
            )
        )
        return 0
    urls_path = Path(args.videos)
    if not urls_path.exists():
        raise SystemExit(f"Videos file not found: {urls_path}")
    urls = [line.strip() for line in urls_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    asyncio.run(run_batch(urls, wedge_mode=wedge_mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
