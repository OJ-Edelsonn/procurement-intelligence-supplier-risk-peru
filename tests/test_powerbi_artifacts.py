from __future__ import annotations

import json
from pathlib import Path

from procurement_intelligence.powerbi.deploy_semantic_layer import (
    load_powerbi_config,
    validate_upstream_gates,
)


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


def test_pbip_text_contains_no_local_user_path_or_credentials() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in PROJECT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".tmdl", ".pbip", ".pbir", ".pbism"}
    ).casefold()
    assert "c:\\users\\" not in text
    assert "password=" not in text
    assert "pwd=" not in text
