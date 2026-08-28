from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from procurement_intelligence.benchmark.run_benchmark import (
    _collect_artifact_metrics,
    _percentile,
    load_benchmark_config,
)


def test_repository_benchmark_contract_is_valid() -> None:
    config = load_benchmark_config(Path("config/benchmark.yml"))
    assert len(config["runtime_evidence"]) == 10
    assert len(config["outcome_metrics"]) == 17
    assert len(config["sql_queries"]) == 3
    assert config["benchmark"]["sql_repeats"] == 3


def test_collect_artifact_metric_with_lookup(tmp_path: Path) -> None:
    artifact = tmp_path / "metrics.json"
    artifact.write_text(
        json.dumps({"items": [{"id": "wanted", "value": "42.5"}]}),
        encoding="utf-8",
    )
    specs = [
        {
            "metric_id": "answer",
            "label": "Answer",
            "artifact": artifact.as_posix(),
            "collection_path": "items",
            "match_field": "id",
            "match_value": "wanted",
            "value_field": "value",
            "unit": "units",
        }
    ]
    metrics = _collect_artifact_metrics(specs, tmp_path, tmp_path)
    assert metrics[0]["value"] == 42.5
    assert len(metrics[0]["source_sha256"]) == 64


def test_percentile_interpolates() -> None:
    assert _percentile([10.0, 20.0, 30.0], 0.95) == pytest.approx(29.0)


def test_duplicate_metric_ids_are_rejected(tmp_path: Path) -> None:
    config = yaml.safe_load(Path("config/benchmark.yml").read_text(encoding="utf-8"))
    config["sql_queries"][0]["metric_id"] = config["runtime_evidence"][0]["metric_id"]
    path = tmp_path / "benchmark.yml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate benchmark metric_id"):
        load_benchmark_config(path)

