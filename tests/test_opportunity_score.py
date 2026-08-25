from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from procurement_intelligence.analytics.run_opportunity_score import (
    FIGURES,
    load_opportunity_config,
    percentile_score,
    score_population,
)
from procurement_intelligence.extraction.download_ocds import (
    sha256_file,
    sha256_text_file,
)


CONFIG_PATH = Path("config/opportunity_score.yml")
REPORT_PATH = Path(
    "reports/opportunity/oece_ocds_seace_v3_2026_07_opportunity_score.json"
)
MARKDOWN_PATH = Path(
    "reports/opportunity/oece_ocds_seace_v3_2026_07_opportunity_score.md"
)
CSV_PATH = Path(
    "reports/opportunity/oece_ocds_seace_v3_2026_07_opportunity_score.csv"
)


def test_opportunity_contract_has_transparent_weights_and_exclusions() -> None:
    config = load_opportunity_config(CONFIG_PATH)
    variables = config["variables"]

    assert len(variables) == 5
    assert sum(item["baseline_weight"] for item in variables) == pytest.approx(1.0)
    assert len(config["sensitivity_scenarios"]) == 3
    assert {item["variable_id"] for item in config["excluded_variables"]} >= {
        "growth",
        "recurrence",
    }
    assert config["opportunity_score"]["source_period"] == "2026-07"


def test_invalid_opportunity_weights_are_rejected(tmp_path: Path) -> None:
    import yaml

    config = load_opportunity_config(CONFIG_PATH)
    config["variables"][0]["baseline_weight"] = 0.99
    path = tmp_path / "invalid.yml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match="must sum to 1"):
        load_opportunity_config(path)


def test_percentile_normalization_handles_direction_and_ties() -> None:
    values = pd.Series([10, 20, 20, 40])

    higher = percentile_score(values, "higher_is_better")
    lower = percentile_score(values, "lower_is_better")

    assert higher.tolist() == pytest.approx([0, 50, 50, 100])
    assert lower.tolist() == pytest.approx([100, 50, 50, 0])


def test_score_population_validates_weighted_arithmetic() -> None:
    config = load_opportunity_config(CONFIG_PATH)
    gate = json.loads(
        Path(
            "reports/concentration/oece_ocds_seace_v3_2026_07_market_concentration.json"
        ).read_text(encoding="utf-8")
    )

    frame, validations = score_population(gate["analysis"]["all_markets"], config)

    assert len(frame) == 87
    assert all(item["status"] == "PASS" for item in validations)
    assert frame["score_baseline"].between(0, 100).all()
    assert frame["rank_baseline"].min() == 1


def test_committed_opportunity_evidence_matches_current_inputs_and_code() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["summary"]["status"] == "PASS_PILOT"
    assert report["summary"]["eligible_markets_scored"] == 87
    assert report["summary"]["score_validations_failed"] == 0
    assert report["summary"]["sensitivity_scenarios"] == 3
    assert report["source"]["config_sha256"] == sha256_text_file(CONFIG_PATH)
    assert report["source"]["runner_sha256"] == sha256_text_file(
        Path("src/procurement_intelligence/analytics/run_opportunity_score.py")
    )
    gate_path = Path(report["source"]["phase11_gate"])
    assert report["source"]["phase11_gate_sha256"] == sha256_text_file(gate_path)
    assert report["artifacts"]["csv_sha256"] == sha256_file(CSV_PATH)


def test_opportunity_top_result_and_sensitivity_are_evidence_backed() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    top = report["analysis"]["ranked_markets"][0]
    sensitivity = {item["scenario"]: item for item in report["analysis"]["sensitivity"]}

    assert top["classification_code"] == "72141107"
    assert top["score_baseline"] == pytest.approx(96.56976744)
    assert top["rank_accessibility_heavy"] == 1
    assert sensitivity["demand_heavy"]["top10_overlap"] == 10
    assert sensitivity["accessibility_heavy"]["top10_overlap"] == 9
    assert sensitivity["accessibility_heavy"]["maximum_absolute_rank_shift"] == 16


def test_opportunity_figures_and_csv_are_current() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    evidence = {item["path"]: item for item in report["artifacts"]["figure_evidence"]}

    assert {Path(path).name for path in evidence} == set(FIGURES)
    assert len(pd.read_csv(CSV_PATH)) == 87
    for relative, metadata in evidence.items():
        path = Path(relative)
        assert path.stat().st_size > 20_000
        assert metadata["sha256"] == sha256_file(path)


def test_opportunity_artifacts_do_not_overclaim_or_leak_paths() -> None:
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "No es pronóstico de ventas" in markdown
    assert "Crecimiento y recurrencia: excluidos" in markdown
    assert "C:\\Users\\" not in report_text
    assert "run-opportunity-score" in pyproject
