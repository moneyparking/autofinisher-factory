from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import Any

BASE_DIR = Path("/home/agent/autofinisher-factory")
VALIDATED_DIR = BASE_DIR / "data" / "validated_niches" / "items"
WINNERS_DIR = BASE_DIR / "data" / "winners"
SKU_TASKS_DIR = BASE_DIR / "data" / "sku_tasks"
READY_TO_PUBLISH_DIR = BASE_DIR / "ready_to_publish"
PUBLISH_PACKETS_DIR = BASE_DIR / "publish_packets"
OUTPUT_PATH = PUBLISH_PACKETS_DIR / "phase4_queue.json"
SUMMARY_PATH = PUBLISH_PACKETS_DIR / "phase4_operator_summary.json"

CORE_ASSET_FILES = (
    "deliverable.pdf",
    "master.png",
    "mockup.png",
)
CORE_PACKET_FILES = (
    "etsy_listing.json",
    "gumroad_listing.json",
    "manual_upload_checklist.txt",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")



def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None



def safe_text(value: Any) -> str:
    return str(value or "").strip()



def file_exists(path_value: str | None) -> bool:
    if not path_value:
        return False
    try:
        return Path(path_value).exists()
    except Exception:
        return False



def asset_status(slug: str) -> tuple[bool, list[str], Path]:
    asset_dir = READY_TO_PUBLISH_DIR / slug
    present = [name for name in CORE_ASSET_FILES if (asset_dir / name).exists()]
    return (len(present) == len(CORE_ASSET_FILES), present, asset_dir)



def packet_status(slug: str) -> tuple[bool, list[str], Path]:
    packet_dir = PUBLISH_PACKETS_DIR / slug
    present = [name for name in CORE_PACKET_FILES if (packet_dir / name).exists()]
    return (len(present) == len(CORE_PACKET_FILES), present, packet_dir)



def infer_slug(validated: dict[str, Any], winner: dict[str, Any] | None, sku_task: dict[str, Any] | None) -> str | None:
    if sku_task:
        cluster = sku_task.get("cluster") or {}
        if isinstance(cluster, dict):
            core = cluster.get("core_skus") or []
            if isinstance(core, list) and core:
                first = core[0]
                if isinstance(first, dict):
                    slug = safe_text(first.get("slug"))
                    if slug:
                        return slug

    if winner:
        cluster = winner.get("recommended_sku_cluster") or {}
        if isinstance(cluster, dict):
            core = cluster.get("core_skus") or []
            if isinstance(core, list) and core:
                first = core[0]
                if isinstance(first, dict):
                    slug = safe_text(first.get("slug"))
                    if slug:
                        return slug

    niche_keyword = safe_text(validated.get("niche_keyword") or validated.get("niche"))
    if niche_keyword:
        return "-".join(part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in niche_keyword).split("-") if part)
    return None



def resolve_state(*, has_winner: bool, has_sku_task: bool, assets_ready: bool, packet_ready: bool) -> str:
    if assets_ready and packet_ready:
        return "publish_ready"
    if packet_ready:
        return "listing_ready"
    if assets_ready:
        return "asset_ready"
    if has_sku_task:
        return "sku_ready"
    if has_winner:
        return "winner_ready"
    return "validated"



def derive_blocking_reasons(
    *,
    has_winner: bool,
    has_sku_task: bool,
    assets_ready: bool,
    packet_ready: bool,
    asset_files_present: list[str],
    packet_files_present: list[str],
) -> list[str]:
    reasons: list[str] = []

    if not has_winner:
        reasons.append("missing_winner")
    if not has_sku_task:
        reasons.append("missing_sku_task")
    if not assets_ready:
        for name in CORE_ASSET_FILES:
            if name not in asset_files_present:
                reasons.append(f"missing_asset:{name}")
    if not packet_ready:
        for name in CORE_PACKET_FILES:
            if name not in packet_files_present:
                reasons.append(f"missing_packet:{name}")

    if assets_ready and packet_ready and (not has_winner or not has_sku_task):
        reasons.append("artifact_chain_gap")

    return reasons



def resolve_queue_priority(
    *,
    state: str,
    blocking_reasons: list[str],
    sku_task: dict[str, Any] | None,
) -> str:
    task_priority = safe_text((sku_task or {}).get("priority")).lower()

    if state == "publish_ready":
        return "urgent" if "artifact_chain_gap" not in blocking_reasons else "review"
    if state in {"listing_ready", "asset_ready"}:
        return "high"
    if state == "sku_ready":
        return "high" if task_priority == "high" else "normal"
    if state == "winner_ready":
        return "normal"
    return "low"



def resolve_next_action(*, state: str, blocking_reasons: list[str]) -> str:
    reason_set = set(blocking_reasons)

    if "artifact_chain_gap" in reason_set:
        return "review_artifact_chain"
    if "missing_winner" in reason_set:
        return "create_winner"
    if "missing_sku_task" in reason_set:
        return "create_sku_task"
    if any(reason.startswith("missing_asset:") for reason in blocking_reasons):
        return "build_assets"
    if any(reason.startswith("missing_packet:") for reason in blocking_reasons):
        return "build_publish_packet"
    if state == "publish_ready":
        return "publish"
    return "inspect"



def build_operator_summary(
    *,
    state: str,
    slug: str | None,
    blocking_reasons: list[str],
    next_action: str,
) -> str:
    base = f"{state}"
    if slug:
        base = f"{base} :: {slug}"
    if blocking_reasons:
        return f"{base} :: next={next_action} :: blockers={', '.join(blocking_reasons[:4])}"
    return f"{base} :: next={next_action} :: clear"



def priority_rank(priority: str) -> int:
    order = {
        "urgent": 0,
        "review": 1,
        "high": 2,
        "normal": 3,
        "low": 4,
    }
    return order.get(priority, 9)



def state_rank(state: str) -> int:
    order = {
        "publish_ready": 0,
        "listing_ready": 1,
        "asset_ready": 2,
        "sku_ready": 3,
        "winner_ready": 4,
        "validated": 5,
        "published": 6,
        "observed": 7,
        "iterated": 8,
    }
    return order.get(state, 9)



def build_compact_summary(*, items: list[dict[str, Any]], state_counts: dict[str, int], priority_counts: dict[str, int], blocking_reason_counts: dict[str, int]) -> dict[str, Any]:
    next_action_counts: Counter[str] = Counter()
    actionable_items = []

    for item in items:
        next_action_counts[item["next_action"]] += 1
        actionable_items.append(
            {
                "niche_id": item["niche_id"],
                "slug": item["slug"],
                "current_state": item["current_state"],
                "queue_priority": item["queue_priority"],
                "next_action": item["next_action"],
                "blocking_reasons": item["blocking_reasons"],
                "operator_summary": item["operator_summary"],
            }
        )

    actionable_items.sort(
        key=lambda item: (
            priority_rank(item["queue_priority"]),
            state_rank(item["current_state"]),
            item["next_action"],
            item["slug"] or item["niche_id"],
        )
    )

    return {
        "created_at": now_iso(),
        "summary_version": "phase4_operator_v1",
        "item_count": len(items),
        "state_counts": state_counts,
        "priority_counts": priority_counts,
        "next_action_counts": dict(next_action_counts),
        "top_blocking_reasons": dict(sorted(blocking_reason_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]),
        "actionable_queue_top": actionable_items[:25],
    }



def build_queue_item(validated_path: Path) -> dict[str, Any] | None:
    validated = read_json(validated_path)
    if not validated:
        return None

    niche_id = safe_text(validated.get("niche_id"))
    niche_keyword = safe_text(validated.get("niche_keyword") or validated.get("niche"))
    validation = validated.get("validation") or {}
    winner_path_value = safe_text(validation.get("win_card_path"))
    sku_task_path_value = safe_text(validation.get("sku_task_path"))

    winner = read_json(Path(winner_path_value)) if winner_path_value else None
    sku_task = read_json(Path(sku_task_path_value)) if sku_task_path_value else None

    slug = infer_slug(validated, winner, sku_task)
    assets_ready, asset_files_present, asset_dir = asset_status(slug) if slug else (False, [], READY_TO_PUBLISH_DIR)
    packet_ready, packet_files_present, packet_dir = packet_status(slug) if slug else (False, [], PUBLISH_PACKETS_DIR)

    state = resolve_state(
        has_winner=winner is not None,
        has_sku_task=sku_task is not None,
        assets_ready=assets_ready,
        packet_ready=packet_ready,
    )
    blocking_reasons = derive_blocking_reasons(
        has_winner=winner is not None,
        has_sku_task=sku_task is not None,
        assets_ready=assets_ready,
        packet_ready=packet_ready,
        asset_files_present=asset_files_present,
        packet_files_present=packet_files_present,
    )
    queue_priority = resolve_queue_priority(
        state=state,
        blocking_reasons=blocking_reasons,
        sku_task=sku_task,
    )
    next_action = resolve_next_action(
        state=state,
        blocking_reasons=blocking_reasons,
    )

    return {
        "niche_id": niche_id,
        "niche_keyword": niche_keyword,
        "vertical": safe_text(validated.get("vertical")),
        "batch_id": safe_text(validated.get("batch_id") or validation.get("batch_id")),
        "validation_status": safe_text(validated.get("status") or validation.get("status")),
        "decision_type": safe_text(validated.get("decision_type") or validation.get("decision_type")),
        "reason": safe_text(validated.get("reason") or validation.get("reason")),
        "fms_score": validated.get("fms_score"),
        "slug": slug,
        "current_state": state,
        "queue_priority": queue_priority,
        "next_action": next_action,
        "blocking_reasons": blocking_reasons,
        "operator_summary": build_operator_summary(
            state=state,
            slug=slug,
            blocking_reasons=blocking_reasons,
            next_action=next_action,
        ),
        "paths": {
            "validated": str(validated_path),
            "winner": winner_path_value or None,
            "sku_task": sku_task_path_value or None,
            "asset_dir": str(asset_dir) if slug else None,
            "packet_dir": str(packet_dir) if slug else None,
        },
        "artifact_presence": {
            "winner": winner is not None,
            "sku_task": sku_task is not None,
            "asset_files_present": asset_files_present,
            "packet_files_present": packet_files_present,
            "assets_ready": assets_ready,
            "packet_ready": packet_ready,
        },
        "pipeline_targets": {
            "target_skus_to_build": (sku_task or {}).get("target_skus_to_build"),
            "priority": safe_text((sku_task or {}).get("priority")),
            "mode": safe_text((sku_task or {}).get("mode")),
        },
    }



def build_queue() -> dict[str, Any]:
    PUBLISH_PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    validated_paths = sorted(VALIDATED_DIR.glob("*.json"))
    items = [item for item in (build_queue_item(path) for path in validated_paths) if item is not None]

    state_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    blocking_reason_counts: Counter[str] = Counter()

    for item in items:
        state = item["current_state"]
        state_counts[state] = state_counts.get(state, 0) + 1

        priority = item["queue_priority"]
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

        for reason in item["blocking_reasons"]:
            blocking_reason_counts[reason] += 1

    items.sort(
        key=lambda item: (
            priority_rank(item["queue_priority"]),
            state_rank(item["current_state"]),
            item["next_action"],
            item["slug"] or item["niche_id"],
        )
    )

    queue = {
        "created_at": now_iso(),
        "queue_version": "phase4_v2",
        "source_roots": {
            "validated": str(VALIDATED_DIR),
            "winners": str(WINNERS_DIR),
            "sku_tasks": str(SKU_TASKS_DIR),
            "ready_to_publish": str(READY_TO_PUBLISH_DIR),
            "publish_packets": str(PUBLISH_PACKETS_DIR),
        },
        "item_count": len(items),
        "state_counts": state_counts,
        "priority_counts": priority_counts,
        "blocking_reason_counts": dict(blocking_reason_counts),
        "items": items,
    }
    summary = build_compact_summary(
        items=items,
        state_counts=state_counts,
        priority_counts=priority_counts,
        blocking_reason_counts=dict(blocking_reason_counts),
    )

    OUTPUT_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return queue


if __name__ == "__main__":
    payload = build_queue()
    summary_payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    print(json.dumps({
        "output_path": str(OUTPUT_PATH),
        "summary_path": str(SUMMARY_PATH),
        "queue_version": payload["queue_version"],
        "item_count": payload["item_count"],
        "state_counts": payload["state_counts"],
        "priority_counts": payload["priority_counts"],
        "next_action_counts": summary_payload["next_action_counts"],
        "top_blocking_reasons": summary_payload["top_blocking_reasons"],
    }, ensure_ascii=False, indent=2))
