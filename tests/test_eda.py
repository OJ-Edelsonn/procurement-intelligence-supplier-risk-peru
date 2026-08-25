from __future__ import annotations

import json
from pathlib import Path

import pytest

from procurement_intelligence.extraction.download_ocds import (
    sha256_file,
    sha256_text_file,
)
from procurement_intelligence.analytics.run_eda import (
    FIGURE_NAMES,
    amount_profile,
    competition_profile,
    load_eda_config,
    require_phase8_gate,
)


CONFIG_PATH = Path("config/eda.yml")
REPORT_PATH = Path("reports/eda/oece_ocds_seace_v3_2026_07_eda_summary.json")
MARKDOWN_PATH = Path("reports/eda/oece_ocds_seace_v3_2026_07_eda_report.md")


def test_eda_contract_declares_ten_dw_datasets_and_outputs() -> None:
    config = load_eda_config(CONFIG_PATH)
    datasets = config["datasets"]

    assert len(datasets) == 10
    assert len({dataset["dataset_id"] for dataset in datasets}) == 10
    assert config["eda"]["top_n"] == 15
    assert config["eda"]["source_period"] == "2026-07"
    for dataset in datasets:
        sql_path = Path(dataset["sql"])
        assert sql_path.is_file()
        sql = sql_path.read_text(encoding="utf-8").casefold()
        assert "select *" not in sql
        assert "stg." not in sql
    for output in config["eda"]["outputs"].values():
        assert not Path(output).is_absolute()


def test_phase8_gate_blocks_any_failed_reconciliation() -> None:
    valid = {
        "summary": {
            "promotion_eligible": True,
            "blocking_failures": 0,
            "row_reconciliations_failed": 0,
            "financial_reconciliations_failed": 0,
            "artifact_reconciliations_failed": 0,
            "python_sql_warning_reconciliations_failed": 0,
        }
    }
    require_phase8_gate(valid)

    invalid = json.loads(json.dumps(valid))
    invalid["summary"]["artifact_reconciliations_failed"] = 1
    with pytest.raises(ValueError, match="artifact_reconciliations_failed"):
        require_phase8_gate(invalid)


def test_amount_profile_preserves_zeros_missing_values_and_outliers() -> None:
    rows = [
        {"stage": "tender", "amount_pen": "0.00"},
        {"stage": "tender", "amount_pen": "10.00"},
        {"stage": "tender", "amount_pen": "20.00"},
        {"stage": "tender", "amount_pen": "1000.00"},
        {"stage": "tender", "amount_pen": None},
        {"stage": "award", "amount_pen": "5.00"},
    ]

    profile = amount_profile(rows, "tender")

    assert profile["rows_total"] == 5
    assert profile["rows_with_pen"] == 4
    assert profile["missing_pen_rows"] == 1
    assert profile["zero_rows"] == 1
    assert profile["amount_sum"] == "1030.00"
    assert profile["maximum"] == "1000.00"
    assert profile["high_outlier_rows_iqr"] == 1


def test_competition_profile_uses_process_grain() -> None:
    rows = [
        {
            "process_key": 1,
            "tenderer_count_declared": 0,
            "tenderer_count_observed": 0,
            "award_count": 0,
            "contract_count": 0,
        },
        {
            "process_key": 2,
            "tenderer_count_declared": 2,
            "tenderer_count_observed": 3,
            "award_count": 1,
            "contract_count": 0,
        },
        {
            "process_key": 3,
            "tenderer_count_declared": None,
            "tenderer_count_observed": 6,
            "award_count": 2,
            "contract_count": 1,
        },
    ]

    profile = competition_profile(rows)

    assert profile["processes"] == 3
    assert profile["processes_without_observed_tenderers"] == 1
    assert profile["declared_observed_comparable_processes"] == 2
    assert profile["declared_observed_different_processes"] == 1
    assert profile["processes_with_awards"] == 2
    assert profile["processes_with_contracts"] == 1


def test_committed_eda_evidence_matches_current_contract_and_scripts() -> None:
    config = load_eda_config(CONFIG_PATH)
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["summary"]["status"] == "PASS"
    assert report["summary"]["datasets_executed"] == 10
    assert report["summary"]["figures_generated"] == 7
    assert report["summary"]["processes_analyzed"] == 6452
    assert report["summary"]["source_period_count"] == 1
    assert report["summary"]["growth_analysis_eligible"] is False
    assert report["source"]["eda_config_sha256"] == sha256_text_file(CONFIG_PATH)
    assert report["source"]["eda_runner_sha256"] == sha256_text_file(
        Path("src/procurement_intelligence/analytics/run_eda.py")
    )
    for dataset in config["datasets"]:
        evidence = report["source"]["sql_datasets"][dataset["dataset_id"]]
        assert evidence["path"] == dataset["sql"]
        assert evidence["sha256"] == sha256_text_file(Path(dataset["sql"]))


def test_eda_figures_are_nonempty_pngs_with_current_hashes() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    evidence = {item["path"]: item for item in report["artifacts"]["figure_evidence"]}

    assert {Path(path).name for path in evidence} == set(FIGURE_NAMES)
    for relative_path, metadata in evidence.items():
        path = Path(relative_path)
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert path.stat().st_size > 20_000
        assert metadata["size_bytes"] == path.stat().st_size
        assert metadata["sha256"] == sha256_file(path)


def test_eda_preserves_phase_boundaries_and_has_no_private_paths() -> None:
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    report = json.loads(report_text)
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")

    assert report["analysis"]["fitness_for_next_phases"]["growth_and_yoy"] == (
        "NOT_ELIGIBLE_SINGLE_SOURCE_PERIOD"
    )
    assert report["analysis"]["fitness_for_next_phases"]["market_concentration"] == (
        "DEFERRED_TO_PHASE_11"
    )
    assert "HHI" in markdown
    assert "no son KPIs" in markdown
    assert "C:\\Users\\" not in report_text
    assert "C:\\Users\\" not in markdown
    for relative_path in report["artifacts"]["figures"]:
        assert Path(relative_path).is_file()


def test_matplotlib_is_a_pinned_runtime_dependency() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
    assert "matplotlib==3.11.1" in requirements
