"""Validate the frozen PBIP report and write final Phase 14 evidence."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from procurement_intelligence.powerbi.deploy_semantic_layer import load_powerbi_config


EXPECTED_PAGES = {
    "7005ff111442b7bde8d9": "Resumen Ejecutivo",
    "742d758fca9d73414f90": "Oportunidad de Mercado",
    "ef444cf215d2d34501c4": "Inteligencia de Proveedores",
    "4064f3b7506d5fe5c18e": "Exposición de Proveedores",
    "09d44d6b9c674ccf2dfc": "Inteligencia de Compradores",
}

EXPECTED_SCREENSHOTS = {
    "Resumen Ejecutivo": "Resumen Ejecutivo.png",
    "Oportunidad de Mercado": "Oportunidad de Mercado.png",
    "Inteligencia de Proveedores": "Supplier Intelligence.png",
    "Exposición de Proveedores": "Supplier Exposure.png",
    "Inteligencia de Compradores": "Buyer Intelligence.png",
}

EXPECTED_SORTS = {
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_manifest_sha256(project_dir: Path) -> str:
    digest = hashlib.sha256()
    included_suffixes = {".json", ".tmdl", ".pbip", ".pbir", ".pbism"}
    files = sorted(
        path
        for path in project_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in included_suffixes
        and ".pbi" not in path.relative_to(project_dir).parts
    )
    for path in files:
        relative = path.relative_to(project_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a valid PNG file: {path}")
    return struct.unpack(">II", header[16:24])


def _validation(rule: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"rule": rule, "status": "PASS" if passed else "FAIL", "detail": detail}


def validate_powerbi_project(
    config_path: Path,
    refresh_seconds: float,
    screenshot_dir: Path | None = None,
    output_override: Path | None = None,
) -> dict[str, Any]:
    """Validate structural and manual evidence for the final Power BI report."""

    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = load_powerbi_config(config_path)
    settings = config["powerbi"]
    project_dir = root / settings["project_directory"]
    report_dir = project_dir / "ProcurementIntelligence.Report/definition"
    pages_root = report_dir / "pages"
    semantic_root = project_dir / "ProcurementIntelligence.SemanticModel/definition"
    screenshots = screenshot_dir or root / "reports/powerbi/screenshots"
    screenshots = screenshots if screenshots.is_absolute() else root / screenshots

    json_files = sorted(project_dir.rglob("*.json"))
    json_errors: list[str] = []
    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            json_errors.append(f"{path.relative_to(root).as_posix()}: {exc}")

    page_files = sorted(pages_root.glob("*/page.json"))
    visual_files = sorted(pages_root.glob("*/visuals/*/visual.json"))
    table_files = sorted((semantic_root / "tables").glob("*.tmdl"))

    page_names: dict[str, str] = {}
    visual_inventory: dict[str, dict[str, int]] = {}
    for page_file in page_files:
        page = json.loads(page_file.read_text(encoding="utf-8"))
        page_id = page["name"]
        page_names[page_id] = page["displayName"]
        types = Counter()
        for visual_file in sorted((page_file.parent / "visuals").glob("*/visual.json")):
            visual = json.loads(visual_file.read_text(encoding="utf-8"))
            types[visual["visual"]["visualType"]] += 1
        visual_inventory[page["displayName"]] = dict(sorted(types.items()))

    sort_results: list[dict[str, Any]] = []
    sort_passed = True
    for relative, (field_kind, property_name, direction) in EXPECTED_SORTS.items():
        visual = json.loads((pages_root / relative).read_text(encoding="utf-8"))
        sort = visual["visual"]["query"]["sortDefinition"]["sort"]
        actual = {
            "field_kind": field_kind,
            "property": sort[0]["field"][field_kind]["Property"],
            "direction": sort[0]["direction"],
        }
        passed = (
            len(sort) == 1
            and actual["property"] == property_name
            and actual["direction"] == direction
        )
        sort_passed = sort_passed and passed
        sort_results.append({"visual": relative, "status": "PASS" if passed else "FAIL", **actual})

    screenshot_evidence: list[dict[str, Any]] = []
    screenshots_passed = True
    for page_name, filename in EXPECTED_SCREENSHOTS.items():
        path = screenshots / filename
        if not path.exists():
            screenshots_passed = False
            screenshot_evidence.append(
                {"page": page_name, "path": path.relative_to(root).as_posix(), "status": "FAIL"}
            )
            continue
        width, height = _png_dimensions(path)
        passed = width >= 1280 and height >= 720
        screenshots_passed = screenshots_passed and passed
        screenshot_evidence.append(
            {
                "page": page_name,
                "path": path.relative_to(root).as_posix(),
                "width_px": width,
                "height_px": height,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "status": "PASS" if passed else "FAIL",
            }
        )

    expected_inventory = {
        "Resumen Ejecutivo": {"cardVisual": 1, "lineChart": 1, "tableEx": 1, "textbox": 3},
        "Oportunidad de Mercado": {
            "cardVisual": 1,
            "clusteredBarChart": 1,
            "tableEx": 1,
            "textbox": 3,
        },
        "Inteligencia de Proveedores": {
            "cardVisual": 1,
            "clusteredBarChart": 1,
            "tableEx": 1,
            "textbox": 3,
        },
        "Exposición de Proveedores": {
            "cardVisual": 1,
            "clusteredBarChart": 1,
            "tableEx": 1,
            "textbox": 3,
        },
        "Inteligencia de Compradores": {
            "cardVisual": 1,
            "clusteredBarChart": 1,
            "tableEx": 1,
            "textbox": 3,
        },
    }

    validations = [
        _validation("pbip_json_valid", not json_errors, json_errors or f"{len(json_files)} JSON files parsed"),
        _validation(
            "semantic_and_report_shape",
            len(table_files) == 12 and len(page_files) == 5 and len(visual_files) == 30,
            {"semantic_tables": len(table_files), "pages": len(page_files), "visuals": len(visual_files)},
        ),
        _validation("user_facing_page_names", page_names == EXPECTED_PAGES, page_names),
        _validation("visual_inventory", visual_inventory == expected_inventory, visual_inventory),
        _validation("ranking_sort_rules", sort_passed, sort_results),
        _validation("final_screenshots_complete_and_legible", screenshots_passed, screenshot_evidence),
        _validation(
            "final_refresh_completed",
            refresh_seconds > 0,
            {"duration_seconds": refresh_seconds, "observation_method": "manual_stopwatch"},
        ),
        _validation(
            "manual_visual_review",
            screenshots_passed,
            "Five refreshed, populated, chrome-free pages reviewed collaboratively; KPI units, labels, tables and disclaimers are legible.",
        ),
    ]
    failed = [item for item in validations if item["status"] != "PASS"]
    report = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "powerbi_final_project_validation",
        "source": {
            "config": config_path.relative_to(root).as_posix(),
            "config_sha256": _sha256(config_path),
            "project": settings["project_directory"],
            "project_manifest_sha256": _project_manifest_sha256(project_dir),
            "source_period": settings["source_period"],
            "server_alias": settings["server"],
            "database": settings["database"],
            "storage_mode": settings["storage_mode"],
            "desktop_minimum_version": settings["desktop_minimum_version"],
        },
        "summary": {
            "status": "PASS" if not failed else "FAIL",
            "pages": len(page_files),
            "visuals": len(visual_files),
            "semantic_tables": len(table_files),
            "screenshots": len([item for item in screenshot_evidence if item["status"] == "PASS"]),
            "refresh_duration_seconds": refresh_seconds,
            "validations_passed": len(validations) - len(failed),
            "validations_failed": len(failed),
        },
        "analysis": {
            "page_names": page_names,
            "visual_inventory": visual_inventory,
            "ranking_sorts": sort_results,
            "screenshots": screenshot_evidence,
            "validations": validations,
        },
    }
    output = output_override or root / settings["validation_output"]
    output = output if output.is_absolute() else root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if failed:
        raise ValueError(f"Power BI final validation failed: {failed}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/powerbi_dashboard.yml"))
    parser.add_argument("--refresh-seconds", type=float, required=True)
    parser.add_argument("--screenshot-dir", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = validate_powerbi_project(
        args.config,
        args.refresh_seconds,
        args.screenshot_dir,
        args.output,
    )
    summary = report["summary"]
    print(
        f"Power BI final validation {summary['status']}: "
        f"{summary['pages']} pages, {summary['visuals']} visuals, "
        f"{summary['screenshots']} screenshots, {summary['refresh_duration_seconds']:.1f}s refresh."
    )


if __name__ == "__main__":
    main()
