#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, '/home/agent/autofinisher-factory')

import youtube_intelligence_orchestrator as yio

BASE_DIR = Path('/home/agent/autofinisher-factory')
OUTPUT_DIR = BASE_DIR / 'youtube_output'
CONTROL_VIDEO_IDS = ['AC1zd_TTVf0', 'sUuA2_k9g18']


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    results: list[dict[str, Any]] = []
    for video_id in CONTROL_VIDEO_IDS:
        out_dir = OUTPUT_DIR / video_id
        validated = read_json(out_dir / 'validated_ideas.json')
        items = validated.get('items') or []
        spec = yio.build_digital_bundle_specs(video_id, items)
        smoke_path = out_dir / 'digital_bundle_spec.smoke.json'
        canonical_path = out_dir / 'digital_bundle_spec.json'
        write_json(smoke_path, spec)
        if not canonical_path.exists():
            write_json(canonical_path, spec)
        bundle_specs = spec.get('bundle_specs') or []
        results.append({
            'video_id': video_id,
            'items_count': len(items),
            'bundle_spec_count': spec.get('bundle_spec_count'),
            'smoke_file': str(smoke_path),
            'canonical_file': str(canonical_path),
            'first_bundle_keys': sorted((bundle_specs[0].keys()) if bundle_specs else []),
            'top_keys': sorted(spec.keys()),
        })
    report = {
        'control_video_count': len(CONTROL_VIDEO_IDS),
        'results': results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
