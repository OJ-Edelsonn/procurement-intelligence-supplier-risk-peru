"""Calculate reproducible supplier concentration by governed standard category."""

from __future__ import annotations

import argparse
import json
import math
import textwrap
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyodbc  # noqa: E402
import yaml  # noqa: E402

from procurement_intelligence.extraction.download_ocds import (  # noqa: E402
    sha256_file,
    sha256_text_file,
)
from procurement_intelligence.settings import load_sql_server_settings  # noqa: E402
from procurement_intelligence.validation.validate_sql_server import (  # noqa: E402
    execute_sql,
)


FIGURES = (
    "01_hhi_distribution.png",
    "02_largest_markets.png",
    "03_market_scale_effective_suppliers.png",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_concentration_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not {"concentration", "datasets"} <= set(config):
        raise ValueError("Concentration config must contain concentration and datasets.")
    dataset_ids = [item["dataset_id"] for item in config["datasets"]]
    if len(dataset_ids) != len(set(dataset_ids)):
        raise ValueError("Concentration dataset IDs must be unique.")
    thresholds = config["concentration"]["eligibility"]
    for key in ("minimum_suppliers", "minimum_buyers", "minimum_award_items"):
        if int(thresholds[key]) < 1:
            raise ValueError(f"Eligibility threshold {key} must be positive.")
    coverage = float(thresholds["minimum_attributable_amount_coverage_pct"])
    if not 0 <= coverage <= 100:
        raise ValueError("Coverage threshold must be between 0 and 100.")
    return config


def _read_sql(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Missing concentration SQL: {path}")
    return path.read_text(encoding="utf-8-sig")


def _validate_columns(dataset: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Concentration dataset {dataset['dataset_id']} returned no rows.")
    missing = set(dataset["required_columns"]) - set(rows[0])
    if missing:
        raise ValueError(f"Missing columns in {dataset['dataset_id']}: {sorted(missing)}")


def validate_share_math(
    markets: list[dict[str, Any]], shares: list[dict[str, Any]], tolerance: float = 0.001
) -> list[dict[str, Any]]:
    """Recompute share sums and HHI independently from supplier-level rows."""

    by_market = {int(row["category_key"]): row for row in markets}
    frame = pd.DataFrame(shares)
    results: list[dict[str, Any]] = []
    for category_key, group in frame.groupby("category_key"):
        key = int(category_key)
        market = by_market[key]
        values = pd.to_numeric(group["supplier_share_pct"], errors="raise")
        share_sum = float(values.sum())
        hhi_python = float(np.square(values).sum())
        hhi_sql = float(market["hhi"])
        passed = (
            abs(share_sum - 100.0) <= tolerance
            and abs(hhi_python - hhi_sql) <= tolerance
            and int(market["supplier_count"]) == len(group)
        )
        results.append(
            {
                "category_key": key,
                "share_sum_pct": round(share_sum, 6),
                "hhi_sql": round(hhi_sql, 6),
                "hhi_python": round(hhi_python, 6),
                "supplier_count_sql": int(market["supplier_count"]),
                "supplier_rows": len(group),
                "status": "PASS" if passed else "FAIL",
            }
        )
    missing = set(by_market) - set(frame["category_key"].astype(int))
    for key in sorted(missing):
        results.append({"category_key": key, "status": "FAIL", "reason": "no shares"})
    return results


def _server_metadata(connection: pyodbc.Connection) -> dict[str, Any]:
    return execute_sql(
        connection,
        "SELECT DB_NAME() AS database_name, CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS product_version;",
    )[0]


def _figure_path(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def _plot_hhi(markets: pd.DataFrame, directory: Path, dpi: int) -> Path:
    eligible = markets[markets["is_analysis_eligible"].astype(bool)]
    path = _figure_path(directory, FIGURES[0])
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.hist(eligible["hhi"].astype(float), bins=25, color="#2563EB", edgecolor="white")
    ax.set(title="Distribución HHI — mercados elegibles", xlabel="HHI (0–10,000)", ylabel="Categorías")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _short(value: str, width: int = 44) -> str:
    return textwrap.shorten(str(value), width=width, placeholder="…")


def _plot_largest(markets: pd.DataFrame, directory: Path, dpi: int) -> Path:
    top = markets[markets["is_analysis_eligible"].astype(bool)].nlargest(
        15, "attributable_amount_pen"
    )
    top = top.sort_values("attributable_amount_pen")
    path = _figure_path(directory, FIGURES[1])
    fig, ax = plt.subplots(figsize=(12, 7.5))
    bars = ax.barh(
        [_short(value) for value in top["classification_description"]],
        top["attributable_amount_pen"].astype(float) / 1_000_000,
        color="#0F766E",
    )
    for bar, hhi in zip(bars, top["hhi"], strict=True):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f" HHI {float(hhi):,.0f}", va="center", fontsize=8)
    ax.set(title="Mayores mercados elegibles por monto atribuible", xlabel="Monto de ítems adjudicados (S/ millones)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _plot_scale(markets: pd.DataFrame, directory: Path, dpi: int) -> Path:
    eligible = markets[markets["is_analysis_eligible"].astype(bool)]
    path = _figure_path(directory, FIGURES[2])
    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(
        eligible["attributable_amount_pen"].astype(float),
        eligible["effective_supplier_count"].astype(float),
        c=eligible["top1_share_pct"].astype(float),
        cmap="viridis_r",
        alpha=0.75,
        edgecolor="white",
        linewidth=0.4,
    )
    ax.set_xscale("log")
    ax.set(title="Escala del mercado y número efectivo de proveedores", xlabel="Monto atribuible PEN (escala log)", ylabel="Número efectivo de proveedores")
    ax.grid(alpha=0.25)
    fig.colorbar(scatter, ax=ax, label="Top 1 share (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _money(value: Any) -> str:
    return f"S/ {float(value):,.2f}"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    safe_rows = [[str(value).replace("|", "\\|").replace("\n", " ") for value in row] for row in rows]
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(row) + " |" for row in safe_rows],
        ]
    )


def build_markdown(report: dict[str, Any]) -> str:
    analysis = report["analysis"]
    summary = report["summary"]
    return "\n".join(
        [
            "# Market Concentration — OECE/SEACE V3, source_period 2026-07",
            "",
            "> HHI y participaciones son descripciones del snapshot por categoría estándar. No constituyen una conclusión legal, anticompetitiva ni de conducta del proveedor.",
            "",
            "## Cobertura",
            "",
            _table(
                ["Métrica", "Resultado"],
                [
                    ["Mercados con monto atribuible", f"{summary['markets_analyzed']:,}"],
                    ["Mercados elegibles", f"{summary['eligible_markets']:,}"],
                    ["Mercados no elegibles", f"{summary['ineligible_markets']:,}"],
                    ["Cobertura monetaria atribuible", f"{summary['attributable_amount_coverage_pct']:.4f}%"],
                    ["Validaciones HHI", f"{summary['share_validations_passed']:,}/{summary['markets_analyzed']:,}"],
                ],
            ),
            "",
            "## Mayores mercados elegibles",
            "",
            _table(
                ["Código", "Categoría", "Monto", "Proveedores", "Top 1", "HHI", "Prov. efectivos"],
                [
                    [row["classification_code"], row["classification_description"], _money(row["attributable_amount_pen"]), row["supplier_count"], f"{float(row['top1_share_pct']):.2f}%", f"{float(row['hhi']):,.2f}", f"{float(row['effective_supplier_count']):.2f}"]
                    for row in analysis["largest_eligible_markets"][:10]
                ],
            ),
            "",
            "## Mayor HHI entre mercados elegibles",
            "",
            _table(
                ["Código", "Categoría", "Monto", "Proveedores", "Top 1", "HHI"],
                [
                    [row["classification_code"], row["classification_description"], _money(row["attributable_amount_pen"]), row["supplier_count"], f"{float(row['top1_share_pct']):.2f}%", f"{float(row['hhi']):,.2f}"]
                    for row in analysis["highest_hhi_eligible_markets"][:10]
                ],
            ),
            "",
            "## Interpretación",
            "",
            "- Top N share muestra qué porcentaje del monto atribuible corresponde a los N mayores proveedores.",
            "- HHI suma los cuadrados de las participaciones porcentuales: aumenta cuando el monto se concentra.",
            "- El número efectivo de proveedores es `10,000 / HHI`; traduce la distribución a un equivalente de proveedores de igual tamaño.",
            "- La elegibilidad exige al menos 3 proveedores, 2 compradores, 5 ítems y 95% de cobertura monetaria atribuible.",
            "- No se usan bandas legales ni se infiere colusión, irregularidad o riesgo del proveedor.",
            "",
            "## Figuras",
            "",
            *[f"![{Path(path).stem}](figures/{Path(path).name})" for path in report["artifacts"]["figures"]],
            "",
        ]
    )


def _project_path(root: Path, override: Path | None, default: str) -> Path:
    path = override if override is not None else Path(default)
    return path if path.is_absolute() else root / path


def run_concentration(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    config_path = args.config.resolve()
    root = config_path.parent.parent
    config = load_concentration_config(config_path)
    settings = config["concentration"]
    gate_path = root / settings["phase10_gate"]
    gate = _load_json(gate_path)
    if gate["summary"]["status"] != "PASS" or gate["summary"]["reconciliations_failed"]:
        raise ValueError("Phase 10 KPI gate is not eligible for concentration analysis.")
    if gate["source"]["source_period"] != settings["source_period"]:
        raise ValueError("Concentration and KPI source periods differ.")

    sql_settings = load_sql_server_settings(args.env_file)
    connection = pyodbc.connect(sql_settings.connection_string(), autocommit=True, timeout=15)
    datasets: dict[str, list[dict[str, Any]]] = {}
    try:
        connection.timeout = int(args.command_timeout_seconds)
        server = _server_metadata(connection)
        for dataset in config["datasets"]:
            rows = execute_sql(connection, _read_sql(root, dataset["sql"]))
            _validate_columns(dataset, rows)
            datasets[dataset["dataset_id"]] = rows
    finally:
        connection.close()

    markets = datasets["category_concentration"]
    shares = datasets["category_supplier_shares"]
    validations = validate_share_math(markets, shares)
    failed = [item for item in validations if item["status"] != "PASS"]
    if failed:
        raise ValueError(f"Supplier-share validation failed: {failed[:5]}")

    frame = pd.DataFrame(markets)
    numeric_columns = [
        "award_item_count", "buyer_count", "supplier_count", "total_category_amount_pen",
        "attributable_amount_pen", "attributable_amount_coverage_pct", "top1_share_pct",
        "top3_share_pct", "top5_share_pct", "top10_share_pct", "hhi", "effective_supplier_count",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    eligible = frame[frame["is_analysis_eligible"].astype(bool)].copy()
    total_amount = Decimal(str(frame["total_category_amount_pen"].sum()))
    attributable_amount = Decimal(str(frame["attributable_amount_pen"].sum()))
    coverage = float(100 * attributable_amount / total_amount) if total_amount else 0.0
    largest = eligible.nlargest(int(settings["top_n"]), "attributable_amount_pen").to_dict("records")
    highest = eligible.nlargest(int(settings["top_n"]), "hhi").to_dict("records")

    output_json = _project_path(root, args.output, settings["outputs"]["json"])
    output_md = _project_path(root, args.markdown_output, settings["outputs"]["markdown"])
    figures_dir = _project_path(root, args.figures_dir, settings["outputs"]["figures"])
    dpi = int(settings["figure_dpi"])
    figures = [
        _plot_hhi(frame, figures_dir, dpi),
        _plot_largest(frame, figures_dir, dpi),
        _plot_scale(frame, figures_dir, dpi),
    ]
    dax_path = root / settings["dax_catalog"]
    sql_hashes = {
        item["dataset_id"]: {"path": item["sql"], "sha256": sha256_text_file(root / item["sql"])}
        for item in config["datasets"]
    }
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "market_concentration",
        "source": {
            "source_id": gate["source"]["source_id"],
            "source_period": settings["source_period"],
            "snapshot_date": gate["source"]["snapshot_date"],
            "load_batch_id": gate["source"]["load_batch_id"],
            "database_name": server["database_name"],
            "sql_server_version": server["product_version"],
            "phase10_gate": settings["phase10_gate"],
            "phase10_gate_sha256": sha256_text_file(gate_path),
            "config": config_path.relative_to(root).as_posix(),
            "config_sha256": sha256_text_file(config_path),
            "runner_sha256": sha256_text_file(Path(__file__)),
            "dax_catalog": settings["dax_catalog"],
            "dax_catalog_sha256": sha256_text_file(dax_path),
            "sql_datasets": sql_hashes,
        },
        "summary": {
            "status": "PASS",
            "datasets_executed": len(datasets),
            "markets_analyzed": len(frame),
            "eligible_markets": len(eligible),
            "ineligible_markets": len(frame) - len(eligible),
            "singleton_supplier_markets": int((frame["supplier_count"] == 1).sum()),
            "total_known_category_amount_pen": str(total_amount),
            "attributable_amount_pen": str(attributable_amount),
            "attributable_amount_coverage_pct": round(coverage, 6),
            "share_validations_passed": len(validations),
            "share_validations_failed": len(failed),
            "figures_generated": len(figures),
            "duration_seconds": round(time.perf_counter() - started, 4),
        },
        "analysis": {
            "market_definition": settings["market_definition"],
            "eligibility": settings["eligibility"],
            "eligible_hhi_median": round(float(eligible["hhi"].median()), 6),
            "eligible_effective_suppliers_median": round(float(eligible["effective_supplier_count"].median()), 6),
            "largest_eligible_markets": largest,
            "highest_hhi_eligible_markets": highest,
            "all_markets": markets,
            "share_validations": validations,
            "limitations": [
                "Single source period; persistence and trend cannot be inferred.",
                "Unknown standard categories are outside the market definition.",
                "Only safely attributable positive PEN amounts enter supplier shares.",
                "The indicator is descriptive, not a legal or misconduct determination.",
            ],
        },
        "artifacts": {
            "json": output_json.relative_to(root).as_posix(),
            "markdown": output_md.relative_to(root).as_posix(),
            "figures": [path.relative_to(root).as_posix() for path in figures],
            "dax": settings["dax_catalog"],
            "figure_evidence": [
                {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
                for path in figures
            ],
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(build_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--config", type=Path, default=Path("config/market_concentration.yml"))
    parser.add_argument("--command-timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--figures-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    report = run_concentration(parse_args())
    summary = report["summary"]
    print(
        f"Concentration {summary['status']}: {summary['markets_analyzed']} markets; "
        f"{summary['eligible_markets']} eligible; {summary['share_validations_passed']} HHI checks."
    )


if __name__ == "__main__":
    main()
