from __future__ import annotations

import json
from pathlib import Path

import pytest

from procurement_intelligence.analytics.run_market_concentration import (
    FIGURES,
    load_concentration_config,
    validate_share_math,
)
from procurement_intelligence.extraction.download_ocds import (
    sha256_file,
    sha256_text_file,
)


CONFIG_PATH = Path("config/market_concentration.yml")
REPORT_PATH = Path(
    "reports/concentration/oece_ocds_seace_v3_2026_07_market_concentration.json"
)
MARKDOWN_PATH = Path(
    "reports/concentration/oece_ocds_seace_v3_2026_07_market_concentration.md"
)
DAX_PATH = Path("powerbi/dax/phase11_concentration_measures.dax")


def test_concentration_contract_defines_market_and_eligibility() -> None:
    config = load_concentration_config(CONFIG_PATH)
    settings = config["concentration"]

    assert settings["source_period"] == "2026-07"
    assert settings["market_definition"] == (
        "one governed standard category within one source period"
    )
    assert settings["eligibility"] == {
        "minimum_suppliers": 3,
        "minimum_buyers": 2,
        "minimum_award_items": 5,
        "minimum_attributable_amount_coverage_pct": 95.0,
    }
    assert len(config["datasets"]) == 2


def test_invalid_concentration_threshold_is_rejected(tmp_path: Path) -> None:
    import yaml

    config = load_concentration_config(CONFIG_PATH)
    config["concentration"]["eligibility"]["minimum_suppliers"] = 0
    path = tmp_path / "invalid.yml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match="must be positive"):
        load_concentration_config(path)


def test_share_math_recomputes_hhi() -> None:
    markets = [{"category_key": 1, "hhi": "5000", "supplier_count": 2}]
    shares = [
        {"category_key": 1, "supplier_share_pct": "50"},
        {"category_key": 1, "supplier_share_pct": "50"},
    ]

    result = validate_share_math(markets, shares)

    assert result[0]["share_sum_pct"] == 100.0
    assert result[0]["hhi_python"] == 5000.0
    assert result[0]["status"] == "PASS"


def test_share_math_detects_inconsistent_sql_hhi() -> None:
    markets = [{"category_key": 1, "hhi": "4000", "supplier_count": 2}]
    shares = [
        {"category_key": 1, "supplier_share_pct": "50"},
        {"category_key": 1, "supplier_share_pct": "50"},
    ]

    assert validate_share_math(markets, shares)[0]["status"] == "FAIL"


def test_committed_concentration_evidence_matches_code_and_sql() -> None:
    config = load_concentration_config(CONFIG_PATH)
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["summary"]["status"] == "PASS"
    assert report["summary"]["markets_analyzed"] == 772
    assert report["summary"]["eligible_markets"] == 87
    assert report["summary"]["share_validations_failed"] == 0
    assert report["source"]["config_sha256"] == sha256_text_file(CONFIG_PATH)
    assert report["source"]["runner_sha256"] == sha256_text_file(
        Path("src/procurement_intelligence/analytics/run_market_concentration.py")
    )
    assert report["source"]["dax_catalog_sha256"] == sha256_text_file(DAX_PATH)
    for dataset in config["datasets"]:
        assert report["source"]["sql_datasets"][dataset["dataset_id"]][
            "sha256"
        ] == sha256_text_file(Path(dataset["sql"]))


def test_concentration_metrics_are_bounded_and_monotonic() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    for market in report["analysis"]["all_markets"]:
        shares = [
            float(market[name])
            for name in (
                "top1_share_pct",
                "top3_share_pct",
                "top5_share_pct",
                "top10_share_pct",
            )
        ]
        assert 0 < float(market["hhi"]) <= 10000
        assert 0 < float(market["effective_supplier_count"])
        assert shares == sorted(shares)
        assert shares[-1] <= 100.001


def test_concentration_figures_are_current_nonempty_pngs() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    evidence = {item["path"]: item for item in report["artifacts"]["figure_evidence"]}

    assert {Path(path).name for path in evidence} == set(FIGURES)
    for relative, metadata in evidence.items():
        path = Path(relative)
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert path.stat().st_size > 20_000
        assert metadata["sha256"] == sha256_file(path)


def test_concentration_artifacts_preserve_nonlegal_interpretation() -> None:
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    dax = DAX_PATH.read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "No constituyen una conclusión legal" in markdown
    assert "ni se infiere colusión" in markdown
    assert "Supplier HHI =" in dax
    assert "Effective Supplier Count =" in dax
    assert "C:\\Users\\" not in report_text
    assert "run-market-concentration" in pyproject
