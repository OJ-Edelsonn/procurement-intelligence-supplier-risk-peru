"""Transform an OECE OCDS CSV archive into typed, partitioned Silver Parquet."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PureWindowsPath
from typing import Any
from zipfile import ZipFile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from procurement_intelligence.extraction.download_ocds import (
    sha256_file,
    sha256_text_file,
)
from procurement_intelligence.profiling.profile_ocds_csv import CANDIDATE_GRAINS
from procurement_intelligence.settings import Settings, load_settings
from procurement_intelligence.validation.validate_ocds_csv import read_archive

CONFIG_TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
SOURCE_PERIOD_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}$")
LINEAGE_KINDS = {
    "source_id": "string",
    "source_period": "string",
    "snapshot_date": "date",
    "ingestion_run_id": "string",
    "source_file_name": "string",
    "source_file_sha256": "string",
    "source_table_name": "string",
    "source_row_number": "integer",
    "loaded_at_utc": "datetime",
}
LOGGER = logging.getLogger(__name__)


def load_etl_config(path: Path) -> dict[str, Any]:
    """Load and validate the Silver transformation contract."""

    with path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    validate_etl_config(config)
    return config


def validate_etl_config(config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValueError("ETL config root must be a mapping")
    etl = config.get("etl")
    tables = config.get("tables")
    typing = config.get("typing")
    treatments = config.get("treatments")
    if not isinstance(etl, dict):
        raise ValueError("etl must be a mapping")
    if not isinstance(tables, dict) or not tables:
        raise ValueError("tables must be a non-empty mapping")
    if set(tables) != set(CANDIDATE_GRAINS):
        raise ValueError("configured tables must match the 22 profiled OCDS tables")
    output_names = list(tables.values())
    if len(output_names) != len(set(output_names)):
        raise ValueError("Silver output table names must be unique")
    if not all(
        isinstance(name, str) and CONFIG_TABLE_PATTERN.fullmatch(name)
        for name in output_names
    ):
        raise ValueError("Silver output names must use lower snake_case")
    if not isinstance(typing, dict) or not isinstance(treatments, dict):
        raise ValueError("typing and treatments must be mappings")
    precision = etl.get("decimal_precision")
    scale = etl.get("decimal_scale")
    if not isinstance(precision, int) or not isinstance(scale, int):
        raise ValueError("decimal precision and scale must be integers")
    if not (1 <= precision <= 38 and 0 <= scale <= precision):
        raise ValueError("decimal precision/scale is outside decimal128 limits")
    duplicate_tables = treatments.get("exact_duplicate_tables", [])
    if not isinstance(duplicate_tables, list) or not set(duplicate_tables).issubset(
        tables
    ):
        raise ValueError("exact duplicate treatment references an unmapped table")
    for target in treatments.get("classification_targets", []):
        if target.get("table") not in tables:
            raise ValueError("classification target references an unmapped table")


def validate_source_period(source_period: str) -> None:
    """Require a real calendar month in the stable YYYY-MM representation."""

    if not SOURCE_PERIOD_PATTERN.fullmatch(source_period):
        raise ValueError("source_period must use YYYY-MM")
    year, month = (int(part) for part in source_period.split("-"))
    try:
        date(year, month, 1)
    except ValueError as exc:
        raise ValueError("source_period must contain a valid calendar month") from exc


def normalize_column_name(source_column: str) -> str:
    """Convert an OCDS JSON path into stable lower snake_case."""

    value = source_column.replace("/0/", "/")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_").lower()
    if not value:
        raise ValueError(f"Column normalizes to an empty name: {source_column!r}")
    return value


def normalized_column_map(columns: list[str]) -> dict[str, str]:
    mapping = {column: normalize_column_name(column) for column in columns}
    normalized = list(mapping.values())
    if len(normalized) != len(set(normalized)):
        collisions = sorted(
            name for name in set(normalized) if normalized.count(name) > 1
        )
        raise ValueError(f"Normalized column collision: {collisions}")
    return mapping


def infer_source_kind(source_column: str, config: dict[str, Any]) -> str:
    typing = config["typing"]
    if source_column in typing.get("integer_columns", []):
        return "integer"
    if source_column in typing.get("boolean_columns", []):
        return "boolean"
    if source_column in typing.get("exact_datetime_columns", []):
        return "datetime"
    if any(source_column.endswith(suffix) for suffix in typing.get("datetime_suffixes", [])):
        return "datetime"
    if any(source_column.endswith(suffix) for suffix in typing.get("decimal_suffixes", [])):
        return "decimal"
    return "string"


def _strip_string_cells(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    cleaned = dataframe.copy()
    changed_cells = 0
    for column in cleaned.columns:
        original = cleaned[column]
        stripped = original.str.strip()
        changed_cells += int((original.notna() & original.ne(stripped)).sum())
        cleaned[column] = stripped
    return cleaned, changed_cells


def _classification_target(
    source_table: str, config: dict[str, Any]
) -> dict[str, Any] | None:
    return next(
        (
            target
            for target in config["treatments"].get("classification_targets", [])
            if target["table"] == source_table
        ),
        None,
    )


def _apply_classification_treatment(
    dataframe: pd.DataFrame, target: dict[str, Any] | None, config: dict[str, Any]
) -> tuple[pd.DataFrame, int, str | None]:
    if target is None:
        return dataframe, 0, None
    columns = [
        target["id_column"],
        target["description_column"],
        target["scheme_column"],
    ]
    missing_columns = [column for column in columns if column not in dataframe]
    if missing_columns:
        raise ValueError(f"Missing classification columns: {missing_columns}")
    transformed = dataframe.copy()
    missing_mask = transformed[columns].isna().any(axis=1)
    unknown = config["etl"]["unknown_classification"]
    transformed.loc[
        missing_mask & transformed[target["id_column"]].isna(), target["id_column"]
    ] = unknown["id"]
    transformed.loc[
        missing_mask & transformed[target["description_column"]].isna(),
        target["description_column"],
    ] = unknown["description"]
    transformed.loc[
        missing_mask & transformed[target["scheme_column"]].isna(),
        target["scheme_column"],
    ] = unknown["scheme"]
    flag_column = "dq_classification_was_missing"
    transformed[flag_column] = pd.Series(
        missing_mask.to_numpy(), index=transformed.index, dtype="boolean"
    )
    return transformed, int(missing_mask.sum()), flag_column


def _ruc_format_flags(
    dataframe: pd.DataFrame, source_table: str, config: dict[str, Any]
) -> tuple[pd.DataFrame, int, str | None]:
    rule = config["treatments"].get("ruc_flag", {})
    if rule.get("table") != source_table:
        return dataframe, 0, None
    required = [rule["scheme_column"], rule["identifier_column"]]
    missing = [column for column in required if column not in dataframe]
    if missing:
        raise ValueError(f"Missing RUC flag columns: {missing}")
    transformed = dataframe.copy()
    applicable = (
        transformed[rule["scheme_column"]]
        .str.upper()
        .eq(rule["scheme_value"].upper())
        .fillna(False)
    )
    normalized = transformed[rule["identifier_column"]].fillna("").str.strip()
    valid = normalized.str.fullmatch(r"\d{11}")
    flags = pd.Series(pd.NA, index=transformed.index, dtype="boolean")
    flags.loc[applicable] = valid.loc[applicable].to_numpy()
    transformed[rule["output_column"]] = flags
    return transformed, int((applicable & ~valid).sum()), rule["output_column"]


def _decimal_is_zero(value: Any) -> bool:
    if pd.isna(value):
        return False
    try:
        return Decimal(str(value)) == 0
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def _simple_quality_flag(
    dataframe: pd.DataFrame,
    source_table: str,
    config: dict[str, Any],
    treatment_name: str,
) -> tuple[pd.DataFrame, int, str | None]:
    rule = config["treatments"].get(treatment_name, {})
    if rule.get("table") != source_table:
        return dataframe, 0, None
    amount_column = rule["amount_column"]
    if amount_column not in dataframe:
        raise ValueError(f"Missing quality flag column: {amount_column}")
    transformed = dataframe.copy()
    if treatment_name == "zero_amount_flag":
        flags = transformed[amount_column].map(_decimal_is_zero).astype("boolean")
        flagged_count = int(flags.sum())
    elif treatment_name == "final_value_flag":
        flags = transformed[amount_column].notna().astype("boolean")
        flagged_count = int((~flags).sum())
    else:
        raise ValueError(f"Unsupported simple flag treatment: {treatment_name}")
    transformed[rule["output_column"]] = flags
    return transformed, flagged_count, rule["output_column"]


def _to_decimal(value: Any, table: str, column: str) -> Decimal | None:
    if pd.isna(value):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{table}.{column} contains a non-decimal value") from exc


def _convert_series(
    series: pd.Series, kind: str, table: str, column: str
) -> pd.Series:
    if kind == "string":
        return series.astype("string")
    if kind == "decimal":
        return series.map(lambda value: _to_decimal(value, table, column))
    if kind == "integer":
        numeric = pd.to_numeric(series, errors="coerce")
        invalid = series.notna() & numeric.isna()
        fractional = numeric.notna() & numeric.mod(1).ne(0)
        if invalid.any() or fractional.any():
            raise ValueError(f"{table}.{column} cannot be converted to integer")
        return numeric.astype("Int64")
    if kind == "boolean":
        normalized = series.str.lower()
        mapped = normalized.map(
            {"true": True, "false": False, "1": True, "0": False}
        )
        invalid = series.notna() & mapped.isna()
        if invalid.any():
            raise ValueError(f"{table}.{column} cannot be converted to boolean")
        return mapped.astype("boolean")
    if kind == "datetime":
        parsed = pd.to_datetime(series, errors="coerce", utc=True, format="mixed")
        if (series.notna() & parsed.isna()).any():
            raise ValueError(f"{table}.{column} cannot be converted to datetime")
        return parsed
    raise ValueError(f"Unsupported output kind: {kind}")


def _arrow_array(series: pd.Series, kind: str, config: dict[str, Any]) -> pa.Array:
    values = [None if pd.isna(value) else value for value in series]
    if kind == "string":
        return pa.array(values, type=pa.string())
    if kind == "integer":
        return pa.array(values, type=pa.int64())
    if kind == "boolean":
        return pa.array(values, type=pa.bool_())
    if kind == "decimal":
        return pa.array(
            values,
            type=pa.decimal128(
                config["etl"]["decimal_precision"],
                config["etl"]["decimal_scale"],
            ),
        )
    if kind == "datetime":
        return pa.array(values, type=pa.timestamp("us", tz="UTC"))
    if kind == "date":
        return pa.array(values, type=pa.date32())
    raise ValueError(f"Unsupported Arrow kind: {kind}")


def dataframe_to_arrow(
    dataframe: pd.DataFrame, kinds: dict[str, str], config: dict[str, Any]
) -> pa.Table:
    arrays = [_arrow_array(dataframe[column], kinds[column], config) for column in dataframe]
    return pa.Table.from_arrays(arrays, names=list(dataframe.columns))


def _lineage_values(
    row_count: int,
    source_table: str,
    context: dict[str, Any],
    row_numbers: pd.Series,
) -> tuple[dict[str, pd.Series], dict[str, str]]:
    values = {
        "source_id": pd.Series([context["source_id"]] * row_count, dtype="string"),
        "source_period": pd.Series([context["source_period"]] * row_count, dtype="string"),
        "snapshot_date": pd.Series([context["snapshot_date"]] * row_count),
        "ingestion_run_id": pd.Series(
            [context["ingestion_run_id"]] * row_count, dtype="string"
        ),
        "source_file_name": pd.Series(
            [context["source_file_name"]] * row_count, dtype="string"
        ),
        "source_file_sha256": pd.Series(
            [context["source_file_sha256"]] * row_count, dtype="string"
        ),
        "source_table_name": pd.Series([source_table] * row_count, dtype="string"),
        "source_row_number": row_numbers.reset_index(drop=True).astype("Int64"),
        "loaded_at_utc": pd.Series([context["loaded_at_utc"]] * row_count),
    }
    return values, dict(LINEAGE_KINDS)


def transform_table(
    source_dataframe: pd.DataFrame,
    source_table: str,
    config: dict[str, Any],
    context: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, str], pd.DataFrame | None, dict[str, Any]]:
    """Apply approved treatments and strict typing to one source table."""

    source_columns = list(source_dataframe.columns)
    dataframe, trimmed_cells = _strip_string_cells(source_dataframe)
    dataframe["__source_row_number"] = pd.Series(
        range(1, len(dataframe) + 1), index=dataframe.index, dtype="Int64"
    )
    grain = CANDIDATE_GRAINS[source_table]
    null_grain_before = int(dataframe[grain].isna().any(axis=1).sum())
    duplicate_grain_before = int(dataframe.duplicated(subset=grain).sum())

    quarantine: pd.DataFrame | None = None
    additional_duplicates_before = int(dataframe[source_columns].duplicated().sum())
    if source_table in config["treatments"].get("exact_duplicate_tables", []):
        duplicate_mask = dataframe[source_columns].duplicated(keep="first")
        quarantine = dataframe.loc[duplicate_mask].copy()
        dataframe = dataframe.loc[~duplicate_mask].copy()

    classification_target = _classification_target(source_table, config)
    classification_before = 0
    if classification_target:
        classification_columns = [
            classification_target["id_column"],
            classification_target["description_column"],
            classification_target["scheme_column"],
        ]
        classification_before = int(
            dataframe[classification_columns].isna().any(axis=1).sum()
        )
    dataframe, classification_normalized, classification_flag = (
        _apply_classification_treatment(dataframe, classification_target, config)
    )
    dataframe, ruc_invalid, ruc_flag = _ruc_format_flags(
        dataframe, source_table, config
    )
    dataframe, zero_amount_rows, zero_flag = _simple_quality_flag(
        dataframe, source_table, config, "zero_amount_flag"
    )
    dataframe, final_value_missing, final_flag = _simple_quality_flag(
        dataframe, source_table, config, "final_value_flag"
    )

    null_grain_after = int(dataframe[grain].isna().any(axis=1).sum())
    duplicate_grain_after = int(dataframe.duplicated(subset=grain).sum())
    duplicate_rows_after = int(dataframe[source_columns].duplicated().sum())
    classification_after = 0
    if classification_target:
        classification_after = int(
            dataframe[
                [
                    classification_target["id_column"],
                    classification_target["description_column"],
                    classification_target["scheme_column"],
                ]
            ]
            .isna()
            .any(axis=1)
            .sum()
        )

    column_map = normalized_column_map(source_columns)
    output = dataframe[source_columns].rename(columns=column_map).reset_index(drop=True)
    kinds = {
        column_map[column]: infer_source_kind(column, config) for column in source_columns
    }
    for column in output:
        output[column] = _convert_series(
            output[column], kinds[column], source_table, column
        )

    quality_flags = [
        flag for flag in (classification_flag, ruc_flag, zero_flag, final_flag) if flag
    ]
    for flag in quality_flags:
        output[flag] = dataframe[flag].reset_index(drop=True).astype("boolean")
        kinds[flag] = "boolean"

    row_numbers = dataframe["__source_row_number"].reset_index(drop=True)
    lineage_values, lineage_kinds = _lineage_values(
        len(output), source_table, context, row_numbers
    )
    for column, values in lineage_values.items():
        output[column] = values
    kinds.update(lineage_kinds)

    quarantine_output: pd.DataFrame | None = None
    if quarantine is not None and not quarantine.empty:
        quarantine_output = quarantine[source_columns].rename(columns=column_map).reset_index(
            drop=True
        )
        quarantine_kinds = {
            column_map[column]: infer_source_kind(column, config)
            for column in source_columns
        }
        for column in quarantine_output:
            quarantine_output[column] = _convert_series(
                quarantine_output[column],
                quarantine_kinds[column],
                source_table,
                column,
            )
        quarantine_output["quarantine_rule_id"] = pd.Series(
            ["DQ-DUP-001"] * len(quarantine_output), dtype="string"
        )
        quarantine_output["quarantine_reason"] = pd.Series(
            ["Exact duplicate beyond first occurrence"] * len(quarantine_output),
            dtype="string",
        )
        quarantine_kinds.update(
            {"quarantine_rule_id": "string", "quarantine_reason": "string"}
        )
        quarantine_rows = quarantine["__source_row_number"].reset_index(drop=True)
        quarantine_lineage, quarantine_lineage_kinds = _lineage_values(
            len(quarantine_output), source_table, context, quarantine_rows
        )
        for column, values in quarantine_lineage.items():
            quarantine_output[column] = values
        quarantine_kinds.update(quarantine_lineage_kinds)
        quarantine_output.attrs["kinds"] = quarantine_kinds

    metrics = {
        "source_table": source_table,
        "raw_rows": len(source_dataframe),
        "silver_rows": len(output),
        "quarantine_rows": 0 if quarantine_output is None else len(quarantine_output),
        "trimmed_string_cells": trimmed_cells,
        "additional_duplicate_rows_before": additional_duplicates_before,
        "additional_duplicate_rows_after": duplicate_rows_after,
        "null_candidate_grain_rows_before": null_grain_before,
        "duplicate_candidate_grain_rows_before": duplicate_grain_before,
        "null_candidate_grain_rows_after": null_grain_after,
        "duplicate_candidate_grain_rows_after": duplicate_grain_after,
        "incomplete_classification_rows_before": classification_before,
        "incomplete_classification_rows_after": classification_after,
        "classification_rows_normalized": classification_normalized,
        "ruc_invalid_rows_flagged": ruc_invalid,
        "zero_amount_rows_flagged": zero_amount_rows,
        "final_value_missing_rows_flagged": final_value_missing,
        "column_count_raw": len(source_columns),
        "column_count_silver": len(output.columns),
        "type_counts": {
            kind: sum(value == kind for value in kinds.values())
            for kind in sorted(set(kinds.values()))
        },
        "column_map": column_map,
    }
    return output, kinds, quarantine_output, metrics


def _write_parquet_atomic(
    table: pa.Table,
    destination: Path,
    config: dict[str, Any],
    overwrite: bool,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Silver output already exists: {destination}. Use --overwrite explicitly."
        )
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        pq.write_table(
            table,
            temporary,
            compression=config["etl"]["compression"],
            row_group_size=config["etl"]["row_group_size"],
        )
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _output_path(
    settings: Settings,
    output_table: str,
    source_period: str,
    snapshot_date: date,
) -> Path:
    return (
        settings.interim_root
        / "staging"
        / "oece_ocds"
        / output_table
        / f"source_period={source_period}"
        / f"snapshot_date={snapshot_date.isoformat()}"
        / "part-00000.parquet"
    )


def _quarantine_path(
    settings: Settings, run_id: str, output_table: str
) -> Path:
    return (
        settings.interim_root
        / "quarantine"
        / "DQ-DUP-001"
        / f"ingestion_run_id={run_id}"
        / f"{output_table}.parquet"
    )


def _metadata_path(
    settings: Settings, source_period: str, snapshot_date: date
) -> Path:
    year, month = source_period.split("-")
    return (
        settings.metadata_root
        / "oece"
        / "ocds"
        / "seace_v3"
        / year
        / month
        / f"snapshot_date={snapshot_date.isoformat()}"
        / "etl_phase5_full.json"
    )


def _raw_uncompressed_csv_bytes(archive_path: Path) -> int:
    with ZipFile(archive_path) as archive:
        return sum(
            member.file_size
            for member in archive.infolist()
            if member.filename.lower().endswith(".csv")
        )


def _quality_comparison(table_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def total(field: str) -> int:
        return sum(int(metrics[field]) for metrics in table_metrics)

    return [
        {
            "rule_id": "DQ-UNIQ-001",
            "metric": "candidate_grain_violations",
            "before": total("null_candidate_grain_rows_before")
            + total("duplicate_candidate_grain_rows_before"),
            "after": total("null_candidate_grain_rows_after")
            + total("duplicate_candidate_grain_rows_after"),
        },
        {
            "rule_id": "DQ-DUP-001",
            "metric": "additional_duplicate_rows",
            "before": total("additional_duplicate_rows_before"),
            "after": total("additional_duplicate_rows_after"),
        },
        {
            "rule_id": "DQ-ID-001",
            "metric": "ruc_invalid_rows_flagged",
            "before": total("ruc_invalid_rows_flagged"),
            "after": total("ruc_invalid_rows_flagged"),
        },
        {
            "rule_id": "DQ-CAT-001",
            "metric": "incomplete_classification_rows",
            "before": total("incomplete_classification_rows_before"),
            "after": total("incomplete_classification_rows_after"),
        },
        {
            "rule_id": "DQ-FIT-001",
            "metric": "final_value_missing_rows",
            "before": total("final_value_missing_rows_flagged"),
            "after": total("final_value_missing_rows_flagged"),
        },
        {
            "rule_id": "DQ-BIZ-001",
            "metric": "zero_tender_amount_rows",
            "before": total("zero_amount_rows_flagged"),
            "after": total("zero_amount_rows_flagged"),
        },
    ]


def transform_archive(
    settings: Settings,
    archive_path: Path,
    config_path: Path,
    source_period: str,
    snapshot_date: date,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the complete RAW-to-Silver transformation and write Parquet outputs."""

    validate_source_period(source_period)
    started = time.perf_counter()
    config = load_etl_config(config_path)
    source_sha256 = sha256_file(archive_path)
    config_sha256 = sha256_text_file(config_path)
    run_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            "|".join(
                [
                    config["etl"]["source_id"],
                    source_period,
                    snapshot_date.isoformat(),
                    source_sha256,
                    config_sha256,
                ]
            ),
        )
    )
    loaded_at = pd.Timestamp.now(tz="UTC")
    context = {
        "source_id": config["etl"]["source_id"],
        "source_period": source_period,
        "snapshot_date": snapshot_date,
        "ingestion_run_id": run_id,
        "source_file_name": archive_path.name,
        "source_file_sha256": source_sha256,
        "loaded_at_utc": loaded_at,
    }
    tables, encodings = read_archive(archive_path)
    missing = sorted(set(config["tables"]) - set(tables))
    unmapped = sorted(set(tables) - set(config["tables"]))
    if missing or unmapped:
        raise ValueError(f"Archive/config table mismatch; missing={missing}, unmapped={unmapped}")

    table_reports = []
    quarantine_reports = []
    total_parquet_bytes = 0
    for source_table, output_table in config["tables"].items():
        LOGGER.info("Transforming %s into %s", source_table, output_table)
        output, kinds, quarantine, metrics = transform_table(
            tables[source_table], source_table, config, context
        )
        arrow_table = dataframe_to_arrow(output, kinds, config)
        destination = _output_path(
            settings, output_table, source_period, snapshot_date
        )
        _write_parquet_atomic(arrow_table, destination, config, overwrite)
        parquet_rows = pq.ParquetFile(destination).metadata.num_rows
        if parquet_rows != len(output):
            raise ValueError(f"Parquet row reconciliation failed for {output_table}")
        output_bytes = destination.stat().st_size
        total_parquet_bytes += output_bytes
        metrics.update(
            {
                "output_table": output_table,
                "encoding": encodings[source_table],
                "output_path": str(destination),
                "output_relative_path": destination.relative_to(
                    settings.interim_root
                ).as_posix(),
                "output_size_bytes": output_bytes,
                "output_sha256": sha256_file(destination),
            }
        )
        table_reports.append(metrics)
        LOGGER.info(
            "Wrote %s: %s Silver rows, %s quarantined",
            output_table,
            len(output),
            metrics["quarantine_rows"],
        )

        if quarantine is not None and not quarantine.empty:
            quarantine_kinds = quarantine.attrs["kinds"]
            quarantine_table = dataframe_to_arrow(
                quarantine, quarantine_kinds, config
            )
            quarantine_destination = _quarantine_path(
                settings, run_id, output_table
            )
            _write_parquet_atomic(
                quarantine_table, quarantine_destination, config, overwrite
            )
            quarantine_reports.append(
                {
                    "rule_id": "DQ-DUP-001",
                    "source_table": source_table,
                    "rows": len(quarantine),
                    "path": str(quarantine_destination),
                    "relative_path": quarantine_destination.relative_to(
                        settings.interim_root
                    ).as_posix(),
                    "size_bytes": quarantine_destination.stat().st_size,
                    "sha256": sha256_file(quarantine_destination),
                }
            )

    raw_uncompressed_bytes = _raw_uncompressed_csv_bytes(archive_path)
    comparisons = _quality_comparison(table_reports)
    blocking_after = {
        "additional_duplicate_rows": sum(
            report["additional_duplicate_rows_after"] for report in table_reports
        ),
        "null_candidate_grain_rows": sum(
            report["null_candidate_grain_rows_after"] for report in table_reports
        ),
        "duplicate_candidate_grain_rows": sum(
            report["duplicate_candidate_grain_rows_after"] for report in table_reports
        ),
        "incomplete_classification_rows": sum(
            report["incomplete_classification_rows_after"] for report in table_reports
        ),
    }
    promotion_eligible = all(value == 0 for value in blocking_after.values())
    warning_after = {
        "ruc_invalid_rows_flagged": sum(
            report["ruc_invalid_rows_flagged"] for report in table_reports
        ),
        "zero_amount_rows_flagged": sum(
            report["zero_amount_rows_flagged"] for report in table_reports
        ),
        "final_value_missing_rows_flagged": sum(
            report["final_value_missing_rows_flagged"] for report in table_reports
        ),
    }
    if not promotion_eligible:
        status = "BLOCKED"
    elif any(value > 0 for value in warning_after.values()):
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    report = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "source_id": config["etl"]["source_id"],
            "source_period": source_period,
            "snapshot_date": snapshot_date.isoformat(),
            "archive_filename": archive_path.name,
            "archive_size_bytes": archive_path.stat().st_size,
            "archive_uncompressed_csv_bytes": raw_uncompressed_bytes,
            "archive_sha256": source_sha256,
            "etl_config": str(config_path),
            "etl_config_sha256": config_sha256,
        },
        "run": {
            "ingestion_run_id": run_id,
            "loaded_at_utc": loaded_at.isoformat(),
            "overwrite": overwrite,
        },
        "summary": {
            "status": status,
            "promotion_eligible": promotion_eligible,
            "tables_processed": len(table_reports),
            "raw_rows": sum(report["raw_rows"] for report in table_reports),
            "silver_rows": sum(report["silver_rows"] for report in table_reports),
            "quarantine_rows": sum(report["quarantine_rows"] for report in table_reports),
            "classification_rows_normalized": sum(
                report["classification_rows_normalized"] for report in table_reports
            ),
            "ruc_invalid_rows_flagged": sum(
                report["ruc_invalid_rows_flagged"] for report in table_reports
            ),
            "zero_amount_rows_flagged": sum(
                report["zero_amount_rows_flagged"] for report in table_reports
            ),
            "final_value_missing_rows_flagged": sum(
                report["final_value_missing_rows_flagged"] for report in table_reports
            ),
            "trimmed_string_cells": sum(
                report["trimmed_string_cells"] for report in table_reports
            ),
            "parquet_size_bytes": total_parquet_bytes,
            "parquet_reduction_vs_uncompressed_csv_pct": round(
                (1 - total_parquet_bytes / raw_uncompressed_bytes) * 100, 4
            ),
            "duration_seconds": round(time.perf_counter() - started, 4),
            "blocking_metrics_after": blocking_after,
            "warning_metrics_after": warning_after,
        },
        "quality_comparison": comparisons,
        "tables": table_reports,
        "quarantine": quarantine_reports,
    }
    return report


def repository_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Remove absolute paths while preserving reproducible ETL evidence."""

    source = dict(report["source"])
    config_value = str(source["etl_config"])
    config_reference = Path(config_value)
    windows_reference = PureWindowsPath(config_value)
    if config_reference.is_absolute():
        source["etl_config"] = config_reference.name
    elif windows_reference.is_absolute():
        source["etl_config"] = windows_reference.name
    else:
        source["etl_config"] = config_reference.as_posix()
    tables = []
    for table_report in report["tables"]:
        sanitized = dict(table_report)
        sanitized.pop("output_path", None)
        tables.append(sanitized)
    quarantine = []
    for quarantine_report in report["quarantine"]:
        sanitized = dict(quarantine_report)
        sanitized.pop("path", None)
        quarantine.append(sanitized)
    return {
        "schema_version": report["schema_version"],
        "source": source,
        "run": report["run"],
        "summary": report["summary"],
        "quality_comparison": report["quality_comparison"],
        "tables": tables,
        "quarantine": quarantine,
    }


def write_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".part")
    temporary.unlink(missing_ok=True)
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/etl_silver.yml"))
    parser.add_argument("--source-period", required=True)
    parser.add_argument("--snapshot-date", type=date.fromisoformat, required=True)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = load_settings(args.env_file)
    report = transform_archive(
        settings,
        args.archive,
        args.config,
        args.source_period,
        args.snapshot_date,
        args.overwrite,
    )
    full_output = _metadata_path(
        settings, args.source_period, args.snapshot_date
    )
    write_json(report, full_output)
    if args.summary_output:
        write_json(repository_summary(report), args.summary_output)
    summary = report["summary"]
    print(
        f"Silver ETL {summary['status']}: {summary['silver_rows']:,} rows in "
        f"{summary['tables_processed']} tables; {summary['quarantine_rows']:,} quarantined."
    )


if __name__ == "__main__":
    main()
