"""Build the transparent Phase 12 B2G Commercial Opportunity Score."""

from __future__ import annotations

import argparse
import json
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from procurement_intelligence.extraction.download_ocds import (  # noqa: E402
    sha256_file,
    sha256_text_file,
)


FIGURES = (
    "01_top_opportunity_scores.png",
    "02_top_market_components.png",
    "03_sensitivity_ranks.png",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_opportunity_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "opportunity_score" not in config or "variables" not in config:
        raise ValueError("Opportunity config must contain opportunity_score and variables.")
    variables = config["variables"]
    variable_ids = [item["variable_id"] for item in variables]
    if len(variable_ids) != len(set(variable_ids)):
        raise ValueError("Opportunity variable IDs must be unique.")
    if abs(sum(float(item["baseline_weight"]) for item in variables) - 1.0) > 1e-9:
        raise ValueError("Baseline opportunity weights must sum to 1.")
    for name, weights in config["sensitivity_scenarios"].items():
        if set(weights) != set(variable_ids):
            raise ValueError(f"Sensitivity scenario {name} has different variables.")
        if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
            raise ValueError(f"Sensitivity scenario {name} weights must sum to 1.")
    return config


def percentile_score(series: pd.Series, direction: str) -> pd.Series:
    """Normalize a variable to 0-100 using cross-sectional average ranks."""

    numeric = pd.to_numeric(series, errors="raise")
    if numeric.isna().any():
        raise ValueError("Opportunity inputs cannot contain null values.")
    if len(numeric) < 2:
        raise ValueError("Opportunity scoring requires at least two markets.")
    ranked = numeric.rank(method="average", ascending=True)
    scores = 100.0 * (ranked - 1.0) / (len(numeric) - 1.0)
    if direction == "lower_is_better":
        scores = 100.0 - scores
    elif direction != "higher_is_better":
        raise ValueError(f"Unsupported score direction: {direction}")
    return scores


def _assign_rank(series: pd.Series) -> pd.Series:
    return series.rank(method="min", ascending=False).astype(int)


def score_population(
    markets: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Normalize inputs, calculate baseline/scenarios and validate arithmetic."""

    frame = pd.DataFrame(markets)
    frame = frame[frame["is_analysis_eligible"].astype(bool)].copy()
    if frame.empty:
        raise ValueError("No eligible markets for opportunity scoring.")
    frame["average_ticket"] = (
        pd.to_numeric(frame["attributable_amount_pen"], errors="raise")
        / pd.to_numeric(frame["award_item_count"], errors="raise")
    )
    source_overrides = {"derived_attributable_amount_per_item": "average_ticket"}
    component_columns: dict[str, str] = {}
    baseline_weights: dict[str, float] = {}
    for variable in config["variables"]:
        variable_id = variable["variable_id"]
        source = source_overrides.get(variable["source_field"], variable["source_field"])
        column = f"component_{variable_id}"
        frame[column] = percentile_score(frame[source], variable["direction"])
        component_columns[variable_id] = column
        baseline_weights[variable_id] = float(variable["baseline_weight"])

    scenarios = {"baseline": baseline_weights, **config["sensitivity_scenarios"]}
    for name, weights in scenarios.items():
        frame[f"score_{name}"] = sum(
            frame[component_columns[variable_id]] * float(weight)
            for variable_id, weight in weights.items()
        )
        frame[f"rank_{name}"] = _assign_rank(frame[f"score_{name}"])

    population = len(frame)
    higher_limit = float(
        config["opportunity_score"]["bands"]["higher_relative_opportunity_max_rank_pct"]
    )
    medium_limit = float(
        config["opportunity_score"]["bands"]["medium_relative_opportunity_max_rank_pct"]
    )
    rank_pct = 100.0 * frame["rank_baseline"] / population
    frame["opportunity_band"] = np.select(
        [rank_pct <= higher_limit, rank_pct <= medium_limit],
        ["HIGHER_RELATIVE", "MEDIUM_RELATIVE"],
        default="LOWER_RELATIVE",
    )
    score_columns = [f"score_{name}" for name in scenarios]
    frame["scenario_score_range"] = frame[score_columns].max(axis=1) - frame[score_columns].min(axis=1)
    rank_columns = [f"rank_{name}" for name in scenarios]
    frame["maximum_absolute_rank_shift"] = (
        frame[rank_columns].max(axis=1) - frame[rank_columns].min(axis=1)
    ).astype(int)

    validations: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        recomputed = sum(
            float(row[component_columns[variable_id]]) * weight
            for variable_id, weight in baseline_weights.items()
        )
        passed = (
            abs(recomputed - float(row["score_baseline"])) <= 1e-9
            and 0 <= float(row["score_baseline"]) <= 100
            and all(0 <= float(row[column]) <= 100 for column in component_columns.values())
        )
        validations.append(
            {
                "category_key": int(row["category_key"]),
                "score_baseline": round(float(row["score_baseline"]), 6),
                "score_recomputed": round(recomputed, 6),
                "status": "PASS" if passed else "FAIL",
            }
        )
    return frame, validations


def sensitivity_summary(frame: pd.DataFrame, scenario_names: list[str], top_n: int = 10) -> list[dict[str, Any]]:
    baseline_top = set(frame.nsmallest(top_n, "rank_baseline")["category_key"].astype(int))
    results: list[dict[str, Any]] = []
    baseline_rank = frame["rank_baseline"].astype(float)
    for name in scenario_names:
        rank = frame[f"rank_{name}"].astype(float)
        scenario_top = set(frame.nsmallest(top_n, f"rank_{name}")["category_key"].astype(int))
        results.append(
            {
                "scenario": name,
                "rank_correlation": round(float(np.corrcoef(baseline_rank, rank)[0, 1]), 6),
                "top10_overlap": len(baseline_top & scenario_top),
                "mean_absolute_rank_shift": round(float((baseline_rank - rank).abs().mean()), 6),
                "maximum_absolute_rank_shift": int((baseline_rank - rank).abs().max()),
            }
        )
    return results


def _short(value: Any, width: int = 46) -> str:
    return textwrap.shorten(str(value), width=width, placeholder="…")


def _figure_path(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def _plot_top(frame: pd.DataFrame, directory: Path, dpi: int) -> Path:
    top = frame.nsmallest(20, "rank_baseline").sort_values("score_baseline")
    path = _figure_path(directory, FIGURES[0])
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.barh([_short(v) for v in top["classification_description"]], top["score_baseline"], color="#2563EB")
    for bar, score in zip(bars, top["score_baseline"], strict=True):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f" {score:.1f}", va="center", fontsize=8)
    ax.set(title="Top 20 — B2G Commercial Opportunity Score piloto", xlabel="Score relativo (0–100)", xlim=(0, 105))
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _plot_components(frame: pd.DataFrame, variables: list[dict[str, Any]], directory: Path, dpi: int) -> Path:
    top = frame.nsmallest(15, "rank_baseline")
    columns = [f"component_{item['variable_id']}" for item in variables]
    path = _figure_path(directory, FIGURES[1])
    fig, ax = plt.subplots(figsize=(11, 8))
    image = ax.imshow(top[columns].to_numpy(dtype=float), cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(columns)), [_short(item["label"], 22) for item in variables], rotation=25, ha="right")
    ax.set_yticks(range(len(top)), [_short(v, 42) for v in top["classification_description"]])
    ax.set_title("Componentes normalizados — Top 15")
    fig.colorbar(image, ax=ax, label="Percentil (0–100)")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _plot_sensitivity(frame: pd.DataFrame, scenarios: list[str], directory: Path, dpi: int) -> Path:
    path = _figure_path(directory, FIGURES[2])
    fig, axes = plt.subplots(1, len(scenarios), figsize=(5 * len(scenarios), 4.8), sharex=True, sharey=True)
    if len(scenarios) == 1:
        axes = [axes]
    maximum = len(frame)
    for ax, name in zip(axes, scenarios, strict=True):
        ax.scatter(frame["rank_baseline"], frame[f"rank_{name}"], alpha=0.65, color="#0F766E")
        ax.plot([1, maximum], [1, maximum], linestyle="--", color="#6B7280", linewidth=1)
        ax.set(title=name.replace("_", " ").title(), xlabel="Ranking baseline", ylabel="Ranking escenario")
        ax.grid(alpha=0.2)
    fig.suptitle("Sensibilidad del ranking a ponderaciones alternativas")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _money(value: Any) -> str:
    return f"S/ {float(value):,.2f}"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    def safe(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |", *["| " + " | ".join(safe(v) for v in row) + " |" for row in rows]])


def build_markdown(report: dict[str, Any]) -> str:
    top = report["analysis"]["ranked_markets"]
    sensitivity = report["analysis"]["sensitivity"]
    return "\n".join(
        [
            "# B2G Commercial Opportunity Score — piloto 2026-07",
            "",
            "> Score relativo y explicable dentro de 87 mercados elegibles. No es pronóstico de ventas, probabilidad de adjudicación, retorno financiero ni recomendación automática.",
            "",
            "## Metodología",
            "",
            "- Tamaño de mercado: 30%.",
            "- Frecuencia de ítems: 20%.",
            "- Diversidad de compradores: 20%.",
            "- Ticket promedio por ítem: 15%.",
            "- Apertura relativa, inversa a HHI: 15%.",
            "- Normalización: percentil 0–100 dentro de la población elegible.",
            "- Crecimiento y recurrencia: excluidos por falta de periodos comparables.",
            "",
            "## Top 20 relativo",
            "",
            _table(
                ["Rank", "Código", "Categoría", "Monto", "Compradores", "HHI", "Score", "Banda"],
                [[row["rank_baseline"], row["classification_code"], row["classification_description"], _money(row["attributable_amount_pen"]), row["buyer_count"], f"{float(row['hhi']):,.2f}", f"{float(row['score_baseline']):.2f}", row["opportunity_band"]] for row in top[:20]],
            ),
            "",
            "## Sensibilidad",
            "",
            _table(
                ["Escenario", "Correlación de ranking", "Coincidencia Top 10", "Cambio medio", "Cambio máximo"],
                [[item["scenario"], f"{item['rank_correlation']:.4f}", f"{item['top10_overlap']}/10", f"{item['mean_absolute_rank_shift']:.2f}", item["maximum_absolute_rank_shift"]] for item in sensitivity],
            ),
            "",
            "Los cambios de ranking muestran dependencia de preferencias de negocio; el reporte conserva los tres escenarios y la variación por mercado.",
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


def run_opportunity_score(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    config_path = args.config.resolve()
    root = config_path.parent.parent
    config = load_opportunity_config(config_path)
    settings = config["opportunity_score"]
    gate_path = root / settings["phase11_gate"]
    gate = _load_json(gate_path)
    if gate["summary"]["status"] != "PASS" or gate["summary"]["share_validations_failed"]:
        raise ValueError("Phase 11 gate is not eligible for opportunity scoring.")
    if gate["source"]["source_period"] != settings["source_period"]:
        raise ValueError("Opportunity and concentration source periods differ.")

    frame, validations = score_population(gate["analysis"]["all_markets"], config)
    failed = [item for item in validations if item["status"] != "PASS"]
    if failed:
        raise ValueError(f"Opportunity score validation failed: {failed[:5]}")
    scenario_names = list(config["sensitivity_scenarios"])
    sensitivity = sensitivity_summary(frame, scenario_names)
    ranked = frame.sort_values(["rank_baseline", "category_key"]).to_dict("records")

    output_json = _project_path(root, args.output, settings["outputs"]["json"])
    output_md = _project_path(root, args.markdown_output, settings["outputs"]["markdown"])
    output_csv = _project_path(root, args.csv_output, settings["outputs"]["csv"])
    figures_dir = _project_path(root, args.figures_dir, settings["outputs"]["figures"])
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    frame.sort_values(["rank_baseline", "category_key"]).to_csv(output_csv, index=False, encoding="utf-8")
    dpi = int(settings["figure_dpi"])
    figures = [
        _plot_top(frame, figures_dir, dpi),
        _plot_components(frame, config["variables"], figures_dir, dpi),
        _plot_sensitivity(frame, scenario_names, figures_dir, dpi),
    ]
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "b2g_commercial_opportunity_score",
        "source": {
            "source_id": gate["source"]["source_id"],
            "source_period": settings["source_period"],
            "snapshot_date": gate["source"]["snapshot_date"],
            "load_batch_id": gate["source"]["load_batch_id"],
            "phase11_gate": settings["phase11_gate"],
            "phase11_gate_sha256": sha256_text_file(gate_path),
            "config": config_path.relative_to(root).as_posix(),
            "config_sha256": sha256_text_file(config_path),
            "runner_sha256": sha256_text_file(Path(__file__)),
        },
        "summary": {
            "status": "PASS_PILOT",
            "score_version": settings["score_version"],
            "eligible_markets_scored": len(frame),
            "score_validations_passed": len(validations),
            "score_validations_failed": len(failed),
            "higher_relative_markets": int((frame["opportunity_band"] == "HIGHER_RELATIVE").sum()),
            "medium_relative_markets": int((frame["opportunity_band"] == "MEDIUM_RELATIVE").sum()),
            "lower_relative_markets": int((frame["opportunity_band"] == "LOWER_RELATIVE").sum()),
            "sensitivity_scenarios": len(sensitivity),
            "figures_generated": len(figures),
            "duration_seconds": round(time.perf_counter() - started, 4),
        },
        "methodology": {
            "population": settings["population"],
            "normalization": settings["normalization"],
            "variables": config["variables"],
            "sensitivity_weights": config["sensitivity_scenarios"],
            "excluded_variables": config["excluded_variables"],
        },
        "analysis": {
            "ranked_markets": ranked,
            "sensitivity": sensitivity,
            "validations": validations,
            "limitations": [
                "Single source period; growth and recurrence are excluded.",
                "Relative score within 87 eligible markets; it is not comparable to another score version without recalibration.",
                "The score does not estimate sales, win probability or return.",
                "Weights express a documented business preference and remain scenario-sensitive.",
            ],
        },
        "artifacts": {
            "json": output_json.relative_to(root).as_posix(),
            "markdown": output_md.relative_to(root).as_posix(),
            "csv": output_csv.relative_to(root).as_posix(),
            "csv_size_bytes": output_csv.stat().st_size,
            "csv_sha256": sha256_file(output_csv),
            "figures": [path.relative_to(root).as_posix() for path in figures],
            "figure_evidence": [{"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in figures],
        },
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(build_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/opportunity_score.yml"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--csv-output", type=Path)
    parser.add_argument("--figures-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    report = run_opportunity_score(parse_args())
    summary = report["summary"]
    print(
        f"Opportunity {summary['status']}: {summary['eligible_markets_scored']} markets; "
        f"{summary['score_validations_passed']} validations; {summary['sensitivity_scenarios']} scenarios."
    )


if __name__ == "__main__":
    main()
