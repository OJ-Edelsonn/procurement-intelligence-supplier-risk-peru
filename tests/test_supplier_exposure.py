from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from procurement_intelligence.analytics.run_supplier_exposure import (
    FIGURES,
    build_supplier_inputs,
    load_exposure_config,
    score_suppliers,
)
from procurement_intelligence.extraction.download_ocds import (
    sha256_file,
    sha256_text_file,
)


CONFIG_PATH = Path("config/supplier_exposure_score.yml")
REPORT_PATH = Path(
    "reports/supplier_exposure/oece_ocds_seace_v3_2026_07_supplier_exposure.json"
)
MARKDOWN_PATH = Path(
    "reports/supplier_exposure/oece_ocds_seace_v3_2026_07_supplier_exposure.md"
)
CSV_PATH = Path(
    "reports/supplier_exposure/oece_ocds_seace_v3_2026_07_supplier_exposure.csv"
)


def test_exposure_contract_is_limited_and_transparent() -> None:
    config = load_exposure_config(CONFIG_PATH)
    settings = config["supplier_exposure"]

    assert settings["input_mode"] == "audited_silver_rebuild"
    assert sum(item["baseline_weight"] for item in config["variables"]) == pytest.approx(1)
    assert len(config["sensitivity_scenarios"]) == 3
    assert {item["variable_id"] for item in config["excluded_variables"]} >= {
        "sanctions",
        "penalties",
        "recurrence",
        "creditworthiness",
    }
    assert "no constituye una calificación crediticia" in settings["disclaimer"]


def test_invalid_exposure_weights_are_rejected(tmp_path: Path) -> None:
    import yaml

    config = load_exposure_config(CONFIG_PATH)
    config["variables"][0]["baseline_weight"] = 0.99
    path = tmp_path / "invalid.yml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    with pytest.raises(ValueError, match="must sum to 1"):
        load_exposure_config(path)


def test_supplier_aggregation_preserves_native_grains() -> None:
    datasets = {
        "supplier_awards": [
            {"award_fact_key": 1, "supplier_key": 10, "supplier_name": "A", "buyer_key": 1, "amount_pen": 60},
            {"award_fact_key": 2, "supplier_key": 10, "supplier_name": "A", "buyer_key": 1, "amount_pen": 40},
            {"award_fact_key": 3, "supplier_key": 20, "supplier_name": "B", "buyer_key": 1, "amount_pen": 50},
            {"award_fact_key": 4, "supplier_key": 20, "supplier_name": "B", "buyer_key": 2, "amount_pen": 50},
        ],
        "supplier_items": [
            {"supplier_key": 10, "standard_category_key": 1, "amount_pen": 100},
            {"supplier_key": 20, "standard_category_key": 1, "amount_pen": 50},
            {"supplier_key": 20, "standard_category_key": 2, "amount_pen": 50},
        ],
        "supplier_contracts": [
            {"contract_fact_key": 1, "supplier_key": 10, "amount_pen": 80},
            {"contract_fact_key": 2, "supplier_key": 20, "amount_pen": 50},
        ],
    }
    frame = build_supplier_inputs(
        datasets,
        {
            "minimum_awards": 2,
            "minimum_known_buyer_amount_coverage_pct": 95,
            "minimum_known_category_item_amount_coverage_pct": 80,
        },
    ).set_index("supplier_key")

    assert frame.loc[10, "top_buyer_share_pct"] == pytest.approx(100)
    assert frame.loc[10, "award_hhi"] == pytest.approx(5200)
    assert frame.loc[20, "top_category_share_pct"] == pytest.approx(50)
    assert frame["is_score_eligible"].all()


def test_scoring_recomputes_all_eligible_suppliers() -> None:
    config = load_exposure_config(CONFIG_PATH)
    source = pd.read_csv(CSV_PATH)

    scored, validations = score_suppliers(source, config)

    assert len(scored) == 179
    assert all(item["status"] == "PASS" for item in validations)
    assert scored["score_baseline"].between(0, 100).all()
    assert scored["rank_baseline"].min() == 1


def test_committed_exposure_evidence_matches_inputs_and_code() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["summary"]["status"] == "PASS_LIMITED"
    assert report["summary"]["eligible_suppliers_scored"] == 179
    assert report["summary"]["score_validations_failed"] == 0
    assert report["source"]["input_mode"] == "audited_silver_rebuild"
    assert report["source"]["config_sha256"] == sha256_text_file(CONFIG_PATH)
    assert report["source"]["runner_sha256"] == sha256_text_file(
        Path("src/procurement_intelligence/analytics/run_supplier_exposure.py")
    )
    for metadata in report["source"]["sql_inputs"].values():
        assert metadata["sha256"] == sha256_text_file(Path(metadata["path"]))
    assert report["artifacts"]["csv_sha256"] == sha256_file(CSV_PATH)


def test_exposure_top_result_and_sensitivity_are_evidence_backed() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    top = report["analysis"]["ranked_suppliers"][0]
    sensitivity = {item["scenario"]: item for item in report["analysis"]["sensitivity"]}

    assert top["supplier_key"] == 1329
    assert top["score_baseline"] == pytest.approx(80.96910112)
    assert top["maximum_absolute_rank_shift"] == 1
    assert sensitivity["dependency_heavy"]["top10_overlap"] == 9
    assert sensitivity["materiality_heavy"]["top10_overlap"] == 4
    assert sensitivity["materiality_heavy"]["maximum_absolute_rank_shift"] == 70


def test_exposure_figures_and_csv_are_current() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    evidence = {item["path"]: item for item in report["artifacts"]["figure_evidence"]}

    assert {Path(path).name for path in evidence} == set(FIGURES)
    assert len(pd.read_csv(CSV_PATH)) == 179
    for relative, metadata in evidence.items():
        path = Path(relative)
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert path.stat().st_size > 20_000
        assert metadata["sha256"] == sha256_file(path)


def test_exposure_artifacts_do_not_overclaim_or_leak_paths() -> None:
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "no constituye una calificación crediticia" in markdown
    assert "no demuestra que un proveedor sea riesgoso" in markdown
    assert "Sanciones, penalidades, recurrencia" in markdown
    assert "C:\\Users\\" not in report_text
    assert "run-supplier-exposure" in pyproject
