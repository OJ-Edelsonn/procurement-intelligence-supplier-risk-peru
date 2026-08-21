"""Run reproducible exploratory analysis over the validated SQL warehouse."""

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

STAGE_LABELS = {
    "tender": "Licitación",
    "award": "Adjudicación",
    "contract": "Contrato",
}
STAGE_COLORS = {
    "tender": "#2563EB",
    "award": "#0F766E",
    "contract": "#D97706",
}
FIGURE_NAMES = (
    "01_lifecycle_coverage.png",
    "02_monthly_activity.png",
    "03_amount_distributions.png",
    "04_top_buyers_tender.png",
    "05_top_suppliers_award.png",
    "06_top_categories_award_items.png",
    "07_competition_distribution.png",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_eda_config(path: Path) -> dict[str, Any]:
    """Load and validate the governed EDA contract."""

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "eda" not in config or "datasets" not in config:
        raise ValueError("EDA config must contain eda and datasets sections.")
    dataset_ids = [dataset["dataset_id"] for dataset in config["datasets"]]
    if len(dataset_ids) != len(set(dataset_ids)):
        raise ValueError("EDA dataset IDs must be unique.")
    if int(config["eda"]["top_n"]) < 1:
        raise ValueError("EDA top_n must be positive.")
    return config


def require_phase8_gate(report: dict[str, Any]) -> None:
    """Block EDA when the SQL validation gate is not promotion eligible."""

    summary = report.get("summary", {})
    if not summary.get("promotion_eligible") or int(
        summary.get("blocking_failures", 1)
    ):
        raise ValueError("Phase 8 validation is not promotion eligible for EDA.")
    for field in (
        "row_reconciliations_failed",
        "financial_reconciliations_failed",
        "artifact_reconciliations_failed",
        "python_sql_warning_reconciliations_failed",
    ):
        if int(summary.get(field, 1)):
            raise ValueError(f"Phase 8 gate contains failed reconciliation: {field}")


def _read_sql(project_root: Path, relative_path: str) -> str:
    path = project_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing EDA SQL dataset: {path}")
    return path.read_text(encoding="utf-8-sig")


def _validate_dataset_columns(
    dataset_id: str, rows: list[dict[str, Any]], required_columns: list[str]
) -> None:
    if not rows:
        raise ValueError(f"EDA dataset {dataset_id} returned no rows.")
    missing = set(required_columns) - set(rows[0])
    if missing:
        raise ValueError(
            f"EDA dataset {dataset_id} is missing columns: {sorted(missing)}"
        )


def amount_profile(rows: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    """Describe a native-grain PEN amount distribution without removing values."""

    values = [
        Decimal(str(row["amount_pen"]))
        for row in rows
        if row["stage"] == stage and row["amount_pen"] is not None
    ]
    total_rows = sum(row["stage"] == stage for row in rows)
    if not values:
        raise ValueError(f"No non-null PEN observations for {stage}.")
    numeric = np.asarray([float(value) for value in values], dtype=float)
    q25, q50, q75, q90, q95, q99 = np.quantile(
        numeric, [0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    )
    iqr = q75 - q25
    upper_fence = q75 + 1.5 * iqr
    return {
        "stage": stage,
        "rows_total": total_rows,
        "rows_with_pen": len(values),
        "missing_pen_rows": total_rows - len(values),
        "zero_rows": sum(value == 0 for value in values),
        "positive_rows": sum(value > 0 for value in values),
        "amount_sum": str(sum(values, Decimal("0"))),
        "minimum": str(min(values)),
        "mean": round(float(np.mean(numeric)), 4),
        "p25": round(float(q25), 4),
        "median": round(float(q50), 4),
        "p75": round(float(q75), 4),
        "p90": round(float(q90), 4),
        "p95": round(float(q95), 4),
        "p99": round(float(q99), 4),
        "maximum": str(max(values)),
        "iqr_upper_fence": round(float(upper_fence), 4),
        "high_outlier_rows_iqr": int(np.sum(numeric > upper_fence)),
        "rows_above_p99": int(np.sum(numeric > q99)),
    }


def competition_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe observed tenderer counts and lifecycle presence per process."""

    frame = pd.DataFrame(rows)
    observed = pd.to_numeric(frame["tenderer_count_observed"], errors="raise")
    declared = pd.to_numeric(frame["tenderer_count_declared"], errors="coerce")
    award = pd.to_numeric(frame["award_count"], errors="raise")
    contract = pd.to_numeric(frame["contract_count"], errors="raise")
    comparable = declared.notna()
    buckets = pd.cut(
        observed,
        bins=[-1, 0, 1, 5, 10, 20, 40, math.inf],
        labels=["0", "1", "2–5", "6–10", "11–20", "21–40", "41+"],
    )
    distribution = [
        {"bucket": str(bucket), "process_count": int(count)}
        for bucket, count in buckets.value_counts(sort=False).items()
    ]
    return {
        "processes": len(frame),
        "processes_without_observed_tenderers": int((observed == 0).sum()),
        "processes_with_observed_tenderers": int((observed > 0).sum()),
        "observed_tenderers_median": round(float(observed.median()), 4),
        "observed_tenderers_p90": round(float(observed.quantile(0.90)), 4),
        "observed_tenderers_p99": round(float(observed.quantile(0.99)), 4),
        "observed_tenderers_maximum": int(observed.max()),
        "declared_observed_comparable_processes": int(comparable.sum()),
        "declared_observed_different_processes": int(
            (declared[comparable] != observed[comparable]).sum()
        ),
        "processes_with_awards": int((award > 0).sum()),
        "processes_with_contracts": int((contract > 0).sum()),
        "tenderer_bucket_distribution": distribution,
    }


def _currency_profile(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                **row,
                "row_count": int(row["row_count"]),
                "missing_pen_rows": int(row["missing_pen_rows"]),
            }
        )
    return output


def _money_millions(value: Any) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    return float(value) / 1_000_000


def _short_label(value: Any, width: int = 52) -> str:
    return textwrap.shorten(str(value or "Sin nombre"), width=width, placeholder="…")


def _figure_path(figures_dir: Path, filename: str) -> Path:
    figures_dir.mkdir(parents=True, exist_ok=True)
    return figures_dir / filename


def _save_figure(figure: plt.Figure, path: Path, dpi: int) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def _plot_lifecycle(
    overview: dict[str, Any], figures_dir: Path, dpi: int
) -> Path:
    labels = ["Procesos", "Con ofertantes", "Con adjudicación", "Con contrato"]
    values = [
        int(overview["process_count"]),
        int(overview["processes_with_tenderers"]),
        int(overview["processes_with_awards"]),
        int(overview["processes_with_contracts"]),
    ]
    figure, axis = plt.subplots(figsize=(9, 4.8))
    bars = axis.barh(labels[::-1], values[::-1], color=["#D97706", "#0F766E", "#475569", "#2563EB"])
    axis.bar_label(bars, labels=[f"{value:,}" for value in values[::-1]], padding=5)
    axis.set_title("Cobertura observada por componente de contratación")
    axis.set_xlabel("Procesos distintos")
    axis.grid(axis="x", alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    path = _figure_path(figures_dir, FIGURE_NAMES[0])
    _save_figure(figure, path, dpi)
    return path


def _plot_monthly(rows: list[dict[str, Any]], figures_dir: Path, dpi: int) -> Path:
    frame = pd.DataFrame(rows)
    frame["event_count"] = pd.to_numeric(frame["event_count"])
    months = sorted(frame["year_month"].unique())
    figure, axis = plt.subplots(figsize=(10, 5.2))
    for stage in STAGE_LABELS:
        subset = (
            frame[frame["stage"] == stage]
            .set_index("year_month")["event_count"]
            .reindex(months, fill_value=0)
        )
        axis.plot(
            months,
            subset.to_numpy(),
            marker="o",
            linewidth=2,
            label=STAGE_LABELS[stage],
            color=STAGE_COLORS[stage],
        )
    axis.set_title("Actividad por mes de la fecha de negocio publicada")
    axis.set_ylabel("Filas en el grano nativo")
    axis.set_xlabel("Mes de negocio; no equivale a source_period histórico")
    axis.legend(frameon=False)
    axis.grid(alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    path = _figure_path(figures_dir, FIGURE_NAMES[1])
    _save_figure(figure, path, dpi)
    return path


def _plot_amounts(
    rows: list[dict[str, Any]], figures_dir: Path, dpi: int, bins: int
) -> Path:
    frame = pd.DataFrame(rows)
    frame["amount_numeric"] = pd.to_numeric(frame["amount_pen"], errors="coerce")
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
    for axis, stage in zip(axes, STAGE_LABELS, strict=True):
        values = frame.loc[
            (frame["stage"] == stage) & (frame["amount_numeric"] > 0),
            "amount_numeric",
        ]
        axis.hist(
            np.log10(values),
            bins=bins,
            color=STAGE_COLORS[stage],
            alpha=0.85,
            edgecolor="white",
        )
        axis.set_title(STAGE_LABELS[stage])
        axis.set_xlabel("log10(monto PEN positivo)")
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Frecuencia")
    figure.suptitle("Distribución de montos PEN por grano (ceros visibles en el reporte)")
    path = _figure_path(figures_dir, FIGURE_NAMES[2])
    _save_figure(figure, path, dpi)
    return path


def _plot_ranking(
    rows: list[dict[str, Any]],
    label_column: str,
    amount_column: str,
    title: str,
    color: str,
    output_path: Path,
    dpi: int,
    top_n: int,
) -> Path:
    frame = pd.DataFrame(rows).head(top_n).copy()
    frame["amount_millions"] = frame[amount_column].map(_money_millions)
    frame["label"] = frame[label_column].map(_short_label)
    frame = frame.sort_values("amount_millions")
    figure, axis = plt.subplots(figsize=(11, 7))
    bars = axis.barh(frame["label"], frame["amount_millions"], color=color)
    axis.bar_label(bars, labels=[f"S/ {value:,.1f} M" for value in frame["amount_millions"]], padding=4, fontsize=8)
    axis.set_title(title)
    axis.set_xlabel("Monto PEN (millones), exploratorio")
    axis.grid(axis="x", alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    _save_figure(figure, output_path, dpi)
    return output_path


def _plot_competition(
    profile: dict[str, Any], figures_dir: Path, dpi: int
) -> Path:
    distribution = profile["tenderer_bucket_distribution"]
    labels = [item["bucket"] for item in distribution]
    values = [item["process_count"] for item in distribution]
    figure, axis = plt.subplots(figsize=(9, 5))
    bars = axis.bar(labels, values, color="#475569")
    axis.bar_label(bars, labels=[f"{value:,}" for value in values], padding=3)
    axis.set_title("Procesos por número observado de ofertantes")
    axis.set_xlabel("Ofertantes observados por proceso")
    axis.set_ylabel("Procesos")
    axis.grid(axis="y", alpha=0.2)
    axis.spines[["top", "right"]].set_visible(False)
    path = _figure_path(figures_dir, FIGURE_NAMES[6])
    _save_figure(figure, path, dpi)
    return path


def _format_money(value: Any) -> str:
    if value is None:
        return "—"
    return f"S/ {float(value):,.2f}"


def _escape_markdown(value: Any) -> str:
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_markdown(value) for value in row) + " |")
    return "\n".join(lines)


def build_findings(
    overview: dict[str, Any],
    profiles: list[dict[str, Any]],
    competition: dict[str, Any],
    quality_rows: list[dict[str, Any]],
    top_buyers: list[dict[str, Any]],
    top_suppliers: list[dict[str, Any]],
    top_categories: list[dict[str, Any]],
) -> list[str]:
    """Build factual, non-causal EDA observations from computed evidence."""

    quality = {row["metric_id"]: row for row in quality_rows}
    tender = next(profile for profile in profiles if profile["stage"] == "tender")
    contract = next(profile for profile in profiles if profile["stage"] == "contract")
    return [
        (
            "Los montos presentan una cola derecha pronunciada: la licitación tiene "
            f"mediana {_format_money(tender['median'])}, p99 {_format_money(tender['p99'])} "
            f"y máximo {_format_money(tender['maximum'])}; los valores extremos se conservan."
        ),
        (
            f"{competition['processes_with_observed_tenderers']:,} de "
            f"{competition['processes']:,} procesos tienen ofertantes observados; la mediana es "
            f"{competition['observed_tenderers_median']:g}, el p90 "
            f"{competition['observed_tenderers_p90']:g} y el máximo "
            f"{competition['observed_tenderers_maximum']}."
        ),
        (
            f"En {quality['tenderer_declared_observed_difference']['numerator']:,} de "
            f"{quality['tenderer_declared_observed_difference']['denominator']:,} procesos comparables, "
            "el número declarado de ofertantes difiere del detalle observado."
        ),
        (
            f"El monto contractual PEN está disponible en {contract['rows_with_pen']:,} de "
            f"{contract['rows_total']:,} contratos; el valor final de implementación falta en "
            f"{quality['contract_final_value_missing']['numerator']:,}."
        ),
        (
            f"El mayor comprador exploratorio por monto licitado es “{top_buyers[0]['buyer_name']}”; "
            f"el mayor proveedor atribuible por monto adjudicado es “{top_suppliers[0]['supplier_name']}”. "
            "Son rankings de un snapshot, no medidas de concentración."
        ),
        (
            f"La categoría estándar con mayor monto de ítems adjudicados en el piloto es "
            f"{top_categories[0]['classification_code']} — {top_categories[0]['classification_description']}."
        ),
        (
            f"Existe {quality['contract_signed_after_snapshot']['numerator']} contrato con fecha de firma "
            "posterior al snapshot; permanece visible para revisión de calidad temporal."
        ),
        (
            f"Solo existe un source_period ({overview['source_period']}); las fechas de negocio entre "
            f"{overview['contract_min_date']} y {overview['contract_max_date']} no convierten el piloto "
            "en una serie histórica apta para crecimiento o comparación interanual."
        ),
    ]


def build_markdown(report: dict[str, Any]) -> str:
    """Render a recruiter-readable generated EDA report."""

    overview = report["analysis"]["overview"]
    profiles = report["analysis"]["amount_profiles"]
    top = report["analysis"]["rankings"]
    quality = report["analysis"]["quality_coverage"]
    lines = [
        "# EDA — OECE/SEACE V3, source_period 2026-07",
        "",
        "> Reporte generado de forma reproducible desde SQL Server. Los rankings son descriptivos; no son KPIs, HHI ni recomendaciones.",
        "",
        "## Universo",
        "",
        _markdown_table(
            ["Objeto", "Filas"],
            [
                ["Procesos", f"{overview['process_count']:,}"],
                ["Ítems de licitación", f"{overview['tender_item_count']:,}"],
                ["Adjudicaciones", f"{overview['award_count']:,}"],
                ["Contratos", f"{overview['contract_count']:,}"],
                ["Compradores conocidos", f"{overview['known_buyer_count']:,}"],
                ["Identidades proveedor/ofertante", f"{overview['known_supplier_count']:,}"],
                ["Categorías conocidas", f"{overview['known_category_count']:,}"],
            ],
        ),
        "",
        "## Perfiles monetarios",
        "",
        _markdown_table(
            ["Grano", "Filas PEN", "Ceros", "Suma de control", "Mediana", "P90", "P99", "Máximo"],
            [
                [
                    STAGE_LABELS[item["stage"]],
                    f"{item['rows_with_pen']:,}/{item['rows_total']:,}",
                    f"{item['zero_rows']:,}",
                    _format_money(item["amount_sum"]),
                    _format_money(item["median"]),
                    _format_money(item["p90"]),
                    _format_money(item["p99"]),
                    _format_money(item["maximum"]),
                ]
                for item in profiles
            ],
        ),
        "",
        "Las sumas anteriores son controles descriptivos por hecho y no deben sumarse entre etapas.",
        "",
        "## Hallazgos exploratorios",
        "",
        *[f"- {finding}" for finding in report["analysis"]["findings"]],
        "",
        "## Principales compradores por monto licitado PEN",
        "",
        _markdown_table(
            ["Comprador", "Procesos", "Monto licitado"],
            [
                [row["buyer_name"], row["process_count"], _format_money(row["tender_amount_pen"])]
                for row in top["buyers"][:10]
            ],
        ),
        "",
        "## Principales proveedores atribuibles por monto adjudicado PEN",
        "",
        _markdown_table(
            ["Proveedor", "Adjudicaciones", "Compradores", "Monto adjudicado"],
            [
                [row["supplier_name"], row["award_count"], row["buyer_count"], _format_money(row["award_amount_pen"])]
                for row in top["suppliers"][:10]
            ],
        ),
        "",
        "## Principales categorías estándar por monto de ítems adjudicados PEN",
        "",
        _markdown_table(
            ["Código", "Descripción", "Ítems", "Monto"],
            [
                [row["classification_code"], row["classification_description"], row["award_item_count"], _format_money(row["award_item_amount_pen"])]
                for row in top["categories"][:10]
            ],
        ),
        "",
        "## Cobertura y calidad relevante",
        "",
        _markdown_table(
            ["Métrica", "Casos", "Denominador", "%", "Interpretación"],
            [
                [row["metric_id"], row["numerator"], row["denominator"], row["metric_pct"], row["interpretation"]]
                for row in quality
            ],
        ),
        "",
        "## Figuras",
        "",
        *[
            f"![{Path(path).stem}](figures/{Path(path).name})"
            for path in report["artifacts"]["figures"]
        ],
        "",
        "## Aptitud para fases siguientes",
        "",
        "- EDA descriptivo de demanda, compradores, proveedores, categorías y competencia: apto con las coberturas publicadas.",
        "- Crecimiento, YoY y recurrencia histórica: no aptos con un solo source_period.",
        "- Geografía: solo texto crudo exploratorio; requiere dimensión oficial UBIGEO.",
        "- Valor final contractual: no apto por cobertura insuficiente.",
        "- HHI, concentración y scores: deliberadamente no calculados en esta fase.",
        "",
    ]
    return "\n".join(lines)


def _server_metadata(connection: pyodbc.Connection) -> dict[str, Any]:
    return execute_sql(
        connection,
        """
        SELECT DB_NAME() AS database_name,
               CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS product_version,
               CONVERT(nvarchar(128), SERVERPROPERTY('Edition')) AS edition;
        """,
    )[0]


def run_eda(args: argparse.Namespace) -> dict[str, Any]:
    """Execute governed SQL datasets, descriptive analysis and figures."""

    started = time.perf_counter()
    config_path = args.config.resolve()
    project_root = config_path.parent.parent
    config = load_eda_config(config_path)
    eda = config["eda"]
    gate_path = project_root / eda["validation_gate"]
    gate = _load_json(gate_path)
    require_phase8_gate(gate)

    outputs = eda["outputs"]
    def project_output_path(override: Path | None, default: str) -> Path:
        path = override if override is not None else Path(default)
        return path if path.is_absolute() else project_root / path

    output_json = project_output_path(args.output, outputs["json"])
    markdown_output = project_output_path(args.markdown_output, outputs["markdown"])
    figures_dir = project_output_path(args.figures_dir, outputs["figures"])

    sql_settings = load_sql_server_settings(args.env_file)
    connection = pyodbc.connect(
        sql_settings.connection_string(), autocommit=True, timeout=15
    )
    datasets: dict[str, list[dict[str, Any]]] = {}
    try:
        connection.timeout = int(args.command_timeout_seconds)
        server = _server_metadata(connection)
        for dataset in config["datasets"]:
            rows = execute_sql(
                connection, _read_sql(project_root, dataset["sql"])
            )
            _validate_dataset_columns(
                dataset["dataset_id"], rows, dataset["required_columns"]
            )
            datasets[dataset["dataset_id"]] = rows
    finally:
        connection.close()

    overview = datasets["overview"][0]
    if int(overview["load_batch_id"]) != int(gate["source"]["load_batch_id"]):
        raise ValueError("EDA active load batch differs from the Phase 8 gate.")
    if overview["source_period"] != eda["source_period"]:
        raise ValueError("EDA source period differs from its governed contract.")

    profiles = [
        amount_profile(datasets["amount_observations"], stage)
        for stage in eda["amount_stages"]
    ]
    competition = competition_profile(datasets["competition"])
    top_n = int(eda["top_n"])
    top_buyers = datasets["buyer_exploration"][:top_n]
    top_suppliers = datasets["supplier_exploration"][:top_n]
    top_categories = datasets["category_exploration"][:top_n]
    quality_rows = datasets["quality_coverage"]
    findings = build_findings(
        overview,
        profiles,
        competition,
        quality_rows,
        top_buyers,
        top_suppliers,
        top_categories,
    )

    dpi = int(eda["figure_dpi"])
    figure_paths = [
        _plot_lifecycle(overview, figures_dir, dpi),
        _plot_monthly(datasets["monthly_activity"], figures_dir, dpi),
        _plot_amounts(
            datasets["amount_observations"],
            figures_dir,
            dpi,
            int(eda["histogram_bins"]),
        ),
        _plot_ranking(
            top_buyers,
            "buyer_name",
            "tender_amount_pen",
            "Compradores con mayor monto licitado PEN — exploración",
            "#2563EB",
            _figure_path(figures_dir, FIGURE_NAMES[3]),
            dpi,
            top_n,
        ),
        _plot_ranking(
            top_suppliers,
            "supplier_name",
            "award_amount_pen",
            "Proveedores atribuibles con mayor monto adjudicado PEN — exploración",
            "#0F766E",
            _figure_path(figures_dir, FIGURE_NAMES[4]),
            dpi,
            top_n,
        ),
        _plot_ranking(
            top_categories,
            "classification_description",
            "award_item_amount_pen",
            "Categorías estándar con mayor monto de ítems adjudicados PEN",
            "#7C3AED",
            _figure_path(figures_dir, FIGURE_NAMES[5]),
            dpi,
            top_n,
        ),
        _plot_competition(competition, figures_dir, dpi),
    ]

    sql_hashes = {
        dataset["dataset_id"]: {
            "path": dataset["sql"],
            "sha256": sha256_text_file(project_root / dataset["sql"]),
        }
        for dataset in config["datasets"]
    }
    duration = round(time.perf_counter() - started, 4)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "exploratory_data_analysis",
        "source": {
            "source_id": overview["source_id"],
            "source_period": overview["source_period"],
            "snapshot_date": overview["snapshot_date"],
            "load_batch_id": int(overview["load_batch_id"]),
            "database_name": server["database_name"],
            "sql_server_version": server["product_version"],
            "sql_server_edition": server["edition"],
            "phase8_gate": eda["validation_gate"],
            "phase8_gate_sha256": sha256_text_file(gate_path),
            "eda_config": config_path.relative_to(project_root).as_posix(),
            "eda_config_sha256": sha256_text_file(config_path),
            "eda_runner_sha256": sha256_text_file(Path(__file__)),
            "sql_datasets": sql_hashes,
            "matplotlib_version": matplotlib.__version__,
        },
        "summary": {
            "status": "PASS",
            "datasets_executed": len(datasets),
            "figures_generated": len(figure_paths),
            "findings_documented": len(findings),
            "processes_analyzed": int(overview["process_count"]),
            "source_period_count": 1,
            "growth_analysis_eligible": False,
            "duration_seconds": duration,
        },
        "analysis": {
            "overview": overview,
            "amount_profiles": profiles,
            "monthly_activity": datasets["monthly_activity"],
            "competition": competition,
            "rankings": {
                "buyers": top_buyers,
                "suppliers": top_suppliers,
                "categories": top_categories,
            },
            "procurement_methods": datasets["procurement_methods"],
            "currencies": _currency_profile(datasets["currencies"]),
            "quality_coverage": quality_rows,
            "findings": findings,
            "fitness_for_next_phases": {
                "descriptive_spend": "ELIGIBLE_WITH_DOCUMENTED_COVERAGE",
                "buyer_supplier_category_rankings": "ELIGIBLE_AS_EXPLORATORY_ONLY",
                "competition_distribution": "ELIGIBLE",
                "growth_and_yoy": "NOT_ELIGIBLE_SINGLE_SOURCE_PERIOD",
                "geographic_analysis": "DEFERRED_UNTIL_OFFICIAL_UBIGEO",
                "final_value_analysis": "NOT_ELIGIBLE_LOW_COVERAGE",
                "market_concentration": "DEFERRED_TO_PHASE_11",
                "scores": "DEFERRED_TO_PHASES_12_AND_13",
            },
        },
        "artifacts": {
            "json": output_json.relative_to(project_root).as_posix(),
            "markdown": markdown_output.relative_to(project_root).as_posix(),
            "figures": [path.relative_to(project_root).as_posix() for path in figure_paths],
            "figure_evidence": [
                {
                    "path": path.relative_to(project_root).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in figure_paths
            ],
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(build_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--config", type=Path, default=Path("config/eda.yml"))
    parser.add_argument("--command-timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--figures-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_eda(args)
    summary = report["summary"]
    print(
        f"EDA {summary['status']}: {summary['datasets_executed']} datasets; "
        f"{summary['figures_generated']} figures; "
        f"{summary['processes_analyzed']} processes."
    )


if __name__ == "__main__":
    main()
