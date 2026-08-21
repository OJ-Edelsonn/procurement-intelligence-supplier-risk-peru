from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pytest
import yaml

from procurement_intelligence.loading.build_dw_frames import (
    _apply_pen_conversion,
    _canonical_by_key,
    _reconciliation_columns,
)
from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.loading.sql_server import (
    _odbc_input_sizes,
    arrow_type_to_sql,
    quote_identifier,
    split_sql_batches,
    staging_table_ddl,
)
from procurement_intelligence.settings import load_sql_server_settings


def test_sql_settings_reject_system_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "SQL_SERVER",
        "SQL_DATABASE",
        "SQL_DRIVER",
        "SQL_TRUSTED_CONNECTION",
        "SQL_ENCRYPT",
        "SQL_TRUST_SERVER_CERTIFICATE",
    ):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                r"SQL_SERVER=localhost\SQLEXPRESS",
                "SQL_DATABASE=master",
                "SQL_DRIVER=ODBC Driver 18 for SQL Server",
                "SQL_TRUSTED_CONNECTION=yes",
                "SQL_ENCRYPT=yes",
                "SQL_TRUST_SERVER_CERTIFICATE=yes",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="system database"):
        load_sql_server_settings(env_file)


def test_identifier_quoting_blocks_uncontrolled_sql() -> None:
    assert quote_identifier("fact_award") == "[fact_award]"
    with pytest.raises(ValueError, match="Unsafe"):
        quote_identifier("dw.fact_award; DROP TABLE x")


def test_go_batches_are_split_for_pyodbc() -> None:
    sql = "SELECT 1;\nGO\nSELECT 'GO inside text';\n  go ;\nSELECT 3;"

    assert split_sql_batches(sql) == [
        "SELECT 1;",
        "SELECT 'GO inside text';",
        "SELECT 3;",
    ]


@pytest.mark.parametrize(
    ("arrow_type", "sql_type"),
    [
        (pa.string(), "nvarchar(max)"),
        (pa.decimal128(38, 14), "decimal(38,14)"),
        (pa.int64(), "bigint"),
        (pa.bool_(), "bit"),
        (pa.date32(), "date"),
        (pa.timestamp("us", tz="UTC"), "datetime2(6)"),
    ],
)
def test_arrow_types_have_lossless_sql_staging_types(
    arrow_type: pa.DataType, sql_type: str
) -> None:
    assert arrow_type_to_sql(arrow_type) == sql_type


def test_staging_ddl_preserves_normalized_column_names() -> None:
    schema = pa.schema(
        [
            pa.field("ocid", pa.string()),
            pa.field("source_row_number", pa.int64()),
        ]
    )

    ddl = staging_table_ddl("stg", "procurement_process", schema)

    assert "DROP TABLE IF EXISTS [stg].[procurement_process]" in ddl
    assert "[ocid] nvarchar(max) NULL" in ddl
    assert "[source_row_number] bigint NULL" in ddl


def test_fast_executemany_uses_full_text_column_length() -> None:
    frame = pd.DataFrame(
        {
            "text_value": ["short", "a much longer value"],
            "numeric_value": [1, 2],
        }
    )

    sizes = _odbc_input_sizes(frame)

    assert sizes[0][1] == len("a much longer value")
    assert sizes[1] is None


def test_canonical_selection_uses_modal_value_and_lexical_tie_break() -> None:
    frame = pd.DataFrame(
        {
            "party": ["A", "A", "A", "B", "B"],
            "name": ["Beta", "Beta", "Alfa", "Zulu", "Árbol"],
        }
    )

    selected = _canonical_by_key(frame, "party", "name")

    assert selected["A"] == "Beta"
    assert selected["B"] == "Árbol"


def test_pen_conversion_never_invents_missing_foreign_rate() -> None:
    frame = pd.DataFrame(
        {
            "currency": ["PEN", "USD", "EUR"],
            "amount": [Decimal("10"), Decimal("10"), Decimal("10")],
            "rate": [None, Decimal("3.75"), None],
        }
    )

    rates, converted, available = _apply_pen_conversion(
        frame, "currency", "amount", "rate"
    )

    assert rates.tolist() == [Decimal("1"), Decimal("3.75"), None]
    assert converted.tolist() == [Decimal("10"), Decimal("37.50"), None]
    assert available.tolist() == [True, True, False]


def test_reconciliation_preserves_header_item_difference() -> None:
    parent = pd.DataFrame(
        {"ocid": ["p1"], "header_amount": [Decimal("100.00")]}
    )
    child = pd.DataFrame(
        {
            "ocid": ["p1", "p1"],
            "item_amount": [Decimal("40.00"), Decimal("55.00")],
        }
    )

    item_sum, difference, reconciled = _reconciliation_columns(
        parent, child, ["ocid"], "header_amount", "item_amount"
    )

    assert item_sum.tolist() == [Decimal("95.00")]
    assert difference.tolist() == [Decimal("5.00")]
    assert reconciled.tolist() == [False]


def test_physical_contract_declares_all_objects_and_safe_bridges() -> None:
    config = yaml.safe_load(Path("config/sql_server.yml").read_text(encoding="utf-8"))
    assert config["reconciliation"] == {
        "expected_dimensions": 8,
        "expected_facts": 6,
        "expected_bridges": 2,
        "compare_staging_to_silver": True,
        "compare_dw_to_dimensional_report": True,
        "require_zero_foreign_key_orphans": True,
    }
    assert "ddl_bundle_sha256" in config["load"]["idempotency_key"]
    for relative_path in config["ddl_scripts"]:
        assert Path(relative_path).is_file()

    dimensions = Path("sql/ddl/002_dimensions.sql").read_text(encoding="utf-8")
    facts = Path("sql/ddl/003_facts_and_bridges.sql").read_text(encoding="utf-8")
    assert dimensions.count("CREATE TABLE dw.dim_") == 8
    assert "currency_code nvarchar(20) NOT NULL" in dimensions
    assert facts.count("CREATE TABLE dw.fact_") == 6
    assert facts.count("CREATE TABLE dw.bridge_") == 2
    process_bridge = facts.split(
        "CREATE TABLE dw.bridge_process_tenderer", maxsplit=1
    )[1].split("CREATE TABLE dw.bridge_award_supplier", maxsplit=1)[0]
    award_bridge = facts.split(
        "CREATE TABLE dw.bridge_award_supplier", maxsplit=1
    )[1]
    assert "amount" not in process_bridge.casefold()
    assert "amount" not in award_bridge.casefold()


def test_committed_sql_load_report_matches_current_contracts() -> None:
    report_path = Path(
        "reports/sql/oece_ocds_seace_v3_2026_07_sql_server_load.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["summary"]["status"] == "PASS"
    assert report["summary"]["load_batch_id"] == 4
    assert report["summary"]["staging_rows"] == 231113
    assert report["summary"]["dimension_rows"] == 26592
    assert report["summary"]["fact_rows"] == 23056
    assert report["summary"]["bridge_rows"] == 37511
    assert report["summary"]["row_reconciliations_failed"] == 0
    assert len(report["table_load_metrics"]) == 38
    assert report["source"]["etl_summary_sha256"] == sha256_text_file(
        Path(report["source"]["etl_summary"])
    )
    assert report["source"]["model_config_sha256"] == sha256_text_file(
        Path(report["source"]["model_config"])
    )
    assert report["source"]["physical_config_sha256"] == sha256_text_file(
        Path(report["source"]["physical_config"])
    )
    for ddl in report["source"]["ddl_scripts"]:
        assert ddl["sha256"] == sha256_text_file(Path(ddl["path"]))
    assert "C:\\Users\\" not in report_path.read_text(encoding="utf-8")
