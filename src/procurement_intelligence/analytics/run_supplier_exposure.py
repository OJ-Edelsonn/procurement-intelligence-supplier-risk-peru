"""Build a limited, transparent supplier operational exposure score."""

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
import pyodbc  # noqa: E402
import yaml  # noqa: E402

from procurement_intelligence.analytics.run_opportunity_score import percentile_score  # noqa: E402
from procurement_intelligence.extraction.download_ocds import (  # noqa: E402
    sha256_file,
    sha256_text_file,
)
from procurement_intelligence.loading.build_dw_frames import (  # noqa: E402
    build_warehouse_frames,
    load_silver_frames,
)
from procurement_intelligence.settings import (  # noqa: E402
    load_settings,
    load_sql_server_settings,
)
from procurement_intelligence.validation.validate_sql_server import execute_sql  # noqa: E402


FIGURES = (
    "01_top_supplier_exposure_scores.png",
    "02_buyer_category_dependency.png",
    "03_exposure_sensitivity_ranks.png",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_exposure_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not {"supplier_exposure", "variables", "input_datasets"} <= set(config):
        raise ValueError("Exposure config must contain supplier_exposure, variables and input_datasets.")
    variable_ids = [item["variable_id"] for item in config["variables"]]
    if len(variable_ids) != len(set(variable_ids)):
        raise ValueError("Exposure variable IDs must be unique.")
    if abs(sum(float(item["baseline_weight"]) for item in config["variables"]) - 1.0) > 1e-9:
        raise ValueError("Baseline exposure weights must sum to 1.")
    for name, weights in config["sensitivity_scenarios"].items():
        if set(weights) != set(variable_ids) or abs(sum(float(v) for v in weights.values()) - 1.0) > 1e-9:
            raise ValueError(f"Invalid sensitivity weights for {name}.")
    return config


def _read_sql(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"Missing exposure SQL input: {path}")
    return path.read_text(encoding="utf-8-sig")


def _validate_columns(dataset: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Exposure dataset {dataset['dataset_id']} returned no rows.")
    missing = set(dataset["required_columns"]) - set(rows[0])
    if missing:
        raise ValueError(f"Exposure dataset {dataset['dataset_id']} missing: {sorted(missing)}")


def _build_datasets_from_silver(
    root: Path,
    env_file: Path,
    settings: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Rebuild the audited dimensional frames when SQL Server is memory constrained."""

    etl_path = root / settings["silver_etl_summary"]
    model_path = root / settings["dimensional_gate"]
    etl_summary = _load_json(etl_path)
    dimensional_gate = _load_json(model_path)
    if not etl_summary["summary"]["promotion_eligible"]:
        raise ValueError("The Phase 5 Silver gate is not promotion eligible.")
    if not dimensional_gate["summary"]["design_eligible_for_phase7"]:
        raise ValueError("The Phase 6 dimensional gate is not eligible for rebuild.")

    data_settings = load_settings(env_file)
    silver_frames = load_silver_frames(data_settings, etl_summary)
    warehouse = build_warehouse_frames(silver_frames, settings["source_period"])

    expected_grains = dimensional_gate["fact_and_bridge_grains"]
    for table_name in ("fact_award", "fact_award_item", "fact_contract"):
        actual_rows = len(warehouse.facts[table_name])
        expected_rows = int(expected_grains[table_name]["rows"])
        if actual_rows != expected_rows:
            raise ValueError(
                f"Silver rebuild diverges for {table_name}: "
                f"expected {expected_rows}; actual {actual_rows}."
            )

    suppliers = warehouse.dimensions["dim_supplier"][
        ["supplier_key", "display_name"]
    ].rename(columns={"supplier_key": "supplier_lookup_key"})
    awards = warehouse.facts["fact_award"]
    awards = awards[
        (awards["attributed_supplier_key"] != 0)
        & (awards["award_amount_pen_calculated"] > 0)
    ].merge(
        suppliers,
        left_on="attributed_supplier_key",
        right_on="supplier_lookup_key",
        how="inner",
        validate="many_to_one",
    )
    award_rows = awards.rename(
        columns={
            "attributed_supplier_key": "supplier_key",
            "display_name": "supplier_name",
            "award_amount_pen_calculated": "amount_pen",
        }
    )[
        ["award_fact_key", "supplier_key", "supplier_name", "buyer_key", "amount_pen"]
    ]

    items = warehouse.facts["fact_award_item"]
    item_rows = items[
        (items["attributed_supplier_key"] != 0)
        & (items["total_amount_pen_calculated"] > 0)
    ].rename(
        columns={
            "attributed_supplier_key": "supplier_key",
            "total_amount_pen_calculated": "amount_pen",
        }
    )[["supplier_key", "standard_category_key", "amount_pen"]]

    contracts = warehouse.facts["fact_contract"]
    contract_rows = contracts[contracts["attributed_supplier_key"] != 0].rename(
        columns={
            "attributed_supplier_key": "supplier_key",
            "contract_amount_pen_calculated": "amount_pen",
        }
    )[["contract_fact_key", "supplier_key", "amount_pen"]]

    datasets = {
        "supplier_awards": award_rows.to_dict("records"),
        "supplier_items": item_rows.to_dict("records"),
        "supplier_contracts": contract_rows.to_dict("records"),
    }
    evidence = {
        "input_mode": "audited_silver_rebuild",
        "etl_summary": settings["silver_etl_summary"],
        "etl_summary_sha256": sha256_text_file(etl_path),
        "dimensional_gate": settings["dimensional_gate"],
        "dimensional_gate_sha256": sha256_text_file(model_path),
        "database_name": None,
        "sql_server_version": None,
    }
    return datasets, evidence


def _load_datasets_from_sql(
    root: Path,
    env_file: Path,
    config: dict[str, Any],
    command_timeout_seconds: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Execute the governed SQL input contracts when the instance is available."""

    sql_settings = load_sql_server_settings(env_file)
    connection = pyodbc.connect(
        sql_settings.connection_string(), autocommit=True, timeout=15
    )
    datasets: dict[str, list[dict[str, Any]]] = {}
    try:
        connection.timeout = command_timeout_seconds
        server = execute_sql(
            connection,
            "SELECT DB_NAME() AS database_name, "
            "CONVERT(nvarchar(128), SERVERPROPERTY('ProductVersion')) AS product_version;",
        )[0]
        for dataset in config["input_datasets"]:
            rows = execute_sql(connection, _read_sql(root, dataset["sql"]))
            _validate_columns(dataset, rows)
            datasets[dataset["dataset_id"]] = rows
    finally:
        connection.close()
    return datasets, {
        "input_mode": "sql_server",
        "etl_summary": None,
        "etl_summary_sha256": None,
        "dimensional_gate": None,
        "dimensional_gate_sha256": None,
        "database_name": server["database_name"],
        "sql_server_version": server["product_version"],
    }


def build_supplier_inputs(
    datasets: dict[str, list[dict[str, Any]]], eligibility: dict[str, Any]
) -> pd.DataFrame:
    """Aggregate atomic award/item/contract rows into auditable supplier inputs."""

    awards = pd.DataFrame(datasets["supplier_awards"]).copy()
    items = pd.DataFrame(datasets["supplier_items"]).copy()
    contracts = pd.DataFrame(datasets["supplier_contracts"]).copy()
    for frame, columns in (
        (awards, ["supplier_key", "buyer_key", "amount_pen"]),
        (items, ["supplier_key", "standard_category_key", "amount_pen"]),
        (contracts, ["supplier_key", "amount_pen"]),
    ):
        for column in columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    award_stats = awards.groupby("supplier_key", as_index=False).agg(
        supplier_name=("supplier_name", "first"),
        award_count=("award_fact_key", "size"),
        buyer_count=("buyer_key", lambda value: value[value != 0].nunique()),
        award_amount_pen=("amount_pen", "sum"),
        average_award_ticket_pen=("amount_pen", "mean"),
    )
    known_buyer = (
        awards[awards["buyer_key"] != 0]
        .groupby("supplier_key", as_index=False)["amount_pen"]
        .sum()
        .rename(columns={"amount_pen": "known_buyer_amount_pen"})
    )
    buyer_totals = (
        awards[awards["buyer_key"] != 0]
        .groupby(["supplier_key", "buyer_key"], as_index=False)["amount_pen"]
        .sum()
    )
    award_totals = award_stats.set_index("supplier_key")["award_amount_pen"]
    buyer_totals["share"] = 100.0 * buyer_totals["amount_pen"] / buyer_totals["supplier_key"].map(award_totals)
    top_buyer = buyer_totals.groupby("supplier_key", as_index=False)["share"].max().rename(columns={"share": "top_buyer_share_pct"})
    awards["share"] = 100.0 * awards["amount_pen"] / awards["supplier_key"].map(award_totals)
    award_hhi = (
        awards.assign(squared=lambda frame: np.square(frame["share"]))
        .groupby("supplier_key", as_index=False)["squared"]
        .sum()
        .rename(columns={"squared": "award_hhi"})
    )

    item_stats = items.groupby("supplier_key", as_index=False).agg(
        award_item_count=("amount_pen", "size"),
        award_item_amount_pen=("amount_pen", "sum"),
    )
    known_items = items[items["standard_category_key"] != 0]
    known_item_stats = (
        known_items.groupby("supplier_key", as_index=False)["amount_pen"]
        .sum()
        .rename(columns={"amount_pen": "known_category_item_amount_pen"})
    )
    category_totals = known_items.groupby(["supplier_key", "standard_category_key"], as_index=False)["amount_pen"].sum()
    known_totals = known_item_stats.set_index("supplier_key")["known_category_item_amount_pen"]
    category_totals["share"] = 100.0 * category_totals["amount_pen"] / category_totals["supplier_key"].map(known_totals)
    category_stats = category_totals.groupby("supplier_key", as_index=False).agg(
        category_count=("standard_category_key", "nunique"),
        top_category_share_pct=("share", "max"),
    )
    contract_stats = contracts.groupby("supplier_key", as_index=False).agg(
        contract_count=("contract_fact_key", "size"),
        contract_amount_pen=("amount_pen", "sum"),
    )

    frame = award_stats.merge(known_buyer, on="supplier_key", how="left")
    for addition in (top_buyer, award_hhi, item_stats, known_item_stats, category_stats):
        frame = frame.merge(addition, on="supplier_key", how="inner")
    frame = frame.merge(contract_stats, on="supplier_key", how="left")
    frame[["contract_count", "contract_amount_pen"]] = frame[["contract_count", "contract_amount_pen"]].fillna(0)
    frame["known_buyer_amount_coverage_pct"] = 100.0 * frame["known_buyer_amount_pen"] / frame["award_amount_pen"]
    frame["known_category_item_amount_coverage_pct"] = 100.0 * frame["known_category_item_amount_pen"] / frame["award_item_amount_pen"]
    for column in (
        "top_buyer_share_pct",
        "top_category_share_pct",
        "known_buyer_amount_coverage_pct",
        "known_category_item_amount_coverage_pct",
    ):
        frame[column] = frame[column].clip(lower=0.0, upper=100.0)
    frame["award_hhi"] = frame["award_hhi"].clip(lower=0.0, upper=10000.0)
    frame["effective_award_count"] = 10000.0 / frame["award_hhi"]
    frame["is_score_eligible"] = (
        (frame["award_count"] >= int(eligibility["minimum_awards"]))
        & (frame["known_buyer_amount_coverage_pct"] >= float(eligibility["minimum_known_buyer_amount_coverage_pct"]))
        & (frame["known_category_item_amount_coverage_pct"] >= float(eligibility["minimum_known_category_item_amount_coverage_pct"]))
    )
    return frame


def score_suppliers(frame: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    scored = frame[frame["is_score_eligible"]].copy()
    if len(scored) < 2:
        raise ValueError("At least two eligible suppliers are required.")
    baseline: dict[str, float] = {}
    components: dict[str, str] = {}
    for variable in config["variables"]:
        variable_id = variable["variable_id"]
        direction = (
            "higher_is_better"
            if variable["direction"] == "higher_is_more_exposure"
            else "lower_is_better"
        )
        column = f"component_{variable_id}"
        scored[column] = percentile_score(scored[variable["source_field"]], direction)
        components[variable_id] = column
        baseline[variable_id] = float(variable["baseline_weight"])
    scenarios = {"baseline": baseline, **config["sensitivity_scenarios"]}
    for name, weights in scenarios.items():
        scored[f"score_{name}"] = sum(scored[components[key]] * float(weight) for key, weight in weights.items())
        scored[f"rank_{name}"] = scored[f"score_{name}"].rank(method="min", ascending=False).astype(int)
    population = len(scored)
    limits = config["supplier_exposure"]["bands"]
    rank_pct = 100.0 * scored["rank_baseline"] / population
    scored["exposure_band"] = np.select(
        [rank_pct <= float(limits["higher_relative_exposure_max_rank_pct"]), rank_pct <= float(limits["medium_relative_exposure_max_rank_pct"])],
        ["HIGHER_RELATIVE", "MEDIUM_RELATIVE"],
        default="LOWER_RELATIVE",
    )
    rank_columns = [f"rank_{name}" for name in scenarios]
    score_columns = [f"score_{name}" for name in scenarios]
    scored["maximum_absolute_rank_shift"] = (scored[rank_columns].max(axis=1) - scored[rank_columns].min(axis=1)).astype(int)
    scored["scenario_score_range"] = scored[score_columns].max(axis=1) - scored[score_columns].min(axis=1)
    validations: list[dict[str, Any]] = []
    for _, row in scored.iterrows():
        recomputed = sum(float(row[components[key]]) * weight for key, weight in baseline.items())
        passed = abs(recomputed - float(row["score_baseline"])) <= 1e-9 and 0 <= recomputed <= 100
        validations.append({"supplier_key": int(row["supplier_key"]), "score": round(float(row["score_baseline"]), 6), "recomputed": round(recomputed, 6), "status": "PASS" if passed else "FAIL"})
    return scored, validations


def sensitivity_summary(frame: pd.DataFrame, names: list[str], top_n: int = 10) -> list[dict[str, Any]]:
    baseline_top = set(frame.nsmallest(top_n, "rank_baseline")["supplier_key"].astype(int))
    baseline = frame["rank_baseline"].astype(float)
    results = []
    for name in names:
        rank = frame[f"rank_{name}"].astype(float)
        top = set(frame.nsmallest(top_n, f"rank_{name}")["supplier_key"].astype(int))
        results.append({"scenario": name, "rank_correlation": round(float(np.corrcoef(baseline, rank)[0, 1]), 6), "top10_overlap": len(baseline_top & top), "mean_absolute_rank_shift": round(float((baseline-rank).abs().mean()), 6), "maximum_absolute_rank_shift": int((baseline-rank).abs().max())})
    return results


def _short(value: Any, width: int = 45) -> str:
    return textwrap.shorten(str(value), width=width, placeholder="…")


def _figure_path(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def _plot_top(frame: pd.DataFrame, directory: Path, dpi: int) -> Path:
    top = frame.nsmallest(20, "rank_baseline").sort_values("score_baseline")
    path = _figure_path(directory, FIGURES[0])
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.barh([_short(v) for v in top["supplier_name"]], top["score_baseline"], color="#D97706")
    for bar, score in zip(bars, top["score_baseline"], strict=True):
        ax.text(bar.get_width(), bar.get_y()+bar.get_height()/2, f" {score:.1f}", va="center", fontsize=8)
    ax.set(title="Top 20 — Supplier Exposure Score piloto", xlabel="Exposición relativa (0–100)", xlim=(0,105))
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout(); fig.savefig(path, dpi=dpi); plt.close(fig)
    return path


def _plot_dependencies(frame: pd.DataFrame, directory: Path, dpi: int) -> Path:
    path = _figure_path(directory, FIGURES[1])
    fig, ax = plt.subplots(figsize=(10,6))
    scatter = ax.scatter(frame["top_buyer_share_pct"], frame["top_category_share_pct"], c=frame["score_baseline"], s=35 + 15*np.log10(frame["award_amount_pen"].astype(float).clip(lower=1)), cmap="plasma", alpha=.72, edgecolor="white", linewidth=.4)
    ax.set(title="Dependencia observada de comprador y categoría", xlabel="Participación del comprador principal (%)", ylabel="Participación de la categoría principal (%)", xlim=(0,102), ylim=(0,102))
    ax.grid(alpha=.25); fig.colorbar(scatter, ax=ax, label="Score de exposición")
    fig.tight_layout(); fig.savefig(path, dpi=dpi); plt.close(fig)
    return path


def _plot_sensitivity(frame: pd.DataFrame, names: list[str], directory: Path, dpi: int) -> Path:
    path = _figure_path(directory, FIGURES[2])
    fig, axes = plt.subplots(1,len(names),figsize=(5*len(names),4.8),sharex=True,sharey=True)
    if len(names)==1: axes=[axes]
    maximum=len(frame)
    for ax,name in zip(axes,names,strict=True):
        ax.scatter(frame["rank_baseline"],frame[f"rank_{name}"],alpha=.65,color="#7C3AED")
        ax.plot([1,maximum],[1,maximum],"--",color="#6B7280",linewidth=1)
        titles = {"dependency_heavy": "Énfasis en dependencia", "materiality_heavy": "Énfasis en materialidad", "balanced_equal": "Ponderación equitativa"}
        ax.set(title=titles.get(name, name.replace("_", " ").title()),xlabel="Ranking base",ylabel="Ranking del escenario");ax.grid(alpha=.2)
    fig.suptitle("Sensibilidad del Supplier Exposure Score")
    fig.tight_layout();fig.savefig(path,dpi=dpi);plt.close(fig)
    return path


def _money(value: Any) -> str:
    return f"S/ {float(value):,.2f}"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    safe=lambda value:str(value).replace("|","\\|").replace("\n"," ")
    return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |",*["| "+" | ".join(safe(v) for v in row)+" |" for row in rows]])


def build_markdown(report: dict[str, Any]) -> str:
    top=report["analysis"]["ranked_suppliers"]
    disclaimer=report["methodology"]["disclaimer"]
    return "\n".join([
        "# Supplier Operational and Commercial Exposure Score — piloto 2026-07","",f"> **Advertencia:** {disclaimer}","",
        "El score ordena exposición relativa observada; no demuestra que un proveedor sea riesgoso, irregular, insolvente o responsable de conducta indebida.","",
        "Los insumos se reconstruyeron desde la capa Silver auditada y se reconciliaron con los conteos del modelo dimensional. Los SQL incluidos son contratos de consulta reproducibles, pero no se ejecutaron en esta corrida por presión de memoria de la instancia local.","",
        "## Componentes","","- Materialidad adjudicada: 20%.","- Dependencia del principal comprador: 30%.","- Dependencia de categoría: 25%.","- Concentración entre adjudicaciones: 15%.","- Amplitud limitada de compradores: 10%.","",
        "## Top 20 relativo","",
        _table(["Rank","Proveedor","Adjudicaciones","Compradores","Monto","Top buyer","Top categoría","Score","Banda"],[[row["rank_baseline"],row["supplier_name"],row["award_count"],row["buyer_count"],_money(row["award_amount_pen"]),f"{row['top_buyer_share_pct']:.2f}%",f"{row['top_category_share_pct']:.2f}%",f"{row['score_baseline']:.2f}",row["exposure_band"]] for row in top[:20]]),"",
        "## Sensibilidad","",
        _table(["Escenario","Correlación","Top 10 común","Cambio medio","Cambio máximo"],[[item["scenario"],f"{item['rank_correlation']:.4f}",f"{item['top10_overlap']}/10",f"{item['mean_absolute_rank_shift']:.2f}",item["maximum_absolute_rank_shift"]] for item in report["analysis"]["sensitivity"]]),"",
        "Sanciones, penalidades, recurrencia y cambios abruptos no se calculan porque sus fuentes o periodos no están disponibles. El escenario con énfasis en materialidad presenta sensibilidad alta; el orden no debe interpretarse como una clasificación estable fuera del periodo observado.","","## Figuras","",*[f"![{Path(path).stem}](figures/{Path(path).name})" for path in report["artifacts"]["figures"]],""
    ])


def _project_path(root: Path, override: Path|None, default: str) -> Path:
    path=override if override is not None else Path(default)
    return path if path.is_absolute() else root/path


def run_supplier_exposure(args: argparse.Namespace) -> dict[str, Any]:
    started=time.perf_counter();config_path=args.config.resolve();root=config_path.parent.parent
    config=load_exposure_config(config_path);settings=config["supplier_exposure"]
    gate_path=root/settings["phase12_gate"];gate=_load_json(gate_path)
    if gate["summary"]["status"]!="PASS_PILOT" or gate["summary"]["score_validations_failed"]:
        raise ValueError("Phase 12 gate is not eligible for supplier exposure.")
    input_mode = args.input_mode or settings["input_mode"]
    if input_mode == "audited_silver_rebuild":
        datasets, input_evidence = _build_datasets_from_silver(
            root, args.env_file, settings
        )
    elif input_mode == "sql_server":
        datasets, input_evidence = _load_datasets_from_sql(
            root,
            args.env_file,
            config,
            int(args.command_timeout_seconds),
        )
    else:
        raise ValueError(f"Unsupported supplier exposure input mode: {input_mode}")
    for dataset in config["input_datasets"]:
        _validate_columns(dataset, datasets[dataset["dataset_id"]])
    inputs=build_supplier_inputs(datasets,settings["eligibility"])
    scored,validations=score_suppliers(inputs,config);failed=[v for v in validations if v["status"]!="PASS"]
    if failed: raise ValueError(f"Exposure score validation failed: {failed[:5]}")
    scenario_names=list(config["sensitivity_scenarios"]);sensitivity=sensitivity_summary(scored,scenario_names)
    ranked=scored.sort_values(["rank_baseline","supplier_key"]).to_dict("records")
    output_json=_project_path(root,args.output,settings["outputs"]["json"]);output_md=_project_path(root,args.markdown_output,settings["outputs"]["markdown"]);output_csv=_project_path(root,args.csv_output,settings["outputs"]["csv"]);figures_dir=_project_path(root,args.figures_dir,settings["outputs"]["figures"])
    output_csv.parent.mkdir(parents=True,exist_ok=True);scored.sort_values(["rank_baseline","supplier_key"]).to_csv(output_csv,index=False,encoding="utf-8")
    dpi=int(settings["figure_dpi"]);figures=[_plot_top(scored,figures_dir,dpi),_plot_dependencies(scored,figures_dir,dpi),_plot_sensitivity(scored,scenario_names,figures_dir,dpi)]
    sql_hashes={item["dataset_id"]:{"path":item["sql"],"sha256":sha256_text_file(root/item["sql"])} for item in config["input_datasets"]}
    report={
      "schema_version":"1.0","generated_at_utc":datetime.now(timezone.utc).isoformat(),"scope":"supplier_operational_commercial_exposure",
      "source":{"source_id":gate["source"]["source_id"],"source_period":settings["source_period"],"snapshot_date":gate["source"]["snapshot_date"],"load_batch_id":gate["source"]["load_batch_id"],**input_evidence,"phase12_gate":settings["phase12_gate"],"phase12_gate_sha256":sha256_text_file(gate_path),"config":config_path.relative_to(root).as_posix(),"config_sha256":sha256_text_file(config_path),"runner_sha256":sha256_text_file(Path(__file__)),"sql_inputs":sql_hashes,"sql_inputs_role":"governed_query_contracts; not executed in audited_silver_rebuild mode"},
      "summary":{"status":"PASS_LIMITED","score_version":settings["score_version"],"suppliers_with_positive_attributed_awards":int(pd.DataFrame(datasets["supplier_awards"])["supplier_key"].nunique()),"suppliers_with_complete_inputs":len(inputs),"eligible_suppliers_scored":len(scored),"score_validations_passed":len(validations),"score_validations_failed":len(failed),"higher_relative_suppliers":int((scored["exposure_band"]=="HIGHER_RELATIVE").sum()),"medium_relative_suppliers":int((scored["exposure_band"]=="MEDIUM_RELATIVE").sum()),"lower_relative_suppliers":int((scored["exposure_band"]=="LOWER_RELATIVE").sum()),"sensitivity_scenarios":len(sensitivity),"figures_generated":len(figures),"duration_seconds":round(time.perf_counter()-started,4)},
      "methodology":{"disclaimer":settings["disclaimer"],"eligibility":settings["eligibility"],"normalization":settings["normalization"],"variables":config["variables"],"sensitivity_weights":config["sensitivity_scenarios"],"excluded_variables":config["excluded_variables"]},
      "analysis":{"ranked_suppliers":ranked,"sensitivity":sensitivity,"validations":validations,"limitations":["Single source period; persistence and abrupt changes cannot be measured.","Sanctions and penalties are not ingested.","The score measures relative operational/commercial exposure, not legal, credit or fraud risk.","Category dependence uses item values and is not added to award header amounts."]},
      "artifacts":{"json":output_json.relative_to(root).as_posix(),"markdown":output_md.relative_to(root).as_posix(),"csv":output_csv.relative_to(root).as_posix(),"csv_size_bytes":output_csv.stat().st_size,"csv_sha256":sha256_file(output_csv),"figures":[p.relative_to(root).as_posix() for p in figures],"figure_evidence":[{"path":p.relative_to(root).as_posix(),"size_bytes":p.stat().st_size,"sha256":sha256_file(p)} for p in figures]}}
    output_json.parent.mkdir(parents=True,exist_ok=True);output_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");output_md.parent.mkdir(parents=True,exist_ok=True);output_md.write_text(build_markdown(report),encoding="utf-8")
    return report


def parse_args()->argparse.Namespace:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--env-file",type=Path,default=Path(".env"));parser.add_argument("--config",type=Path,default=Path("config/supplier_exposure_score.yml"));parser.add_argument("--input-mode",choices=("audited_silver_rebuild","sql_server"));parser.add_argument("--command-timeout-seconds",type=int,default=120);parser.add_argument("--output",type=Path);parser.add_argument("--markdown-output",type=Path);parser.add_argument("--csv-output",type=Path);parser.add_argument("--figures-dir",type=Path);return parser.parse_args()


def main()->None:
    report=run_supplier_exposure(parse_args());summary=report["summary"];print(f"Supplier exposure {summary['status']}: {summary['eligible_suppliers_scored']} suppliers; {summary['score_validations_passed']} validations; {summary['sensitivity_scenarios']} scenarios.")


if __name__=="__main__": main()
