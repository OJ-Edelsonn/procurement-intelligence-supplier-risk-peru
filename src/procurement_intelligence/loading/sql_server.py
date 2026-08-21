"""Safe SQL Server primitives for staging and dimensional loads."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyodbc

from procurement_intelligence.settings import SqlServerSettings

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
GO_PATTERN = re.compile(r"^\s*GO\s*;?\s*$", re.IGNORECASE | re.MULTILINE)


def quote_identifier(identifier: str) -> str:
    """Validate and quote a SQL Server identifier controlled by the repository."""

    if not IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Unsafe SQL Server identifier: {identifier!r}")
    return f"[{identifier}]"


def split_sql_batches(sql: str) -> list[str]:
    """Split sqlcmd-style GO batches without treating GO as T-SQL."""

    return [batch.strip() for batch in GO_PATTERN.split(sql) if batch.strip()]


def connect_sql_server(
    settings: SqlServerSettings,
    database: str | None = None,
    *,
    autocommit: bool = False,
    timeout_seconds: int = 15,
) -> pyodbc.Connection:
    return pyodbc.connect(
        settings.connection_string(database),
        autocommit=autocommit,
        timeout=timeout_seconds,
    )


def ensure_database(settings: SqlServerSettings) -> bool:
    """Create the configured user database when absent; return whether it was created."""

    database_sql = quote_identifier(settings.database)
    with connect_sql_server(settings, "master", autocommit=True) as connection:
        exists = connection.cursor().execute(
            "SELECT CASE WHEN DB_ID(?) IS NULL THEN 0 ELSE 1 END;",
            settings.database,
        ).fetchval()
        if exists:
            return False
        connection.cursor().execute(f"CREATE DATABASE {database_sql};")
    return True


def execute_sql_scripts(
    connection: pyodbc.Connection, scripts: Iterable[Path]
) -> None:
    cursor = connection.cursor()
    for script in scripts:
        sql = script.read_text(encoding="utf-8")
        for batch in split_sql_batches(sql):
            cursor.execute(batch)


def arrow_type_to_sql(data_type: pa.DataType) -> str:
    if pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
        return "nvarchar(max)"
    if pa.types.is_decimal(data_type):
        return f"decimal({data_type.precision},{data_type.scale})"
    if pa.types.is_int64(data_type):
        return "bigint"
    if pa.types.is_boolean(data_type):
        return "bit"
    if pa.types.is_date32(data_type) or pa.types.is_date64(data_type):
        return "date"
    if pa.types.is_timestamp(data_type):
        return "datetime2(6)"
    raise ValueError(f"Unsupported Arrow type for SQL Server staging: {data_type}")


def staging_table_ddl(schema: str, table: str, arrow_schema: pa.Schema) -> str:
    qualified = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    columns = ",\n        ".join(
        f"{quote_identifier(field.name)} {arrow_type_to_sql(field.type)} NULL"
        for field in arrow_schema
    )
    return (
        f"DROP TABLE IF EXISTS {qualified};\n"
        f"CREATE TABLE {qualified}\n(\n        {columns}\n);"
    )


def _normalize_scalar(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is not None:
            value = value.tz_convert("UTC").tz_localize(None)
        return value.to_pydatetime()
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (str, bytes, Decimal, date, int, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _chunks(values: list[tuple[Any, ...]], size: int) -> Iterable[list[tuple[Any, ...]]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _odbc_input_sizes(frame: pd.DataFrame) -> list[Any]:
    """Prevent fast_executemany from sizing text buffers from only the first row."""

    sizes: list[Any] = []
    for column in frame.columns:
        values = frame[column].dropna()
        if values.empty:
            sizes.append(None)
            continue
        first = values.iloc[0]
        if isinstance(first, str):
            maximum = max(int(values.astype("string").str.len().max()), 1)
            if maximum <= 4000:
                sizes.append((pyodbc.SQL_WVARCHAR, maximum, 0))
            else:
                sizes.append((pyodbc.SQL_WLONGVARCHAR, 0, 0))
        else:
            sizes.append(None)
    return sizes


def bulk_insert_frame(
    connection: pyodbc.Connection,
    schema: str,
    table: str,
    frame: pd.DataFrame,
    *,
    batch_rows: int,
) -> int:
    """Insert a frame using parameterized fast executemany batches."""

    if frame.columns.duplicated().any():
        raise ValueError(f"Duplicate columns in {schema}.{table}")
    qualified = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    columns = ", ".join(quote_identifier(column) for column in frame.columns)
    placeholders = ", ".join("?" for _ in frame.columns)
    statement = f"INSERT INTO {qualified} ({columns}) VALUES ({placeholders});"
    rows = [
        tuple(_normalize_scalar(value) for value in row)
        for row in frame.itertuples(index=False, name=None)
    ]
    cursor = connection.cursor()
    cursor.fast_executemany = True
    cursor.setinputsizes(_odbc_input_sizes(frame))
    for chunk in _chunks(rows, batch_rows):
        cursor.executemany(statement, chunk)
    return len(rows)


def table_columns(
    connection: pyodbc.Connection, schema: str, table: str
) -> list[str]:
    rows = connection.cursor().execute(
        """
        SELECT c.name
        FROM sys.columns AS c
        INNER JOIN sys.tables AS t ON t.object_id = c.object_id
        INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
        WHERE s.name = ? AND t.name = ?
        ORDER BY c.column_id;
        """,
        schema,
        table,
    ).fetchall()
    return [row[0] for row in rows]


def table_row_count(connection: pyodbc.Connection, schema: str, table: str) -> int:
    qualified = f"{quote_identifier(schema)}.{quote_identifier(table)}"
    return int(connection.cursor().execute(f"SELECT COUNT_BIG(*) FROM {qualified};").fetchval())
