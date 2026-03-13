from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_DIR / 'digital_product_factory' / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from qa_runner import run_qa


def test_qa_runner_outputs_valid_json() -> None:
    result = run_qa('missing-slug')
    payload = json.dumps(result)
    parsed = json.loads(payload)
    assert parsed['checks_passed'] is False
    assert parsed['contract_checks_passed'] is False


def test_qa_runner_planner_family_rules() -> None:
    result = run_qa('2026-adhd-digital-planner')
    assert result['product_slug'] == '2026-adhd-digital-planner'
    assert result['contract_checks_passed'] is True
    assert result['checks_passed'] is True


def test_qa_runner_checklist_family_rules() -> None:
    result = run_qa('2026-adhd-digital-planner-checklist')
    assert result['contract_checks_passed'] is True
    assert result['checks_passed'] is True


def test_qa_runner_spreadsheet_family_rules() -> None:
    result = run_qa('budget-spreadsheet')
    assert result['contract_checks_passed'] is True
    assert result['checks_passed'] is True


def test_qa_runner_notion_family_rules() -> None:
    result = run_qa('notion-freelancer-template-crm-client-tracker-business-planner-project-management-notion-companion')
    assert result['contract_checks_passed'] is True
    assert result['checks_passed'] is True


def test_qa_runner_handles_missing_packet_gracefully(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import qa_runner

    product_dir = tmp_path / 'product'
    product_dir.mkdir(parents=True)
    spec = {
        'product_slug': 'product',
        'product_kind': 'spreadsheet',
        'must_have_files': ['deliverable.xlsx', 'preview.pdf'],
        'qa_thresholds': {'must_have_sheets': []},
    }
    manifest = {
        'artifacts': [],
        'completeness': {'required_artifacts_ready': True, 'preview_assets_ready': True},
        'qa': {'broken_links': 0, 'notes': []},
    }
    (product_dir / 'digital_product_spec.json').write_text(json.dumps(spec), encoding='utf-8')
    (product_dir / 'artifact_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (product_dir / 'deliverable.xlsx').write_text('stub', encoding='utf-8')
    (product_dir / 'preview.pdf').write_text('stub', encoding='utf-8')

    monkeypatch.setattr(qa_runner, 'OUTPUTS_DIR', tmp_path)
    result = qa_runner.run_qa('product')
    assert 'listing_packet_missing' in result['notes']
    assert result['checks_passed'] is False



def test_qa_runner_flags_market_readiness_issues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import qa_runner

    product_dir = tmp_path / 'product'
    product_dir.mkdir(parents=True)
    spec = {
        'product_slug': 'product',
        'product_kind': 'spreadsheet',
        'must_have_files': ['deliverable.xlsx', 'preview.pdf'],
        'qa_thresholds': {'must_have_sheets': []},
    }
    manifest = {
        'artifacts': [],
        'completeness': {'required_artifacts_ready': True, 'preview_assets_ready': True},
        'qa': {'broken_links': 0, 'notes': []},
    }
    packet = {
        'title': 'Budget Spreadsheet | Budget Spreadsheet',
        'listing_title': 'Budget Spreadsheet | Budget Spreadsheet',
        'description': 'Buyer receives an Etsy-ready artifact.',
        'description_intro': 'Buyer receives an Etsy-ready artifact.',
        'description_whats_included': 'x',
        'description_how_it_works': 'x',
        'description_what_youll_get': 'x',
        'tags': ['one', 'two'],
        'seo_aeo': {
            'what_is_it': '',
            'who_is_it_for': 'x',
            'what_do_i_get': 'x',
            'how_do_i_use_it': 'x',
            'compatibility': 'x',
        },
        'listing_image_plan': [],
        'listing_image_paths': [],
        'artifacts': {
            'deliverable_path': 'x',
            'preview_path': 'x',
            'master_path': 'x',
            'mockup_path': 'x',
            'seo_path': 'x',
            'source_csv_path': 'x',
            'rendered_listing_html_path': str(product_dir / 'listing_preview.html'),
            'listing_image_plan_path': str(product_dir / 'listing_image_plan.json'),
        },
        'market_readiness': {
            'buyer_facing_copy': False,
            'seo_aeo_complete': False,
            'title_readable': False,
            'tags_ready': False,
            'image_plan_ready': False,
        },
    }
    (product_dir / 'digital_product_spec.json').write_text(json.dumps(spec), encoding='utf-8')
    (product_dir / 'artifact_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (product_dir / 'listing_packet_etsy.json').write_text(json.dumps(packet), encoding='utf-8')
    (product_dir / 'deliverable.xlsx').write_text('stub', encoding='utf-8')
    (product_dir / 'preview.pdf').write_text('stub', encoding='utf-8')

    monkeypatch.setattr(qa_runner, 'OUTPUTS_DIR', tmp_path)
    result = qa_runner.run_qa('product')
    assert result['commercial_checks_passed'] is False
    assert 'listing_title_tautology' in result['notes']
    assert 'listing_tags_count_invalid' in result['notes']
    assert 'listing_image_plan_count_invalid' in result['notes']
    assert 'market_readiness_incomplete' in result['notes']
    assert any(note.startswith('buyer_facing_jargon:') for note in result['notes'])
