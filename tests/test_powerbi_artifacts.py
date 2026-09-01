from __future__ import annotations

import json
from pathlib import Path

from procurement_intelligence.powerbi.deploy_semantic_layer import (
    load_powerbi_config,
    validate_upstream_gates,
)
from procurement_intelligence.powerbi.validate_project import validate_powerbi_project


CONFIG = Path("config/powerbi_dashboard.yml")
PROJECT = Path("powerbi/project")


def test_powerbi_contract_and_upstream_gates() -> None:
    config = load_powerbi_config(CONFIG)
    assert len(config["tables"]) == 12
    assert len(config["pages"]) == 5
    assert config["powerbi"]["storage_mode"] == "import"
    gates = validate_upstream_gates(Path.cwd(), config["powerbi"])
    assert len(gates) == 4
    assert {gate["status"] for gate in gates} == {
        "PASS",
        "PASS_PILOT",
        "PASS_LIMITED",
    }


def test_committed_pbip_shape_matches_contract() -> None:
    table_files = list(
        (PROJECT / "ProcurementIntelligence.SemanticModel/definition/tables").glob(
            "*.tmdl"
        )
    )
    pages_root = PROJECT / "ProcurementIntelligence.Report/definition/pages"
    page_files = list(pages_root.glob("*/page.json"))
    visual_files = list(pages_root.glob("*/visuals/*/visual.json"))
    assert len(table_files) == 12
    assert len(page_files) == 5
    assert len(visual_files) == 30


def test_powerbi_page_names_are_user_facing_spanish() -> None:
    pages_root = PROJECT / "ProcurementIntelligence.Report/definition/pages"
    display_names = {
        json.loads(path.read_text(encoding="utf-8"))["displayName"]
        for path in pages_root.glob("*/page.json")
    }
    assert display_names == {
        "Resumen Ejecutivo",
        "Oportunidad de Mercado",
        "Inteligencia de Proveedores",
        "Exposición de Proveedores",
        "Inteligencia de Compradores",
    }


def test_powerbi_ranking_tables_have_explicit_business_sorting() -> None:
    pages_root = PROJECT / "ProcurementIntelligence.Report/definition/pages"
    expected_sorts = {
        "7005ff111442b7bde8d9/visuals/ea9c57b654ab05908e49/visual.json": (
            "Measure",
            "Monto Ítems Adjudicados Top PEN",
            "Descending",
        ),
        "09d44d6b9c674ccf2dfc/visuals/c0fa875a714581d681b0/visual.json": (
            "Measure",
            "Monto Licitado Top PEN",
            "Descending",
        ),
        "4064f3b7506d5fe5c18e/visuals/9e81ebeb9447961be549/visual.json": (
            "Column",
            "rank_baseline",
            "Ascending",
        ),
    }
    for relative_path, (field_kind, property_name, direction) in expected_sorts.items():
        visual = json.loads((pages_root / relative_path).read_text(encoding="utf-8"))
        sort = visual["visual"]["query"]["sortDefinition"]["sort"]
        assert len(sort) == 1
        assert sort[0]["direction"] == direction
        assert sort[0]["field"][field_kind]["Property"] == property_name


def test_semantic_layer_load_evidence_passes() -> None:
    report = json.loads(
        Path("reports/powerbi/phase14_semantic_layer_load.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["summary"] == {
        "status": "PASS",
        "tables": 3,
        "views": 10,
        "score_rows_loaded": 266,
        "query_surfaces": 12,
        "validations_passed": 4,
        "validations_failed": 0,
        "duration_seconds": report["summary"]["duration_seconds"],
    }


def test_final_powerbi_validation_evidence_passes(tmp_path: Path) -> None:
    generated = validate_powerbi_project(
        CONFIG,
        refresh_seconds=200.0,
        output_override=tmp_path / "phase14_powerbi_validation.json",
    )
    assert generated["summary"] == {
        "status": "PASS",
        "pages": 5,
        "visuals": 30,
        "semantic_tables": 12,
        "screenshots": 5,
        "refresh_duration_seconds": 200.0,
        "validations_passed": 8,
        "validations_failed": 0,
    }


def test_pbip_text_contains_no_local_user_path_or_credentials() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in PROJECT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".tmdl", ".pbip", ".pbir", ".pbism"}
    ).casefold()
    assert "c:\\users\\" not in text
    assert "password=" not in text
    assert "pwd=" not in text
