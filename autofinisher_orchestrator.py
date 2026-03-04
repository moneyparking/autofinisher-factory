#!/usr/bin/env python3
import argparse
import copy
import csv
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path("/home/agent/autofinisher-factory")
RADAR_SCRIPT = BASE_DIR / "niche_profit_engine.py"
BUILDER_SCRIPT = BASE_DIR / "artifact_builder.py"

ACCEPTED_DIR = BASE_DIR / "niche_engine" / "accepted"
ACCEPTED_PACKAGE_PATH = ACCEPTED_DIR / "niche_package.json"
ROOT_PACKAGE_PATH = BASE_DIR / "niche_package.json"

READY_DIR = BASE_DIR / "ready_to_publish"
ARCHIVE_DIR = BASE_DIR / "archive"
LOG_PATH = BASE_DIR / "factory_log.csv"

ARCHIVE_AFTER_DAYS = 7
DEFAULT_INTERVAL_HOURS = 12
ALLOWED_INTERVALS = {12, 24}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ts(msg: str) -> None:
    print(f"[{now_utc_iso()}] {msg}", flush=True)


def safe_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "untitled-niche"


def ensure_dirs() -> None:
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    READY_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        ts(f"[!] Failed to read JSON {path}: {exc}")
        return None


def extract_items(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]

        niches = payload.get("niches")
        if isinstance(niches, list):
            normalized = []
            for niche in niches:
                if isinstance(niche, dict):
                    normalized.append(niche)
                elif isinstance(niche, str):
                    normalized.append({"niche": niche})
            return normalized

    return []


def extract_niche_name(item: dict) -> str:
    for key in ("niche", "keyword", "query", "name", "title"):
        value = str(item.get(key, "")).strip()
        if value:
            return value
    return ""


def extract_str_value(item: dict) -> float:
    metrics = item.get("metrics", {})
    value = metrics.get("sell_through_rate", 0)
    try:
        return round(float(value), 2)
    except Exception:
        return 0.0


def ensure_log_file() -> None:
    if LOG_PATH.exists():
        return
    with LOG_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "niche", "str", "status"])


def append_log(niche_name: str, str_value: float, status: str) -> None:
    ensure_log_file()
    with LOG_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([now_utc_iso(), niche_name, f"{str_value:.2f}", status])


def print_subprocess_output(name: str, result: subprocess.CompletedProcess) -> None:
    if result.stdout:
        ts(f"[{name}] stdout:\n{result.stdout.rstrip()}")
    if result.stderr:
        ts(f"[{name}] stderr:\n{result.stderr.rstrip()}")


def run_python_script(script_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        check=False,
    )


def locate_latest_package() -> Path | None:
    candidates = [path for path in (ACCEPTED_PACKAGE_PATH, ROOT_PACKAGE_PATH) if path.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def sync_radar_output_to_accepted() -> Path | None:
    latest = locate_latest_package()
    if latest is None:
        return None

    if latest != ACCEPTED_PACKAGE_PATH:
        ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(latest, ACCEPTED_PACKAGE_PATH)
        ts(f"[i] Synced radar package from {latest} -> {ACCEPTED_PACKAGE_PATH}")

    return ACCEPTED_PACKAGE_PATH if ACCEPTED_PACKAGE_PATH.exists() else latest


def build_filtered_payload(original_payload, new_items: list[dict]):
    if isinstance(original_payload, list):
        return copy.deepcopy(new_items)

    if isinstance(original_payload, dict):
        payload = copy.deepcopy(original_payload)
        if "items" in payload or "accepted_count" in payload or "schema_version" in payload:
            payload["items"] = copy.deepcopy(new_items)
        if "niches" in payload:
            payload["niches"] = copy.deepcopy(new_items)
        elif "items" not in payload:
            payload["niches"] = copy.deepcopy(new_items)
        if "accepted_count" in payload:
            payload["accepted_count"] = len(new_items)
        if "total_approved" in payload:
            payload["total_approved"] = len(new_items)
        payload["generated_at"] = now_utc_iso()
        return payload

    return {"generated_at": now_utc_iso(), "items": copy.deepcopy(new_items), "accepted_count": len(new_items)}


def get_existing_ready_slugs() -> set[str]:
    if not READY_DIR.exists():
        return set()
    return {path.name for path in READY_DIR.iterdir() if path.is_dir()}


def verify_built(niche_name: str) -> str:
    niche_dir = READY_DIR / safe_slug(niche_name)
    required = ["master.png", "mockup.png", "SEO.txt"]

    if not niche_dir.exists():
        return "build_missing"

    if all((niche_dir / name).exists() for name in required):
        return "build_success"

    existing = [name for name in required if (niche_dir / name).exists()]
    if existing:
        return "build_partial"

    return "build_failed"


def archive_old_ready_items(days: int = ARCHIVE_AFTER_DAYS) -> int:
    if not READY_DIR.exists():
        return 0

    cutoff = time.time() - days * 86400
    archived = 0

    for path in READY_DIR.iterdir():
        if not path.is_dir():
            continue

        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue

        if mtime >= cutoff:
            continue

        destination = ARCHIVE_DIR / path.name
        if destination.exists():
            suffix = datetime.now().strftime("%Y%m%d%H%M%S")
            destination = ARCHIVE_DIR / f"{path.name}_{suffix}"

        shutil.move(str(path), str(destination))
        archived += 1
        ts(f"[archive] Moved {path.name} -> {destination}")

    return archived


def run_radar_cycle() -> Path | None:
    if not RADAR_SCRIPT.exists():
        ts(f"[!] Radar script not found: {RADAR_SCRIPT}")
        return None

    ts("[phase] Running niche_profit_engine.py")
    result = run_python_script(RADAR_SCRIPT)
    print_subprocess_output("radar", result)

    if result.returncode != 0:
        ts(f"[!] Radar failed with exit code {result.returncode}. Builder will not run.")
        return None

    package_path = sync_radar_output_to_accepted()
    if package_path is None or not package_path.exists():
        ts("[!] Radar finished, but niche_package.json was not found. Builder will not run.")
        return None

    return package_path


def run_builder_for_new_items(package_path: Path) -> int:
    if not BUILDER_SCRIPT.exists():
        ts(f"[!] Builder script not found: {BUILDER_SCRIPT}")
        return 0

    payload = read_json(package_path)
    if payload is None:
        ts("[!] Cannot read radar output package. Builder will not run.")
        return 0

    items = extract_items(payload)
    if not items:
        ts("[i] Radar package contains no approved niches.")
        return 0

    existing_slugs = get_existing_ready_slugs()
    new_items = []
    skipped = 0

    for item in items:
        niche_name = extract_niche_name(item)
        if not niche_name:
            continue

        niche_slug = safe_slug(niche_name)
        str_value = extract_str_value(item)

        if niche_slug in existing_slugs:
            append_log(niche_name, str_value, "already_built")
            skipped += 1
            continue

        new_items.append(item)

    if not new_items:
        ts(f"[i] No new niches to build. Existing/skipped: {skipped}")
        return 0

    backup_text = package_path.read_text(encoding="utf-8") if package_path.exists() else None
    filtered_payload = build_filtered_payload(payload, new_items)
    package_path.write_text(json.dumps(filtered_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ts(f"[phase] Running artifact_builder.py for {len(new_items)} new niche(s)")
    result = None

    try:
        result = run_python_script(BUILDER_SCRIPT)
        print_subprocess_output("builder", result)
    finally:
        if backup_text is not None:
            package_path.write_text(backup_text, encoding="utf-8")

    built_count = 0
    for item in new_items:
        niche_name = extract_niche_name(item)
        str_value = extract_str_value(item)

        if result is None or result.returncode != 0:
            status = "build_failed"
        else:
            status = verify_built(niche_name)

        append_log(niche_name, str_value, status)
        if status == "build_success":
            built_count += 1

    if result is None or result.returncode != 0:
        ts(f"[!] Builder failed with exit code {None if result is None else result.returncode}")
    else:
        ts(f"[i] Builder finished. Successful builds: {built_count}/{len(new_items)}")

    return built_count


def run_once() -> None:
    ensure_dirs()

    archived = archive_old_ready_items(ARCHIVE_AFTER_DAYS)
    if archived:
        ts(f"[i] Archived old niches: {archived}")

    package_path = run_radar_cycle()
    if package_path is None:
        return

    run_builder_for_new_items(package_path)


def print_crontab_examples() -> None:
    python_bin = sys.executable
    script = BASE_DIR / "autofinisher_orchestrator.py"

    every_12h = f"0 */12 * * * {python_bin} {script} --mode once >> {BASE_DIR / 'orchestrator.log'} 2>&1"
    every_24h = f"0 0 * * * {python_bin} {script} --mode once >> {BASE_DIR / 'orchestrator.log'} 2>&1"

    print(every_12h)
    print(every_24h)


def parse_args():
    parser = argparse.ArgumentParser(description="Autofinisher Factory Orchestrator")
    parser.add_argument("--mode", choices=("once", "loop"), default="once")
    parser.add_argument("--interval-hours", type=int, choices=sorted(ALLOWED_INTERVALS), default=DEFAULT_INTERVAL_HOURS)
    parser.add_argument("--print-crontab", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.print_crontab:
        print_crontab_examples()
        return 0

    if args.mode == "once":
        run_once()
        return 0

    sleep_seconds = args.interval_hours * 3600
    ts(f"[master-schedule] Loop mode enabled. Interval: {args.interval_hours}h")

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            ts("[i] Interrupted by user. Stopping orchestrator.")
            return 0
        except Exception as exc:
            ts(f"[!] Unhandled orchestrator error: {exc}")

        ts(f"[master-schedule] Sleeping for {args.interval_hours}h")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
