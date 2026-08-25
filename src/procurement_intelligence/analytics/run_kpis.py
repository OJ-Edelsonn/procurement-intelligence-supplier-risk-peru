"""Build the governed Phase 10 KPI evidence from the validated SQL warehouse."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyodbc
import yaml

from procurement_intelligence.analytics.run_eda import require_phase8_gate
from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.settings import load_sql_server_settings
from procurement_intelligence.validation.validate_sql_server import execute_sql


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_kpi_config(path: Path) -> dict[str, Any]:
    """Load and structurally validate the KPI semantic contract."""

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not {"kpis", "datasets", "catalog"} <= set(config):
        raise ValueError("KPI config must contain kpis, datasets and catalog sections.")
    metric_ids = [item["metric_id"] for item in config["catalog"]]
    blocked_ids = [item["metric_id"] for item in config.get("blocked_metrics", [])]
    dataset_ids = [item["dataset_id"] for item in config["datasets"]]
    if len(metric_ids) != len(set(metric_ids)):
        raise ValueError("Published KPI IDs must be unique.")
    if len(blocked_ids) != len(set(blocked_ids)):
        raise ValueError("Blocked KPI IDs must be unique.")
    if set(metric_ids) & set(blocked_ids):
        raise ValueError("A KPI cannot be published and blocked simultaneously.")
    if len(dataset_ids) != len(set(dataset_ids)):
        raise ValueError("KPI dataset IDs must be unique.")
    return config


def _read_sql(project_root: Path, relative_path: str) -> str:
    path = project_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing KPI SQL dataset: {path}")
    return path.read_text(encoding="utf-8-sig")


def _validate_columns(dataset: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"KPI dataset {dataset['dataset_id']} returned no rows.")
    missing = set(dataset["required_columns"]) - set(rows[0])
    if missing:
        raise ValueError(
            f"KPI dataset {dataset['dataset_id']} is missing columns: {sorted(missing)}"
        )


def _server_metadata(connection: pyodbc.Connection) -> dict[str, Any]:
    return execute_sql(
        connection,
        """
        SELECT DB_NAME() AS database_name,
               CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS product_version,
               CONVERT(nvarchar(128), SERVERPROPERTY('Edition')) AS edition;
        """,
    )[0]


def _as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def reconcile_with_eda(
    metric_map: dict[str, dict[str, Any]], eda_report: dict[str, Any]
) -> list[dict[str, Any]]:
    """Independently reconcile critical KPI results with committed Phase 9 evidence."""

    overview = eda_report["analysis"]["overview"]
    profiles = {
        item["stage"]: item for item in eda_report["analysis"]["amount_profiles"]
    }
    expected = {
        "procurement_processes": Decimal(str(overview["process_count"])),
        "tender_amount_pen": _as_decimal(profiles["tender"]["amount_sum"]),
        "award_count": Decimal(str(overview["award_count"])),
        "award_amount_pen": _as_decimal(profiles["award"]["amount_sum"]),
        "contract_count": Decimal(str(overview["contract_count"])),
        "contract_amount_pen": _as_decimal(profiles["contract"]["amount_sum"]),
        "active_buyers": Decimal(str(overview["known_buyer_count"])),
    }
    results: list[dict[str, Any]] = []
    for metric_id, expected_value in expected.items():
        actual = _as_decimal(metric_map[metric_id]["metric_value"])
        difference = actual - expected_value
        passed = abs(difference) <= Decimal("0.000001")
        results.append(
            {
                "metric_id": metric_id,
                "kpi_value": str(actual),
                "eda_value": str(expected_value),
                "difference": str(difference),
                "status": "PASS" if passed else "FAIL",
            }
        )
    return results


def _money(value: Any) -> str:
    return f"S/ {float(value):,.2f}"


def _metric_display(row: dict[str, Any]) -> str:
    if row["unit"] == "PEN":
        return _money(row["metric_value"])
    if row["unit"] == "percent":
        return f"{float(row['metric_value']):,.4f}%"
    if row["unit"] == "count":
        return f"{int(Decimal(str(row['metric_value']))):,}"
    return f"{float(row['metric_value']):,.4f}"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    def safe(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(safe(value) for value in row) + " |" for row in rows],
        ]
    )


def build_markdown(report: dict[str, Any]) -> str:
    metrics = report["analysis"]["portfolio_kpis"]
    rankings = report["analysis"]["rankings"]
    return "\n".join(
        [
            "# KPIs gobernados — OECE/SEACE V3, source_period 2026-07",
            "",
            "> Los KPIs describen un único periodo fuente. Monto licitado, adjudicado y contractual pertenecen a hechos diferentes y no se suman.",
            "",
            "## Portafolio publicable",
            "",
            _table(
                ["KPI", "Valor", "Numerador/denominador", "Dominio"],
                [
                    [
                        item["label"],
                        _metric_display(item),
                        f"{item['numerator']:,}/{item['denominator']:,}",
                        item["domain"],
                    ]
                    for item in metrics
                ],
            ),
            "",
            "## Top compradores por monto licitado PEN",
            "",
            _table(
                ["Comprador", "Procesos", "Monto", "Ticket promedio"],
                [
                    [row["buyer_name"], row["process_count"], _money(row["tender_amount_pen"]), _money(row["average_tender_ticket_pen"])]
                    for row in rankings["buyers"][:10]
                ],
            ),
            "",
            "## Top proveedores por monto adjudicado atribuible PEN",
            "",
            _table(
                ["Proveedor", "Adjudicaciones", "Compradores", "Monto", "Ticket promedio"],
                [
                    [row["supplier_name"], row["award_count"], row["buyer_count"], _money(row["award_amount_pen"]), _money(row["average_award_ticket_pen"])]
                    for row in rankings["suppliers"][:10]
                ],
            ),
            "",
            "## Top categorías por monto de ítems adjudicados PEN",
            "",
            _table(
                ["Código", "Categoría", "Ítems", "Compradores", "Monto"],
                [
                    [row["classification_code"], row["classification_description"], row["award_item_count"], row["buyer_count"], _money(row["award_item_amount_pen"])]
                    for row in rankings["categories"][:10]
                ],
            ),
            "",
            "## KPIs bloqueados",
            "",
            *[
                f"- `{item['metric_id']}`: {item['reason']}"
                for item in report["analysis"]["blocked_metrics"]
            ],
            "",
            "## Reconciliación",
            "",
            f"Las {len(report['analysis']['reconciliations'])} métricas críticas coinciden con la evidencia de Fase 9. No se calculan crecimiento, YoY, HHI ni scores en esta fase.",
            "",
        ]
    )


def _project_path(project_root: Path, override: Path | None, default: str) -> Path:
    path = override if override is not None else Path(default)
    return path if path.is_absolute() else project_root / path


def run_kpis(args: argparse.Namespace) -> dict[str, Any]:
    """Execute, validate and persist the Phase 10 governed KPI package."""

    started = time.perf_counter()
    config_path = args.config.resolve()
    project_root = config_path.parent.parent
    config = load_kpi_config(config_path)
    settings = config["kpis"]
    phase8_path = project_root / settings["phase8_gate"]
    phase9_path = project_root / settings["phase9_gate"]
    phase8 = _load_json(phase8_path)
    phase9 = _load_json(phase9_path)
    require_phase8_gate(phase8)
    if phase9["summary"]["status"] != "PASS":
        raise ValueError("Phase 9 EDA is not approved for KPI consumption.")
    if phase9["source"]["source_period"] != settings["source_period"]:
        raise ValueError("KPI and EDA source periods differ.")

    sql_settings = load_sql_server_settings(args.env_file)
    connection = pyodbc.connect(
        sql_settings.connection_string(), autocommit=True, timeout=15
    )
    datasets: dict[str, list[dict[str, Any]]] = {}
    try:
        connection.timeout = int(args.command_timeout_seconds)
        server = _server_metadata(connection)
        for dataset in config["datasets"]:
            rows = execute_sql(connection, _read_sql(project_root, dataset["sql"]))
            _validate_columns(dataset, rows)
            datasets[dataset["dataset_id"]] = rows
    finally:
        connection.close()

    catalog = {item["metric_id"]: item for item in config["catalog"]}
    portfolio_rows = datasets["portfolio_kpis"]
    metric_map = {row["metric_id"]: row for row in portfolio_rows}
    if len(metric_map) != len(portfolio_rows):
        raise ValueError("SQL returned duplicate KPI IDs.")
    if set(metric_map) != set(catalog):
        raise ValueError(
            f"SQL/catalog KPI mismatch: SQL-only={sorted(set(metric_map)-set(catalog))}; "
            f"catalog-only={sorted(set(catalog)-set(metric_map))}"
        )
    enriched: list[dict[str, Any]] = []
    for metadata in config["catalog"]:
        row = metric_map[metadata["metric_id"]]
        if row["unit"] != metadata["unit"]:
            raise ValueError(f"Unit mismatch for KPI {row['metric_id']}")
        enriched.append({**metadata, **row})

    reconciliations = reconcile_with_eda(metric_map, phase9)
    failed = [item for item in reconciliations if item["status"] != "PASS"]
    if failed:
        raise ValueError(f"KPI-to-EDA reconciliation failed: {failed}")

    output_json = _project_path(project_root, args.output, settings["outputs"]["json"])
    output_md = _project_path(
        project_root, args.markdown_output, settings["outputs"]["markdown"]
    )
    dax_path = project_root / settings["dax_catalog"]
    sql_hashes = {
        item["dataset_id"]: {
            "path": item["sql"],
            "sha256": sha256_text_file(project_root / item["sql"]),
        }
        for item in config["datasets"]
    }
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "governed_kpis",
        "source": {
            "source_id": phase9["source"]["source_id"],
            "source_period": settings["source_period"],
            "snapshot_date": phase9["source"]["snapshot_date"],
            "load_batch_id": phase9["source"]["load_batch_id"],
            "database_name": server["database_name"],
            "sql_server_version": server["product_version"],
            "phase8_gate": settings["phase8_gate"],
            "phase8_gate_sha256": sha256_text_file(phase8_path),
            "phase9_gate": settings["phase9_gate"],
            "phase9_gate_sha256": sha256_text_file(phase9_path),
            "kpi_config": config_path.relative_to(project_root).as_posix(),
            "kpi_config_sha256": sha256_text_file(config_path),
            "kpi_runner_sha256": sha256_text_file(Path(__file__)),
            "dax_catalog": settings["dax_catalog"],
            "dax_catalog_sha256": sha256_text_file(dax_path),
            "sql_datasets": sql_hashes,
        },
        "summary": {
            "status": "PASS",
            "datasets_executed": len(datasets),
            "published_kpis": len(enriched),
            "blocked_kpis": len(config["blocked_metrics"]),
            "reconciliations_passed": len(reconciliations),
            "reconciliations_failed": len(failed),
            "source_period_count": 1,
            "duration_seconds": round(time.perf_counter() - started, 4),
        },
        "analysis": {
            "portfolio_kpis": enriched,
            "rankings": {
                "buyers": datasets["buyer_kpis"][: int(settings["top_n"])],
                "suppliers": datasets["supplier_kpis"][: int(settings["top_n"])],
                "categories": datasets["category_kpis"][: int(settings["top_n"])],
            },
            "blocked_metrics": config["blocked_metrics"],
            "reconciliations": reconciliations,
        },
        "artifacts": {
            "json": output_json.relative_to(project_root).as_posix(),
            "markdown": output_md.relative_to(project_root).as_posix(),
            "dax": settings["dax_catalog"],
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(build_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--config", type=Path, default=Path("config/kpis.yml"))
    parser.add_argument("--command-timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args()


def main() -> None:
    report = run_kpis(parse_args())
    summary = report["summary"]
    print(
        f"KPI {summary['status']}: {summary['published_kpis']} published; "
        f"{summary['blocked_kpis']} blocked; "
        f"{summary['reconciliations_passed']} reconciled."
    )


if __name__ == "__main__":
    main()
