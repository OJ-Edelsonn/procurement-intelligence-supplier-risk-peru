"""Deploy the governed Power BI semantic layer to local SQL Server."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from procurement_intelligence.extraction.download_ocds import (
    sha256_file,
    sha256_text_file,
)
from procurement_intelligence.loading.sql_server import (
    bulk_insert_frame,
    connect_sql_server,
    execute_sql_scripts,
)
from procurement_intelligence.settings import load_sql_server_settings
from procurement_intelligence.validation.validate_sql_server import execute_sql


GATE_STATUSES = {
    "phase10": "PASS",
    "phase11": "PASS",
    "phase12": "PASS_PILOT",
    "phase13": "PASS_LIMITED",
}


def load_powerbi_config(path: Path) -> dict[str, Any]:
    """Load and validate the Power BI deployment contract."""

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not {"powerbi", "tables", "pages"} <= set(
        config
    ):
        raise ValueError("Power BI config must contain powerbi, tables and pages.")
    settings = config["powerbi"]
    if settings["storage_mode"] != "import":
        raise ValueError("The pilot Power BI model must use Import mode.")
    table_names = [item["model_name"] for item in config["tables"]]
    if len(table_names) != len(set(table_names)):
        raise ValueError("Power BI model table names must be unique.")
    page_ids = [item["page_id"] for item in config["pages"]]
    if len(page_ids) != len(set(page_ids)):
        raise ValueError("Power BI page IDs must be unique.")
    if len(config["pages"]) != 5:
        raise ValueError("The approved pilot must define exactly five report pages.")
    return config


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_upstream_gates(root: Path, settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Reject a semantic deployment when an analytical gate is stale or failed."""

    evidence: list[dict[str, Any]] = []
    for phase, relative in settings["upstream_gates"].items():
        path = root / relative
        report = _load_json(path)
        expected = GATE_STATUSES[phase]
        actual = report["summary"]["status"]
        if actual != expected:
            raise ValueError(f"{phase} gate status {actual!r}; expected {expected!r}.")
        evidence.append(
            {
                "phase": phase,
                "path": relative,
                "sha256": sha256_text_file(path),
                "status": actual,
            }
        )
    return evidence


def _score_frame(path: Path, table_name: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty or frame.columns.duplicated().any():
        raise ValueError(f"Invalid Power BI score input: {path}")
    boolean_columns = [column for column in frame if column.startswith("is_")]
    for column in boolean_columns:
        frame[column] = frame[column].astype(bool)
    count_like = [
        column
        for column in frame
        if (column.endswith("_count") and not column.startswith("effective_"))
        or column.startswith("rank_")
        or column in {"category_key", "supplier_key", "maximum_absolute_rank_shift"}
    ]
    for column in count_like:
        frame[column] = pd.to_numeric(frame[column], errors="raise").round().astype("int64")
    if not frame["score_baseline"].between(0, 100).all():
        raise ValueError(f"Out-of-range score in {table_name}.")
    return frame


def _replace_table(
    connection: Any,
    table_name: str,
    frame: pd.DataFrame,
    source_relative_path: str,
    source_sha256: str,
) -> int:
    cursor = connection.cursor()
    cursor.execute(f"TRUNCATE TABLE bi.[{table_name}];")
    inserted = bulk_insert_frame(
        connection,
        "bi",
        table_name,
        frame,
        batch_rows=500,
    )
    cursor.execute(
        """
        DELETE FROM bi.semantic_load_audit WHERE artifact_name = ?;
        INSERT INTO bi.semantic_load_audit
            (artifact_name, source_relative_path, source_sha256, source_rows, loaded_at_utc)
        VALUES (?, ?, ?, ?, SYSUTCDATETIME());
        """,
        table_name,
        table_name,
        source_relative_path,
        source_sha256,
        inserted,
    )
    return inserted


def deploy_semantic_layer(
    config_path: Path,
    env_file: Path,
    output_override: Path | None = None,
) -> dict[str, Any]:
    """Create BI objects, load both scores, and validate Power BI query surfaces."""

    started = time.perf_counter()
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = load_powerbi_config(config_path)
    settings = config["powerbi"]
    gates = validate_upstream_gates(root, settings)
    ddl_path = root / settings["ddl"]

    score_frames: dict[str, pd.DataFrame] = {}
    score_evidence: list[dict[str, Any]] = []
    for table_name, relative in settings["score_inputs"].items():
        path = root / relative
        frame = _score_frame(path, table_name)
        score_frames[table_name] = frame
        score_evidence.append(
            {
                "table": table_name,
                "source": relative,
                "rows": len(frame),
                "sha256": sha256_file(path),
            }
        )

    sql_settings = load_sql_server_settings(env_file)
    connection = connect_sql_server(sql_settings, timeout_seconds=20)
    try:
        connection.timeout = 180
        execute_sql_scripts(connection, [ddl_path])
        loaded_rows: dict[str, int] = {}
        for item in score_evidence:
            loaded_rows[item["table"]] = _replace_table(
                connection,
                item["table"],
                score_frames[item["table"]],
                item["source"],
                item["sha256"],
            )
        connection.commit()

        overview = execute_sql(connection, "SELECT * FROM bi.vw_executive_overview;")[0]
        object_counts = execute_sql(
            connection,
            """
            SELECT
              (SELECT COUNT(*) FROM sys.tables WHERE schema_id = SCHEMA_ID(N'bi')) AS table_count,
              (SELECT COUNT(*) FROM sys.views WHERE schema_id = SCHEMA_ID(N'bi')) AS view_count;
            """,
        )[0]
        query_surfaces = {}
        for table in config["tables"]:
            source = table["source_object"]
            row = execute_sql(
                connection,
                f"SELECT COUNT_BIG(*) AS row_count FROM bi.[{source}];",
            )[0]
            query_surfaces[source] = int(row["row_count"])
        audit_rows = execute_sql(
            connection,
            "SELECT artifact_name, source_sha256, source_rows FROM bi.semantic_load_audit ORDER BY artifact_name;",
        )
    finally:
        connection.close()

    validations = [
        {
            "rule": "score_rows_reconciled",
            "status": "PASS"
            if loaded_rows == {item["table"]: item["rows"] for item in score_evidence}
            else "FAIL",
        },
        {
            "rule": "semantic_objects_created",
            "status": "PASS"
            if int(object_counts["table_count"]) == 3
            and int(object_counts["view_count"]) == 10
            else "FAIL",
        },
        {
            "rule": "executive_score_counts",
            "status": "PASS"
            if int(overview["eligible_markets"]) == 87
            and int(overview["scored_suppliers"]) == 179
            else "FAIL",
        },
        {
            "rule": "all_query_surfaces_nonempty",
            "status": "PASS" if all(value > 0 for value in query_surfaces.values()) else "FAIL",
        },
    ]
    failed = [item for item in validations if item["status"] != "PASS"]
    report = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "powerbi_semantic_sql_layer",
        "source": {
            "config": config_path.relative_to(root).as_posix(),
            "config_sha256": sha256_text_file(config_path),
            "ddl": settings["ddl"],
            "ddl_sha256": sha256_text_file(ddl_path),
            "upstream_gates": gates,
            "score_inputs": score_evidence,
            "server_alias": settings["server"],
            "database": settings["database"],
        },
        "summary": {
            "status": "PASS" if not failed else "FAIL",
            "tables": int(object_counts["table_count"]),
            "views": int(object_counts["view_count"]),
            "score_rows_loaded": sum(loaded_rows.values()),
            "query_surfaces": len(query_surfaces),
            "validations_passed": len(validations) - len(failed),
            "validations_failed": len(failed),
            "duration_seconds": round(time.perf_counter() - started, 4),
        },
        "analysis": {
            "executive_overview": overview,
            "loaded_rows": loaded_rows,
            "query_surface_rows": query_surfaces,
            "audit_rows": audit_rows,
            "validations": validations,
        },
    }
    if failed:
        raise ValueError(f"Power BI semantic layer validation failed: {failed}")
    output = output_override or root / settings["semantic_load_output"]
    output = output if output.is_absolute() else root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/powerbi_dashboard.yml"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = deploy_semantic_layer(args.config, args.env_file, args.output)
    summary = report["summary"]
    print(
        f"Power BI semantic layer {summary['status']}: "
        f"{summary['tables']} tables, {summary['views']} views, "
        f"{summary['score_rows_loaded']} score rows."
    )


if __name__ == "__main__":
    main()
