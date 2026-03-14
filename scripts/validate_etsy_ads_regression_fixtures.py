#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path('/home/agent/autofinisher-factory')
FIXTURE_ROOT = BASE_DIR / 'fixtures' / 'regression' / 'etsy_ads_cluster_v1'
VIDEO_FIXTURE_DIR = FIXTURE_ROOT / 'videos'
OUTPUT_DIR = BASE_DIR / 'youtube_output'
WEDGE_DIR = BASE_DIR / 'wedge_outputs'

ALLOWED_SUB_ORIGINS = {
    'sub_wedge_from_transcript',
    'sub_wedge_backfill_from_parent',
}
ALLOWED_EVIDENCE_CONFIDENCE = {'medium', 'low'}
REQUIRED_TOP_KEYS = {'generated_at', 'video_id', 'bundle_spec_count', 'bundle_specs'}

STATUS_PASS = 'pass'
STATUS_TARGET_FAIL = 'target_fail'
STATUS_V1_FAIL = 'v1_fail'
STATUS_HARD_FAIL = 'hard_fail'

TARGET_FMS_FLOOR = 68.5
V1_FMS_FLOOR = 67.0
TARGET_MIN_SUB_WEDGES = 3
V1_MIN_SUB_WEDGES = 2
TARGET_MIN_BUNDLES = 3
V1_MIN_BUNDLES = 2
TARGET_QUOTE_MAX_CHARS = 280
TARGET_QUOTE_MAX_WORDS = 40
V1_QUOTE_MAX_CHARS = 420
V1_QUOTE_MAX_WORDS = 70
TARGET_EVIDENCE_QUOTE_MAX_CHARS = 280
V1_EVIDENCE_QUOTE_MAX_CHARS = 420


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def normalize_slug(value: str | None) -> str:
    value = (value or '').strip().lower().replace('-', '_')
    return '_'.join(part for part in value.split() if part)


def clean_quote(text: str | None) -> str:
    return ' '.join(str(text or '').replace('\n', ' ').split())


def fail(errors: list[str], video_id: str, message: str) -> None:
    errors.append(f'{video_id}: {message}')


def append_floor_breach(
    *,
    value: float | int,
    v1_floor: float | int,
    target_floor: float | int,
    v1_message: str,
    target_message: str,
    v1_breaches: list[str],
    target_breaches: list[str],
) -> None:
    if value < v1_floor:
        v1_breaches.append(v1_message)
    elif value < target_floor:
        target_breaches.append(target_message)


def validate_video_fixture(fixture: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    video_id = fixture['video_id']
    out_dir = OUTPUT_DIR / video_id
    wedge_dir = WEDGE_DIR / video_id

    hard_errors: list[str] = []
    v1_breaches: list[str] = []
    target_breaches: list[str] = []

    try:
        quality = read_json(out_dir / 'quality_gate.json')
        parent = read_json(wedge_dir / 'parent_wedge.json')
        sub_wedges = read_json(wedge_dir / 'sub_wedges.json')
        validated = read_json(out_dir / 'validated_ideas.json')
        bundle_spec = read_json(out_dir / 'digital_bundle_spec.json')
    except Exception as exc:
        message = f'{video_id}: io_or_parse_error: {exc}'
        errors.append(message)
        return {
            'video_id': video_id,
            'status': STATUS_HARD_FAIL,
            'hard_errors': [f'io_or_parse_error: {exc}'],
            'v1_breaches': [],
            'target_breaches': [],
            'metrics': {},
        }

    validated_items = validated.get('items') or []
    bundle_specs = bundle_spec.get('bundle_specs') or []
    expected = fixture['expected_contract']
    v1_floor = fixture.get('v1_floor') or {}

    q = expected['quality_gate']
    q_v1 = v1_floor.get('quality_gate') or {}
    if quality.get('passed') is not q['passed']:
        hard_errors.append(f"quality_gate passed != {q['passed']}")
    if quality.get('wedge_mode') is not q['wedge_mode']:
        hard_errors.append(f"quality_gate wedge_mode != {q['wedge_mode']}")
    if int(quality.get('min_ideas', -1)) != q['min_ideas_exact']:
        hard_errors.append('min_ideas drift')
    if float(quality.get('min_fms', -1.0)) != q['min_fms_exact']:
        hard_errors.append('min_fms drift')
    if float(quality.get('min_bundle_power', -1.0)) != q['min_bundle_power_exact']:
        hard_errors.append('min_bundle_power drift')

    idea_count = int(quality.get('idea_count', 0) or 0)
    top_fms_score = float(quality.get('top_fms_score', 0.0) or 0.0)
    top_bundle_power = float(quality.get('top_bundle_power', 0.0) or 0.0)

    if idea_count < q_v1.get('idea_count_min', q['idea_count_min']):
        v1_breaches.append('idea_count_below_v1_floor')
    elif idea_count < q['idea_count_min']:
        target_breaches.append('idea_count_below_target_floor')

    append_floor_breach(
        value=top_fms_score,
        v1_floor=max(V1_FMS_FLOOR, float(q_v1.get('top_fms_score_min', V1_FMS_FLOOR) or 0.0)),
        target_floor=max(TARGET_FMS_FLOOR, float(q.get('top_fms_score_min', TARGET_FMS_FLOOR) or 0.0)),
        v1_message='top_fms_below_v1_floor',
        target_message='top_fms_below_target_floor',
        v1_breaches=v1_breaches,
        target_breaches=target_breaches,
    )
    append_floor_breach(
        value=top_bundle_power,
        v1_floor=float(q_v1.get('top_bundle_power_min', q['top_bundle_power_min']) or 0.0),
        target_floor=float(q.get('top_bundle_power_min', 0.0) or 0.0),
        v1_message='top_bundle_power_below_v1_floor',
        target_message='top_bundle_power_below_target_floor',
        v1_breaches=v1_breaches,
        target_breaches=target_breaches,
    )

    pw = expected['parent_wedge']
    if parent.get('domain') != pw['domain_exact']:
        hard_errors.append('parent_wedge domain drift')
    if parent.get('ads_context_confirmed') is not pw['ads_context_confirmed_exact']:
        hard_errors.append('parent_wedge ads_context_confirmed drift')
    if parent.get('origin') != pw['origin_exact']:
        hard_errors.append('parent_wedge origin drift')

    sw = expected['sub_wedges']
    sw_v1 = v1_floor.get('sub_wedges') or {}
    distinct_ids = sorted({normalize_slug(item.get('id') or item.get('wedge')) for item in sub_wedges if normalize_slug(item.get('id') or item.get('wedge'))})
    distinct_sub_wedge_count = len(distinct_ids)
    append_floor_breach(
        value=distinct_sub_wedge_count,
        v1_floor=max(V1_MIN_SUB_WEDGES, int(sw_v1.get('distinct_count_min', V1_MIN_SUB_WEDGES) or 0)),
        target_floor=max(TARGET_MIN_SUB_WEDGES, int(sw.get('distinct_count_min', TARGET_MIN_SUB_WEDGES) or 0)),
        v1_message='sub_wedges_below_v1_floor',
        target_message='sub_wedges_below_target_floor',
        v1_breaches=v1_breaches,
        target_breaches=target_breaches,
    )
    transcript_native = 0
    max_sub_quote_chars = 0
    max_sub_quote_words = 0
    for item in sub_wedges:
        if item.get('domain') != 'etsy_ads':
            hard_errors.append('sub_wedge domain drift')
        if item.get('ads_context_confirmed') is not True:
            hard_errors.append('sub_wedge ads_context_confirmed drift')
        if item.get('primary_channel') != 'etsy':
            hard_errors.append('sub_wedge primary_channel drift')
        if item.get('secondary_channel') != 'gumroad':
            hard_errors.append('sub_wedge secondary_channel drift')
        if item.get('claim_verification_status') != 'unverified':
            hard_errors.append('sub_wedge claim_verification_status drift')
        if item.get('origin') not in ALLOWED_SUB_ORIGINS:
            hard_errors.append('sub_wedge origin invalid')
        if item.get('source_type') not in ALLOWED_SUB_ORIGINS:
            hard_errors.append('sub_wedge source_type invalid')
        if item.get('evidence_confidence') not in ALLOWED_EVIDENCE_CONFIDENCE:
            hard_errors.append('sub_wedge evidence_confidence invalid')
        quote = clean_quote(item.get('quote'))
        max_sub_quote_chars = max(max_sub_quote_chars, len(quote))
        max_sub_quote_words = max(max_sub_quote_words, len(quote.split()))
        if len(quote) > max(V1_QUOTE_MAX_CHARS, int(sw_v1.get('quote_max_chars', V1_QUOTE_MAX_CHARS) or 0)):
            v1_breaches.append('sub_wedge_quote_too_long_v1')
        elif len(quote) > min(TARGET_QUOTE_MAX_CHARS, int(sw.get('quote_max_chars', TARGET_QUOTE_MAX_CHARS) or TARGET_QUOTE_MAX_CHARS)):
            target_breaches.append('sub_wedge_quote_too_long_target')
        if len(quote.split()) > max(V1_QUOTE_MAX_WORDS, int(sw_v1.get('quote_max_words', V1_QUOTE_MAX_WORDS) or 0)):
            v1_breaches.append('sub_wedge_quote_word_count_too_high_v1')
        elif len(quote.split()) > min(TARGET_QUOTE_MAX_WORDS, int(sw.get('quote_max_words', TARGET_QUOTE_MAX_WORDS) or TARGET_QUOTE_MAX_WORDS)):
            target_breaches.append('sub_wedge_quote_word_count_too_high_target')
        if item.get('origin') == 'sub_wedge_from_transcript':
            transcript_native += 1
    if sw['at_least_one_transcript_native'] and transcript_native < 1:
        hard_errors.append('no transcript-native sub_wedge present')

    vi = expected['validated_ideas']
    vi_v1 = v1_floor.get('validated_ideas') or {}
    if len(validated_items) < int(vi_v1.get('item_count_min', vi['item_count_min']) or 0):
        v1_breaches.append('validated_item_count_below_v1_floor')
    elif len(validated_items) < vi['item_count_min']:
        target_breaches.append('validated_item_count_below_target_floor')
    ads_specific = 0
    top3_ads_specific = True
    top5_non_generic = True
    distinct_canonical = set()
    for idx, item in enumerate(validated_items):
        joined = ' '.join(str(item.get(k, '')) for k in ('title', 'wedge', 'framework', 'niche_query', 'etsy_keyword')).lower()
        is_ads = any(token in joined for token in ('etsy ads', 'roas', 'profitability', 'testing', 'listing', 'ads', 'tacos', 'ad spend'))
        is_generic = any(token in joined for token in ('planner', 'life planner', 'notion template', 'productivity planner', 'business planner'))
        if is_ads:
            ads_specific += 1
        if idx < 3 and not is_ads:
            top3_ads_specific = False
        if idx < 5 and is_generic:
            top5_non_generic = False
        slug = normalize_slug(item.get('wedge'))
        if 'break' in joined and 'roas' in joined:
            distinct_canonical.add('etsy_break_even_roas_calculator')
        elif 'margin' in joined and ('guardrail' in joined or 'profit' in joined):
            distinct_canonical.add('etsy_ads_margin_guardrail_toolkit')
        elif 'testing' in joined or 'experiment' in joined:
            distinct_canonical.add('etsy_ads_testing_tracker')
        elif 'listing' in joined and ('decision' in joined or 'pause' in joined or 'scale' in joined):
            distinct_canonical.add('etsy_listing_level_ad_decision_system')
        elif 'profitability' in joined or 'ads dashboard' in joined or 'reporting' in joined or slug == 'etsy_ads_profitability_system':
            distinct_canonical.add('etsy_ads_profitability_system')
    ratio = ads_specific / len(validated_items) if validated_items else 0.0
    if ratio < float(vi_v1.get('ads_specific_ratio_min', vi['ads_specific_ratio_min']) or 0.0):
        v1_breaches.append('ads_specific_ratio_below_v1_floor')
    elif ratio < float(vi['ads_specific_ratio_min'] or 0.0):
        target_breaches.append('ads_specific_ratio_below_target_floor')
    distinct_canonical_count = len(distinct_canonical)
    append_floor_breach(
        value=distinct_canonical_count,
        v1_floor=int(vi_v1.get('distinct_canonical_sub_wedges_min', V1_MIN_SUB_WEDGES) or 0),
        target_floor=int(vi['distinct_canonical_sub_wedges_min'] or 0),
        v1_message='distinct_canonical_validated_ideas_below_v1_floor',
        target_message='distinct_canonical_validated_ideas_below_target_floor',
        v1_breaches=v1_breaches,
        target_breaches=target_breaches,
    )
    if top3_ads_specific is not vi['top3_ads_specific_exact']:
        hard_errors.append('top3 ads specificity drift')
    if top5_non_generic is not vi['top5_non_generic_exact']:
        hard_errors.append('top5 generic drift')

    ds = expected['digital_bundle_spec']
    ds_v1 = v1_floor.get('digital_bundle_spec') or {}
    if not REQUIRED_TOP_KEYS.issubset(bundle_spec.keys()):
        hard_errors.append('bundle spec top-level keys missing')
    bundle_spec_count = len(bundle_specs)
    append_floor_breach(
        value=bundle_spec_count,
        v1_floor=max(V1_MIN_BUNDLES, int(ds_v1.get('bundle_spec_count_min', V1_MIN_BUNDLES) or 0)),
        target_floor=max(TARGET_MIN_BUNDLES, int(ds.get('bundle_spec_count_min', TARGET_MIN_BUNDLES) or 0)),
        v1_message='bundle_spec_count_below_v1_floor',
        target_message='bundle_spec_count_below_target_floor',
        v1_breaches=v1_breaches,
        target_breaches=target_breaches,
    )
    max_bundle_evidence_quote_chars = 0
    for item in bundle_specs:
        if not set(ds['required_bundle_keys']).issubset(item.keys()):
            hard_errors.append('bundle spec required keys missing')
            continue
        if len(item.get('artifact_stack') or []) < ds['artifact_stack_len_min']:
            hard_errors.append('artifact_stack too short')
        if len(item.get('offer_formats') or []) < ds['offer_formats_len_min']:
            hard_errors.append('offer_formats too short')
        if len(item.get('sku_ladder') or []) < ds['sku_ladder_len_min']:
            hard_errors.append('sku_ladder too short')
        if len(item.get('factory_tasks') or []) < ds['factory_tasks_len_min']:
            hard_errors.append('factory_tasks too short')
        prices = item.get('price_ladder') or []
        if prices != sorted(prices):
            hard_errors.append('price_ladder not sorted')
        if any((not isinstance(price, (int, float))) or price <= 0 for price in prices):
            hard_errors.append('price_ladder contains non-positive values')
        if item.get('primary_channel') != 'etsy':
            hard_errors.append('bundle spec primary_channel drift')
        if item.get('secondary_channel') != 'gumroad':
            hard_errors.append('bundle spec secondary_channel drift')
        evidence = item.get('evidence') or {}
        evidence_quote_len = len(clean_quote(evidence.get('source_quote')))
        max_bundle_evidence_quote_chars = max(max_bundle_evidence_quote_chars, evidence_quote_len)
        if evidence_quote_len > max(V1_EVIDENCE_QUOTE_MAX_CHARS, int(ds_v1.get('evidence_quote_max_chars', V1_EVIDENCE_QUOTE_MAX_CHARS) or 0)):
            v1_breaches.append('bundle_spec_evidence_quote_too_long_v1')
        elif evidence_quote_len > min(TARGET_EVIDENCE_QUOTE_MAX_CHARS, int(ds.get('evidence_quote_max_chars', TARGET_EVIDENCE_QUOTE_MAX_CHARS) or TARGET_EVIDENCE_QUOTE_MAX_CHARS)):
            target_breaches.append('bundle_spec_evidence_quote_too_long_target')

    metrics = {
        'idea_count': idea_count,
        'top_fms_score': top_fms_score,
        'top_bundle_power': top_bundle_power,
        'distinct_sub_wedge_count': distinct_sub_wedge_count,
        'transcript_native_sub_wedge_count': transcript_native,
        'max_sub_wedge_quote_chars': max_sub_quote_chars,
        'max_sub_wedge_quote_words': max_sub_quote_words,
        'validated_item_count': len(validated_items),
        'ads_specific_ratio': round(ratio, 4),
        'distinct_canonical_validated_ideas': distinct_canonical_count,
        'bundle_spec_count': bundle_spec_count,
        'max_bundle_evidence_quote_chars': max_bundle_evidence_quote_chars,
    }

    hard_errors = sorted(set(hard_errors))
    v1_breaches = sorted(set(v1_breaches))
    target_breaches = sorted(set(target_breaches))

    if hard_errors:
        status = STATUS_HARD_FAIL
        for message in hard_errors:
            fail(errors, video_id, message)
    elif v1_breaches:
        status = STATUS_V1_FAIL
        for message in v1_breaches:
            fail(errors, video_id, message)
    elif target_breaches:
        status = STATUS_TARGET_FAIL
    else:
        status = STATUS_PASS

    return {
        'video_id': video_id,
        'status': status,
        'hard_errors': hard_errors,
        'v1_breaches': v1_breaches,
        'target_breaches': target_breaches,
        'metrics': metrics,
        'quality_gate': {
            'idea_count': quality.get('idea_count'),
            'top_fms_score': quality.get('top_fms_score'),
            'top_bundle_power': quality.get('top_bundle_power'),
        },
        'sub_wedges': {
            'distinct_count': distinct_sub_wedge_count,
            'transcript_native_count': transcript_native,
        },
        'validated_ideas': {
            'item_count': len(validated_items),
            'ads_specific_ratio': round(ratio, 4),
            'distinct_canonical_sub_wedges': distinct_canonical_count,
        },
        'digital_bundle_spec': {
            'bundle_spec_count': bundle_spec_count,
        },
    }


def main() -> int:
    inputs = read_json(FIXTURE_ROOT / 'inputs.json')
    cluster_manifest = read_json(FIXTURE_ROOT / 'cluster_manifest.json')
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    for entry in inputs['videos']:
        fixture = read_json(VIDEO_FIXTURE_DIR / f"{entry['video_id']}.json")
        results.append(validate_video_fixture(fixture, errors))

    batch_video_ids = {entry['video_id'] for entry in inputs['videos'] if entry['role'] == 'batch'}
    batch_results = [item for item in results if item['video_id'] in batch_video_ids]

    status_buckets = {
        STATUS_HARD_FAIL: [item['video_id'] for item in batch_results if item['status'] == STATUS_HARD_FAIL],
        STATUS_V1_FAIL: [item['video_id'] for item in batch_results if item['status'] == STATUS_V1_FAIL],
        STATUS_TARGET_FAIL: [item['video_id'] for item in batch_results if item['status'] == STATUS_TARGET_FAIL],
        STATUS_PASS: [item['video_id'] for item in batch_results if item['status'] == STATUS_PASS],
    }

    pass_count = len(status_buckets[STATUS_PASS])
    target_fail_count = len(status_buckets[STATUS_TARGET_FAIL])
    v1_fail_count = len(status_buckets[STATUS_V1_FAIL])
    hard_fail_count = len(status_buckets[STATUS_HARD_FAIL])

    cluster_contract = cluster_manifest['cluster_contract']
    cluster_v1_floor = cluster_manifest.get('cluster_v1_floor') or {}
    if min((item['quality_gate']['idea_count'] or 0 for item in batch_results), default=0) < cluster_v1_floor.get('min_idea_count_across_cluster', cluster_contract['min_idea_count_across_cluster']):
        errors.append('cluster: min idea count below v1 floor')
    if min((float(item['quality_gate']['top_fms_score'] or 0.0) for item in batch_results), default=0.0) < max(V1_FMS_FLOOR, float(cluster_v1_floor.get('min_top_fms_across_cluster', V1_FMS_FLOOR) or 0.0)):
        errors.append('cluster: min top fms below v1 floor')
    if min((float(item['quality_gate']['top_bundle_power'] or 0.0) for item in batch_results), default=0.0) < cluster_v1_floor.get('min_top_bundle_power_across_cluster', cluster_contract['min_top_bundle_power_across_cluster']):
        errors.append('cluster: min top bundle power below v1 floor')
    if min((item['sub_wedges']['distinct_count'] or 0 for item in batch_results), default=0) < cluster_v1_floor.get('min_distinct_sub_wedges_across_cluster', V1_MIN_SUB_WEDGES):
        errors.append('cluster: min distinct sub_wedges below v1 floor')
    if min((item['digital_bundle_spec']['bundle_spec_count'] or 0 for item in batch_results), default=0) < 1:
        errors.append('cluster: missing digital bundle specs in batch')

    report = {
        'fixture_root': str(FIXTURE_ROOT),
        'video_count_checked': len(results),
        'batch_video_count_checked': len(batch_results),
        'hard_fail_count': hard_fail_count,
        'v1_fail_count': v1_fail_count,
        'target_fail_count': target_fail_count,
        'pass_count': pass_count,
        'v1_green_video_ids': sorted(status_buckets[STATUS_TARGET_FAIL] + status_buckets[STATUS_PASS]),
        'target_only_video_ids': sorted(status_buckets[STATUS_TARGET_FAIL]),
        'pass_video_ids': sorted(status_buckets[STATUS_PASS]),
        'v1_fail_video_ids': sorted(status_buckets[STATUS_V1_FAIL]),
        'hard_fail_video_ids': sorted(status_buckets[STATUS_HARD_FAIL]),
        'errors': errors,
        'results': results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if hard_fail_count or v1_fail_count or errors else 0



if __name__ == '__main__':
    raise SystemExit(main())
