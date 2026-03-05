from __future__ import annotations


def test_import_settings() -> None:
    from money_niche_hunter.config.settings import TOP_N, THRESHOLDS, WEIGHTS

    assert TOP_N > 0
    assert THRESHOLDS.min_confidence == "high"
    assert WEIGHTS.fms_score > 0


def test_import_main() -> None:
    import money_niche_hunter.main as main_module

    assert hasattr(main_module, "main")
