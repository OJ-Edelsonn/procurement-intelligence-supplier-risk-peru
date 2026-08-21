from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.modeling.validate_dimensional_model import (
    _amount_reconciliation,
    _foreign_rate_coverage,
    _grain_metrics,
    load_etl_summary,
    load_model_config,
    silver_column_catalog,
    validate_model_config,
)

MODEL_PATH = Path("config/dimensional_model.yml")
ETL_SUMMARY_PATH = Path(
    "reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json"
)
ANALYSIS_PATH = Path(
    "reports/modeling/oece_ocds_seace_v3_2026_07_dimensional_model_analysis.json"
)


def test_approved_model_contract_is_valid_and_has_expected_objects() -> None:
    config = load_model_config(MODEL_PATH)
    summary = load_etl_summary(ETL_SUMMARY_PATH)

    validate_model_config(config, silver_column_catalog(summary))

    assert config["model"]["architecture"] == "fact_constellation"
    assert config["model"]["unknown_surrogate_key"] == 0
    assert len(config["dimensions"]) == 8
    assert len(config["facts"]) == 6
    assert len(config["bridges"]) == 2
    assert "loaded_at_utc" in config["technical_columns"]["facts_and_bridges"]
    assert "canonical_ingestion_run_id" in config["technical_columns"][
        "silver_derived_dimensions"
    ]
    assert config["facts"]["fact_award"]["grain_columns"] == [
        "ocid",
        "compiled_release_awards_id",
    ]
    assert config["facts"]["fact_contract"]["attribution_policy"].startswith(
        "Inherit the award supplier only"
    )


def test_model_contract_rejects_unknown_silver_column() -> None:
    config = deepcopy(load_model_config(MODEL_PATH))
    summary = load_etl_summary(ETL_SUMMARY_PATH)
    config["facts"]["fact_award"]["measures"]["award_amount_original"][
        "source_ref"
    ] = "award.not_a_real_column"

    with pytest.raises(ValueError, match="Unknown Silver column"):
        validate_model_config(config, silver_column_catalog(summary))


def test_model_contract_rejects_monetary_bridge_without_prohibition() -> None:
    config = deepcopy(load_model_config(MODEL_PATH))
    summary = load_etl_summary(ETL_SUMMARY_PATH)
    config["bridges"]["bridge_award_supplier"]["prohibited_measures"] = []

    with pytest.raises(ValueError, match="prohibit monetary propagation"):
        validate_model_config(config, silver_column_catalog(summary))


def test_grain_metrics_detect_nulls_and_additional_duplicates() -> None:
    frame = pd.DataFrame(
        {"ocid": ["p1", "p1", "p2"], "award_id": ["a1", "a1", None]}
    )

    result = _grain_metrics(frame, ["ocid", "award_id"])

    assert result == {
        "rows": 3,
        "null_grain_rows": 1,
        "duplicate_grain_rows": 1,
    }


def test_amount_reconciliation_preserves_header_item_difference() -> None:
    parent = pd.DataFrame(
        {
            "ocid": ["p1", "p2"],
            "amount": [Decimal("10.00"), Decimal("20.00")],
            "currency": ["PEN", "PEN"],
        }
    )
    child = pd.DataFrame(
        {
            "ocid": ["p1", "p1", "p2"],
            "item_amount": [Decimal("4.00"), Decimal("6.00"), Decimal("18.00")],
            "item_currency": ["PEN", "PEN", "PEN"],
        }
    )

    result = _amount_reconciliation(
        parent,
        child,
        ["ocid"],
        "amount",
        "item_amount",
        "currency",
        "item_currency",
    )

    assert result["exact_matches"] == 1
    assert result["mismatches_over_0_01"] == 1
    assert result["maximum_absolute_difference"] == "2.00"


def test_foreign_rate_coverage_does_not_invent_conversion() -> None:
    parent = pd.DataFrame(
        {
            "ocid": ["p1", "p2", "p3"],
            "currency": ["USD", "EUR", "PEN"],
        }
    )
    rates = pd.DataFrame({"ocid": ["p1"]})

    result = _foreign_rate_coverage(parent, rates, ["ocid"], "currency")

    assert result["foreign_rows"] == 2
    assert result["rows_with_oece_pen_rate"] == 1
    assert result["rows_without_oece_pen_rate"] == 1
    assert result["unsupported_conversions_created"] == 0


def test_committed_analysis_reconciles_with_model_and_etl_evidence() -> None:
    report = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))

    assert report["source"]["model_config_sha256"] == sha256_text_file(MODEL_PATH)
    assert report["source"]["etl_summary_sha256"] == sha256_text_file(
        ETL_SUMMARY_PATH
    )
    assert report["summary"]["status"] == "PASS_WITH_WARNINGS"
    assert report["summary"]["design_eligible_for_phase7"] is True
    assert report["summary"]["modeled_objects"] == 16
    assert report["summary"]["fact_source_rows"] == 23056
    assert report["summary"]["bridge_source_rows"] == 37511
    assert report["summary"]["quality_gates_passed"] == 6
    assert report["summary"]["quality_gates_failed"] == 0
    assert all(gate["status"] == "PASS" for gate in report["quality_gates"])
    assert report["dimension_estimates"]["dim_supplier"] == 12820
    assert report["supplier_attribution"]["invented_allocations"] == 0
    assert "C:\\Data\\" not in ANALYSIS_PATH.read_text(encoding="utf-8")
