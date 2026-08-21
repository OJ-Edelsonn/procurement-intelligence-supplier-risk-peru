"""Load all Silver tables and the approved dimensional constellation to SQL Server."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.loading.build_dw_frames import (
    BRIDGE_TABLES,
    DIMENSION_TABLES,
    FACT_TABLES,
    WarehouseFrames,
    build_warehouse_frames,
    load_silver_frames,
)
from procurement_intelligence.loading.sql_server import (
    bulk_insert_frame,
    connect_sql_server,
    ensure_database,
    execute_sql_scripts,
    quote_identifier,
    staging_table_ddl,
    table_columns,
    table_row_count,
)
from procurement_intelligence.settings import (
    load_settings,
    load_sql_server_settings,
)

UNKNOWN_DIMENSION_ADJUSTMENT = {
    "dim_date": 1,
    "dim_process": 1,
    "dim_buyer": 1,
    "dim_supplier": 1,
    "dim_category": 0,
    "dim_procurement_method": 1,
    "dim_currency": 1,
    "dim_unit": 1,
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _physical_contract_paths(
    physical_config: dict[str, Any], config_path: Path
) -> list[Path]:
    root = config_path.parent.parent
    paths = [root / item for item in physical_config["ddl_scripts"]]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing SQL DDL scripts: {missing}")
    return paths


def _ddl_evidence(paths: list[Path]) -> tuple[list[dict[str, str]], str]:
    evidence = [
        {"path": path.as_posix(), "sha256": sha256_text_file(path)} for path in paths
    ]
    serialized = json.dumps(
        evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return evidence, hashlib.sha256(serialized).hexdigest()


def validate_warehouse_build(
    warehouse: WarehouseFrames,
    dimensional_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Block a load when the in-memory warehouse diverges from Phase 6 evidence."""

    if list(warehouse.dimensions) != DIMENSION_TABLES:
        raise ValueError("Warehouse dimensions diverge from the approved load order")
    if list(warehouse.facts) != FACT_TABLES:
        raise ValueError("Warehouse facts diverge from the approved load order")
    if list(warehouse.bridges) != BRIDGE_TABLES:
        raise ValueError("Warehouse bridges diverge from the approved load order")

    fact_rows = sum(len(frame) for frame in warehouse.facts.values())
    bridge_rows = sum(len(frame) for frame in warehouse.bridges.values())
    expected = dimensional_analysis["summary"]
    if fact_rows != expected["fact_source_rows"]:
        raise ValueError(
            f"Fact rows {fact_rows} do not reconcile with Phase 6 "
            f"{expected['fact_source_rows']}"
        )
    if bridge_rows != expected["bridge_source_rows"]:
        raise ValueError(
            f"Bridge rows {bridge_rows} do not reconcile with Phase 6 "
            f"{expected['bridge_source_rows']}"
        )

    business_estimates = dimensional_analysis["dimension_estimates"]
    for table, frame in warehouse.dimensions.items():
        expected_rows = (
            business_estimates[table] + UNKNOWN_DIMENSION_ADJUSTMENT[table]
        )
        if len(frame) != expected_rows:
            raise ValueError(
                f"{table} has {len(frame)} rows; expected {expected_rows}"
            )
        key_column = frame.columns[0]
        if int((frame[key_column] == 0).sum()) != 1:
            raise ValueError(f"{table} must contain exactly one surrogate key 0")

    for table, frame in warehouse.bridges.items():
        if "supplier_key" in frame and frame["supplier_key"].eq(0).any():
            raise ValueError(f"{table} contains an unresolved supplier")
        if frame["process_key"].eq(0).any():
            raise ValueError(f"{table} contains an unresolved process")
        monetary = [column for column in frame if "amount" in column]
        if monetary:
            raise ValueError(f"{table} contains prohibited monetary columns: {monetary}")

    return {
        "dimensions": len(warehouse.dimensions),
        "facts": len(warehouse.facts),
        "bridges": len(warehouse.bridges),
        "dimension_rows": sum(len(frame) for frame in warehouse.dimensions.values()),
        "fact_rows": fact_rows,
        "bridge_rows": bridge_rows,
        "unresolved_bridge_keys": 0,
        "bridge_monetary_columns": 0,
    }


def _validate_existing_database(
    connection: Any,
    etl_summary: dict[str, Any],
    dimensional_analysis: dict[str, Any],
) -> tuple[dict[str, int], dict[str, Any]]:
    """Reconcile an audited successful batch before idempotently skipping it."""

    counts: dict[str, int] = {}
    for metadata in etl_summary["tables"]:
        table = metadata["output_table"]
        actual = table_row_count(connection, "stg", table)
        expected = int(metadata["silver_rows"])
        if actual != expected:
            raise ValueError(
                f"Audited batch diverges at stg.{table}: expected {expected}; actual {actual}"
            )
        counts[f"stg.{table}"] = actual

    business_estimates = dimensional_analysis["dimension_estimates"]
    for table in DIMENSION_TABLES:
        actual = table_row_count(connection, "dw", table)
        expected = business_estimates[table] + UNKNOWN_DIMENSION_ADJUSTMENT[table]
        if actual != expected:
            raise ValueError(
                f"Audited batch diverges at dw.{table}: expected {expected}; actual {actual}"
            )
        counts[f"dw.{table}"] = actual

    grain_metrics = dimensional_analysis["fact_and_bridge_grains"]
    for table in [*FACT_TABLES, *BRIDGE_TABLES]:
        actual = table_row_count(connection, "dw", table)
        expected = int(grain_metrics[table]["rows"])
        if actual != expected:
            raise ValueError(
                f"Audited batch diverges at dw.{table}: expected {expected}; actual {actual}"
            )
        counts[f"dw.{table}"] = actual

    validation = {
        "dimensions": len(DIMENSION_TABLES),
        "facts": len(FACT_TABLES),
        "bridges": len(BRIDGE_TABLES),
        "staging_rows": sum(
            count for name, count in counts.items() if name.startswith("stg.")
        ),
        "dimension_rows": sum(counts[f"dw.{name}"] for name in DIMENSION_TABLES),
        "fact_rows": sum(counts[f"dw.{name}"] for name in FACT_TABLES),
        "bridge_rows": sum(counts[f"dw.{name}"] for name in BRIDGE_TABLES),
        "row_reconciliations_failed": 0,
    }
    return counts, validation


def _successful_batch(
    connection: Any,
    source: dict[str, Any],
    ingestion_run_id: str,
    hashes: dict[str, str],
) -> int | None:
    row = connection.cursor().execute(
        """
        SELECT TOP (1) load_batch_id
        FROM audit.load_batch
        WHERE source_id = ?
          AND source_period = ?
          AND snapshot_date = ?
          AND ingestion_run_id = ?
          AND model_config_sha256 = ?
          AND physical_config_sha256 = ?
          AND ddl_bundle_sha256 = ?
          AND status = 'SUCCEEDED'
        ORDER BY load_batch_id DESC;
        """,
        source["source_id"],
        source["source_period"],
        source["snapshot_date"],
        ingestion_run_id,
        hashes["model_config"],
        hashes["physical_config"],
        hashes["ddl_bundle"],
    ).fetchone()
    return None if row is None else int(row[0])


def _warehouse_has_rows(connection: Any) -> bool:
    return bool(
        connection.cursor().execute(
            "SELECT CASE WHEN EXISTS (SELECT TOP (1) 1 FROM dw.fact_procurement_process) THEN 1 ELSE 0 END;"
        ).fetchval()
    )


def _start_audit_batch(
    connection: Any,
    source: dict[str, Any],
    ingestion_run_id: str,
    hashes: dict[str, str],
    load_mode: str,
    database: str,
    started_at: datetime,
) -> int:
    return int(
        connection.cursor().execute(
            """
            INSERT INTO audit.load_batch
            (
                source_id, source_period, snapshot_date, ingestion_run_id,
                archive_sha256, etl_summary_sha256, model_config_sha256,
                physical_config_sha256, ddl_bundle_sha256, load_mode, database_name,
                started_at_utc, status
            )
            OUTPUT INSERTED.load_batch_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'STARTED');
            """,
            source["source_id"],
            source["source_period"],
            source["snapshot_date"],
            ingestion_run_id,
            source["archive_sha256"],
            hashes["etl_summary"],
            hashes["model_config"],
            hashes["physical_config"],
            hashes["ddl_bundle"],
            load_mode,
            database,
            started_at,
        ).fetchval()
    )


def _finish_audit_batch(
    connection: Any,
    batch_id: int,
    status: str,
    *,
    completed_at: datetime,
    duration_seconds: float,
    staging_rows: int | None = None,
    dimension_rows: int | None = None,
    fact_rows: int | None = None,
    bridge_rows: int | None = None,
    error_message: str | None = None,
) -> None:
    connection.cursor().execute(
        """
        UPDATE audit.load_batch
        SET completed_at_utc = ?, status = ?, staging_rows = ?,
            dimension_rows = ?, fact_rows = ?, bridge_rows = ?,
            duration_seconds = ?, error_message = ?
        WHERE load_batch_id = ?;
        """,
        completed_at,
        status,
        staging_rows,
        dimension_rows,
        fact_rows,
        bridge_rows,
        round(duration_seconds, 4),
        None if error_message is None else error_message[:4000],
        batch_id,
    )


def _record_table_audits(
    connection: Any, batch_id: int, metrics: list[dict[str, Any]]
) -> None:
    cursor = connection.cursor()
    for metric in metrics:
        cursor.execute(
            """
            INSERT INTO audit.load_table
            (
                load_batch_id, layer, schema_name, table_name,
                expected_rows, loaded_rows, started_at_utc,
                completed_at_utc, duration_seconds, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCEEDED');
            """,
            batch_id,
            metric["layer"],
            metric["schema"],
            metric["table"],
            metric["expected_rows"],
            metric["loaded_rows"],
            metric["started_at_utc"],
            metric["completed_at_utc"],
            metric["duration_seconds"],
        )


def _clear_warehouse(connection: Any) -> None:
    cursor = connection.cursor()
    for table in [*BRIDGE_TABLES, *reversed(FACT_TABLES)]:
        cursor.execute(f"DELETE FROM [dw].{quote_identifier(table)};")
    for table in reversed(DIMENSION_TABLES):
        cursor.execute(f"DELETE FROM [dw].{quote_identifier(table)};")


def _validate_physical_columns(connection: Any, warehouse: WarehouseFrames) -> None:
    for table, frame in warehouse.all_tables.items():
        physical = table_columns(connection, "dw", table)
        logical = frame.columns.tolist()
        if physical != logical:
            raise ValueError(
                f"Physical columns differ for dw.{table}: "
                f"physical={physical}; frame={logical}"
            )


def _load_table(
    connection: Any,
    schema: str,
    table: str,
    frame: Any,
    batch_rows: int,
    layer: str,
) -> dict[str, Any]:
    started = _utc_now()
    clock = time.perf_counter()
    try:
        loaded = bulk_insert_frame(
            connection, schema, table, frame, batch_rows=batch_rows
        )
    except Exception as exc:
        raise RuntimeError(f"Load failed for {schema}.{table}: {exc}") from exc
    completed = _utc_now()
    return {
        "layer": layer,
        "schema": schema,
        "table": table,
        "expected_rows": len(frame),
        "loaded_rows": loaded,
        "started_at_utc": started,
        "completed_at_utc": completed,
        "duration_seconds": round(time.perf_counter() - clock, 4),
    }


def _write_json(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)


def run_load(args: argparse.Namespace) -> dict[str, Any]:
    started_at = _utc_now()
    total_clock = time.perf_counter()
    etl_summary = _load_json(args.etl_summary)
    dimensional_analysis = _load_json(args.dimensional_analysis)
    physical_config = _load_yaml(args.physical_config)
    model_config = _load_yaml(args.model)
    if len(model_config["dimensions"]) != 8 or len(model_config["facts"]) != 6:
        raise ValueError("The logical dimensional contract is not the approved Phase 6 model")

    hashes = {
        "etl_summary": sha256_text_file(args.etl_summary),
        "model_config": sha256_text_file(args.model),
        "physical_config": sha256_text_file(args.physical_config),
    }
    ddl_scripts = _physical_contract_paths(physical_config, args.physical_config)
    ddl_evidence, hashes["ddl_bundle"] = _ddl_evidence(ddl_scripts)
    if hashes["model_config"] != dimensional_analysis["source"]["model_config_sha256"]:
        raise ValueError("Dimensional analysis does not match the current model contract")
    if hashes["etl_summary"] != dimensional_analysis["source"]["etl_summary_sha256"]:
        raise ValueError("Dimensional analysis does not match the current ETL summary")

    source = etl_summary["source"]
    base_report = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "source_id": source["source_id"],
            "source_period": source["source_period"],
            "snapshot_date": source["snapshot_date"],
            "archive_sha256": source["archive_sha256"],
            "etl_summary": args.etl_summary.as_posix(),
            "etl_summary_sha256": hashes["etl_summary"],
            "model_config": args.model.as_posix(),
            "model_config_sha256": hashes["model_config"],
            "physical_config": args.physical_config.as_posix(),
            "physical_config_sha256": hashes["physical_config"],
            "ddl_bundle_sha256": hashes["ddl_bundle"],
            "ddl_scripts": ddl_evidence,
        },
    }
    if args.dry_run:
        data_settings = load_settings(args.env_file)
        build_clock = time.perf_counter()
        silver = load_silver_frames(data_settings, etl_summary)
        warehouse = build_warehouse_frames(
            silver, etl_summary["source"]["source_period"]
        )
        build_seconds = time.perf_counter() - build_clock
        build_validation = validate_warehouse_build(
            warehouse, dimensional_analysis
        )
        base_report["build_validation"] = build_validation
        base_report["table_rows"] = warehouse.row_counts
        base_report["summary"] = {
            "status": "DRY_RUN_PASS",
            "database_loaded": False,
            "staging_rows": sum(len(frame) for frame in silver.values()),
            **build_validation,
            "build_seconds": round(build_seconds, 4),
            "total_seconds": round(time.perf_counter() - total_clock, 4),
        }
        return base_report

    sql_settings = load_sql_server_settings(args.env_file)
    if args.create_database:
        database_created = ensure_database(sql_settings)
    else:
        database_created = False
    audit_connection = connect_sql_server(sql_settings, autocommit=True)
    batch_id: int | None = None
    try:
        execute_sql_scripts(audit_connection, ddl_scripts)
        existing_batch = _successful_batch(
            audit_connection,
            source,
            etl_summary["run"]["ingestion_run_id"],
            hashes,
        )
        if existing_batch is not None:
            existing_counts, existing_validation = _validate_existing_database(
                audit_connection, etl_summary, dimensional_analysis
            )
            base_report["database_validation"] = existing_validation
            base_report["table_rows"] = existing_counts
            base_report["summary"] = {
                "status": "SKIPPED_IDEMPOTENT",
                "database_loaded": True,
                "database_created": database_created,
                "load_batch_id": existing_batch,
                "reason": "An identical successful batch already exists.",
                "total_seconds": round(time.perf_counter() - total_clock, 4),
                **existing_validation,
            }
            return base_report

        populated = _warehouse_has_rows(audit_connection)
        if populated and not args.replace_snapshot:
            raise RuntimeError(
                "The warehouse already contains a different snapshot. "
                "Re-run with --replace-snapshot after reviewing the target."
            )
        data_settings = load_settings(args.env_file)
        build_clock = time.perf_counter()
        silver = load_silver_frames(data_settings, etl_summary)
        warehouse = build_warehouse_frames(
            silver, etl_summary["source"]["source_period"]
        )
        build_seconds = time.perf_counter() - build_clock
        build_validation = validate_warehouse_build(
            warehouse, dimensional_analysis
        )
        base_report["build_validation"] = build_validation
        base_report["table_rows"] = warehouse.row_counts
        load_mode = "replace_snapshot" if populated else "initial_snapshot"
        batch_id = _start_audit_batch(
            audit_connection,
            source,
            etl_summary["run"]["ingestion_run_id"],
            hashes,
            load_mode,
            sql_settings.database,
            started_at,
        )

        data_connection = connect_sql_server(sql_settings, autocommit=False)
        table_metrics: list[dict[str, Any]] = []
        try:
            lock_result = data_connection.cursor().execute(
                """
                DECLARE @result int;
                EXEC @result = sys.sp_getapplock
                    @Resource = N'ProcurementIntelligence_Phase7_Load',
                    @LockMode = N'Exclusive',
                    @LockOwner = N'Transaction',
                    @LockTimeout = 10000;
                SELECT @result;
                """
            ).fetchval()
            if int(lock_result) < 0:
                raise RuntimeError(f"Could not acquire SQL load lock: {lock_result}")
            if populated:
                _clear_warehouse(data_connection)
            _validate_physical_columns(data_connection, warehouse)

            batch_rows = int(physical_config["load"]["batch_rows"])
            table_metadata = {
                table["output_table"]: table for table in etl_summary["tables"]
            }
            for table_name, frame in silver.items():
                metadata = table_metadata[table_name]
                parquet_path = data_settings.interim_root / metadata[
                    "output_relative_path"
                ]
                arrow_schema = pq.read_schema(parquet_path)
                data_connection.cursor().execute(
                    staging_table_ddl("stg", table_name, arrow_schema)
                )
                table_metrics.append(
                    _load_table(
                        data_connection,
                        "stg",
                        table_name,
                        frame,
                        batch_rows,
                        "STG",
                    )
                )

            for table_name, frame in warehouse.all_tables.items():
                table_metrics.append(
                    _load_table(
                        data_connection,
                        "dw",
                        table_name,
                        frame,
                        batch_rows,
                        "DW",
                    )
                )

            for metric in table_metrics:
                actual = table_row_count(
                    data_connection, metric["schema"], metric["table"]
                )
                if actual != metric["expected_rows"]:
                    raise ValueError(
                        f"Row reconciliation failed for {metric['schema']}.{metric['table']}: "
                        f"expected {metric['expected_rows']}; actual {actual}"
                    )
            data_connection.commit()
        except Exception:
            data_connection.rollback()
            raise
        finally:
            data_connection.close()

        _record_table_audits(audit_connection, batch_id, table_metrics)
        duration = time.perf_counter() - total_clock
        staging_rows = sum(len(frame) for frame in silver.values())
        _finish_audit_batch(
            audit_connection,
            batch_id,
            "SUCCEEDED",
            completed_at=_utc_now(),
            duration_seconds=duration,
            staging_rows=staging_rows,
            dimension_rows=build_validation["dimension_rows"],
            fact_rows=build_validation["fact_rows"],
            bridge_rows=build_validation["bridge_rows"],
        )
        base_report["summary"] = {
            "status": "PASS",
            "database_loaded": True,
            "database_created": database_created,
            "database": sql_settings.database,
            "load_batch_id": batch_id,
            "load_mode": load_mode,
            "staging_tables": len(silver),
            "staging_rows": staging_rows,
            **build_validation,
            "build_seconds": round(build_seconds, 4),
            "sql_load_seconds": round(duration - build_seconds, 4),
            "total_seconds": round(duration, 4),
            "row_reconciliations_failed": 0,
        }
        base_report["table_load_metrics"] = [
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in metric.items()
            }
            for metric in table_metrics
        ]
        return base_report
    except Exception as exc:
        if batch_id is not None:
            _finish_audit_batch(
                audit_connection,
                batch_id,
                "FAILED",
                completed_at=_utc_now(),
                duration_seconds=time.perf_counter() - total_clock,
                error_message=str(exc),
            )
        raise
    finally:
        audit_connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load Silver Parquet and the governed dimensional model to SQL Server."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--etl-summary",
        type=Path,
        default=Path("reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json"),
    )
    parser.add_argument(
        "--dimensional-analysis",
        type=Path,
        default=Path(
            "reports/modeling/oece_ocds_seace_v3_2026_07_dimensional_model_analysis.json"
        ),
    )
    parser.add_argument(
        "--model", type=Path, default=Path("config/dimensional_model.yml")
    )
    parser.add_argument(
        "--physical-config", type=Path, default=Path("config/sql_server.yml")
    )
    parser.add_argument("--create-database", action="store_true")
    parser.add_argument("--replace-snapshot", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_load(args)
    _write_json(report, args.output)
    print(
        f"SQL Server load {report['summary']['status']}: "
        f"{report['summary'].get('staging_rows', 0)} staged rows; "
        f"{report['summary'].get('fact_rows', 0)} fact rows."
    )


if __name__ == "__main__":
    main()
