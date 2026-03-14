#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, '/home/agent/autofinisher-factory')

import youtube_intelligence_orchestrator as yio

BASE_DIR = Path('/home/agent/autofinisher-factory')
FIXTURE_ROOT = BASE_DIR / 'fixtures' / 'regression' / 'etsy_ads_cluster_v1'
VIDEO_FIXTURE_DIR = FIXTURE_ROOT / 'videos'
OUTPUT_DIR = BASE_DIR / 'youtube_output'
WEDGE_DIR = BASE_DIR / 'wedge_outputs'
TRANSCRIPTS_DIR = BASE_DIR / 'transcripts'

BATCH_VIDEO_IDS = [
    'ztcfOv8uv6U',
    'WNQgc8NzLYc',
    'xLmnJYWHQ34',
    'D107mfmR27M',
    '5vXGrgql6Jg',
    'SeULgy3Dgi0',
    '0Xrx-OXQmd4',
    '9-us_15_Z9I',
    '8Jtp2WDrU3M',
    'p5j8pYbeUJs',
]

CONTROL_VIDEO_IDS = [
    'AC1zd_TTVf0',
    'sUuA2_k9g18',
]

CATALOG = {
    'etsy_ads_profitability_system',
    'etsy_break_even_roas_calculator',
    'etsy_ads_testing_tracker',
    'etsy_ads_margin_guardrail_toolkit',
    'etsy_listing_level_ad_decision_system',
}

ALLOWED_SUB_ORIGINS = {
    'sub_wedge_from_transcript',
    'sub_wedge_backfill_from_parent',
}

ALLOWED_EVIDENCE_CONFIDENCE = {'medium', 'low'}

REQUIRED_BUNDLE_KEYS = {
    'video_id',
    'sub_wedge_id',
    'buyer',
    'pain',
    'outcome',
    'promise',
    'wedge',
    'artifact_stack',
    'offer_formats',
    'sku_ladder',
    'price_ladder',
    'primary_channel',
    'secondary_channel',
    'factory_tasks',
    'launch_assets',
    'bundle_power',
    'top_fms_score',
    'evidence',
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def normalize_slug(value: str | None) -> str:
    return yio.slugify(yio.normalize_space(value or '')).replace('-', '_')


def normalize_quote(text: str | None) -> str:
    return yio.clean_evidence_quote_text(text or '')


def find_canonical_sub_wedge(item: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    for key in ('sub_wedge_id', 'wedge', 'framework', 'title', 'niche_query', 'etsy_keyword'):
        value = item.get(key)
        if value:
            candidates.append(str(value))
    joined = ' '.join(candidates).lower()
    if 'break' in joined and 'roas' in joined:
        return 'etsy_break_even_roas_calculator'
    if 'margin' in joined and ('guardrail' in joined or 'profit' in joined):
        return 'etsy_ads_margin_guardrail_toolkit'
    if 'testing' in joined or 'experiment' in joined:
        return 'etsy_ads_testing_tracker'
    if 'listing' in joined and ('decision' in joined or 'pause' in joined or 'scale' in joined):
        return 'etsy_listing_level_ad_decision_system'
    if 'profitability' in joined or 'ads dashboard' in joined or 'reporting' in joined:
        return 'etsy_ads_profitability_system'
    slug = normalize_slug(item.get('sub_wedge_id') or item.get('wedge'))
    return slug if slug in CATALOG else None


def is_ads_specific(item: dict[str, Any]) -> bool:
    if find_canonical_sub_wedge(item):
        return True
    joined = ' '.join(str(item.get(k, '')) for k in ('title', 'wedge', 'framework', 'niche_query', 'etsy_keyword')).lower()
    tokens = ('etsy ads', 'roas', 'profitability', 'testing', 'listing', 'ads', 'tacos', 'ad spend')
    return any(token in joined for token in tokens)


def is_non_generic(item: dict[str, Any]) -> bool:
    joined = ' '.join(str(item.get(k, '')) for k in ('title', 'wedge', 'framework', 'niche_query')).lower()
    generic = ('planner', 'life planner', 'notion template', 'generic etsy', 'productivity planner', 'business planner')
    return not any(token in joined for token in generic)


def ensure_bundle_spec(video_id: str, validated_items: list[dict[str, Any]]) -> tuple[dict[str, Any], bool]:
    path = OUTPUT_DIR / video_id / 'digital_bundle_spec.json'
    if path.exists():
        return read_json(path), False
    spec = yio.build_digital_bundle_specs(video_id, validated_items)
    write_json(path, spec)
    return spec, True


def build_video_fixture(video_id: str, role: str) -> dict[str, Any]:
    quality_gate = read_json(OUTPUT_DIR / video_id / 'quality_gate.json')
    parent_wedge = read_json(WEDGE_DIR / video_id / 'parent_wedge.json')
    sub_wedges = read_json(WEDGE_DIR / video_id / 'sub_wedges.json')
    validated = read_json(OUTPUT_DIR / video_id / 'validated_ideas.json')
    validated_items = validated.get('items') or []
    spec, synthesized = ensure_bundle_spec(video_id, validated_items)

    normalized_sub_ids = sorted({normalize_slug(item.get('id') or item.get('wedge')) for item in sub_wedges if normalize_slug(item.get('id') or item.get('wedge'))})
    distinct_canonical_ideas = sorted({canonical for item in validated_items if (canonical := find_canonical_sub_wedge(item))})
    ads_specific_count = sum(1 for item in validated_items if is_ads_specific(item))
    non_generic_top5 = all(is_non_generic(item) for item in validated_items[:5]) if validated_items else False
    top3_ads_specific = all(is_ads_specific(item) for item in validated_items[:3]) if len(validated_items) >= 3 else False
    sub_quotes = [normalize_quote(item.get('quote')) for item in sub_wedges if normalize_quote(item.get('quote'))]
    sub_quote_char_max = max((len(q) for q in sub_quotes), default=0)
    sub_quote_word_max = max((len(q.split()) for q in sub_quotes), default=0)
    transcript_native_count = sum(1 for item in sub_wedges if item.get('origin') == 'sub_wedge_from_transcript')
    bundle_specs = spec.get('bundle_specs') or []

    return {
        'video_id': video_id,
        'role': role,
        'fixture_version': 'etsy_ads_cluster_v1',
        'expected_contract': {
            'quality_gate': {
                'passed': True,
                'wedge_mode': True,
                'min_ideas_exact': 10,
                'min_fms_exact': 45.0,
                'min_bundle_power_exact': 7.5,
                'idea_count_min': 10,
                'top_fms_score_min': 68.5,
                'top_bundle_power_min': 9.0,
            },
            'parent_wedge': {
                'domain_exact': 'etsy_ads',
                'ads_context_confirmed_exact': True,
                'origin_exact': 'parent_wedge_from_transcript',
            },
            'sub_wedges': {
                'distinct_count_min': 3,
                'canonical_catalog_only': True,
                'at_least_one_transcript_native': True,
                'allowed_origins': sorted(ALLOWED_SUB_ORIGINS),
                'allowed_evidence_confidence': sorted(ALLOWED_EVIDENCE_CONFIDENCE),
                'quote_max_chars': 280,
                'quote_max_words': 40,
            },
            'validated_ideas': {
                'item_count_min': 10,
                'ads_specific_ratio_min': 0.80,
                'distinct_canonical_sub_wedges_min': 3,
                'top3_ads_specific_exact': True,
                'top5_non_generic_exact': True,
            },
            'digital_bundle_spec': {
                'file_required': True,
                'bundle_spec_count_min': 3,
                'artifact_stack_len_min': 3,
                'offer_formats_len_min': 3,
                'sku_ladder_len_min': 3,
                'factory_tasks_len_min': 5,
                'price_ladder_sorted': True,
                'evidence_quote_max_chars': 280,
                'required_bundle_keys': sorted(REQUIRED_BUNDLE_KEYS),
            },
        },
        'v1_floor': {
            'quality_gate': {
                'idea_count_min': 10,
                'top_fms_score_min': 54.75,
                'top_bundle_power_min': 9.0,
            },
            'sub_wedges': {
                'distinct_count_min': 2,
                'quote_max_chars': 420,
                'quote_max_words': 70,
            },
            'validated_ideas': {
                'item_count_min': 10,
                'ads_specific_ratio_min': 0.80,
                'distinct_canonical_sub_wedges_min': 2,
            },
            'digital_bundle_spec': {
                'bundle_spec_count_min': 2,
                'evidence_quote_max_chars': 420,
            },
        },
        'baseline_observed': {
            'quality_gate': {
                'idea_count': quality_gate.get('idea_count'),
                'top_fms_score': quality_gate.get('top_fms_score'),
                'top_bundle_power': quality_gate.get('top_bundle_power'),
                'attempt': quality_gate.get('attempt'),
            },
            'parent_wedge': {
                'domain': parent_wedge.get('domain'),
                'origin': parent_wedge.get('origin'),
                'wedge': parent_wedge.get('wedge'),
            },
            'sub_wedges': {
                'count': len(sub_wedges),
                'distinct_canonical_ids': normalized_sub_ids,
                'transcript_native_count': transcript_native_count,
                'quote_char_max': sub_quote_char_max,
                'quote_word_max': sub_quote_word_max,
            },
            'validated_ideas': {
                'item_count': len(validated_items),
                'ads_specific_ratio': round(ads_specific_count / len(validated_items), 4) if validated_items else 0.0,
                'distinct_canonical_sub_wedges': distinct_canonical_ideas,
                'top3_ads_specific': top3_ads_specific,
                'top5_non_generic': non_generic_top5,
                'top_titles': [item.get('title') for item in validated_items[:5]],
            },
            'digital_bundle_spec': {
                'bundle_spec_count': spec.get('bundle_spec_count'),
                'bundle_spec_ids': [normalize_slug(item.get('sub_wedge_id') or item.get('wedge')) for item in bundle_specs],
                'max_evidence_quote_chars': max((len(normalize_quote((item.get('evidence') or {}).get('source_quote'))) for item in bundle_specs), default=0),
                'synthesized_by_fixture_builder': synthesized,
            },
        },
    }


def build_inputs() -> dict[str, Any]:
    videos: list[dict[str, Any]] = []
    for video_id in BATCH_VIDEO_IDS:
        transcript_path = TRANSCRIPTS_DIR / f'{video_id}.txt'
        videos.append({
            'video_id': video_id,
            'role': 'batch',
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'transcript_file': str(transcript_path.relative_to(BASE_DIR)) if transcript_path.exists() else None,
        })
    for video_id in CONTROL_VIDEO_IDS:
        transcript_path = TRANSCRIPTS_DIR / f'{video_id}.txt'
        videos.append({
            'video_id': video_id,
            'role': 'control',
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'transcript_file': str(transcript_path.relative_to(BASE_DIR)) if transcript_path.exists() else None,
        })
    return {
        'cluster_name': 'etsy_ads_cluster_v1',
        'wedge_mode': True,
        'videos': videos,
    }


def build_cluster_manifest(video_fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    batch_fixtures = [item for item in video_fixtures if item['role'] == 'batch']
    quality = [item['baseline_observed']['quality_gate'] for item in batch_fixtures]
    sub = [item['baseline_observed']['sub_wedges'] for item in batch_fixtures]
    return {
        'cluster_name': 'etsy_ads_cluster_v1',
        'fixture_version': 'v1',
        'video_count': len(batch_fixtures),
        'control_video_count': len([item for item in video_fixtures if item['role'] == 'control']),
        'video_ids': [item['video_id'] for item in batch_fixtures],
        'control_video_ids': [item['video_id'] for item in video_fixtures if item['role'] == 'control'],
        'cluster_contract': {
            'expected_pass_count_exact': len(batch_fixtures),
            'allowed_fail_count_exact': 0,
            'min_idea_count_across_cluster': 10,
            'min_top_fms_across_cluster': 68.5,
            'min_top_bundle_power_across_cluster': 9.0,
            'min_distinct_sub_wedges_across_cluster': 3,
            'digital_bundle_spec_required_for_all': True,
            'domains_only': ['etsy_ads'],
        },
        'cluster_v1_floor': {
            'min_idea_count_across_cluster': 10,
            'min_top_fms_across_cluster': 54.75,
            'min_top_bundle_power_across_cluster': 9.0,
            'min_distinct_sub_wedges_across_cluster': 2,
        },
        'baseline_observed': {
            'target_pass_count': sum(
                1
                for item in batch_fixtures
                if (
                    (item['baseline_observed']['quality_gate'].get('idea_count') or 0) >= 10
                    and float(item['baseline_observed']['quality_gate'].get('top_fms_score') or 0.0) >= 68.5
                    and float(item['baseline_observed']['quality_gate'].get('top_bundle_power') or 0.0) >= 9.0
                    and len(item['baseline_observed']['sub_wedges'].get('distinct_canonical_ids') or []) >= 3
                )
            ),
            'min_idea_count': min((item.get('idea_count', 0) for item in quality), default=0),
            'min_top_fms_score': min((float(item.get('top_fms_score', 0.0) or 0.0) for item in quality), default=0.0),
            'min_top_bundle_power': min((float(item.get('top_bundle_power', 0.0) or 0.0) for item in quality), default=0.0),
            'min_distinct_sub_wedges': min((len(item.get('distinct_canonical_ids') or []) for item in sub), default=0),
        },
    }


def main() -> int:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    VIDEO_FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    inputs = build_inputs()
    write_json(FIXTURE_ROOT / 'inputs.json', inputs)

    fixtures: list[dict[str, Any]] = []
    for entry in inputs['videos']:
        fixture = build_video_fixture(entry['video_id'], entry['role'])
        fixtures.append(fixture)
        write_json(VIDEO_FIXTURE_DIR / f"{entry['video_id']}.json", fixture)

    cluster_manifest = build_cluster_manifest(fixtures)
    write_json(FIXTURE_ROOT / 'cluster_manifest.json', cluster_manifest)

    report = {
        'fixture_root': str(FIXTURE_ROOT),
        'video_fixture_count': len(fixtures),
        'batch_video_count': len(BATCH_VIDEO_IDS),
        'control_video_count': len(CONTROL_VIDEO_IDS),
        'synthesized_specs': [item['video_id'] for item in fixtures if item['baseline_observed']['digital_bundle_spec']['synthesized_by_fixture_builder']],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
