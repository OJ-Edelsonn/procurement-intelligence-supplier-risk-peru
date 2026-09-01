"""Build a deterministic, source-controlled Power BI Project (PBIP)."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from procurement_intelligence.powerbi.deploy_semantic_layer import (
    load_powerbi_config,
)


REPORT_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/report/3.3.0/schema.json"
)
PAGE_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/page/2.1.0/schema.json"
)
VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/visualContainer/2.9.0/schema.json"
)
PAGES_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/"
    "definition/pagesMetadata/1.0.0/schema.json"
)


def _stable_hex(value: str, length: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _stable_guid(value: str) -> str:
    token = _stable_hex(value, 32)
    return f"{token[:8]}-{token[8:12]}-{token[12:16]}-{token[16:20]}-{token[20:]}"


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _tmdl_name(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def _tmdl_scalar(value: str) -> str:
    if '"' not in value:
        return value
    return '"' + value.replace('"', '""') + '"'


def _build_table_tmdl(table: dict[str, Any], server: str, database: str) -> str:
    name = table["model_name"]
    source = table["source_object"]
    lines = [f"table {_tmdl_name(name)}", ""]
    for measure in table.get("measures", []):
        expression = measure["expression"]
        if scale := measure.get("scale"):
            expression = f"DIVIDE ( {expression}, {int(scale)} )"
        lines.extend(
            [
                f"\tmeasure {_tmdl_name(measure['name'])} = {expression}",
                f"\t\tformatString: {_tmdl_scalar(measure['format'])}",
                "",
            ]
        )
    for column, data_type in table["columns"].items():
        lines.extend(
            [
                f"\tcolumn {_tmdl_name(column)}",
                f"\t\tdataType: {data_type}",
                "\t\tsummarizeBy: none",
                f"\t\tsourceColumn: {column}",
                "",
            ]
        )
    lines.extend(
        [
            f"\tpartition {_tmdl_name(name)} = m",
            "\t\tmode: import",
            "\t\tsource =",
            "\t\t\tlet",
            f'\t\t\t\tSource = Sql.Database("{server}", "{database}"),',
            f'\t\t\t\tData = Source{{[Schema="bi", Item="{source}"]}}[Data]',
            "\t\t\tin",
            "\t\t\t\tData",
            "",
        ]
    )
    return "\n".join(lines)


def _field(table: str, property_name: str, field_type: str) -> dict[str, Any]:
    return {
        field_type: {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": property_name,
        }
    }


def _projection(
    table: str,
    property_name: str,
    field_type: str,
    *,
    active: bool = False,
) -> dict[str, Any]:
    projection = {
        "field": _field(table, property_name, field_type),
        "queryRef": f"{table}.{property_name}",
        "nativeQueryRef": property_name,
    }
    if active:
        projection["active"] = True
    return projection


def _position(x: int, y: int, width: int, height: int, z: int) -> dict[str, int]:
    return {
        "x": x,
        "y": y,
        "z": z,
        "height": height,
        "width": width,
        "tabOrder": z,
    }


def _literal(value: str) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": value}}}


def _visual_title(title: str) -> dict[str, Any]:
    return {
        "title": [
            {
                "properties": {
                    "show": _literal("true"),
                    "text": _literal("'" + title.replace("'", "''") + "'"),
                    "fontSize": _literal("13D"),
                    "fontColor": {
                        "solid": {"color": _literal("'#17324D'")}
                    },
                }
            }
        ],
        "background": [
            {
                "properties": {
                    "show": _literal("true"),
                    "color": {"solid": {"color": _literal("'#FFFFFF'")}},
                    "transparency": _literal("0D"),
                }
            }
        ],
        "border": [
            {
                "properties": {
                    "show": _literal("true"),
                    "color": {"solid": {"color": _literal("'#D5DFE8'")}},
                    "radius": _literal("6D"),
                }
            }
        ],
    }


def _textbox(
    seed: str,
    text: str,
    position: dict[str, int],
    *,
    font_size: int,
    color: str,
    font_family: str = "Segoe UI",
    background: str | None = None,
) -> dict[str, Any]:
    container: dict[str, Any] = {
        "$schema": VISUAL_SCHEMA,
        "name": _stable_hex(seed),
        "position": position,
        "visual": {
            "visualType": "textbox",
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {
                                    "textRuns": [
                                        {
                                            "value": text,
                                            "textStyle": {
                                                "fontFamily": font_family,
                                                "fontSize": f"{font_size}px",
                                                "color": color,
                                            },
                                        }
                                    ],
                                    "horizontalTextAlignment": "left",
                                }
                            ]
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "background": [
                    {
                        "properties": {
                            "show": _literal("true" if background else "false"),
                            **(
                                {
                                    "color": {
                                        "solid": {
                                            "color": _literal(f"'{background}'")
                                        }
                                    },
                                    "transparency": _literal("0D"),
                                }
                                if background
                                else {}
                            ),
                        }
                    }
                ],
                "border": [{"properties": {"show": _literal("false")}}],
                "padding": [
                    {
                        "properties": {
                            "top": _literal("4D"),
                            "bottom": _literal("4D"),
                            "left": _literal("8D"),
                            "right": _literal("8D"),
                        }
                    }
                ],
            },
        },
    }
    return container


def _card(seed: str, spec: dict[str, Any], position: dict[str, int]) -> dict[str, Any]:
    table = spec["table"]
    projections = [
        _projection(table, measure, "Measure") for measure in spec["measures"]
    ]
    return {
        "$schema": VISUAL_SCHEMA,
        "name": _stable_hex(seed),
        "position": position,
        "visual": {
            "visualType": "cardVisual",
            "query": {"queryState": {"Data": {"projections": projections}}},
            "objects": {
                "outline": [
                    {
                        "properties": {"show": _literal("false")},
                        "selector": {"id": "default"},
                    }
                ],
                "value": [
                    {
                        "properties": {
                            "fontSize": _literal("20D"),
                            "labelDisplayUnits": _literal("0D"),
                            "fontColor": {
                                "solid": {"color": _literal("'#0B6E75'")}
                            },
                        },
                        "selector": {"id": "default"},
                    }
                ],
                "label": [
                    {
                        "properties": {"fontSize": _literal("10D")},
                        "selector": {"id": "default"},
                    }
                ],
            },
            "visualContainerObjects": _visual_title("Indicadores principales"),
        },
    }


def _chart(seed: str, spec: dict[str, Any], position: dict[str, int]) -> dict[str, Any]:
    table = spec["table"]
    category = spec["category"]
    measures = spec["measures"]
    category_projection = _projection(table, category, "Column", active=True)
    measure_projections = [
        _projection(table, measure, "Measure") for measure in measures
    ]
    sort_property = category if spec["type"] == "lineChart" else measures[0]
    sort_type = "Column" if spec["type"] == "lineChart" else "Measure"
    direction = "Ascending" if spec["type"] == "lineChart" else "Descending"
    return {
        "$schema": VISUAL_SCHEMA,
        "name": _stable_hex(seed),
        "position": position,
        "visual": {
            "visualType": spec["type"],
            "query": {
                "queryState": {
                    "Category": {"projections": [category_projection]},
                    "Y": {"projections": measure_projections},
                },
                "sortDefinition": {
                    "sort": [
                        {
                            "field": _field(table, sort_property, sort_type),
                            "direction": direction,
                        }
                    ],
                    "isDefaultSort": True,
                },
            },
            "objects": {
                "categoryAxis": [
                    {
                        "properties": {
                            "show": _literal("true"),
                            "fontSize": _literal("9D"),
                        }
                    }
                ],
                "valueAxis": [
                    {
                        "properties": {
                            "show": _literal("true"),
                            "gridlineStyle": _literal("'dotted'"),
                        }
                    }
                ],
            },
            "visualContainerObjects": _visual_title(spec["title"]),
        },
    }


def _table(seed: str, spec: dict[str, Any], position: dict[str, int]) -> dict[str, Any]:
    table = spec["table"]
    return {
        "$schema": VISUAL_SCHEMA,
        "name": _stable_hex(seed),
        "position": position,
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            _projection(table, column, "Column")
                            for column in spec["columns"]
                        ]
                    }
                }
            },
            "objects": {
                "columnHeaders": [
                    {
                        "properties": {
                            "columnAdjustment": _literal("'growToFit'"),
                            "autoSizeColumnWidth": _literal("true"),
                            "fontColor": {
                                "solid": {"color": _literal("'#FFFFFF'")}
                            },
                            "backColor": {
                                "solid": {"color": _literal("'#17324D'")}
                            },
                        }
                    }
                ]
            },
            "visualContainerObjects": _visual_title(spec["title"]),
        },
    }


def _theme(filename: str) -> dict[str, Any]:
    return {
        "name": filename,
        "dataColors": [
            "#0B6E75",
            "#E98732",
            "#2D5F8B",
            "#6A8E3A",
            "#8A5A8C",
            "#D1A13A",
        ],
        "good": "#2E7D32",
        "neutral": "#D1A13A",
        "bad": "#C62828",
        "maximum": "#0B6E75",
        "center": "#F3C969",
        "minimum": "#D95D39",
        "foreground": "#17324D",
        "foregroundNeutralSecondary": "#66788A",
        "background": "#F4F7FA",
        "secondaryBackground": "#FFFFFF",
        "tableAccent": "#0B6E75",
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "color": "#17324D"},
            "header": {"fontFace": "Segoe UI Semibold", "color": "#17324D"},
            "label": {"fontFace": "Segoe UI", "color": "#415466"},
            "callout": {"fontFace": "Segoe UI Semibold", "color": "#0B6E75"},
        },
        "visualStyles": {
            "tableEx": {
                "*": {
                    "columnHeaders": [
                        {
                            "autoSizeColumnWidth": True,
                            "columnAdjustment": "growToFit",
                        }
                    ]
                }
            }
        },
    }


def build_project(config_path: Path) -> dict[str, Any]:
    """Generate the semantic model and report folders from the governed YAML."""

    config_path = config_path.resolve()
    root = config_path.parent.parent
    config = load_powerbi_config(config_path)
    settings = config["powerbi"]
    project_root = root / settings["project_directory"]
    name = settings["project_name"]
    semantic_dir = project_root / f"{name}.SemanticModel"
    report_dir = project_root / f"{name}.Report"
    semantic_definition = semantic_dir / "definition"
    report_definition = report_dir / "definition"

    if project_root.exists():
        shutil.rmtree(project_root)
    semantic_definition.mkdir(parents=True)
    (report_definition / "pages").mkdir(parents=True)

    _json(
        semantic_dir / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {"qnaEnabled": False},
        },
    )
    platform_schema = (
        "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/"
        "platformProperties/2.1.0/schema.json"
    )
    _json(
        semantic_dir / ".platform",
        {
            "$schema": platform_schema,
            "metadata": {
                "type": "SemanticModel",
                "displayName": f"{name} Semantic Model",
                "description": "Modelo semántico gobernado del piloto peruano de Procurement Intelligence.",
            },
            "config": {
                "version": "2.0",
                "logicalId": _stable_guid(f"{name}:semantic-model"),
            },
        },
    )
    database_id = _stable_hex(f"{name}:database", 32)
    (semantic_definition / "database.tmdl").write_text(
        f"database {database_id}\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n\tlanguage: 3082\n",
        encoding="utf-8",
    )
    table_references = "\n".join(
        f"ref table {_tmdl_name(table['model_name'])}" for table in config["tables"]
    )
    (semantic_definition / "model.tmdl").write_text(
        "model Model\n"
        "\tculture: es-PE\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: es-PE\n\n"
        + table_references
        + "\n",
        encoding="utf-8",
    )
    table_dir = semantic_definition / "tables"
    table_dir.mkdir()
    for index, table in enumerate(config["tables"], 1):
        filename = f"{index:02d}_{_stable_hex(table['model_name'], 12)}.tmdl"
        (table_dir / filename).write_text(
            _build_table_tmdl(
                table,
                settings["server"],
                settings["database"],
            ),
            encoding="utf-8",
        )

    _json(
        report_dir / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{name}.SemanticModel"}},
        },
    )
    _json(
        report_dir / ".platform",
        {
            "$schema": platform_schema,
            "metadata": {
                "type": "Report",
                "displayName": "Procurement Intelligence & Supplier Exposure – Perú",
                "description": "Dashboard ejecutivo reproducible para el universo oficial OECE/SEACE del piloto.",
            },
            "config": {
                "version": "2.0",
                "logicalId": _stable_guid(f"{name}:report"),
            },
        },
    )
    theme_suffix = _stable_hex(json.dumps(config, sort_keys=True, ensure_ascii=False), 8)
    theme_filename = f"ProcurementExecutive-{theme_suffix}.json"
    _json(
        report_definition / "report.json",
        {
            "$schema": REPORT_SCHEMA,
            "themeCollection": {
                "customTheme": {
                    "name": theme_filename,
                    "reportVersionAtImport": {
                        "visual": "2.6.0",
                        "report": "3.1.0",
                        "page": "2.3.0",
                    },
                    "type": "RegisteredResources",
                }
            },
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {
                            "name": theme_filename,
                            "path": theme_filename,
                            "type": "CustomTheme",
                        }
                    ],
                }
            ],
        },
    )
    _json(
        report_definition / "version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    resources = report_dir / "StaticResources" / "RegisteredResources"
    _json(resources / theme_filename, _theme(theme_filename))

    page_order: list[str] = []
    visual_count = 0
    for page in config["pages"]:
        page_name = _stable_hex(f"{name}:page:{page['page_id']}")
        page_order.append(page_name)
        page_dir = report_definition / "pages" / page_name
        visuals_dir = page_dir / "visuals"
        visuals_dir.mkdir(parents=True)
        _json(
            page_dir / "page.json",
            {
                "$schema": PAGE_SCHEMA,
                "name": page_name,
                "displayName": page["display_name"],
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
                "objects": {
                    "background": [
                        {
                            "properties": {
                                "color": {
                                    "solid": {"color": _literal("'#F4F7FA'")}
                                },
                                "transparency": _literal("0D"),
                            }
                        }
                    ]
                },
            },
        )
        visuals = [
            _textbox(
                f"{page_name}:title",
                page["title"],
                _position(24, 12, 1232, 46, 0),
                font_size=23,
                color="#17324D",
                font_family="Segoe UI Semibold",
            ),
            _textbox(
                f"{page_name}:subtitle",
                page["subtitle"],
                _position(24, 58, 1232, 30, 10),
                font_size=11,
                color="#52687A",
            ),
            _card(
                f"{page_name}:card",
                page["card"],
                _position(24, 92, 1232, 128, 20),
            ),
            _chart(
                f"{page_name}:chart",
                page["chart"],
                _position(24, 232, 590, 380, 30),
            ),
            _table(
                f"{page_name}:table",
                page["table"],
                _position(630, 232, 626, 380, 40),
            ),
            _textbox(
                f"{page_name}:note",
                page["note"],
                _position(24, 624, 1232, 72, 50),
                font_size=11,
                color="#6A4700",
                font_family="Segoe UI Semibold",
                background="#FFF4D6",
            ),
        ]
        for visual in visuals:
            _json(visuals_dir / visual["name"] / "visual.json", visual)
        visual_count += len(visuals)

    _json(
        report_definition / "pages" / "pages.json",
        {
            "$schema": PAGES_SCHEMA,
            "pageOrder": page_order,
            "activePageName": page_order[0],
        },
    )
    _json(
        project_root / f"{name}.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{name}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    return {
        "project": project_root,
        "entrypoint": project_root / f"{name}.pbip",
        "semantic_tables": len(config["tables"]),
        "pages": len(config["pages"]),
        "visuals": visual_count,
        "theme": theme_filename,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("config/powerbi_dashboard.yml")
    )
    return parser.parse_args()


def main() -> None:
    result = build_project(parse_args().config)
    print(
        f"PBIP built: {result['pages']} pages, {result['visuals']} visuals, "
        f"{result['semantic_tables']} semantic tables at {result['entrypoint']}"
    )


if __name__ == "__main__":
    main()
