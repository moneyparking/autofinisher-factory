#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import youtube_cluster_automanifest as yca

BASE_DIR = Path('/home/agent/autofinisher-factory')
FIXTURE_NAME = os.getenv('ETSY_ADS_FIXTURE_NAME', 'etsy_ads_cluster_v2').strip() or 'etsy_ads_cluster_v2'
FIXTURE_ROOT = BASE_DIR / 'fixtures' / 'regression' / FIXTURE_NAME
VIDEO_FIXTURE_DIR = FIXTURE_ROOT / 'videos'
OUTPUT_DIR = BASE_DIR / 'youtube_output'
WEDGE_DIR = BASE_DIR / 'wedge_outputs'
DECISION_SUB_WEDGES = {'etsy_listing_level_ad_decision_system'}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')



def ensure_cluster_manifest_autogen() -> None:
    if FIXTURE_NAME != 'etsy_ads_cluster_v2':
        return
    inputs_path = FIXTURE_ROOT / 'inputs.json'
    if not inputs_path.exists():
        return
    inputs = read_json(inputs_path)
    video_entries = inputs.get('videos') or []
    batch_entries = [entry for entry in video_entries if entry.get('role', 'batch') == 'batch']
    video_ids = [entry['video_id'] for entry in batch_entries if entry.get('video_id')]
    if not video_ids:
        return
    yca.generate_automanifest(
        {
            'cluster_id': FIXTURE_NAME,
            'topic_cluster': 'etsy_ads_v2',
            'video_ids': video_ids,
            'language_hint': 'en',
            'default_tier': 'A',
        }
    )


def mean_or_zero(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def median_or_zero(values: list[float]) -> float:
    return round(float(statistics.median(values)), 4) if values else 0.0


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def count_distinct_sub_wedges(sub_wedges: list[dict[str, Any]]) -> int:
    return len({str(item.get('id') or item.get('wedge') or '').strip().lower() for item in sub_wedges if str(item.get('id') or item.get('wedge') or '').strip()})


def has_decision_wedge(sub_wedges: list[dict[str, Any]]) -> bool:
    return any(str(item.get('id') or '').strip().lower() in DECISION_SUB_WEDGES for item in sub_wedges)


def has_transcript_native_decision_wedge(sub_wedges: list[dict[str, Any]]) -> bool:
    return any(
        str(item.get('id') or '').strip().lower() in DECISION_SUB_WEDGES
        and item.get('origin') == 'sub_wedge_from_transcript'
        for item in sub_wedges
    )


def main() -> int:
    ensure_cluster_manifest_autogen()
    inputs = read_json(FIXTURE_ROOT / 'inputs.json')
    cluster_manifest = read_json(FIXTURE_ROOT / 'cluster_manifest.json')
    validator_report = read_json(FIXTURE_ROOT / 'validator_report.json') if (FIXTURE_ROOT / 'validator_report.json').exists() else {}

    video_entries = inputs.get('videos') or []
    batch_video_ids = [entry['video_id'] for entry in video_entries if entry.get('role', 'batch') == 'batch']

    per_video_metrics: list[dict[str, Any]] = []
    top_fms_values: list[float] = []
    bundle_counts: list[int] = []
    sub_wedge_counts: list[int] = []
    decision_video_fms: list[float] = []
    no_decision_video_fms: list[float] = []
    decision_wedge_video_count = 0
    transcript_native_decision_wedge_video_count = 0
    videos_with_3plus_bundles = 0
    videos_with_3plus_sub_wedges = 0

    for video_id in batch_video_ids:
        quality = read_json(OUTPUT_DIR / video_id / 'quality_gate.json')
        sub_wedges = read_json(WEDGE_DIR / video_id / 'sub_wedges.json')
        bundle_spec = read_json(OUTPUT_DIR / video_id / 'digital_bundle_spec.json')
        top_fms_score = safe_float(quality.get('top_fms_score'), 0.0)
        bundle_spec_count = int(bundle_spec.get('bundle_spec_count') or len(bundle_spec.get('bundle_specs') or []))
        distinct_sub_wedge_count = count_distinct_sub_wedges(sub_wedges)
        decision_present = has_decision_wedge(sub_wedges)
        transcript_native_decision_present = has_transcript_native_decision_wedge(sub_wedges)

        top_fms_values.append(top_fms_score)
        bundle_counts.append(bundle_spec_count)
        sub_wedge_counts.append(distinct_sub_wedge_count)

        if decision_present:
            decision_wedge_video_count += 1
            decision_video_fms.append(top_fms_score)
        else:
            no_decision_video_fms.append(top_fms_score)
        if transcript_native_decision_present:
            transcript_native_decision_wedge_video_count += 1
        if bundle_spec_count >= 3:
            videos_with_3plus_bundles += 1
        if distinct_sub_wedge_count >= 3:
            videos_with_3plus_sub_wedges += 1

        per_video_metrics.append(
            {
                'video_id': video_id,
                'top_fms_score': top_fms_score,
                'bundle_spec_count': bundle_spec_count,
                'distinct_sub_wedge_count': distinct_sub_wedge_count,
                'decision_wedge_present': decision_present,
                'transcript_native_decision_wedge_present': transcript_native_decision_present,
            }
        )

    hard_fail_count = int(validator_report.get('hard_fail_count', 0) or 0)
    v1_fail_count = int(validator_report.get('v1_fail_count', 0) or 0)
    target_fail_count = int(validator_report.get('target_fail_count', 0) or 0)
    pass_count = int(validator_report.get('pass_count', 0) or 0)
    video_count = len(batch_video_ids)
    v1_green_count = pass_count + target_fail_count

    payload = {
        'cluster_id': cluster_manifest.get('cluster_name', FIXTURE_NAME),
        'fixture_name': FIXTURE_NAME,
        'video_count': video_count,
        'hard_fail_count': hard_fail_count,
        'v1_fail_count': v1_fail_count,
        'target_fail_count': target_fail_count,
        'pass_count': pass_count,
        'v1_green_count': v1_green_count,
        'v1_pass_ratio': round(v1_green_count / video_count, 4) if video_count else 0.0,
        'target_pass_ratio': round(pass_count / video_count, 4) if video_count else 0.0,
        'decision_wedge_video_count': decision_wedge_video_count,
        'decision_wedge_video_ratio': round(decision_wedge_video_count / video_count, 4) if video_count else 0.0,
        'transcript_native_decision_wedge_video_count': transcript_native_decision_wedge_video_count,
        'transcript_native_decision_wedge_video_ratio': round(transcript_native_decision_wedge_video_count / video_count, 4) if video_count else 0.0,
        'top_fms_min': round(min(top_fms_values), 4) if top_fms_values else 0.0,
        'top_fms_max': round(max(top_fms_values), 4) if top_fms_values else 0.0,
        'top_fms_mean': mean_or_zero(top_fms_values),
        'top_fms_median': median_or_zero(top_fms_values),
        'top_fms_decision_videos_mean': mean_or_zero(decision_video_fms),
        'top_fms_no_decision_videos_mean': mean_or_zero(no_decision_video_fms),
        'avg_bundle_spec_count_per_video': mean_or_zero([float(x) for x in bundle_counts]),
        'median_bundle_spec_count_per_video': median_or_zero([float(x) for x in bundle_counts]),
        'share_videos_with_3plus_bundles': round(videos_with_3plus_bundles / video_count, 4) if video_count else 0.0,
        'avg_distinct_sub_wedge_count_per_video': mean_or_zero([float(x) for x in sub_wedge_counts]),
        'share_videos_with_3plus_sub_wedges': round(videos_with_3plus_sub_wedges / video_count, 4) if video_count else 0.0,
        'videos': per_video_metrics,
    }

    write_json(FIXTURE_ROOT / 'cluster_metrics.json', payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
