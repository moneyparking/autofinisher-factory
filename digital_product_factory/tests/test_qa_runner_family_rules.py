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
