from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq

from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.validation.validate_sql_server import (
    aggregate_financial_controls,
    classify_rule_results,
    expected_row_counts,
    load_validation_config,
    reconcile_financial_controls,
    reconcile_rows,
)


CONFIG_PATH = Path("config/sql_validation.yml")
REPORT_PATH = Path(
    "reports/sql/oece_ocds_seace_v3_2026_07_phase8_validation.json"
)


def test_sql_validation_contract_declares_45_unique_rules_and_all_scripts() -> None:
    config = load_validation_config(CONFIG_PATH)
    rules = config["rules"]

    assert len(rules) == 45
    assert len({rule["rule_id"] for rule in rules}) == 45
    assert sum(rule["severity"] == "error" for rule in rules) == 34
    assert sum(rule["severity"] == "warning" for rule in rules) == 11
    for relative_path in config["validation"]["sql_scripts"].values():
        assert Path(relative_path).is_file()


def test_every_governed_rule_is_produced_by_sql_or_dbcc_runner() -> None:
    config = load_validation_config(CONFIG_PATH)
    integrity = Path(
        config["validation"]["sql_scripts"]["integrity"]
    ).read_text(encoding="utf-8")
    business = Path(
        config["validation"]["sql_scripts"]["business_quality"]
    ).read_text(encoding="utf-8")
    runner = Path(
        "src/procurement_intelligence/validation/validate_sql_server.py"
    ).read_text(encoding="utf-8")
    produced = set(
        re.findall(r"SQL-[A-Z]+-\d{3}", integrity + business + runner)
    )

    assert produced == {rule["rule_id"] for rule in config["rules"]}


def test_external_row_expectations_cover_all_38_loaded_tables() -> None:
    config = load_validation_config(CONFIG_PATH)
    etl = json.loads(
        Path(config["validation"]["inputs"]["etl_summary"]).read_text(
            encoding="utf-8"
        )
    )
    model = json.loads(
        Path(config["validation"]["inputs"]["dimensional_analysis"]).read_text(
            encoding="utf-8"
        )
    )

    expected = expected_row_counts(etl, model, config)

    assert len(expected) == 38
    assert sum(value for (layer, _), value in expected.items() if layer == "STG") == 231113
    assert expected[("DW", "dim_date")] == 2136
    assert expected[("DW", "dim_category")] == 3690
    assert expected[("DW", "fact_award")] == 3397
    assert expected[("DW", "bridge_process_tenderer")] == 34115


def test_row_reconciliation_detects_a_physical_mismatch() -> None:
    sql_rows = [
        {
            "layer": "DW",
            "table_name": "fact_award",
            "actual_rows": 9,
            "audit_expected_rows": 10,
            "audit_loaded_rows": 10,
            "audit_status": "SUCCEEDED",
        }
    ]

    result = reconcile_rows(sql_rows, {("DW", "fact_award"): 10})

    assert result[0]["status"] == "FAIL"


def test_rule_classification_separates_warning_from_blocking_failure() -> None:
    config = {
        "rules": [
            {
                "rule_id": "SQL-TEST-001",
                "name": "blocking",
                "category": "test",
                "severity": "error",
            },
            {
                "rule_id": "SQL-TEST-002",
                "name": "warning",
                "category": "test",
                "severity": "warning",
            },
        ]
    }
    rows = [
        {
            "rule_id": "SQL-TEST-001",
            "rows_evaluated": 1,
            "violation_count": 1,
            "observed_value": "1",
            "expected_value": "0",
            "details": "blocking",
        },
        {
            "rule_id": "SQL-TEST-002",
            "rows_evaluated": 1,
            "violation_count": 1,
            "observed_value": "1",
            "expected_value": "0",
            "details": "warning",
        },
    ]

    classified = classify_rule_results(rows, config)

    assert [result["status"] for result in classified] == ["FAIL", "WARN"]


def test_financial_control_uses_currency_grain_and_exact_decimals(
    tmp_path: Path,
) -> None:
    relative_path = Path("staging/test/part-00000.parquet")
    parquet_path = tmp_path / "interim" / relative_path
    parquet_path.parent.mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "currency": ["PEN", "PEN", "USD", None],
                "amount": pa.array(
                    [Decimal("10.10"), Decimal("2.20"), Decimal("3.00"), None],
                    type=pa.decimal128(38, 14),
                ),
            }
        ),
        parquet_path,
    )
    settings = SimpleNamespace(interim_root=tmp_path / "interim")
    etl = {
        "tables": [
            {"output_table": "test", "output_relative_path": relative_path.as_posix()}
        ]
    }
    controls = [
        {
            "control_id": "test_amount",
            "silver_table": "test",
            "currency_column": "currency",
            "amount_column": "amount",
        }
    ]

    expected = aggregate_financial_controls(settings, etl, controls)

    assert expected[("test_amount", "PEN")] == {
        "row_count": 2,
        "amount_non_null_rows": 2,
        "amount_sum": Decimal("12.30000000000000"),
    }
    assert expected[("test_amount", "__UNKNOWN__")]["row_count"] == 1

    sql_rows = []
    for layer in ("STG", "DW"):
        for (control_id, currency), metric in expected.items():
            sql_rows.append(
                {
                    "control_id": control_id,
                    "layer": layer,
                    "currency_code": currency,
                    **metric,
                }
            )
    reconciled = reconcile_financial_controls(sql_rows, expected)
    assert all(result["status"] == "PASS" for result in reconciled)


def test_committed_phase8_report_is_reproducible_and_has_no_failures() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    config = load_validation_config(CONFIG_PATH)

    assert report["summary"]["overall_status"] == "PASS_WITH_WARNINGS"
    assert report["summary"]["promotion_eligible"] is True
    assert report["summary"]["rules_total"] == 45
    assert report["summary"]["blocking_failures"] == 0
    assert report["summary"]["row_reconciliations_failed"] == 0
    assert report["summary"]["financial_reconciliations_failed"] == 0
    assert report["summary"]["artifact_reconciliations_failed"] == 0
    assert report["summary"]["python_sql_warning_reconciliations_failed"] == 0
    assert all(item["status"] == "PASS" for item in report["row_reconciliation"])
    assert all(
        item["status"] == "PASS" for item in report["financial_reconciliation"]
    )
    assert report["source"]["validation_config_sha256"] == sha256_text_file(
        CONFIG_PATH
    )
    assert report["source"]["validator_sha256"] == sha256_text_file(
        Path("src/procurement_intelligence/validation/validate_sql_server.py")
    )
    for name, relative_path in config["validation"]["sql_scripts"].items():
        evidence = report["source"]["sql_script_hashes"][name]
        assert evidence["path"] == relative_path
        assert evidence["sha256"] == sha256_text_file(Path(relative_path))
    assert "C:\\Users\\" not in REPORT_PATH.read_text(encoding="utf-8")
