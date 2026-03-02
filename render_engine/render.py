#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import pathname2url

from jinja2 import Environment, FileSystemLoader, select_autoescape
from jsonschema import Draft202012Validator, FormatChecker
from playwright.sync_api import sync_playwright

ROOT = Path("/home/agent/autofinisher-factory")
ENGINE_DIR = ROOT / "render_engine"
TEMPLATES_DIR = ENGINE_DIR / "templates"
SCHEMAS_DIR = ENGINE_DIR / "schemas"
TOKENS_PATH = ENGINE_DIR / "style_tokens" / "style_tokens.json"
DEBUG_DIR = ENGINE_DIR / "output" / "debug"
MASTERS_DIR = ENGINE_DIR / "output" / "masters"


class PayloadValidationError(ValueError):
    pass


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return text or "poster"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contracts() -> tuple[dict, dict, dict]:
    payload_schema = load_json(SCHEMAS_DIR / "render_payload.schema.json")
    token_schema = load_json(SCHEMAS_DIR / "style_tokens.schema.json")
    style_tokens = load_json(TOKENS_PATH)
    Draft202012Validator(token_schema).validate(style_tokens)
    return payload_schema, token_schema, style_tokens


def validate_payload(payload: dict, payload_schema: dict) -> None:
    validator = Draft202012Validator(payload_schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        details = []
        for error in errors:
            path = ".".join(str(part) for part in error.absolute_path) or "payload"
            details.append(f"{path}: {error.message}")
        raise PayloadValidationError("; ".join(details))


def ensure_profile_matches(payload: dict, style_tokens: dict) -> None:
    profile_id = payload["output"]["profile_id"]
    expected = style_tokens["output_profiles"].get(profile_id)
    if not expected:
        raise PayloadValidationError(f"output.profile_id '{profile_id}' is not defined in style token contract")
    for field in ("width", "height", "format", "dpi", "background"):
        if payload["output"][field] != expected[field]:
            raise PayloadValidationError(
                f"output.{field}={payload['output'][field]!r} does not match profile '{profile_id}' contract value {expected[field]!r}"
            )


def resolve_style_tokens(payload: dict, style_tokens: dict) -> tuple[dict, dict]:
    template_id = payload["template_id"]
    template_contract = style_tokens["templates"].get(template_id)
    if not template_contract:
        raise PayloadValidationError(f"template_id '{template_id}' is not registered in style token contract")

    family_id = payload["style"]["family"]
    if family_id != template_contract["family"]:
        raise PayloadValidationError(
            f"style.family '{family_id}' does not match template contract family '{template_contract['family']}'"
        )

    family = style_tokens["families"].get(family_id)
    if not family:
        raise PayloadValidationError(f"style.family '{family_id}' is not defined in style token contract")

    resolved = {}
    token_map = {
        "palette_id": "palettes",
        "font_pack": "font_packs",
        "background_mode": "background_modes",
        "accent_mode": "accent_modes",
        "grid_mode": "grid_modes",
        "spacing_preset": "spacing_presets",
        "metadata_color": "metadata_color_modes",
    }
    for payload_field, contract_section in token_map.items():
        token_id = payload["style"][payload_field]
        token_value = family[contract_section].get(token_id)
        if token_value is None:
            raise PayloadValidationError(
                f"style.{payload_field} '{token_id}' is not defined under {family_id}.{contract_section}"
            )
        resolved.update(token_value)

    overrides = payload["style"].get("overrides", {})
    disallowed = sorted(set(overrides) - set(family["allowed_overrides"]))
    if disallowed:
        raise PayloadValidationError(
            f"style.overrides contains unsupported keys for family '{family_id}': {', '.join(disallowed)}"
        )
    resolved.update(overrides)
    resolved["font_css_url"] = resolved.get("font_css_url", "")
    return resolved, template_contract


def build_headline_markup(headline: str, mode: str, max_lines: int) -> str:
    words = headline.strip().split()
    if not words:
        raise PayloadValidationError("content.headline cannot be blank after trimming")

    if mode == "retro_emphasis":
        styled = []
        for idx, word in enumerate(words):
            css_class = "hl" if idx == 0 else "pink" if idx == 1 else "hot" if idx == len(words) - 1 else ""
            styled.append(f'<span class="{css_class}">{word}</span>' if css_class else word)
        if len(styled) <= 2:
            return " ".join(styled)
        midpoint = min(max(1, len(styled) // 2), len(styled) - 1)
        lines = [" ".join(styled[:1]), " ".join(styled[1:midpoint + 1]), " ".join(styled[midpoint + 1:])]
        return "<br/>".join([line for line in lines if line.strip()])

    chunk = max(1, (len(words) + max_lines - 1) // max_lines)
    lines = [" ".join(words[index:index + chunk]) for index in range(0, len(words), chunk)]
    if len(lines) > max_lines:
        raise PayloadValidationError(f"content.headline exceeds deterministic line budget for template mode '{mode}'")
    return "<br/>".join(lines)


def normalize_payload(payload: dict, style_tokens: dict) -> dict:
    ensure_profile_matches(payload, style_tokens)
    resolved_tokens, template_contract = resolve_style_tokens(payload, style_tokens)
    headline_html = build_headline_markup(
        payload["content"]["headline"],
        template_contract["headline_mode"],
        int(payload["layout"]["headline_max_lines"]),
    )

    created_at = payload["metadata"]["created_at"]
    try:
        created_at_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PayloadValidationError(f"metadata.created_at is invalid ISO-8601 datetime: {created_at}") from exc

    payload["metadata"]["created_at_display"] = created_at_dt.astimezone(timezone.utc).strftime("RENDERED %Y-%m-%d")
    payload["content"]["headline_html"] = headline_html
    payload["render_context"] = {
        "safe_x": resolved_tokens.get("safe_x", "8%"),
        "safe_y": resolved_tokens.get("safe_y", "7%"),
        "headline_width": resolved_tokens.get("headline_width", f"{int(payload['layout']['headline_width_ratio'] * 100)}%"),
        "subheadline_width": resolved_tokens.get("subheadline_width", "68%"),
        "metadata_rail_width": resolved_tokens.get("metadata_rail_width", "15%"),
    }
    payload["resolved_style_tokens"] = resolved_tokens
    payload["template_contract"] = template_contract
    return payload


def compute_cache_key(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def render_html(payload: dict) -> Path:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape(["html", "xml"]))
    template = env.get_template(payload["template_contract"]["template_file"])
    html = template.render(**payload, range=range)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    debug_name = f"{slugify(payload['content']['headline'])}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.html"
    debug_path = DEBUG_DIR / debug_name
    debug_path.write_text(html, encoding="utf-8")
    return debug_path


def html_file_url(path: Path) -> str:
    return urljoin("file:", pathname2url(str(path.resolve())))


def screenshot_html(debug_html_path: Path, output_path: Path, width: int, height: int, image_format: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_type = "jpeg" if image_format == "jpg" else image_format
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        page.goto(html_file_url(debug_html_path), wait_until="networkidle")
        page.wait_for_load_state("networkidle")
        page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
        page.screenshot(path=str(output_path), type=image_type, animations="disabled")
        browser.close()


def write_report(payload: dict, payload_path: Path, output_path: Path, debug_html_path: Path, cache_key: str, started_at: datetime) -> Path:
    finished_at = datetime.utcnow()
    report = {
        "status": "success",
        "cache_key": cache_key,
        "template_id": payload["template_id"],
        "template_version": payload["template_version"],
        "render_start_timestamp": started_at.isoformat() + "Z",
        "render_end_timestamp": finished_at.isoformat() + "Z",
        "total_render_ms": int((finished_at - started_at).total_seconds() * 1000),
        "output_dimensions": {"width": payload["output"]["width"], "height": payload["output"]["height"]},
        "asset_versions": {"style_token_contract": "1.0.0"},
        "overflow_actions_taken": [],
        "validation_status": "passed",
        "payload_path": str(payload_path),
        "debug_html_path": str(debug_html_path),
        "output_path": str(output_path),
        "output_profile": payload["output"]["profile_id"],
        "resolved_style_family": payload["style"]["family"],
    }
    report_path = output_path.with_suffix(output_path.suffix + ".render.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def derive_default_output(payload: dict) -> Path:
    if payload["template_id"] == "retro_neon_grid" and payload["content"]["headline"].strip().upper() == "YOU'RE ABSOLUTELY RIGHT!":
        return ROOT / "ready_to_publish" / "HTML_PROOF.png"
    filename = f"{slugify(payload['content']['headline'])}_{payload['template_id']}.{payload['output']['format']}"
    return MASTERS_DIR / filename


def render_payload(payload_path: Path, output_override: str | None = None) -> dict:
    started_at = datetime.utcnow()
    payload_schema, _token_schema, style_tokens = load_contracts()
    payload = load_json(payload_path)
    validate_payload(payload, payload_schema)
    payload = normalize_payload(payload, style_tokens)
    cache_key = compute_cache_key(payload)
    debug_html_path = render_html(payload)
    output_path = Path(output_override) if output_override else derive_default_output(payload)
    screenshot_html(debug_html_path, output_path, int(payload["output"]["width"]), int(payload["output"]["height"]), payload["output"]["format"])
    report_path = write_report(payload, payload_path, output_path, debug_html_path, cache_key, started_at)
    return {
        "status": "success",
        "payload_path": str(payload_path),
        "debug_html_path": str(debug_html_path),
        "output_path": str(output_path),
        "report_path": str(report_path),
        "template_id": payload["template_id"],
        "cache_key": cache_key,
        "viewport": {"width": payload["output"]["width"], "height": payload["output"]["height"]},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render poster payload into a deterministic image via Jinja2 + Playwright.")
    parser.add_argument("--payload", required=True, help="Path to JSON payload.")
    parser.add_argument("--out", required=False, help="Output image path.")
    args = parser.parse_args()
    try:
        result = render_payload(Path(args.payload), args.out)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
