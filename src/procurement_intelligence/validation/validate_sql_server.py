"""Validate SQL Server integrity, data quality and cross-layer reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq
import pyodbc
import yaml

from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.loading.sql_server import split_sql_batches
from procurement_intelligence.settings import load_settings, load_sql_server_settings

UNKNOWN_TEXT = "__UNKNOWN__"
DIMENSION_TABLES = (
    "dim_date",
    "dim_process",
    "dim_buyer",
    "dim_supplier",
    "dim_category",
    "dim_procurement_method",
    "dim_currency",
    "dim_unit",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_validation_config(path: Path) -> dict[str, Any]:
    """Load and validate the governed SQL validation contract."""

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "validation" not in config or "rules" not in config:
        raise ValueError("SQL validation config must contain validation and rules sections.")
    rules = config["rules"]
    rule_ids = [rule["rule_id"] for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise ValueError("SQL validation rule IDs must be unique.")
    allowed_severities = set(config["validation"]["blocking_severities"]) | set(
        config["validation"]["warning_severities"]
    )
    invalid_severities = {
        rule["severity"] for rule in rules if rule["severity"] not in allowed_severities
    }
    if invalid_severities:
        raise ValueError(f"Unsupported SQL validation severities: {invalid_severities}")
    return config


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def _rows_from_current_result(cursor: pyodbc.Cursor) -> list[dict[str, Any]]:
    if cursor.description is None:
        return []
    columns = [str(column[0]) for column in cursor.description]
    return [
        {column: _json_value(value) for column, value in zip(columns, row, strict=True)}
        for row in cursor.fetchall()
    ]


def execute_sql(connection: pyodbc.Connection, sql: str) -> list[dict[str, Any]]:
    """Execute all GO-delimited batches and collect every tabular result set."""

    results: list[dict[str, Any]] = []
    cursor = connection.cursor()
    for batch in split_sql_batches(sql):
        cursor.execute(batch)
        while True:
            results.extend(_rows_from_current_result(cursor))
            if not cursor.nextset():
                break
    return results


def _read_script(project_root: Path, relative_path: str) -> str:
    path = project_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing SQL validation script: {path}")
    return path.read_text(encoding="utf-8-sig")


def _nested_value(payload: dict[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for key in dotted_path.split("."):
        value = value[key]
    return value


def expected_row_counts(
    etl_summary: dict[str, Any],
    dimensional_analysis: dict[str, Any],
    config: dict[str, Any],
) -> dict[tuple[str, str], int]:
    """Build independent expected row counts from committed Python evidence."""

    expected: dict[tuple[str, str], int] = {}
    for table in etl_summary["tables"]:
        expected[("STG", table["output_table"])] = int(table["silver_rows"])

    adjustment = config["reconciliation"]["dimension_unknown_adjustment"]
    for table_name in DIMENSION_TABLES:
        expected[("DW", table_name)] = int(
            dimensional_analysis["dimension_estimates"][table_name]
        ) + int(adjustment[table_name])

    for table_name, metrics in dimensional_analysis["fact_and_bridge_grains"].items():
        expected[("DW", table_name)] = int(metrics["rows"])
    return expected


def reconcile_rows(
    sql_rows: list[dict[str, Any]],
    expected: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    """Compare physical, audit and external Python row counts table by table."""

    reconciled: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in sql_rows:
        key = (str(row["layer"]), str(row["table_name"]))
        seen.add(key)
        external_expected = expected.get(key)
        actual = int(row["actual_rows"])
        audit_expected = int(row["audit_expected_rows"])
        audit_loaded = int(row["audit_loaded_rows"])
        passed = (
            external_expected is not None
            and actual == external_expected == audit_expected == audit_loaded
            and row["audit_status"] == "SUCCEEDED"
        )
        reconciled.append(
            {
                "layer": key[0],
                "table_name": key[1],
                "actual_rows": actual,
                "python_expected_rows": external_expected,
                "audit_expected_rows": audit_expected,
                "audit_loaded_rows": audit_loaded,
                "audit_status": row["audit_status"],
                "status": "PASS" if passed else "FAIL",
            }
        )
    for key in sorted(set(expected) - seen):
        reconciled.append(
            {
                "layer": key[0],
                "table_name": key[1],
                "actual_rows": None,
                "python_expected_rows": expected[key],
                "audit_expected_rows": None,
                "audit_loaded_rows": None,
                "audit_status": None,
                "status": "FAIL",
            }
        )
    return sorted(reconciled, key=lambda item: (item["layer"], item["table_name"]))


def _normalize_currency(value: Any) -> str:
    if value is None:
        return UNKNOWN_TEXT
    text = str(value).strip()
    return text or UNKNOWN_TEXT


def aggregate_financial_controls(
    data_root_settings: Any,
    etl_summary: dict[str, Any],
    controls: Iterable[dict[str, str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Aggregate Silver monetary control totals by published currency."""

    table_metadata = {
        table["output_table"]: table for table in etl_summary["tables"]
    }
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}
    for control in controls:
        metadata = table_metadata[control["silver_table"]]
        parquet_path = (
            data_root_settings.interim_root / metadata["output_relative_path"]
        )
        table = pq.read_table(
            parquet_path,
            columns=[control["currency_column"], control["amount_column"]],
        )
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"row_count": 0, "amount_non_null_rows": 0, "amount_sum": None}
        )
        currencies = table.column(control["currency_column"]).to_pylist()
        amounts = table.column(control["amount_column"]).to_pylist()
        for currency_value, amount in zip(currencies, amounts, strict=True):
            currency = _normalize_currency(currency_value)
            metric = grouped[currency]
            metric["row_count"] += 1
            if amount is not None:
                decimal_amount = Decimal(amount)
                metric["amount_non_null_rows"] += 1
                metric["amount_sum"] = (
                    decimal_amount
                    if metric["amount_sum"] is None
                    else metric["amount_sum"] + decimal_amount
                )
        for currency, metric in grouped.items():
            aggregates[(control["control_id"], currency)] = metric
    return aggregates


def reconcile_financial_controls(
    sql_rows: list[dict[str, Any]],
    expected: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare STG and DW controls with independently aggregated Silver values."""

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in sql_rows:
        control_id = str(row["control_id"])
        layer = str(row["layer"])
        currency = str(row["currency_code"])
        source_key = (control_id, currency)
        seen.add((control_id, layer, currency))
        reference = expected.get(source_key)
        sql_sum = None if row["amount_sum"] is None else Decimal(str(row["amount_sum"]))
        passed = (
            reference is not None
            and int(row["row_count"]) == reference["row_count"]
            and int(row["amount_non_null_rows"])
            == reference["amount_non_null_rows"]
            and sql_sum == reference["amount_sum"]
        )
        results.append(
            {
                "control_id": control_id,
                "layer": layer,
                "currency_code": currency,
                "sql_row_count": int(row["row_count"]),
                "python_row_count": None if reference is None else reference["row_count"],
                "sql_amount_non_null_rows": int(row["amount_non_null_rows"]),
                "python_amount_non_null_rows": (
                    None if reference is None else reference["amount_non_null_rows"]
                ),
                "sql_amount_sum": None if sql_sum is None else str(sql_sum),
                "python_amount_sum": (
                    None
                    if reference is None or reference["amount_sum"] is None
                    else str(reference["amount_sum"])
                ),
                "status": "PASS" if passed else "FAIL",
            }
        )

    for control_id, currency in sorted(expected):
        for layer in ("STG", "DW"):
            if (control_id, layer, currency) in seen:
                continue
            reference = expected[(control_id, currency)]
            results.append(
                {
                    "control_id": control_id,
                    "layer": layer,
                    "currency_code": currency,
                    "sql_row_count": None,
                    "python_row_count": reference["row_count"],
                    "sql_amount_non_null_rows": None,
                    "python_amount_non_null_rows": reference["amount_non_null_rows"],
                    "sql_amount_sum": None,
                    "python_amount_sum": (
                        None
                        if reference["amount_sum"] is None
                        else str(reference["amount_sum"])
                    ),
                    "status": "FAIL",
                }
            )
    return sorted(
        results,
        key=lambda item: (item["control_id"], item["layer"], item["currency_code"]),
    )


def classify_rule_results(
    sql_results: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Attach governed metadata and classify violations by severity."""

    metadata = {rule["rule_id"]: rule for rule in config["rules"]}
    result_by_id: dict[str, dict[str, Any]] = {}
    for result in sql_results:
        rule_id = str(result["rule_id"])
        if rule_id in result_by_id:
            raise ValueError(f"Duplicate SQL result for governed rule {rule_id}.")
        result_by_id[rule_id] = result

    missing = set(metadata) - set(result_by_id)
    unexpected = set(result_by_id) - set(metadata)
    if missing or unexpected:
        raise ValueError(
            f"SQL rule result contract mismatch; missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )

    classified: list[dict[str, Any]] = []
    for rule_id in sorted(metadata):
        rule = metadata[rule_id]
        result = result_by_id[rule_id]
        violations = int(result["violation_count"])
        if violations == 0:
            status = "PASS"
        elif rule["severity"] == "warning":
            status = "WARN"
        else:
            status = "FAIL"
        classified.append(
            {
                "rule_id": rule_id,
                "name": rule["name"],
                "category": rule["category"],
                "severity": rule["severity"],
                "status": status,
                "rows_evaluated": int(result["rows_evaluated"]),
                "violation_count": violations,
                "observed_value": result.get("observed_value"),
                "expected_value": result.get("expected_value"),
                "details": result["details"],
            }
        )
    return classified


def _reconciliation_result(
    reconciliation_id: str, observed: Any, expected: Any, description: str
) -> dict[str, Any]:
    passed = observed == expected
    return {
        "reconciliation_id": reconciliation_id,
        "status": "PASS" if passed else "FAIL",
        "observed": _json_value(observed),
        "expected": _json_value(expected),
        "description": description,
    }


def reconcile_artifacts(
    batch: dict[str, Any],
    etl_summary: dict[str, Any],
    dimensional_analysis: dict[str, Any],
    load_report: dict[str, Any],
    paths: dict[str, Path],
    project_root: Path,
) -> list[dict[str, Any]]:
    """Reconcile database batch identity and hashes with committed evidence."""

    source = etl_summary["source"]
    load_source = load_report["source"]
    ddl_evidence = [
        {
            "path": ddl["path"],
            "sha256": sha256_text_file(project_root / ddl["path"]),
        }
        for ddl in load_source["ddl_scripts"]
    ]
    ddl_serialized = json.dumps(
        ddl_evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    current_ddl_bundle_sha256 = hashlib.sha256(ddl_serialized).hexdigest()
    checks = [
        ("ART-001", int(batch["load_batch_id"]), int(load_report["summary"]["load_batch_id"]), "Active SQL batch equals the committed load report."),
        ("ART-002", batch["source_id"], source["source_id"], "SQL source ID equals ETL source identity."),
        ("ART-003", batch["source_period"], source["source_period"], "SQL source period equals ETL evidence."),
        ("ART-004", batch["snapshot_date"], source["snapshot_date"], "SQL snapshot date equals ETL evidence."),
        ("ART-005", batch["ingestion_run_id"], etl_summary["run"]["ingestion_run_id"], "SQL ingestion run equals ETL evidence."),
        ("ART-006", batch["archive_sha256"], source["archive_sha256"], "SQL archive hash equals ETL evidence."),
        ("ART-007", batch["etl_summary_sha256"], sha256_text_file(paths["etl_summary"]), "SQL ETL-summary hash equals the current repository artifact."),
        ("ART-008", batch["model_config_sha256"], sha256_text_file(project_root / load_source["model_config"]), "SQL model hash equals the current logical model contract."),
        ("ART-009", batch["physical_config_sha256"], sha256_text_file(project_root / load_source["physical_config"]), "SQL physical-contract hash equals the current repository contract."),
        ("ART-010", batch["ddl_bundle_sha256"], current_ddl_bundle_sha256, "SQL DDL bundle hash equals the current repository scripts."),
        ("ART-011", batch["staging_rows"], load_report["summary"]["staging_rows"], "SQL staging total equals Phase 7 report."),
        ("ART-012", batch["dimension_rows"], load_report["summary"]["dimension_rows"], "SQL dimension total equals Phase 7 report."),
        ("ART-013", batch["fact_rows"], load_report["summary"]["fact_rows"], "SQL fact total equals Phase 7 report."),
        ("ART-014", batch["bridge_rows"], load_report["summary"]["bridge_rows"], "SQL bridge total equals Phase 7 report."),
    ]
    return [_reconciliation_result(*check) for check in checks]


def reconcile_warning_metrics(
    rules: list[dict[str, Any]],
    dimensional_analysis: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ensure SQL warning counts reproduce the Phase 6 Python evidence."""

    by_id = {rule["rule_id"]: rule for rule in rules}
    results: list[dict[str, Any]] = []
    for rule_id, dotted_path in config["reconciliation"][
        "warning_metric_mapping"
    ].items():
        observed = by_id[rule_id]["violation_count"]
        expected = int(_nested_value(dimensional_analysis, dotted_path))
        results.append(
            _reconciliation_result(
                f"PYSQL-{rule_id}",
                observed,
                expected,
                f"SQL {rule_id} equals Python metric {dotted_path}.",
            )
        )
    return results


def _latest_batch(connection: pyodbc.Connection) -> dict[str, Any]:
    rows = execute_sql(
        connection,
        """
        SELECT TOP (1)
            load_batch_id, source_id, source_period,
            CONVERT(char(10), snapshot_date, 23) AS snapshot_date,
            ingestion_run_id, archive_sha256, etl_summary_sha256,
            model_config_sha256, physical_config_sha256, ddl_bundle_sha256,
            staging_rows, dimension_rows, fact_rows, bridge_rows
        FROM audit.load_batch
        WHERE status = 'SUCCEEDED'
        ORDER BY load_batch_id DESC;
        """,
    )
    if not rows:
        raise RuntimeError("No successful SQL Server load batch exists.")
    return rows[0]


def _server_metadata(connection: pyodbc.Connection) -> dict[str, Any]:
    return execute_sql(
        connection,
        """
        SELECT
            DB_NAME() AS database_name,
            CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS product_version,
            CONVERT(nvarchar(128), SERVERPROPERTY('Edition')) AS edition;
        """,
    )[0]


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    """Run the complete read-only Phase 8 validation contract."""

    started = time.perf_counter()
    config_path = args.config.resolve()
    project_root = config_path.parent.parent
    config = load_validation_config(config_path)
    validation = config["validation"]
    paths = {
        name: project_root / relative
        for name, relative in validation["inputs"].items()
    }
    etl_summary = _load_json(paths["etl_summary"])
    dimensional_analysis = _load_json(paths["dimensional_analysis"])
    load_report = _load_json(paths["sql_load_report"])
    data_settings = load_settings(args.env_file)
    sql_settings = load_sql_server_settings(args.env_file)

    connection = pyodbc.connect(
        sql_settings.connection_string(),
        autocommit=True,
        timeout=15,
    )
    try:
        connection.timeout = int(args.command_timeout_seconds)
        server = _server_metadata(connection)
        batch = _latest_batch(connection)

        raw_rules: list[dict[str, Any]] = []
        for script_key in ("integrity", "business_quality"):
            raw_rules.extend(
                execute_sql(
                    connection,
                    _read_script(project_root, validation["sql_scripts"][script_key]),
                )
            )

        dbcc_rows = execute_sql(
            connection,
            _read_script(project_root, validation["sql_scripts"]["dbcc"]),
        )
        raw_rules.append(
            {
                "rule_id": "SQL-REF-001",
                "rows_evaluated": int(validation["expected_objects"]["foreign_keys"]),
                "violation_count": len(dbcc_rows),
                "observed_value": str(len(dbcc_rows)),
                "expected_value": "0",
                "details": "DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS returned no violation rows.",
            }
        )
        rules = classify_rule_results(raw_rules, config)

        row_sql = execute_sql(
            connection,
            _read_script(
                project_root, validation["sql_scripts"]["row_reconciliation"]
            ),
        )
        row_expected = expected_row_counts(
            etl_summary, dimensional_analysis, config
        )
        row_reconciliation = reconcile_rows(row_sql, row_expected)

        financial_sql = execute_sql(
            connection,
            _read_script(
                project_root, validation["sql_scripts"]["financial_reconciliation"]
            ),
        )
        financial_expected = aggregate_financial_controls(
            data_settings,
            etl_summary,
            config["financial_controls"],
        )
        financial_reconciliation = reconcile_financial_controls(
            financial_sql, financial_expected
        )
        artifact_reconciliation = reconcile_artifacts(
            batch,
            etl_summary,
            dimensional_analysis,
            load_report,
            paths,
            project_root,
        )
        warning_reconciliation = reconcile_warning_metrics(
            rules, dimensional_analysis, config
        )
    finally:
        connection.close()

    blocking_failures = [rule for rule in rules if rule["status"] == "FAIL"]
    warnings = [rule for rule in rules if rule["status"] == "WARN"]
    failed_reconciliations = (
        [item for item in row_reconciliation if item["status"] == "FAIL"]
        + [item for item in financial_reconciliation if item["status"] == "FAIL"]
        + [item for item in artifact_reconciliation if item["status"] == "FAIL"]
        + [item for item in warning_reconciliation if item["status"] == "FAIL"]
    )
    if blocking_failures or failed_reconciliations:
        overall_status = "BLOCKED"
    elif warnings:
        overall_status = "PASS_WITH_WARNINGS"
    else:
        overall_status = "PASS"

    duration = round(time.perf_counter() - started, 4)
    return {
        "schema_version": "1.0",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "sql_server_quality_and_advanced_reconciliation",
        "source": {
            "source_id": etl_summary["source"]["source_id"],
            "source_period": etl_summary["source"]["source_period"],
            "snapshot_date": etl_summary["source"]["snapshot_date"],
            "load_batch_id": int(batch["load_batch_id"]),
            "database_name": server["database_name"],
            "sql_server_version": server["product_version"],
            "sql_server_edition": server["edition"],
            "validation_config": config_path.relative_to(project_root).as_posix(),
            "validation_config_sha256": sha256_text_file(config_path),
            "validator_sha256": sha256_text_file(Path(__file__)),
            "input_hashes": {
                name: sha256_text_file(path) for name, path in paths.items()
            },
            "sql_script_hashes": {
                name: {
                    "path": relative_path,
                    "sha256": sha256_text_file(project_root / relative_path),
                }
                for name, relative_path in validation["sql_scripts"].items()
            },
        },
        "summary": {
            "overall_status": overall_status,
            "promotion_eligible": not blocking_failures
            and not failed_reconciliations,
            "rules_total": len(rules),
            "rules_passed": sum(rule["status"] == "PASS" for rule in rules),
            "warning_findings": len(warnings),
            "blocking_failures": len(blocking_failures),
            "row_reconciliations": len(row_reconciliation),
            "row_reconciliations_failed": sum(
                item["status"] == "FAIL" for item in row_reconciliation
            ),
            "financial_reconciliations": len(financial_reconciliation),
            "financial_reconciliations_failed": sum(
                item["status"] == "FAIL" for item in financial_reconciliation
            ),
            "artifact_reconciliations": len(artifact_reconciliation),
            "artifact_reconciliations_failed": sum(
                item["status"] == "FAIL" for item in artifact_reconciliation
            ),
            "python_sql_warning_reconciliations": len(warning_reconciliation),
            "python_sql_warning_reconciliations_failed": sum(
                item["status"] == "FAIL" for item in warning_reconciliation
            ),
            "duration_seconds": duration,
        },
        "rules": rules,
        "row_reconciliation": row_reconciliation,
        "financial_reconciliation": financial_reconciliation,
        "artifact_reconciliation": artifact_reconciliation,
        "python_sql_warning_reconciliation": warning_reconciliation,
    }


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--config", type=Path, default=Path("config/sql_validation.yml")
    )
    parser.add_argument("--command-timeout-seconds", type=int, default=120)
    parser.add_argument("--strict-warnings", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_validation(args)
    write_json(report, args.output)
    summary = report["summary"]
    print(
        f"SQL validation {summary['overall_status']}: "
        f"{summary['rules_passed']}/{summary['rules_total']} rules passed; "
        f"{summary['blocking_failures']} blocking failures; "
        f"{summary['warning_findings']} warning findings."
    )
    if summary["overall_status"] == "BLOCKED":
        raise SystemExit(1)
    if args.strict_warnings and summary["warning_findings"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
