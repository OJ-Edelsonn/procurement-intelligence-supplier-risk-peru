"""Build governed dimensional frames from typed Silver Parquet tables."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from procurement_intelligence.settings import Settings

LIMA_TIMEZONE = "America/Lima"
UNKNOWN_TEXT = "__UNKNOWN__"
UNKNOWN_CATEGORY_CODE = "__UNCLASSIFIED__"
UNKNOWN_CATEGORY_DESCRIPTION = "Sin clasificar"
COMMON_LINEAGE_COLUMNS = [
    "source_id",
    "source_period",
    "snapshot_date",
    "ingestion_run_id",
    "source_file_name",
    "source_file_sha256",
    "source_table_name",
    "source_row_number",
    "loaded_at_utc",
]
DIMENSION_TABLES = [
    "dim_date",
    "dim_process",
    "dim_buyer",
    "dim_supplier",
    "dim_category",
    "dim_procurement_method",
    "dim_currency",
    "dim_unit",
]
FACT_TABLES = [
    "fact_procurement_process",
    "fact_tender_item",
    "fact_award",
    "fact_award_item",
    "fact_contract",
    "fact_contract_item",
]
BRIDGE_TABLES = ["bridge_process_tenderer", "bridge_award_supplier"]


@dataclass(frozen=True)
class WarehouseFrames:
    """Ordered warehouse frames and deterministic row-count metrics."""

    dimensions: dict[str, pd.DataFrame]
    facts: dict[str, pd.DataFrame]
    bridges: dict[str, pd.DataFrame]

    @property
    def all_tables(self) -> dict[str, pd.DataFrame]:
        return {**self.dimensions, **self.facts, **self.bridges}

    @property
    def row_counts(self) -> dict[str, int]:
        return {name: len(frame) for name, frame in self.all_tables.items()}


def load_silver_frames(
    settings: Settings, etl_summary: dict[str, Any]
) -> dict[str, pd.DataFrame]:
    """Read every committed Silver table without mutating its Parquet source."""

    frames: dict[str, pd.DataFrame] = {}
    for table in etl_summary["tables"]:
        path = settings.interim_root / table["output_relative_path"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing Silver Parquet: {path}")
        frames[table["output_table"]] = pq.read_table(path).to_pandas()
    return frames


def _normalized_sort_value(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value).strip())
    return unicodedata.normalize("NFKD", text).casefold()


def _canonical_value(series: pd.Series) -> Any:
    values = [value for value in series.tolist() if not pd.isna(value)]
    if not values:
        return None
    counts: dict[Any, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    highest = max(counts.values())
    candidates = [value for value, count in counts.items() if count == highest]
    return sorted(candidates, key=_normalized_sort_value)[0]


def _period_bounds(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    periods = frame["source_period"].dropna().astype(str)
    if periods.empty:
        return None, None
    return periods.min(), periods.max()


def _canonical_by_key(
    frame: pd.DataFrame, key_column: str, value_column: str
) -> dict[Any, Any]:
    """Select modal values per key with the same deterministic lexical tie-break."""

    candidates = frame[[key_column, value_column]].dropna(subset=[value_column])
    if candidates.empty:
        return {}
    counts = (
        candidates.groupby([key_column, value_column], dropna=False)
        .size()
        .rename("observation_count")
        .reset_index()
    )
    counts["lexical_order"] = counts[value_column].map(_normalized_sort_value)
    selected = (
        counts.sort_values(
            [key_column, "observation_count", "lexical_order"],
            ascending=[True, False, True],
            kind="stable",
        )
        .drop_duplicates(key_column, keep="first")
        .set_index(key_column)[value_column]
    )
    return selected.to_dict()


def _lineage(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[COMMON_LINEAGE_COLUMNS].reset_index(drop=True).copy()


def _prepend_unknown(
    frame: pd.DataFrame, key_name: str, unknown: dict[str, Any]
) -> pd.DataFrame:
    ordered = frame.reset_index(drop=True).copy()
    ordered.insert(0, key_name, range(1, len(ordered) + 1))
    unknown_record = {column: None for column in ordered.columns}
    unknown_record.update(unknown)
    unknown_record[key_name] = 0
    return pd.concat(
        [pd.DataFrame([unknown_record], columns=ordered.columns), ordered],
        ignore_index=True,
    )


def _date_key(series: pd.Series) -> pd.Series:
    converted = pd.to_datetime(series, errors="coerce", utc=True)
    local_dates = converted.dt.tz_convert(LIMA_TIMEZONE).dt.strftime("%Y%m%d")
    return pd.to_numeric(local_dates, errors="coerce").fillna(0).astype("int64")


def _composite_lookup(
    frame: pd.DataFrame,
    left_columns: list[str],
    lookup: dict[tuple[Any, ...], int],
) -> pd.Series:
    def normalize(value: Any) -> Any:
        return None if pd.isna(value) else value

    keys = (
        tuple(normalize(value) for value in values)
        for values in frame[left_columns].itertuples(index=False, name=None)
    )
    return pd.Series((lookup.get(key, 0) for key in keys), index=frame.index, dtype="int64")


def _build_dim_date(tables: dict[str, pd.DataFrame], source_period: str) -> pd.DataFrame:
    dates: list[pd.Series] = []
    for table_name in ("procurement_process", "award", "contract"):
        frame = tables[table_name]
        for column in frame.columns:
            if column == "loaded_at_utc":
                continue
            if pd.api.types.is_datetime64_any_dtype(frame[column]):
                values = frame[column].dropna()
                if not values.empty:
                    dates.append(values.dt.tz_convert(LIMA_TIMEZONE).dt.date)
    combined = pd.concat(dates, ignore_index=True)
    calendar = pd.date_range(min(combined), max(combined), freq="D")
    month_names = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    day_names = [
        "lunes",
        "martes",
        "miércoles",
        "jueves",
        "viernes",
        "sábado",
        "domingo",
    ]
    ytd_month = int(source_period.split("-")[1])
    frame = pd.DataFrame(
        {
            "date_key": calendar.strftime("%Y%m%d").astype(int),
            "full_date": calendar.date,
            "year": calendar.year,
            "semester": ((calendar.month - 1) // 6) + 1,
            "quarter": calendar.quarter,
            "month_number": calendar.month,
            "month_name_es": [month_names[value - 1] for value in calendar.month],
            "year_month": calendar.strftime("%Y-%m"),
            "day_of_month": calendar.day,
            "day_of_week_number": calendar.dayofweek + 1,
            "day_name_es": [day_names[value] for value in calendar.dayofweek],
            "is_weekend": calendar.dayofweek >= 5,
            "is_ytd_comparable_month": calendar.month <= ytd_month,
            "created_at_utc": datetime.now(timezone.utc),
        }
    )
    unknown = {column: None for column in frame.columns}
    unknown.update(
        {
            "date_key": 0,
            "is_weekend": False,
            "is_ytd_comparable_month": False,
            "created_at_utc": datetime.now(timezone.utc),
        }
    )
    return pd.concat([pd.DataFrame([unknown]), frame], ignore_index=True)


def _build_dim_process(process: pd.DataFrame) -> pd.DataFrame:
    source = process.sort_values("ocid", kind="stable").reset_index(drop=True)
    frame = pd.DataFrame(
        {
            "ocid": source["ocid"],
            "compiled_release_id": source["compiled_release_id"],
            "tender_id": source["compiled_release_tender_id"],
            "tender_title": source["compiled_release_tender_title"],
            "tender_description": source["compiled_release_tender_description"],
            "initiation_type": source["compiled_release_initiation_type"],
            "main_procurement_category": source[
                "compiled_release_tender_main_procurement_category"
            ],
            "additional_procurement_categories": source[
                "compiled_release_tender_additional_procurement_categories"
            ],
            "data_segmentation_id": source["compiled_release_data_segmentation_id"],
            "data_segmentation_criteria": source[
                "compiled_release_data_segmentation_criteria"
            ],
            "first_observed_period": source["source_period"],
            "last_observed_period": source["source_period"],
            "canonical_ingestion_run_id": source["ingestion_run_id"],
        }
    )
    return _prepend_unknown(frame, "process_key", {"ocid": UNKNOWN_TEXT})


def _build_party_dimension(
    party: pd.DataFrame,
    role_pattern: str,
    key_name: str,
    additional_identifiers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    source = party[
        party["compiled_release_parties_roles"].str.contains(role_pattern, na=False)
    ].copy()
    if additional_identifiers is not None:
        alternate = additional_identifiers[
            additional_identifiers[
                "compiled_release_parties_additional_identifiers_scheme"
            ].eq("PE-RUC")
        ][
            [
                "ocid",
                "compiled_release_parties_id",
                "compiled_release_parties_additional_identifiers_id",
            ]
        ].rename(
            columns={
                "compiled_release_parties_additional_identifiers_id": "alternate_ruc"
            }
        )
        source = source.merge(
            alternate,
            on=["ocid", "compiled_release_parties_id"],
            how="left",
            validate="one_to_one",
        )

    source_party_id = "compiled_release_parties_id"
    grouped = source.groupby(source_party_id, sort=True)
    frame = grouped.agg(
        name_variant_count=(
            "compiled_release_parties_identifier_legal_name",
            "nunique",
        ),
        first_observed_period=("source_period", "min"),
        last_observed_period=("source_period", "max"),
    ).reset_index(names="source_party_id")
    canonical_columns = {
        "identifier_scheme": "compiled_release_parties_identifier_scheme",
        "identifier_id": "compiled_release_parties_identifier_id",
        "display_name": "compiled_release_parties_name",
        "legal_name": "compiled_release_parties_identifier_legal_name",
        "country_name_raw": "compiled_release_parties_address_country_name",
        "canonical_ingestion_run_id": "ingestion_run_id",
    }
    if key_name == "buyer_key":
        canonical_columns.update(
            {
                "alternate_ruc": "alternate_ruc",
                "department_name_raw": "compiled_release_parties_address_department",
                "province_name_raw": "compiled_release_parties_address_region",
                "locality_name_raw": "compiled_release_parties_address_locality",
            }
        )
    else:
        canonical_columns["dq_ruc_format_valid"] = "dq_ruc_format_valid"
    for output_column, source_column in canonical_columns.items():
        selected = _canonical_by_key(source, source_party_id, source_column)
        frame[output_column] = frame["source_party_id"].map(selected)
    frame["dq_name_conflict"] = frame["name_variant_count"].gt(1)
    unknown = {
        "source_party_id": UNKNOWN_TEXT,
        "display_name": "Desconocido",
        "legal_name": "Desconocido",
        "name_variant_count": 0,
        "dq_name_conflict": False,
    }
    result = _prepend_unknown(frame, key_name, unknown)
    if key_name == "buyer_key":
        columns = [
            "buyer_key",
            "source_party_id",
            "identifier_scheme",
            "identifier_id",
            "alternate_ruc",
            "display_name",
            "legal_name",
            "department_name_raw",
            "province_name_raw",
            "locality_name_raw",
            "country_name_raw",
            "name_variant_count",
            "dq_name_conflict",
            "first_observed_period",
            "last_observed_period",
            "canonical_ingestion_run_id",
        ]
    else:
        columns = [
            "supplier_key",
            "source_party_id",
            "identifier_scheme",
            "identifier_id",
            "display_name",
            "legal_name",
            "country_name_raw",
            "dq_ruc_format_valid",
            "name_variant_count",
            "dq_name_conflict",
            "first_observed_period",
            "last_observed_period",
            "canonical_ingestion_run_id",
        ]
    return result[columns]


def _build_dim_category(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    specs = [
        (
            "tender_item",
            "compiled_release_tender_items_classification_scheme",
            "compiled_release_tender_items_classification_id",
            "compiled_release_tender_items_classification_description",
        ),
        (
            "tender_item_classification",
            "compiled_release_tender_items_additional_classifications_scheme",
            "compiled_release_tender_items_additional_classifications_id",
            "compiled_release_tender_items_additional_classifications_description",
        ),
        (
            "award_item",
            "compiled_release_awards_items_classification_scheme",
            "compiled_release_awards_items_classification_id",
            "compiled_release_awards_items_classification_description",
        ),
        (
            "award_item_classification",
            "compiled_release_awards_items_additional_classifications_scheme",
            "compiled_release_awards_items_additional_classifications_id",
            "compiled_release_awards_items_additional_classifications_description",
        ),
        (
            "contract_item",
            "compiled_release_contracts_items_classification_scheme",
            "compiled_release_contracts_items_classification_id",
            "compiled_release_contracts_items_classification_description",
        ),
        (
            "contract_item_classification",
            "compiled_release_contracts_items_additional_classifications_scheme",
            "compiled_release_contracts_items_additional_classifications_id",
            "compiled_release_contracts_items_additional_classifications_description",
        ),
    ]
    observations = []
    for table_name, scheme, code, description in specs:
        frame = tables[table_name][
            [scheme, code, description, "dq_classification_was_missing", "source_period", "ingestion_run_id"]
        ].copy()
        frame.columns = [
            "classification_scheme",
            "classification_code",
            "classification_description",
            "dq_missing",
            "source_period",
            "ingestion_run_id",
        ]
        missing = (
            frame["dq_missing"].fillna(False)
            | frame["classification_scheme"].isna()
            | frame["classification_code"].isna()
        )
        frame.loc[missing, "classification_scheme"] = "UNKNOWN"
        frame.loc[missing, "classification_code"] = UNKNOWN_CATEGORY_CODE
        frame.loc[missing, "classification_description"] = (
            UNKNOWN_CATEGORY_DESCRIPTION
        )
        observations.append(frame)
    combined = pd.concat(observations, ignore_index=True)
    records = []
    for (scheme, code), group in combined.groupby(
        ["classification_scheme", "classification_code"], sort=True
    ):
        first_period, last_period = _period_bounds(group)
        variants = int(group["classification_description"].nunique(dropna=True))
        records.append(
            {
                "classification_scheme": scheme,
                "classification_code": code,
                "classification_description": _canonical_value(
                    group["classification_description"]
                ),
                "description_variant_count": variants,
                "dq_description_conflict": variants > 1,
                "is_unknown": scheme == "UNKNOWN" and code == UNKNOWN_CATEGORY_CODE,
                "first_observed_period": first_period,
                "last_observed_period": last_period,
                "canonical_ingestion_run_id": _canonical_value(
                    group["ingestion_run_id"]
                ),
            }
        )
    frame = pd.DataFrame(records)
    unknown_mask = frame["is_unknown"]
    unknown = frame.loc[unknown_mask].copy()
    known = frame.loc[~unknown_mask].sort_values(
        ["classification_scheme", "classification_code"], kind="stable"
    )
    known.insert(0, "category_key", range(1, len(known) + 1))
    if unknown.empty:
        unknown = pd.DataFrame(
            [
                {
                    "classification_scheme": "UNKNOWN",
                    "classification_code": UNKNOWN_CATEGORY_CODE,
                    "classification_description": UNKNOWN_CATEGORY_DESCRIPTION,
                    "description_variant_count": 0,
                    "dq_description_conflict": False,
                    "is_unknown": True,
                }
            ]
        )
    unknown.insert(0, "category_key", 0)
    return pd.concat([unknown, known], ignore_index=True)[known.columns]


def _build_dim_procurement_method(process: pd.DataFrame) -> pd.DataFrame:
    source = process[
        [
            "compiled_release_tender_procurement_method",
            "compiled_release_tender_procurement_method_details",
            "source_period",
            "ingestion_run_id",
        ]
    ].copy()
    source["compiled_release_tender_procurement_method"] = source[
        "compiled_release_tender_procurement_method"
    ].fillna(UNKNOWN_TEXT)
    source["compiled_release_tender_procurement_method_details"] = source[
        "compiled_release_tender_procurement_method_details"
    ].fillna(UNKNOWN_TEXT)
    source = source[
        ~(
            source["compiled_release_tender_procurement_method"].eq(UNKNOWN_TEXT)
            & source["compiled_release_tender_procurement_method_details"].eq(
                UNKNOWN_TEXT
            )
        )
    ]
    records = []
    for (method, details), group in source.groupby(
        [
            "compiled_release_tender_procurement_method",
            "compiled_release_tender_procurement_method_details",
        ],
        sort=True,
        dropna=False,
    ):
        first_period, last_period = _period_bounds(group)
        records.append(
            {
                "procurement_method": method,
                "procurement_method_details": details,
                "first_observed_period": first_period,
                "last_observed_period": last_period,
                "canonical_ingestion_run_id": _canonical_value(
                    group["ingestion_run_id"]
                ),
            }
        )
    frame = pd.DataFrame(records).sort_values(
        ["procurement_method", "procurement_method_details"], kind="stable"
    )
    return _prepend_unknown(
        frame,
        "procurement_method_key",
        {
            "procurement_method": UNKNOWN_TEXT,
            "procurement_method_details": UNKNOWN_TEXT,
        },
    )


def _build_dim_currency(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    specs = [
        (
            "procurement_process",
            "compiled_release_tender_value_currency",
            "compiled_release_tender_value_currency_name",
        ),
        (
            "procurement_process",
            "compiled_release_planning_budget_amount_currency",
            "compiled_release_planning_budget_amount_currency_name",
        ),
        (
            "tender_item",
            "compiled_release_tender_items_total_value_currency",
            "compiled_release_tender_items_total_value_currency_name",
        ),
        (
            "award",
            "compiled_release_awards_value_currency",
            "compiled_release_awards_value_currency_name",
        ),
        (
            "award_item",
            "compiled_release_awards_items_total_value_currency",
            "compiled_release_awards_items_total_value_currency_name",
        ),
        (
            "contract",
            "compiled_release_contracts_value_currency",
            "compiled_release_contracts_value_currency_name",
        ),
        (
            "contract_item",
            "compiled_release_contracts_items_total_value_currency",
            "compiled_release_contracts_items_total_value_currency_name",
        ),
    ]
    observations = []
    for table_name, code, name in specs:
        frame = tables[table_name][
            [code, name, "source_period", "ingestion_run_id"]
        ].copy()
        frame.columns = [
            "currency_code",
            "currency_name",
            "source_period",
            "ingestion_run_id",
        ]
        observations.append(frame.dropna(subset=["currency_code"]))
    combined = pd.concat(observations, ignore_index=True)
    records = []
    for code, group in combined.groupby("currency_code", sort=True):
        first_period, last_period = _period_bounds(group)
        records.append(
            {
                "currency_code": code,
                "currency_name": _canonical_value(group["currency_name"]),
                "first_observed_period": first_period,
                "last_observed_period": last_period,
                "canonical_ingestion_run_id": _canonical_value(
                    group["ingestion_run_id"]
                ),
            }
        )
    frame = pd.DataFrame(records).sort_values("currency_code", kind="stable")
    return _prepend_unknown(
        frame,
        "currency_key",
        {"currency_code": UNKNOWN_TEXT, "currency_name": "Desconocida"},
    )


def _build_dim_unit(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    specs = [
        ("tender_item", "compiled_release_tender_items_unit"),
        ("award_item", "compiled_release_awards_items_unit"),
        ("contract_item", "compiled_release_contracts_items_unit"),
    ]
    observations = []
    for table_name, prefix in specs:
        frame = tables[table_name][
            [
                f"{prefix}_scheme",
                f"{prefix}_id",
                f"{prefix}_name",
                "source_period",
                "ingestion_run_id",
            ]
        ].copy()
        frame.columns = [
            "unit_scheme",
            "unit_code",
            "unit_name",
            "source_period",
            "ingestion_run_id",
        ]
        observations.append(frame.dropna(subset=["unit_scheme", "unit_code"]))
    combined = pd.concat(observations, ignore_index=True)
    records = []
    for (scheme, code), group in combined.groupby(
        ["unit_scheme", "unit_code"], sort=True
    ):
        first_period, last_period = _period_bounds(group)
        records.append(
            {
                "unit_scheme": scheme,
                "unit_code": code,
                "unit_name": _canonical_value(group["unit_name"]),
                "first_observed_period": first_period,
                "last_observed_period": last_period,
                "canonical_ingestion_run_id": _canonical_value(
                    group["ingestion_run_id"]
                ),
            }
        )
    frame = pd.DataFrame(records).sort_values(
        ["unit_scheme", "unit_code"], kind="stable"
    )
    return _prepend_unknown(
        frame,
        "unit_key",
        {"unit_scheme": UNKNOWN_TEXT, "unit_code": UNKNOWN_TEXT, "unit_name": "Desconocida"},
    )


def _dimension_lookups(
    dimensions: dict[str, pd.DataFrame],
) -> dict[str, dict[Any, int]]:
    return {
        "process": dict(
            zip(dimensions["dim_process"]["ocid"], dimensions["dim_process"]["process_key"])
        ),
        "buyer": dict(
            zip(
                dimensions["dim_buyer"]["source_party_id"],
                dimensions["dim_buyer"]["buyer_key"],
            )
        ),
        "supplier": dict(
            zip(
                dimensions["dim_supplier"]["source_party_id"],
                dimensions["dim_supplier"]["supplier_key"],
            )
        ),
        "category": {
            (row.classification_scheme, row.classification_code): row.category_key
            for row in dimensions["dim_category"].itertuples(index=False)
        },
        "method": {
            (row.procurement_method, row.procurement_method_details): row.procurement_method_key
            for row in dimensions["dim_procurement_method"].itertuples(index=False)
        },
        "currency": dict(
            zip(
                dimensions["dim_currency"]["currency_code"],
                dimensions["dim_currency"]["currency_key"],
            )
        ),
        "unit": {
            (row.unit_scheme, row.unit_code): row.unit_key
            for row in dimensions["dim_unit"].itertuples(index=False)
        },
    }


def _process_context(
    process: pd.DataFrame, lookups: dict[str, dict[Any, int]]
) -> pd.DataFrame:
    context = process[
        [
            "ocid",
            "compiled_release_buyer_id",
            "compiled_release_tender_procurement_method",
            "compiled_release_tender_procurement_method_details",
            "compiled_release_tender_date_published",
        ]
    ].copy()
    context["process_key"] = context["ocid"].map(lookups["process"]).fillna(0).astype(int)
    context["buyer_key"] = (
        context["compiled_release_buyer_id"].map(lookups["buyer"]).fillna(0).astype(int)
    )
    method_details = context[
        "compiled_release_tender_procurement_method_details"
    ].fillna(UNKNOWN_TEXT)
    method_values = context[
        "compiled_release_tender_procurement_method"
    ].fillna(UNKNOWN_TEXT)
    context["procurement_method_key"] = pd.Series(
        (
            lookups["method"].get((method, details), 0)
            for method, details in zip(
                method_values, method_details
            )
        ),
        index=context.index,
        dtype="int64",
    )
    context["tender_published_date_key"] = _date_key(
        context["compiled_release_tender_date_published"]
    )
    return context[
        [
            "ocid",
            "process_key",
            "buyer_key",
            "procurement_method_key",
            "tender_published_date_key",
        ]
    ]


def _category_keys(
    source: pd.DataFrame,
    prefix: str,
    additional: pd.DataFrame,
    additional_prefix: str,
    grain: list[str],
    category_lookup: dict[tuple[Any, ...], int],
) -> tuple[pd.Series, pd.Series, pd.Series]:
    primary = _composite_lookup(
        source,
        [f"{prefix}_classification_scheme", f"{prefix}_classification_id"],
        category_lookup,
    )
    additional_columns = grain + [
        f"{additional_prefix}_additional_classifications_scheme",
        f"{additional_prefix}_additional_classifications_id",
    ]
    standard = source[grain].merge(
        additional[additional_columns],
        on=grain,
        how="left",
        validate="one_to_one",
    )
    standard_key = _composite_lookup(
        standard,
        [
            f"{additional_prefix}_additional_classifications_scheme",
            f"{additional_prefix}_additional_classifications_id",
        ],
        category_lookup,
    )
    missing = standard_key.eq(0)
    return primary, standard_key, missing


def _apply_pen_conversion(
    frame: pd.DataFrame,
    currency_column: str,
    amount_column: str,
    rate_column: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    rates: list[Decimal | None] = []
    converted: list[Decimal | None] = []
    available: list[bool] = []
    for currency, amount, source_rate in frame[
        [currency_column, amount_column, rate_column]
    ].itertuples(index=False, name=None):
        if currency == "PEN":
            rate = Decimal("1")
        elif not pd.isna(source_rate):
            rate = source_rate
        else:
            rate = None
        can_convert = rate is not None and not pd.isna(amount)
        rates.append(rate)
        converted.append(amount * rate if can_convert else None)
        available.append(can_convert)
    return (
        pd.Series(rates, index=frame.index, dtype="object"),
        pd.Series(converted, index=frame.index, dtype="object"),
        pd.Series(available, index=frame.index, dtype="boolean"),
    )


def _reconciliation_columns(
    parent: pd.DataFrame,
    child: pd.DataFrame,
    keys: list[str],
    parent_amount: str,
    child_amount: str,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    sums = child.groupby(keys, dropna=False)[child_amount].sum(min_count=1)
    indexed = parent.set_index(keys)
    child_sum = sums.reindex(indexed.index).reset_index(drop=True)
    difference = indexed[parent_amount].reset_index(drop=True) - child_sum
    reconciled = difference.map(
        lambda value: False
        if pd.isna(value)
        else abs(value) <= Decimal("0.01")
    ).astype("boolean")
    return child_sum, difference, reconciled


def _award_supplier_attribution(
    award_supplier: pd.DataFrame, supplier_lookup: dict[Any, int]
) -> pd.DataFrame:
    keys = ["ocid", "compiled_release_awards_id"]
    counts = award_supplier.groupby(keys).size().rename("supplier_count").reset_index()
    unique = award_supplier.merge(counts, on=keys, how="left", validate="many_to_one")
    unique = unique[unique["supplier_count"].eq(1)].drop_duplicates(keys)
    unique["attributed_supplier_key"] = (
        unique["compiled_release_awards_suppliers_id"]
        .map(supplier_lookup)
        .fillna(0)
        .astype(int)
    )
    return counts.merge(
        unique[keys + ["attributed_supplier_key"]], on=keys, how="left"
    ).assign(
        attributed_supplier_key=lambda frame: frame[
            "attributed_supplier_key"
        ].fillna(0).astype(int),
        dq_supplier_amount_attributable=lambda frame: frame[
            "supplier_count"
        ].eq(1)
        & frame["attributed_supplier_key"].ne(0),
    )


def _build_fact_procurement_process(
    tables: dict[str, pd.DataFrame], lookups: dict[str, dict[Any, int]]
) -> pd.DataFrame:
    process = tables["procurement_process"].sort_values("ocid", kind="stable").reset_index(drop=True)
    tenderer_count = tables["tenderer"].groupby("ocid").size()
    item_sum, difference, reconciled = _reconciliation_columns(
        process,
        tables["tender_item"],
        ["ocid"],
        "compiled_release_tender_value_amount",
        "compiled_release_tender_items_total_value_amount",
    )
    method_details = process[
        "compiled_release_tender_procurement_method_details"
    ].fillna(UNKNOWN_TEXT)
    method_values = process[
        "compiled_release_tender_procurement_method"
    ].fillna(UNKNOWN_TEXT)
    frame = pd.DataFrame(
        {
            "procurement_process_fact_key": range(1, len(process) + 1),
            "process_key": process["ocid"].map(lookups["process"]).fillna(0).astype(int),
            "buyer_key": process["compiled_release_buyer_id"].map(lookups["buyer"]).fillna(0).astype(int),
            "procurement_method_key": [
                lookups["method"].get((method, details), 0)
                for method, details in zip(
                    method_values, method_details
                )
            ],
            "tender_currency_key": process["compiled_release_tender_value_currency"].map(lookups["currency"]).fillna(0).astype(int),
            "budget_currency_key": process["compiled_release_planning_budget_amount_currency"].map(lookups["currency"]).fillna(0).astype(int),
            "tender_published_date_key": _date_key(process["compiled_release_tender_date_published"]),
            "record_date_key": _date_key(process["compiled_release_date"]),
            "published_date_key": _date_key(process["compiled_release_published_date"]),
            "tender_period_start_date_key": _date_key(process["compiled_release_tender_tender_period_start_date"]),
            "tender_period_end_date_key": _date_key(process["compiled_release_tender_tender_period_end_date"]),
            "enquiry_period_start_date_key": _date_key(process["compiled_release_tender_enquiry_period_start_date"]),
            "enquiry_period_end_date_key": _date_key(process["compiled_release_tender_enquiry_period_end_date"]),
            "process_count": 1,
            "planning_budget_amount_original": process["compiled_release_planning_budget_amount_amount"],
            "tender_amount_original": process["compiled_release_tender_value_amount"],
            "tender_amount_pen_published": process["compiled_release_tender_value_amount_pen"],
            "tenderer_count_declared": process["compiled_release_tender_number_of_tenderers"],
            "tenderer_count_observed": process["ocid"].map(tenderer_count).fillna(0).astype(int),
            "tender_item_amount_sum_original": item_sum,
            "tender_amount_difference_original": difference,
            "dq_tender_value_is_zero": process["dq_tender_value_is_zero"].fillna(False),
            "dq_tender_amount_reconciled_0_01": reconciled,
        }
    )
    frame["dq_tenderer_count_matches_observed"] = frame[
        "tenderer_count_declared"
    ].eq(frame["tenderer_count_observed"])
    frame = frame[
        [
            *frame.columns[:21],
            "dq_tender_value_is_zero",
            "dq_tenderer_count_matches_observed",
            "dq_tender_amount_reconciled_0_01",
        ]
    ]
    return pd.concat([frame, _lineage(process)], axis=1)


def _build_item_fact(
    tables: dict[str, pd.DataFrame],
    lookups: dict[str, dict[Any, int]],
    lifecycle: str,
    process_context: pd.DataFrame,
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    if lifecycle == "tender":
        table_name = "tender_item"
        prefix = "compiled_release_tender_items"
        additional_name = "tender_item_classification"
        additional_prefix = "compiled_release_tender_items"
        rate_name = "tender_item_exchange_rate"
        rate_column = f"{prefix}_total_value_exchange_rates_rate"
        grain = ["ocid", f"{prefix}_id"]
        id_columns = [f"{prefix}_id"]
        key_name = "tender_item_fact_key"
        count_name = "tender_item_count"
    elif lifecycle == "award":
        table_name = "award_item"
        prefix = "compiled_release_awards_items"
        additional_name = "award_item_classification"
        additional_prefix = "compiled_release_awards_items"
        rate_name = "award_item_exchange_rate"
        rate_column = f"{prefix}_total_value_exchange_rates_rate"
        grain = ["ocid", "compiled_release_awards_id", f"{prefix}_id"]
        id_columns = ["compiled_release_awards_id", f"{prefix}_id"]
        key_name = "award_item_fact_key"
        count_name = "award_item_count"
    else:
        table_name = "contract_item"
        prefix = "compiled_release_contracts_items"
        additional_name = "contract_item_classification"
        additional_prefix = "compiled_release_contracts_items"
        rate_name = "contract_item_exchange_rate"
        rate_column = f"{prefix}_total_value_exchange_rates_rate"
        grain = ["ocid", "compiled_release_contracts_id", f"{prefix}_id"]
        id_columns = ["compiled_release_contracts_id", f"{prefix}_id"]
        key_name = "contract_item_fact_key"
        count_name = "contract_item_count"

    source = tables[table_name].sort_values(grain, kind="stable").reset_index(drop=True)
    source = source.merge(process_context, on="ocid", how="left", validate="many_to_one")
    rate = tables[rate_name][grain + [rate_column]]
    source = source.merge(rate, on=grain, how="left", validate="one_to_one")
    primary, standard, standard_missing = _category_keys(
        source,
        prefix,
        tables[additional_name],
        additional_prefix,
        grain,
        lookups["category"],
    )
    conversion_rate, amount_pen, conversion_available = _apply_pen_conversion(
        source,
        f"{prefix}_total_value_currency",
        f"{prefix}_total_value_amount",
        rate_column,
    )
    frame = pd.DataFrame(
        {
            key_name: range(1, len(source) + 1),
            "process_key": source["process_key"].fillna(0).astype(int),
            "buyer_key": source["buyer_key"].fillna(0).astype(int),
        }
    )
    if lifecycle == "tender":
        frame["procurement_method_key"] = source["procurement_method_key"].fillna(0).astype(int)
    else:
        join_keys = ["ocid", "compiled_release_awards_id"]
        if lifecycle == "contract":
            parent = tables["contract"][["ocid", "compiled_release_contracts_id", "compiled_release_contracts_award_id", "compiled_release_contracts_date_signed"]]
            source = source.merge(
                parent,
                on=["ocid", "compiled_release_contracts_id"],
                how="left",
                validate="many_to_one",
            )
            source = source.merge(
                attribution,
                left_on=["ocid", "compiled_release_contracts_award_id"],
                right_on=["ocid", "compiled_release_awards_id"],
                how="left",
                validate="many_to_one",
            )
        else:
            source = source.merge(
                attribution,
                on=join_keys,
                how="left",
                validate="many_to_one",
            )
        frame["attributed_supplier_key"] = source[
            "attributed_supplier_key"
        ].fillna(0).astype(int)
    frame["primary_category_key"] = primary.to_numpy()
    frame["standard_category_key"] = standard.to_numpy()
    frame["unit_key"] = _composite_lookup(
        source,
        [f"{prefix}_unit_scheme", f"{prefix}_unit_id"],
        lookups["unit"],
    ).to_numpy()
    frame["currency_key"] = (
        source[f"{prefix}_total_value_currency"]
        .map(lookups["currency"])
        .fillna(0)
        .astype(int)
        .to_numpy()
    )
    if lifecycle == "tender":
        frame["tender_published_date_key"] = source[
            "tender_published_date_key"
        ].fillna(0).astype(int)
        frame["tender_item_id"] = source[id_columns[0]]
    elif lifecycle == "award":
        award_dates = tables["award"][["ocid", "compiled_release_awards_id", "compiled_release_awards_date"]]
        source = source.merge(
            award_dates,
            on=["ocid", "compiled_release_awards_id"],
            how="left",
            validate="many_to_one",
        )
        frame["award_date_key"] = _date_key(source["compiled_release_awards_date"])
        frame["award_id"] = source[id_columns[0]]
        frame["award_item_id"] = source[id_columns[1]]
    else:
        frame["contract_signed_date_key"] = _date_key(
            source["compiled_release_contracts_date_signed"]
        )
        frame["contract_id"] = source[id_columns[0]]
        frame["contract_item_id"] = source[id_columns[1]]
    frame["item_position"] = source[f"{prefix}_position"]
    frame["item_description"] = source[f"{prefix}_description"]
    frame["item_status"] = source[f"{prefix}_status"]
    frame["item_status_details"] = source[f"{prefix}_status_details"]
    frame[count_name] = 1
    frame["quantity"] = source[f"{prefix}_quantity"]
    frame["total_amount_original"] = source[f"{prefix}_total_value_amount"]
    frame["conversion_rate_to_pen"] = conversion_rate
    frame["total_amount_pen_calculated"] = amount_pen
    frame["dq_classification_was_missing"] = source[
        "dq_classification_was_missing"
    ].fillna(False)
    frame["dq_standard_category_missing"] = standard_missing.to_numpy()
    if lifecycle != "tender":
        frame["dq_supplier_amount_attributable"] = source[
            "dq_supplier_amount_attributable"
        ].fillna(False)
    frame["dq_pen_conversion_available"] = conversion_available
    return pd.concat([frame, _lineage(source)], axis=1)


def _build_fact_award(
    tables: dict[str, pd.DataFrame],
    lookups: dict[str, dict[Any, int]],
    process_context: pd.DataFrame,
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    grain = ["ocid", "compiled_release_awards_id"]
    source = tables["award"].sort_values(grain, kind="stable").reset_index(drop=True)
    source = source.merge(process_context, on="ocid", how="left", validate="many_to_one")
    source = source.merge(attribution, on=grain, how="left", validate="one_to_one")
    rate_column = "compiled_release_awards_value_exchange_rates_rate"
    source = source.merge(
        tables["award_value_exchange_rate"][grain + [rate_column]],
        on=grain,
        how="left",
        validate="one_to_one",
    )
    conversion_rate, amount_pen, conversion_available = _apply_pen_conversion(
        source,
        "compiled_release_awards_value_currency",
        "compiled_release_awards_value_amount",
        rate_column,
    )
    item_sum, difference, reconciled = _reconciliation_columns(
        source,
        tables["award_item"],
        grain,
        "compiled_release_awards_value_amount",
        "compiled_release_awards_items_total_value_amount",
    )
    frame = pd.DataFrame(
        {
            "award_fact_key": range(1, len(source) + 1),
            "process_key": source["process_key"].fillna(0).astype(int),
            "buyer_key": source["buyer_key"].fillna(0).astype(int),
            "procurement_method_key": source["procurement_method_key"].fillna(0).astype(int),
            "attributed_supplier_key": source["attributed_supplier_key"].fillna(0).astype(int),
            "currency_key": source["compiled_release_awards_value_currency"].map(lookups["currency"]).fillna(0).astype(int),
            "award_date_key": _date_key(source["compiled_release_awards_date"]),
            "award_id": source["compiled_release_awards_id"],
            "award_count": 1,
            "award_amount_original": source["compiled_release_awards_value_amount"],
            "conversion_rate_to_pen": conversion_rate,
            "award_amount_pen_calculated": amount_pen,
            "supplier_count": source["supplier_count"].fillna(0).astype(int),
            "award_item_amount_sum_original": item_sum,
            "award_amount_difference_original": difference,
            "dq_supplier_amount_attributable": source["dq_supplier_amount_attributable"].fillna(False),
            "dq_pen_conversion_available": conversion_available,
            "dq_award_amount_reconciled_0_01": reconciled,
        }
    )
    return pd.concat([frame, _lineage(source)], axis=1)


def _build_fact_contract(
    tables: dict[str, pd.DataFrame],
    lookups: dict[str, dict[Any, int]],
    process_context: pd.DataFrame,
    attribution: pd.DataFrame,
) -> pd.DataFrame:
    grain = ["ocid", "compiled_release_contracts_id"]
    source = tables["contract"].sort_values(grain, kind="stable").reset_index(drop=True)
    source = source.merge(process_context, on="ocid", how="left", validate="many_to_one")
    source = source.merge(
        attribution,
        left_on=["ocid", "compiled_release_contracts_award_id"],
        right_on=["ocid", "compiled_release_awards_id"],
        how="left",
        validate="many_to_one",
    )
    rate_column = "compiled_release_contracts_value_exchange_rates_rate"
    source = source.merge(
        tables["contract_value_exchange_rate"][grain + [rate_column]],
        on=grain,
        how="left",
        validate="one_to_one",
    )
    conversion_rate, amount_pen, conversion_available = _apply_pen_conversion(
        source,
        "compiled_release_contracts_value_currency",
        "compiled_release_contracts_value_amount",
        rate_column,
    )
    item_sum, difference, reconciled = _reconciliation_columns(
        source,
        tables["contract_item"],
        grain,
        "compiled_release_contracts_value_amount",
        "compiled_release_contracts_items_total_value_amount",
    )
    frame = pd.DataFrame(
        {
            "contract_fact_key": range(1, len(source) + 1),
            "process_key": source["process_key"].fillna(0).astype(int),
            "buyer_key": source["buyer_key"].fillna(0).astype(int),
            "procurement_method_key": source["procurement_method_key"].fillna(0).astype(int),
            "attributed_supplier_key": source["attributed_supplier_key"].fillna(0).astype(int),
            "currency_key": source["compiled_release_contracts_value_currency"].map(lookups["currency"]).fillna(0).astype(int),
            "contract_signed_date_key": _date_key(source["compiled_release_contracts_date_signed"]),
            "contract_period_start_date_key": _date_key(source["compiled_release_contracts_period_start_date"]),
            "contract_period_end_date_key": _date_key(source["compiled_release_contracts_period_end_date"]),
            "implementation_end_date_key": _date_key(source["compiled_release_contracts_implementation_end_date"]),
            "contract_id": source["compiled_release_contracts_id"],
            "award_id": source["compiled_release_contracts_award_id"],
            "contract_title": source["compiled_release_contracts_title"],
            "contract_description": source["compiled_release_contracts_description"],
            "contract_count": 1,
            "contract_amount_original": source["compiled_release_contracts_value_amount"],
            "conversion_rate_to_pen": conversion_rate,
            "contract_amount_pen_calculated": amount_pen,
            "contract_duration_days": source["compiled_release_contracts_period_duration_in_days"],
            "final_value_original": source["compiled_release_contracts_implementation_final_value_amount"],
            "contract_item_amount_sum_original": item_sum,
            "contract_amount_difference_original": difference,
            "dq_final_value_available": source["dq_final_value_available"].fillna(False),
            "dq_supplier_amount_attributable": source["dq_supplier_amount_attributable"].fillna(False),
            "dq_pen_conversion_available": conversion_available,
            "dq_contract_amount_reconciled_0_01": reconciled,
        }
    )
    return pd.concat([frame, _lineage(source)], axis=1)


def _build_bridges(
    tables: dict[str, pd.DataFrame], lookups: dict[str, dict[Any, int]]
) -> dict[str, pd.DataFrame]:
    tenderer = tables["tenderer"].sort_values(
        ["ocid", "compiled_release_tender_tenderers_id"], kind="stable"
    ).reset_index(drop=True)
    tenderer_frame = pd.DataFrame(
        {
            "process_tenderer_bridge_key": range(1, len(tenderer) + 1),
            "process_key": tenderer["ocid"].map(lookups["process"]).fillna(0).astype(int),
            "supplier_key": tenderer["compiled_release_tender_tenderers_id"].map(lookups["supplier"]).fillna(0).astype(int),
            "participation_count": 1,
        }
    )
    tenderer_frame = pd.concat([tenderer_frame, _lineage(tenderer)], axis=1)

    supplier = tables["award_supplier"].sort_values(
        ["ocid", "compiled_release_awards_id", "compiled_release_awards_suppliers_id"],
        kind="stable",
    ).reset_index(drop=True)
    supplier_frame = pd.DataFrame(
        {
            "award_supplier_bridge_key": range(1, len(supplier) + 1),
            "process_key": supplier["ocid"].map(lookups["process"]).fillna(0).astype(int),
            "supplier_key": supplier["compiled_release_awards_suppliers_id"].map(lookups["supplier"]).fillna(0).astype(int),
            "award_id": supplier["compiled_release_awards_id"],
            "participation_count": 1,
        }
    )
    supplier_frame = pd.concat([supplier_frame, _lineage(supplier)], axis=1)
    return {
        "bridge_process_tenderer": tenderer_frame,
        "bridge_award_supplier": supplier_frame,
    }


def build_warehouse_frames(
    tables: dict[str, pd.DataFrame], source_period: str
) -> WarehouseFrames:
    """Transform Silver frames into the approved physical constellation."""

    dimensions = {
        "dim_date": _build_dim_date(tables, source_period),
        "dim_process": _build_dim_process(tables["procurement_process"]),
        "dim_buyer": _build_party_dimension(
            tables["party"],
            r"buyer",
            "buyer_key",
            tables["party_additional_identifier"],
        ),
        "dim_supplier": _build_party_dimension(
            tables["party"], r"tenderer|supplier", "supplier_key"
        ),
        "dim_category": _build_dim_category(tables),
        "dim_procurement_method": _build_dim_procurement_method(
            tables["procurement_process"]
        ),
        "dim_currency": _build_dim_currency(tables),
        "dim_unit": _build_dim_unit(tables),
    }
    lookups = _dimension_lookups(dimensions)
    process_context = _process_context(tables["procurement_process"], lookups)
    attribution = _award_supplier_attribution(
        tables["award_supplier"], lookups["supplier"]
    )
    facts = {
        "fact_procurement_process": _build_fact_procurement_process(tables, lookups),
        "fact_tender_item": _build_item_fact(
            tables, lookups, "tender", process_context, attribution
        ),
        "fact_award": _build_fact_award(
            tables, lookups, process_context, attribution
        ),
        "fact_award_item": _build_item_fact(
            tables, lookups, "award", process_context, attribution
        ),
        "fact_contract": _build_fact_contract(
            tables, lookups, process_context, attribution
        ),
        "fact_contract_item": _build_item_fact(
            tables, lookups, "contract", process_context, attribution
        ),
    }
    bridges = _build_bridges(tables, lookups)
    return WarehouseFrames(dimensions=dimensions, facts=facts, bridges=bridges)
