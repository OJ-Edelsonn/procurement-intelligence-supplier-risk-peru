from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest

from procurement_intelligence.profiling.profile_ocds_csv import CANDIDATE_GRAINS
from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.transformation.transform_ocds_silver import (
    _quality_comparison,
    _write_parquet_atomic,
    dataframe_to_arrow,
    infer_source_kind,
    load_etl_config,
    normalize_column_name,
    normalized_column_map,
    repository_summary,
    transform_table,
    validate_source_period,
    write_json,
)

CONFIG_PATH = Path("config/etl_silver.yml")
SUMMARY_PATH = Path("reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json")


def _context() -> dict[str, object]:
    return {
        "source_id": "oece_ocds_seace_v3_bulk",
        "source_period": "2026-07",
        "snapshot_date": date(2026, 8, 19),
        "ingestion_run_id": "00000000-0000-0000-0000-000000000001",
        "source_file_name": "sample.zip",
        "source_file_sha256": "a" * 64,
        "loaded_at_utc": pd.Timestamp("2026-08-19T12:00:00Z"),
    }


def _strings(data: dict[str, list[object]]) -> pd.DataFrame:
    return pd.DataFrame(data).astype("string")


def test_governed_etl_config_maps_every_profiled_table() -> None:
    config = load_etl_config(CONFIG_PATH)

    assert set(config["tables"]) == set(CANDIDATE_GRAINS)
    assert len(config["tables"]) == 22
    assert len(set(config["tables"].values())) == 22
    assert config["etl"]["decimal_precision"] == 38
    assert config["etl"]["decimal_scale"] == 14


def test_column_normalization_and_type_inference_are_stable() -> None:
    config = load_etl_config(CONFIG_PATH)

    assert normalize_column_name("compiledRelease/tender/items/0/totalValue/amount") == (
        "compiled_release_tender_items_total_value_amount"
    )
    assert infer_source_kind("compiledRelease/tender/value/amount", config) == "decimal"
    assert infer_source_kind("compiledRelease/date", config) == "datetime"
    assert infer_source_kind("compiledRelease/tender/items/0/position", config) == (
        "integer"
    )
    with pytest.raises(ValueError, match="collision"):
        normalized_column_map(["some/value", "some_value"])
    with pytest.raises(ValueError, match="calendar month"):
        validate_source_period("2026-13")


def test_exact_duplicate_is_quarantined_and_decimal_schema_is_fixed() -> None:
    config = load_etl_config(CONFIG_PATH)
    source_table = "com_ten_ite_tot_exchangeRates.csv"
    rate_column = (
        "compiledRelease/tender/items/0/totalValue/exchangeRates/0/rate"
    )
    dataframe = _strings(
        {
            "ocid": ["ocds-1", "ocds-1"],
            "compiledRelease/tender/items/0/id": ["item-1", "item-1"],
            "compiledRelease/tender/items/0/totalValue/exchangeRates/0/currency": [
                "USD",
                "USD",
            ],
            rate_column: ["3.74561234567890", "3.74561234567890"],
        }
    )

    output, kinds, quarantine, metrics = transform_table(
        dataframe, source_table, config, _context()
    )
    arrow_table = dataframe_to_arrow(output, kinds, config)
    normalized_rate = normalize_column_name(rate_column)

    assert len(output) == 1
    assert quarantine is not None and len(quarantine) == 1
    assert output.loc[0, normalized_rate] == Decimal("3.74561234567890")
    assert arrow_table.schema.field(normalized_rate).type == pa.decimal128(38, 14)
    assert arrow_table.schema.field("loaded_at_utc").type == pa.timestamp(
        "us", tz="UTC"
    )
    assert metrics["additional_duplicate_rows_before"] == 1
    assert metrics["additional_duplicate_rows_after"] == 0
    assert metrics["duplicate_candidate_grain_rows_before"] == 1
    assert metrics["duplicate_candidate_grain_rows_after"] == 0
    assert output.loc[0, "source_row_number"] == 1
    assert quarantine.loc[0, "source_row_number"] == 2


def test_missing_classification_is_normalized_and_flagged() -> None:
    config = load_etl_config(CONFIG_PATH)
    source_table = "com_ten_items.csv"
    prefix = "compiledRelease/tender/items/0/classification/"
    dataframe = _strings(
        {
            "ocid": ["ocds-1", "ocds-2"],
            "compiledRelease/tender/items/0/id": ["item-1", "item-2"],
            f"{prefix}id": [None, "44120000"],
            f"{prefix}description": [None, "Suministros de oficina"],
            f"{prefix}scheme": [None, "UNSPSC"],
        }
    )

    output, _, quarantine, metrics = transform_table(
        dataframe, source_table, config, _context()
    )

    assert quarantine is None
    assert output.loc[0, normalize_column_name(f"{prefix}id")] == "__UNCLASSIFIED__"
    assert output.loc[0, normalize_column_name(f"{prefix}description")] == (
        "Sin clasificar"
    )
    assert output.loc[0, normalize_column_name(f"{prefix}scheme")] == "UNKNOWN"
    assert bool(output.loc[0, "dq_classification_was_missing"]) is True
    assert bool(output.loc[1, "dq_classification_was_missing"]) is False
    assert metrics["incomplete_classification_rows_before"] == 1
    assert metrics["incomplete_classification_rows_after"] == 0
    assert metrics["classification_rows_normalized"] == 1


def test_ruc_values_are_preserved_and_only_format_validity_is_flagged() -> None:
    config = load_etl_config(CONFIG_PATH)
    source_table = "com_parties.csv"
    identifier_column = "compiledRelease/parties/0/identifier/id"
    dataframe = _strings(
        {
            "ocid": ["ocds-1", "ocds-2", "ocds-3"],
            "compiledRelease/parties/0/id": ["party-1", "party-2", "party-3"],
            "compiledRelease/parties/0/identifier/scheme": [
                "PE-RUC",
                "PE-RUC",
                "PE-CONSUCODE",
            ],
            identifier_column: ["20123456789", "1234567", "ABC123"],
        }
    )

    output, _, _, metrics = transform_table(
        dataframe, source_table, config, _context()
    )
    normalized_identifier = normalize_column_name(identifier_column)

    assert output[normalized_identifier].tolist() == [
        "20123456789",
        "1234567",
        "ABC123",
    ]
    assert bool(output.loc[0, "dq_ruc_format_valid"]) is True
    assert bool(output.loc[1, "dq_ruc_format_valid"]) is False
    assert pd.isna(output.loc[2, "dq_ruc_format_valid"])
    assert metrics["ruc_invalid_rows_flagged"] == 1


def test_quality_comparison_uses_candidate_grain_metrics_directly() -> None:
    metrics = [
        {
            "null_candidate_grain_rows_before": 1,
            "duplicate_candidate_grain_rows_before": 10,
            "null_candidate_grain_rows_after": 0,
            "duplicate_candidate_grain_rows_after": 0,
            "additional_duplicate_rows_before": 10,
            "additional_duplicate_rows_after": 0,
            "ruc_invalid_rows_flagged": 1797,
            "incomplete_classification_rows_before": 2135,
            "incomplete_classification_rows_after": 0,
            "final_value_missing_rows_flagged": 1116,
            "zero_amount_rows_flagged": 1752,
        }
    ]

    comparison = _quality_comparison(metrics)
    uniqueness = next(row for row in comparison if row["rule_id"] == "DQ-UNIQ-001")

    assert uniqueness == {
        "rule_id": "DQ-UNIQ-001",
        "metric": "candidate_grain_violations",
        "before": 11,
        "after": 0,
    }


def test_committed_etl_summary_reconciles_with_config_and_rows() -> None:
    report = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    tables = report["tables"]
    serialized = SUMMARY_PATH.read_text(encoding="utf-8")

    assert report["source"]["etl_config_sha256"] == sha256_text_file(CONFIG_PATH)
    assert report["source"]["archive_sha256"] == (
        "024ef9eb7a282de74559ea78ba149ff87aa041d7c92947795ac354d49f0ba4e8"
    )
    assert report["summary"]["status"] == "PASS_WITH_WARNINGS"
    assert report["summary"]["promotion_eligible"] is True
    assert len(tables) == 22
    assert sum(table["raw_rows"] for table in tables) == 231123
    assert sum(table["silver_rows"] for table in tables) == 231113
    assert sum(table["quarantine_rows"] for table in tables) == 10
    assert all(
        value == 0
        for value in report["summary"]["blocking_metrics_after"].values()
    )
    assert report["summary"]["warning_metrics_after"] == {
        "ruc_invalid_rows_flagged": 1797,
        "zero_amount_rows_flagged": 1752,
        "final_value_missing_rows_flagged": 1116,
    }
    assert "C:\\Data\\" not in serialized


def test_atomic_writes_require_explicit_parquet_overwrite(tmp_path: Path) -> None:
    config = load_etl_config(CONFIG_PATH)
    destination = tmp_path / "table.parquet"
    table = pa.table({"id": pa.array([1], type=pa.int64())})

    _write_parquet_atomic(table, destination, config, overwrite=False)

    with pytest.raises(FileExistsError, match="--overwrite"):
        _write_parquet_atomic(table, destination, config, overwrite=False)
    _write_parquet_atomic(table, destination, config, overwrite=True)
    write_json({"status": "PASS"}, tmp_path / "manifest.json")

    assert destination.is_file()
    assert not destination.with_suffix(".parquet.part").exists()
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == {
        "status": "PASS"
    }
    assert not (tmp_path / "manifest.json.part").exists()


def test_repository_summary_removes_absolute_paths() -> None:
    report = {
        "schema_version": "1.0",
        "source": {"etl_config": r"C:\private\config\etl_silver.yml"},
        "run": {"ingestion_run_id": "run-1"},
        "summary": {"status": "PASS"},
        "quality_comparison": [],
        "tables": [{"output_path": r"C:\private\silver.parquet", "raw_rows": 1}],
        "quarantine": [{"path": r"C:\private\quarantine.parquet", "rows": 1}],
    }

    summary = repository_summary(report)
    serialized = json.dumps(summary)

    assert summary["source"]["etl_config"] == "etl_silver.yml"
    assert "C:\\private" not in serialized
