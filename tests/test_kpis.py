from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from procurement_intelligence.analytics.run_kpis import (
    load_kpi_config,
    reconcile_with_eda,
)
from procurement_intelligence.extraction.download_ocds import sha256_text_file


CONFIG_PATH = Path("config/kpis.yml")
REPORT_PATH = Path("reports/kpis/oece_ocds_seace_v3_2026_07_kpi_summary.json")
EDA_PATH = Path("reports/eda/oece_ocds_seace_v3_2026_07_eda_summary.json")
DAX_PATH = Path("powerbi/dax/phase10_kpi_measures.dax")


def test_kpi_contract_has_unique_published_and_blocked_metrics() -> None:
    config = load_kpi_config(CONFIG_PATH)
    published = {item["metric_id"] for item in config["catalog"]}
    blocked = {item["metric_id"] for item in config["blocked_metrics"]}

    assert len(published) == 21
    assert len(blocked) == 7
    assert not published & blocked
    assert config["kpis"]["source_period"] == "2026-07"
    assert "yoy_growth_pct" in blocked
    assert "supplier_market_share" in blocked


def test_kpi_sql_uses_native_dw_grains_and_bounded_rankings() -> None:
    config = load_kpi_config(CONFIG_PATH)

    assert len(config["datasets"]) == 4
    for dataset in config["datasets"]:
        sql = Path(dataset["sql"]).read_text(encoding="utf-8").casefold()
        assert "select *" not in sql
        assert "stg." not in sql
        assert "raw" not in sql
    for dataset_id in ("buyer_kpis", "supplier_kpis", "category_kpis"):
        dataset = next(
            item for item in config["datasets"] if item["dataset_id"] == dataset_id
        )
        assert "top (20)" in Path(dataset["sql"]).read_text(encoding="utf-8").casefold()


def test_invalid_kpi_contract_is_rejected(tmp_path: Path) -> None:
    config = load_kpi_config(CONFIG_PATH)
    config["blocked_metrics"].append(
        {"metric_id": config["catalog"][0]["metric_id"], "reason": "conflict"}
    )
    invalid = tmp_path / "invalid.yml"
    import yaml

    invalid.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="published and blocked"):
        load_kpi_config(invalid)


def test_committed_kpi_evidence_matches_contract_runner_sql_and_dax() -> None:
    config = load_kpi_config(CONFIG_PATH)
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["summary"]["status"] == "PASS"
    assert report["summary"]["published_kpis"] == 21
    assert report["summary"]["blocked_kpis"] == 7
    assert report["summary"]["reconciliations_failed"] == 0
    assert report["source"]["kpi_config_sha256"] == sha256_text_file(CONFIG_PATH)
    assert report["source"]["kpi_runner_sha256"] == sha256_text_file(
        Path("src/procurement_intelligence/analytics/run_kpis.py")
    )
    assert report["source"]["dax_catalog_sha256"] == sha256_text_file(DAX_PATH)
    for dataset in config["datasets"]:
        evidence = report["source"]["sql_datasets"][dataset["dataset_id"]]
        assert evidence["sha256"] == sha256_text_file(Path(dataset["sql"]))


def test_kpi_values_and_denominators_are_evidence_backed() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    metrics = {
        item["metric_id"]: item for item in report["analysis"]["portfolio_kpis"]
    }

    assert Decimal(metrics["procurement_processes"]["metric_value"]) == 6452
    assert Decimal(metrics["tender_amount_pen"]["metric_value"]) == Decimal(
        "6924924015.380000"
    )
    assert metrics["competition_coverage_pct"]["numerator"] == 4243
    assert metrics["competition_coverage_pct"]["denominator"] == 6452
    assert metrics["contract_amount_pen_coverage_pct"]["numerator"] == 1115
    assert metrics["contract_amount_pen_coverage_pct"]["denominator"] == 1119
    assert metrics["award_item_standard_category_coverage_pct"]["numerator"] == 2942
    assert metrics["award_item_standard_category_coverage_pct"]["denominator"] == 3590


def test_kpi_reconciliation_detects_a_changed_critical_value() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    eda = json.loads(EDA_PATH.read_text(encoding="utf-8"))
    metric_map = {
        item["metric_id"]: item for item in report["analysis"]["portfolio_kpis"]
    }
    metric_map["procurement_processes"] = {
        **metric_map["procurement_processes"],
        "metric_value": "6453",
    }

    results = reconcile_with_eda(metric_map, eda)

    assert next(
        item for item in results if item["metric_id"] == "procurement_processes"
    )["status"] == "FAIL"


def test_dax_catalog_preserves_phase_boundaries() -> None:
    dax = DAX_PATH.read_text(encoding="utf-8")

    for measure in (
        "Tender Amount PEN =",
        "Award Amount PEN =",
        "Contract Amount PEN =",
        "Competition Coverage % =",
        "Award Process Presence % =",
    ):
        assert measure in dax
    for prohibited in ("HHI =", "Growth =", "Opportunity Score =", "Risk Score ="):
        assert prohibited not in dax


def test_kpi_artifacts_have_no_private_paths_and_cli_is_registered() -> None:
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    markdown = Path(
        "reports/kpis/oece_ocds_seace_v3_2026_07_kpi_report.md"
    ).read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "C:\\Users\\" not in report_text
    assert "C:\\Users\\" not in markdown
    assert "run-procurement-kpis" in pyproject
    assert "No se calculan crecimiento, YoY, HHI ni scores" in markdown
