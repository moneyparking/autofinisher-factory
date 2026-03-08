from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / 'digital_product_factory' / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import integration_check
from run_product import run_source_path


def _packet_payload(slug: str) -> dict:
    return {
        'packet_version': 'v1',
        'packet_id': 'x',
        'product_slug': slug,
        'product_kind': 'spreadsheet',
        'product_family': 'budget_sheet_base',
        'channel': 'etsy',
        'title': 'x',
        'description': 'x',
        'tags': ['x'],
        'category': 'x',
        'price_anchor': 1,
        'format_hint': 'x',
        'artifacts': {
            'deliverable_path': 'x',
            'preview_path': 'x',
            'master_path': 'x',
            'mockup_path': 'x',
            'seo_path': 'x',
            'source_csv_path': 'x',
        },
        'source_provenance': {'niche_id': 'x', 'winner_path': '', 'sku_task_path': ''},
        'digital_product_spec_path': 'x',
        'artifact_manifest_path': 'x',
        'listing_title': 'x',
        'buyer_promise': 'x',
        'short_description': 'x',
        'long_description': 'x',
        'feature_bullets': [],
        'benefit_bullets': [],
        'deliverable_files': ['x'],
        'preview_files': [],
        'manual_steps': [],
        'review_checks': [],
        'publish_status': 'draft',
    }


def _write_artifacts(base_dir: Path, slug: str) -> None:
    slug_dir = base_dir / slug
    slug_dir.mkdir(parents=True)
    (slug_dir / 'digital_product_spec.json').write_text(json.dumps({'product_slug': slug}), encoding='utf-8')
    (slug_dir / 'artifact_manifest.json').write_text(
        json.dumps({'manifest_version': 'v1', 'product_slug': slug, 'product_spec_path': 'x', 'build_status': 'ready', 'artifacts': [], 'completeness': {}, 'qa': {}}),
        encoding='utf-8',
    )
    (slug_dir / 'listing_packet_etsy.json').write_text(json.dumps(_packet_payload(slug)), encoding='utf-8')


def test_integration_check_resolves_real_output_slug() -> None:
    config = integration_check.load_canonical_config()
    case = config['cases'][2]
    slug = run_source_path(niche_id=case['niche_id'], winner_path=None, sku_task_path=None, product_kind=case['product_kind'])
    assert slug == 'budget-spreadsheet'


def test_integration_check_calls_run_product_with_real_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / 'out'
    slug = 'budget-spreadsheet'
    _write_artifacts(output_dir, slug)
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ['python3', 'scripts/qa_runner.py', slug]:
            return Mock(stdout="{'product_slug': 'budget-spreadsheet', 'checks_passed': True, 'missing_files': [], 'broken_links': 0}\n")
        return Mock(stdout='')

    monkeypatch.setattr(integration_check, 'OUTPUTS_DIR', output_dir)
    monkeypatch.setattr(integration_check, 'SUMMARY_PATH', output_dir / '_integration_summary.json')
    monkeypatch.setattr(integration_check, 'load_canonical_config', lambda: {'cases': [{'niche_id': 'budget_spreadsheet_v1', 'product_kind': 'spreadsheet'}]})
    monkeypatch.setattr(integration_check, 'run_source_path', lambda **kwargs: slug)
    monkeypatch.setattr(integration_check, 'validate_schema', lambda *args, **kwargs: None)
    monkeypatch.setattr(integration_check.subprocess, 'run', _fake_run)
    integration_check.main()
    captured = capsys.readouterr()
    assert 'PASSED' in captured.out
    assert any(cmd[:2] == ['python3', 'scripts/run_product.py'] and '--niche-id' in cmd and '--product-kind' in cmd for cmd in calls)


def test_integration_check_fails_fast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / 'out'
    monkeypatch.setattr(integration_check, 'OUTPUTS_DIR', output_dir)
    monkeypatch.setattr(integration_check, 'SUMMARY_PATH', output_dir / '_integration_summary.json')
    monkeypatch.setattr(integration_check, 'load_canonical_config', lambda: {'cases': [{'niche_id': 'budget_spreadsheet_v1', 'product_kind': 'spreadsheet'}, {'niche_id': 'x', 'product_kind': 'planner'}]})
    monkeypatch.setattr(integration_check, 'run_source_path', lambda **kwargs: 'budget-spreadsheet')
    monkeypatch.setattr(integration_check.subprocess, 'run', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('boom')))
    with pytest.raises(SystemExit):
        integration_check.main()
    summary = json.loads((output_dir / '_integration_summary.json').read_text(encoding='utf-8'))
    assert len(summary) == 1


def test_integration_check_validates_real_schema_paths() -> None:
    assert integration_check.SCHEMA_SPEC.name == 'digital_product_spec.schema.json'
    assert integration_check.SCHEMA_MANIFEST.name == 'artifact_manifest.schema.json'
    assert integration_check.SCHEMA_PACKET.name == 'listing_packet.schema.json'


def test_integration_check_writes_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_dir = tmp_path / 'out'
    slug = 'budget-spreadsheet'
    _write_artifacts(output_dir, slug)
    monkeypatch.setattr(integration_check, 'OUTPUTS_DIR', output_dir)
    monkeypatch.setattr(integration_check, 'SUMMARY_PATH', output_dir / '_integration_summary.json')
    monkeypatch.setattr(integration_check, 'load_canonical_config', lambda: {'cases': [{'niche_id': 'budget_spreadsheet_v1', 'product_kind': 'spreadsheet'}]})
    monkeypatch.setattr(integration_check, 'run_source_path', lambda **kwargs: slug)
    monkeypatch.setattr(integration_check, 'validate_schema', lambda *args, **kwargs: None)
    monkeypatch.setattr(integration_check.subprocess, 'run', lambda cmd, **kwargs: Mock(stdout="{'product_slug': 'budget-spreadsheet', 'checks_passed': True, 'missing_files': [], 'broken_links': 0}\n") if cmd[:3] == ['python3', 'scripts/qa_runner.py', slug] else Mock(stdout=''))
    integration_check.main()
    summary = json.loads((output_dir / '_integration_summary.json').read_text(encoding='utf-8'))
    assert summary[slug]['status'] == 'PASSED'
