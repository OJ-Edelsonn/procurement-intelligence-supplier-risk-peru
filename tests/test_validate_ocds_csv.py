from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import yaml

from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.profiling.profile_ocds_csv import CANDIDATE_GRAINS
from procurement_intelligence.validation.validate_ocds_csv import (
    _peru_ruc,
    evaluate_archive,
    load_quality_config,
    repository_summary,
)

RULES_PATH = Path("config/data_quality_rules.yml")
SUMMARY_PATH = Path(
    "reports/data_quality/oece_ocds_seace_v3_2026_07_quality_summary.json"
)


def _write_minimal_rules(path: Path) -> None:
    config = {
        "framework": {
            "schema_version": "1.0",
            "source_id": "test_source",
            "blocking_severities": ["critical", "error"],
        },
        "rules": [
            {
                "rule_id": "DQ-SCHEMA-001",
                "name": "Required table",
                "dimension": "schema",
                "type": "required_tables",
                "severity": "critical",
                "description": "Synthetic table must exist.",
                "threshold": {"max_invalid_count": 0},
                "parameters": {"tables": ["records.csv"]},
            },
            {
                "rule_id": "DQ-SCHEMA-002",
                "name": "Required columns",
                "dimension": "schema",
                "type": "required_columns",
                "severity": "critical",
                "description": "Synthetic columns must exist.",
                "threshold": {"max_invalid_count": 0},
                "parameters": {
                    "targets": [
                        {"table": "records.csv", "columns": ["ocid", "amount"]}
                    ]
                },
            },
            {
                "rule_id": "DQ-VALID-001",
                "name": "Non-negative amount",
                "dimension": "validity",
                "type": "numeric_min",
                "severity": "error",
                "description": "Synthetic amount cannot be negative.",
                "threshold": {"max_invalid_count": 0},
                "parameters": {
                    "minimum": 0,
                    "inclusive": True,
                    "allow_null": False,
                    "targets": [{"table": "records.csv", "column": "amount"}],
                },
            },
            {
                "rule_id": "DQ-DUP-001",
                "name": "Exact duplicates",
                "dimension": "uniqueness",
                "type": "exact_duplicates",
                "severity": "warning",
                "description": "Synthetic duplicates are measured.",
                "threshold": {"max_invalid_count": 0},
                "parameters": {"tables": "all"},
            },
        ],
    }
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_governed_rules_are_valid_and_cover_profiled_tables() -> None:
    config = load_quality_config(RULES_PATH)
    required_tables_rule = next(
        rule for rule in config["rules"] if rule["type"] == "required_tables"
    )

    assert len(config["rules"]) == 17
    assert set(required_tables_rule["parameters"]["tables"]) == set(
        CANDIDATE_GRAINS
    )


def test_evaluate_archive_reports_blocking_and_warning_failures(tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.zip"
    rules_path = tmp_path / "rules.yml"
    records = pd.DataFrame(
        {
            "ocid": ["p1", "p1", "p2", "p3"],
            "amount": ["10", "10", "-1", None],
        }
    )
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("records.csv", records.to_csv(index=False))
    _write_minimal_rules(rules_path)

    report = evaluate_archive(archive_path, rules_path, "2026-07", "2026-08-19")

    assert report["summary"]["overall_status"] == "BLOCKED"
    assert report["summary"]["promotion_eligible"] is False
    assert report["summary"]["passed_rules"] == 2
    assert report["summary"]["failed_rules"] == 2
    assert report["summary"]["blocking_failures"] == 1
    assert report["summary"]["warning_failures"] == 1
    numeric_result = next(
        result for result in report["results"] if result["rule_id"] == "DQ-VALID-001"
    )
    duplicate_result = next(
        result for result in report["results"] if result["rule_id"] == "DQ-DUP-001"
    )
    assert numeric_result["invalid_rows"] == 2
    assert duplicate_result["invalid_rows"] == 1


def test_repository_summary_removes_volatile_fields(tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.zip"
    rules_path = tmp_path / "rules.yml"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("records.csv", "ocid,amount\np1,10\n")
    _write_minimal_rules(rules_path)
    report = evaluate_archive(archive_path, rules_path, "2026-07", "2026-08-19")

    summary = repository_summary(report)

    assert "evaluated_at_utc" not in summary
    assert "duration_seconds" not in summary["summary"]
    assert summary["source"]["rule_config"] == rules_path.as_posix()


def test_peru_ruc_rule_reports_aggregate_format_reasons() -> None:
    rule = {
        "parameters": {
            "table": "parties.csv",
            "scheme_column": "scheme",
            "scheme_value": "PE-RUC",
            "identifier_column": "identifier",
        }
    }
    tables = {
        "parties.csv": pd.DataFrame(
            {
                "scheme": pd.Series(["PE-RUC"] * 3, dtype="string"),
                "identifier": pd.Series(
                    ["20100070970", "1234567", "L0100070970"], dtype="string"
                ),
            }
        )
    }

    invalid, evaluated, details = _peru_ruc(rule, tables)

    assert evaluated == 3
    assert invalid == 2
    assert details["invalid_length_rows"] == 1
    assert details["non_digit_rows_with_length_11"] == 1


def test_committed_quality_summary_reconciles_with_rules() -> None:
    report = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    results = report["results"]
    failures = [result for result in results if result["status"] == "FAIL"]
    blocking = [
        result
        for result in failures
        if result["severity"] in {"critical", "error"}
    ]

    assert report["source"]["rule_config_sha256"] == sha256_text_file(RULES_PATH)
    assert report["summary"]["rule_count"] == len(results) == 17
    assert report["summary"]["passed_rules"] == len(results) - len(failures) == 11
    assert report["summary"]["failed_rules"] == len(failures) == 6
    assert report["summary"]["blocking_failures"] == len(blocking) == 1
    assert report["summary"]["overall_status"] == "BLOCKED"
    assert all(
        result["post_treatment"]["status"] == "NOT_EVALUATED"
        for result in results
    )
    uniqueness = next(
        result for result in results if result["rule_id"] == "DQ-UNIQ-001"
    )
    assert uniqueness["invalid_rows"] == 11
