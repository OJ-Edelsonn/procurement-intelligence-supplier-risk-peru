"""Build a reproducible benchmark from governed artifacts and read-only SQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from procurement_intelligence.loading.sql_server import connect_sql_server
from procurement_intelligence.settings import load_settings, load_sql_server_settings
from procurement_intelligence.validation.validate_sql_server import execute_sql


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nested(payload: Any, dotted_path: str) -> Any:
    value = payload
    for part in dotted_path.split("."):
        if isinstance(value, Mapping):
            value = value[part]
        elif isinstance(value, list):
            value = value[int(part)]
        else:
            raise KeyError(dotted_path)
    return value


def load_benchmark_config(path: Path) -> dict[str, Any]:
    """Load and validate the benchmark contract."""

    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("benchmark"), dict):
        raise ValueError("Benchmark config must contain a benchmark mapping.")
    settings = config["benchmark"]
    if str(settings.get("schema_version")) != "1.0":
        raise ValueError("Unsupported benchmark schema_version; expected 1.0.")
    if int(settings.get("sql_repeats", 0)) < 1:
        raise ValueError("sql_repeats must be positive.")
    identifiers: set[str] = set()
    for section in ("runtime_evidence", "outcome_metrics", "sql_queries"):
        items = config.get(section, [])
        if not isinstance(items, list):
            raise ValueError(f"{section} must be a list.")
        for item in items:
            identifier = str(item["metric_id"])
            if identifier in identifiers:
                raise ValueError(f"Duplicate benchmark metric_id: {identifier}")
            identifiers.add(identifier)
    return config


def _resolve_path(value: str, root: Path, data_root: Path) -> Path:
    rendered = value.replace("${DATA_ROOT}", str(data_root))
    path = Path(rendered)
    return path if path.is_absolute() else root / path


def _display_path(path: Path, root: Path, data_root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "${DATA_ROOT}/" + path.resolve().relative_to(data_root.resolve()).as_posix()


def _extract(spec: Mapping[str, Any], payload: Mapping[str, Any]) -> Any:
    if "value_path" in spec:
        return _nested(payload, str(spec["value_path"]))
    collection = _nested(payload, str(spec["collection_path"]))
    matches = [
        item
        for item in collection
        if str(item[str(spec["match_field"])]) == str(spec["match_value"])
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one match for {spec['metric_id']}; found {len(matches)}."
        )
    return matches[0][str(spec["value_field"])]


def _normalize_number(value: Any) -> int | float | str | bool | None:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isfinite(number) and number.is_integer():
        return int(number)
    return number


def _collect_artifact_metrics(
    specs: list[dict[str, Any]], root: Path, data_root: Path
) -> list[dict[str, Any]]:
    cache: dict[Path, dict[str, Any]] = {}
    metrics: list[dict[str, Any]] = []
    for spec in specs:
        path = _resolve_path(str(spec["artifact"]), root, data_root)
        if not path.is_file():
            raise FileNotFoundError(f"Missing benchmark evidence: {path}")
        payload = cache.setdefault(path, _read_json(path))
        metrics.append(
            {
                "metric_id": str(spec["metric_id"]),
                "label": str(spec["label"]),
                "value": _normalize_number(_extract(spec, payload)),
                "unit": str(spec["unit"]),
                "source_artifact": _display_path(path, root, data_root),
                "source_sha256": _sha256(path),
            }
        )
    return metrics


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def benchmark_sql_queries(
    specs: list[dict[str, Any]],
    root: Path,
    env_file: Path,
    *,
    warmups: int,
    repeats: int,
    timeout_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Measure governed read-only queries on one reusable SQL connection."""

    settings = load_sql_server_settings(env_file)
    connection_clock = time.perf_counter()
    connection = connect_sql_server(settings)
    connection_seconds = time.perf_counter() - connection_clock
    results: list[dict[str, Any]] = []
    try:
        connection.timeout = timeout_seconds
        database_size = execute_sql(
            connection,
            "SELECT SUM(CONVERT(bigint, size)) * 8192 AS database_size_bytes "
            "FROM sys.database_files;",
        )[0]["database_size_bytes"]
        for spec in specs:
            sql_path = root / str(spec["sql"])
            sql = sql_path.read_text(encoding="utf-8-sig")
            for _ in range(warmups):
                warm_rows = execute_sql(connection, sql)
                if not warm_rows:
                    raise ValueError(f"SQL warmup returned no rows: {spec['metric_id']}")
            timings: list[float] = []
            row_count = 0
            for _ in range(repeats):
                clock = time.perf_counter()
                rows = execute_sql(connection, sql)
                timings.append((time.perf_counter() - clock) * 1000)
                row_count = len(rows)
                if not rows:
                    raise ValueError(f"SQL benchmark returned no rows: {spec['metric_id']}")
            results.append(
                {
                    "metric_id": str(spec["metric_id"]),
                    "label": str(spec["label"]),
                    "sql": sql_path.relative_to(root).as_posix(),
                    "sql_sha256": _sha256(sql_path),
                    "warmups": warmups,
                    "repeats": repeats,
                    "result_rows": row_count,
                    "min_ms": round(min(timings), 4),
                    "median_ms": round(statistics.median(timings), 4),
                    "mean_ms": round(statistics.fmean(timings), 4),
                    "p95_ms": round(_percentile(timings, 0.95), 4),
                    "max_ms": round(max(timings), 4),
                    "samples_ms": [round(value, 4) for value in timings],
                }
            )
    finally:
        connection.close()
    return results, {
        "database": settings.database,
        "database_size_bytes": int(database_size),
        "connection_seconds": round(connection_seconds, 4),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Fase 16 — Benchmark y resultados verificables",
        "",
        f"- Estado: **{summary['status']}**",
        f"- Periodo fuente: `{report['scope']['source_period']}`",
        f"- Corrida automatizada observada: **{summary['automated_run_seconds']:.2f} s**",
        f"- Pasos ejecutados/reutilizados: **{summary['steps_executed']} / {summary['steps_reused']}**",
        "- Línea base manual: **no disponible; no se calcula ni se afirma ahorro de tiempo**.",
        "",
        "## Tiempos registrados en artefactos",
        "",
        "| Componente | Segundos | Evidencia |",
        "|---|---:|---|",
    ]
    for item in report["runtime_evidence"]:
        lines.append(
            f"| {item['label']} | {float(item['value']):,.4f} | `{item['source_artifact']}` |"
        )
    lines.extend(
        [
            "",
            "La suma de componentes procede de ejecuciones documentadas distintas y no se presenta como una única corrida end-to-end.",
            "",
            "## Benchmark SQL de solo lectura",
            "",
            "| Consulta | Filas | Mediana ms | p95 ms |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in report["sql_benchmarks"]:
        lines.append(
            f"| {item['label']} | {item['result_rows']:,} | {item['median_ms']:,.4f} | {item['p95_ms']:,.4f} |"
        )
    lines.extend(
        [
            "",
            "## Resultados cuantitativos",
            "",
            "| Métrica | Valor | Unidad |",
            "|---|---:|---|",
        ]
    )
    for item in report["outcome_metrics"]:
        value = item["value"]
        rendered = f"{value:,.4f}" if isinstance(value, float) else f"{value:,}" if isinstance(value, int) else str(value)
        lines.append(f"| {item['label']} | {rendered} | {item['unit']} |")
    lines.extend(
        [
            "",
            "## Interpretación responsable",
            "",
            "Los tiempos corresponden al equipo y la instancia SQL local utilizados en esta ejecución; no son un SLA. No existe una medición manual comparable, por lo que no se declara reducción porcentual de tiempo. Los montos de licitación, adjudicación y contrato pertenecen a hechos distintos y no deben sumarse.",
            "",
        ]
    )
    return "\n".join(lines)


def run_benchmark(
    config_path: Path,
    env_file: Path,
    output: Path | None = None,
    markdown_output: Path | None = None,
) -> dict[str, Any]:
    """Collect evidence, benchmark SQL, and publish JSON/Markdown results."""

    started = time.perf_counter()
    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = load_benchmark_config(config_path)
    settings = config["benchmark"]
    data_root = load_settings(env_file).data_root
    runtime = _collect_artifact_metrics(config["runtime_evidence"], root, data_root)
    outcomes = _collect_artifact_metrics(config["outcome_metrics"], root, data_root)
    sql_results, database = benchmark_sql_queries(
        config["sql_queries"],
        root,
        env_file,
        warmups=int(settings["sql_warmups"]),
        repeats=int(settings["sql_repeats"]),
        timeout_seconds=int(settings["sql_timeout_seconds"]),
    )
    pipeline_path = root / str(settings["pipeline_report"])
    pipeline = _read_json(pipeline_path)
    pipeline_summary = pipeline["summary"]
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "source_id": settings["source_id"],
            "source_period": settings["source_period"],
            "snapshot_date": settings["snapshot_date"],
            "benchmark_config": config_path.relative_to(root).as_posix(),
            "benchmark_config_sha256": _sha256(config_path),
            "pipeline_report": pipeline_path.relative_to(root).as_posix(),
            "pipeline_report_sha256": _sha256(pipeline_path),
        },
        "summary": {
            "status": "PASS",
            "runtime_metrics": len(runtime),
            "outcome_metrics": len(outcomes),
            "sql_queries_benchmarked": len(sql_results),
            "automated_run_seconds": float(pipeline_summary["duration_seconds"]),
            "steps_executed": int(pipeline_summary["steps_executed"]),
            "steps_reused": int(pipeline_summary["steps_reused"]),
            "steps_failed": int(pipeline_summary["steps_failed"]),
            "manual_baseline_status": "NOT_AVAILABLE",
            "time_savings_claimed": False,
            "benchmark_duration_seconds": round(time.perf_counter() - started, 4),
        },
        "runtime_evidence": runtime,
        "runtime_component_sum_seconds": round(
            sum(float(item["value"]) for item in runtime), 4
        ),
        "sql_environment": database,
        "sql_benchmarks": sql_results,
        "outcome_metrics": outcomes,
        "limitations": [
            "Component timings were captured in different governed runs and are not one end-to-end elapsed time.",
            "SQL latency is specific to the local workstation, SQL Server Express instance, cache state and concurrent workload.",
            "No measured manual baseline exists, so time saved and percentage reduction are intentionally not calculated.",
            "Power BI visual formatting and final refresh timing remain deferred until the dashboard is frozen.",
        ],
    }
    json_path = output or root / str(settings["output_json"])
    md_path = markdown_output or root / str(settings["output_markdown"])
    if not json_path.is_absolute():
        json_path = root / json_path
    if not md_path.is_absolute():
        md_path = root / md_path
    json_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = json_path.with_suffix(json_path.suffix + ".part")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, json_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/benchmark.yml"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_benchmark(
        args.config, args.env_file, args.output, args.markdown_output
    )
    summary = report["summary"]
    print(
        f"Benchmark {summary['status']}: {summary['sql_queries_benchmarked']} SQL queries, "
        f"{summary['outcome_metrics']} outcomes, {summary['automated_run_seconds']:.2f}s pipeline run."
    )


if __name__ == "__main__":
    main()

