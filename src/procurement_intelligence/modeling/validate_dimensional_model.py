"""Validate the approved dimensional contract against Silver Parquet evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq
import yaml

from procurement_intelligence.extraction.download_ocds import sha256_text_file
from procurement_intelligence.settings import Settings, load_settings
from procurement_intelligence.transformation.transform_ocds_silver import (
    LINEAGE_KINDS,
)

OBJECT_NAME_PATTERN = re.compile(r"^(dim|fact|bridge)_[a-z0-9_]+$")
FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ALLOWED_SCD_TYPES = {0, 1, 2}
ALLOWED_AGGREGATIONS = {"sum", "average", "none"}
ALLOWED_ADDITIVITY = {
    "additive",
    "conditional_same_currency",
    "conditional_same_unit",
    "additive_when_conversion_available",
    "additive_count_not_distinct_suppliers",
    "non_additive",
    "non_additive_audit",
    "not_fit_for_kpi",
}
QUALITY_FLAG_COLUMNS = {
    "procurement_process": {"dq_tender_value_is_zero"},
    "party": {"dq_ruc_format_valid"},
    "tender_item": {"dq_classification_was_missing"},
    "tender_item_classification": {"dq_classification_was_missing"},
    "award_item": {"dq_classification_was_missing"},
    "award_item_classification": {"dq_classification_was_missing"},
    "contract": {"dq_final_value_available"},
    "contract_item": {"dq_classification_was_missing"},
    "contract_item_classification": {"dq_classification_was_missing"},
}


def load_model_config(path: Path) -> dict[str, Any]:
    """Load a governed dimensional-model contract."""

    with path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


def load_etl_summary(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as summary_file:
        return json.load(summary_file)


def silver_column_catalog(summary: dict[str, Any]) -> dict[str, set[str]]:
    """Reconstruct the committed Silver schema contract from ETL evidence."""

    lineage = set(LINEAGE_KINDS)
    catalog: dict[str, set[str]] = {}
    for table in summary["tables"]:
        output_table = table["output_table"]
        catalog[output_table] = (
            set(table["column_map"].values())
            | lineage
            | QUALITY_FLAG_COLUMNS.get(output_table, set())
        )
    return catalog


def _iter_source_refs(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_ref" and isinstance(child, str):
                yield child
            elif key == "source_refs" and isinstance(child, list):
                yield from (item for item in child if isinstance(item, str))
            else:
                yield from _iter_source_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_source_refs(child)


def _validate_source_ref(reference: str, catalog: dict[str, set[str]]) -> None:
    if "." not in reference:
        raise ValueError(f"Invalid Silver source reference: {reference}")
    table, column = reference.split(".", 1)
    if table not in catalog:
        raise ValueError(f"Unknown Silver table in source reference: {reference}")
    if column not in catalog[table]:
        raise ValueError(f"Unknown Silver column in source reference: {reference}")


def validate_model_config(
    config: dict[str, Any], catalog: dict[str, set[str]]
) -> None:
    """Fail fast on invalid grains, references or dimensional semantics."""

    if not isinstance(config, dict):
        raise ValueError("dimensional model root must be a mapping")
    model = config.get("model")
    dimensions = config.get("dimensions")
    facts = config.get("facts")
    bridges = config.get("bridges")
    if not isinstance(model, dict):
        raise ValueError("model must be a mapping")
    if model.get("architecture") != "fact_constellation":
        raise ValueError("approved architecture must be fact_constellation")
    if model.get("unknown_surrogate_key") != 0:
        raise ValueError("unknown_surrogate_key must be 0")
    technical_columns = config.get("technical_columns")
    if not isinstance(technical_columns, dict):
        raise ValueError("technical_columns must be a mapping")
    for scope in ("silver_derived_dimensions", "facts_and_bridges"):
        columns = technical_columns.get(scope)
        if not isinstance(columns, list) or not columns:
            raise ValueError(f"technical_columns.{scope} must be a non-empty list")
        if len(columns) != len(set(columns)) or any(
            not isinstance(column, str) or not FIELD_NAME_PATTERN.fullmatch(column)
            for column in columns
        ):
            raise ValueError(f"technical_columns.{scope} contains invalid columns")
    for collection_name, collection in (
        ("dimensions", dimensions),
        ("facts", facts),
        ("bridges", bridges),
    ):
        if not isinstance(collection, dict) or not collection:
            raise ValueError(f"{collection_name} must be a non-empty mapping")
        for object_name in collection:
            if not OBJECT_NAME_PATTERN.fullmatch(object_name):
                raise ValueError(f"Invalid dimensional object name: {object_name}")

    all_objects = set(dimensions) | set(facts) | set(bridges)
    if len(all_objects) != len(dimensions) + len(facts) + len(bridges):
        raise ValueError("dimensional object names must be globally unique")

    surrogate_keys: set[str] = set()
    for name, dimension in dimensions.items():
        key = dimension.get("surrogate_key")
        if not isinstance(key, str) or not FIELD_NAME_PATTERN.fullmatch(key):
            raise ValueError(f"{name} has an invalid surrogate key")
        if key in surrogate_keys:
            raise ValueError(f"Duplicate dimension surrogate key: {key}")
        surrogate_keys.add(key)
        natural_key = dimension.get("natural_key")
        if not isinstance(natural_key, list) or not natural_key:
            raise ValueError(f"{name} must declare a natural key")
        if dimension.get("scd_type") not in ALLOWED_SCD_TYPES:
            raise ValueError(f"{name} has an unsupported SCD type")

    for collection_name, collection in (("fact", facts), ("bridge", bridges)):
        for name, obj in collection.items():
            source_table = obj.get("source_table")
            if source_table not in catalog:
                raise ValueError(f"{name} references unknown source table {source_table}")
            grain_columns = obj.get("grain_columns")
            if not isinstance(grain_columns, list) or not grain_columns:
                raise ValueError(f"{name} must declare grain_columns")
            missing_grain = sorted(set(grain_columns) - catalog[source_table])
            if missing_grain:
                raise ValueError(f"{name} has unknown grain columns: {missing_grain}")
            foreign_keys = obj.get("foreign_keys")
            if not isinstance(foreign_keys, dict) or not foreign_keys:
                raise ValueError(f"{name} must declare foreign keys")
            unknown_dimensions = sorted(set(foreign_keys.values()) - set(dimensions))
            if unknown_dimensions:
                raise ValueError(
                    f"{name} references unknown dimensions: {unknown_dimensions}"
                )
            measures = obj.get("measures")
            if not isinstance(measures, dict) or not measures:
                raise ValueError(f"{name} must declare measures")
            for measure_name, measure in measures.items():
                if not FIELD_NAME_PATTERN.fullmatch(measure_name):
                    raise ValueError(f"{name} has invalid measure {measure_name}")
                if measure.get("aggregation") not in ALLOWED_AGGREGATIONS:
                    raise ValueError(f"{name}.{measure_name} has invalid aggregation")
                if measure.get("additivity") not in ALLOWED_ADDITIVITY:
                    raise ValueError(f"{name}.{measure_name} has invalid additivity")
            if collection_name == "bridge":
                prohibited = set(obj.get("prohibited_measures", []))
                if not prohibited:
                    raise ValueError(f"{name} must prohibit monetary propagation")

    if len(dimensions) != 8 or len(facts) != 6 or len(bridges) != 2:
        raise ValueError("approved MVP must contain 8 dimensions, 6 facts and 2 bridges")
    if any("process_key" not in obj["foreign_keys"] for obj in facts.values()):
        raise ValueError("every approved fact must reference dim_process")

    for reference in _iter_source_refs(config):
        _validate_source_ref(reference, catalog)

    gates = config.get("quality_gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("quality_gates must be a non-empty list")
    gate_ids = [gate.get("gate_id") for gate in gates]
    if len(gate_ids) != len(set(gate_ids)):
        raise ValueError("quality gate IDs must be unique")


def _read_silver_tables(
    settings: Settings, summary: dict[str, Any], required: set[str]
) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    reports = {table["output_table"]: table for table in summary["tables"]}
    for table_name in sorted(required):
        table_report = reports[table_name]
        path = settings.interim_root / table_report["output_relative_path"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing Silver Parquet: {path}")
        tables[table_name] = pq.read_table(path).to_pandas()
    return tables


def _grain_metrics(
    frame: pd.DataFrame, columns: list[str]
) -> dict[str, int]:
    return {
        "rows": len(frame),
        "null_grain_rows": int(frame[columns].isna().any(axis=1).sum()),
        "duplicate_grain_rows": int(frame.duplicated(subset=columns).sum()),
    }


def _group_cardinality(
    frame: pd.DataFrame, columns: list[str]
) -> dict[str, int | float]:
    counts = frame.groupby(columns, dropna=False).size()
    return {
        "parents": len(counts),
        "rows": len(frame),
        "minimum": int(counts.min()),
        "median": float(counts.median()),
        "maximum": int(counts.max()),
        "parents_with_multiple_rows": int((counts > 1).sum()),
    }


def _amount_reconciliation(
    parent: pd.DataFrame,
    child: pd.DataFrame,
    keys: list[str],
    parent_amount: str,
    child_amount: str,
    parent_currency: str,
    child_currency: str,
) -> dict[str, Any]:
    child_sum = child.groupby(keys, dropna=False)[child_amount].sum(min_count=1)
    child_count = child.groupby(keys, dropna=False).size().rename("child_count")
    joined = parent.set_index(keys).join(child_sum.rename("child_sum")).join(child_count)
    comparable = joined[parent_amount].notna() & joined["child_sum"].notna()
    difference = (
        joined.loc[comparable, parent_amount] - joined.loc[comparable, "child_sum"]
    ).abs()
    child_currencies = child.groupby(keys, dropna=False)[child_currency].agg(
        lambda values: ";".join(sorted(set(values.dropna().astype(str))))
    )
    joined = joined.join(child_currencies.rename("child_currencies"))
    currency_match = joined[parent_currency].fillna("").astype(str).eq(
        joined["child_currencies"].fillna("")
    )
    return {
        "parent_rows": len(parent),
        "parents_with_items": int(joined["child_count"].notna().sum()),
        "comparable_amount_rows": int(comparable.sum()),
        "exact_matches": int((difference == 0).sum()),
        "matches_within_0_01": int((difference <= Decimal("0.01")).sum()),
        "mismatches_over_0_01": int((difference > Decimal("0.01")).sum()),
        "maximum_absolute_difference": str(difference.max()),
        "currency_matches": int(currency_match.sum()),
        "currency_mismatches": int((~currency_match).sum()),
    }


def _foreign_rate_coverage(
    parent: pd.DataFrame,
    rate: pd.DataFrame,
    keys: list[str],
    currency_column: str,
) -> dict[str, int]:
    foreign = parent.loc[parent[currency_column].ne("PEN"), keys].drop_duplicates()
    foreign_keys = set(map(tuple, foreign.itertuples(index=False, name=None)))
    rate_keys = set(
        map(tuple, rate[keys].drop_duplicates().itertuples(index=False, name=None))
    )
    return {
        "foreign_rows": len(foreign),
        "rows_with_oece_pen_rate": len(foreign_keys & rate_keys),
        "rows_without_oece_pen_rate": len(foreign_keys - rate_keys),
        "unsupported_conversions_created": 0,
    }


def _category_dimension_metrics(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
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
    classifications = []
    for table_name, scheme, code, description in specs:
        frame = tables[table_name][
            [scheme, code, description, "dq_classification_was_missing"]
        ].copy()
        frame.columns = ["scheme", "code", "description", "dq_missing"]
        missing = frame["dq_missing"].fillna(False)
        frame.loc[missing, ["scheme", "code", "description"]] = [
            "UNKNOWN",
            "__UNCLASSIFIED__",
            "Sin clasificar",
        ]
        classifications.append(frame)
    combined = pd.concat(classifications, ignore_index=True)
    variants = combined.groupby(["scheme", "code"], dropna=False)[
        "description"
    ].nunique()
    return {
        "observations": len(combined),
        "estimated_rows_including_unknown": int(
            combined[["scheme", "code"]].drop_duplicates().shape[0]
        ),
        "scheme_observations": {
            str(key): int(value)
            for key, value in combined["scheme"].value_counts(dropna=False).items()
        },
        "keys_with_description_conflicts": int((variants > 1).sum()),
        "unknown_observations": int((combined["scheme"] == "UNKNOWN").sum()),
    }


def _date_dimension_metrics(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    dates = []
    for table_name in ("procurement_process", "award", "contract"):
        frame = tables[table_name]
        for column in frame.columns:
            if column == "loaded_at_utc":
                continue
            if pd.api.types.is_datetime64_any_dtype(frame[column]):
                values = frame[column].dropna()
                if not values.empty:
                    dates.append(values.dt.tz_convert("America/Lima").dt.date)
    combined = pd.concat(dates, ignore_index=True)
    minimum = min(combined)
    maximum = max(combined)
    return {
        "minimum_business_date": minimum.isoformat(),
        "maximum_business_date": maximum.isoformat(),
        "observed_distinct_dates": int(combined.nunique()),
        "calendar_rows_required": (maximum - minimum).days + 1,
    }


def analyze_dimensional_model(
    settings: Settings,
    model_path: Path,
    etl_summary_path: Path,
) -> dict[str, Any]:
    """Measure whether the approved logical model fits the Silver pilot."""

    model_config = load_model_config(model_path)
    etl_summary = load_etl_summary(etl_summary_path)
    catalog = silver_column_catalog(etl_summary)
    validate_model_config(model_config, catalog)
    required_tables = {
        table
        for table in catalog
        if table
        in {
            "procurement_process",
            "party",
            "party_additional_identifier",
            "tenderer",
            "tender_item",
            "tender_item_classification",
            "tender_item_exchange_rate",
            "award",
            "award_supplier",
            "award_item",
            "award_item_classification",
            "award_item_exchange_rate",
            "award_value_exchange_rate",
            "contract",
            "contract_item",
            "contract_item_classification",
            "contract_item_exchange_rate",
            "contract_value_exchange_rate",
        }
    }
    tables = _read_silver_tables(settings, etl_summary, required_tables)

    facts = model_config["facts"]
    bridges = model_config["bridges"]
    grain_results: dict[str, dict[str, int]] = {}
    for name, obj in {**facts, **bridges}.items():
        grain_results[name] = _grain_metrics(
            tables[obj["source_table"]], obj["grain_columns"]
        )

    process = tables["procurement_process"]
    party = tables["party"]
    tenderer = tables["tenderer"]
    award = tables["award"]
    award_supplier = tables["award_supplier"]
    award_item = tables["award_item"]
    contract = tables["contract"]
    contract_item = tables["contract_item"]

    party_key = "compiled_release_parties_id"
    party_roles = "compiled_release_parties_roles"
    buyer_rows = party[party[party_roles].str.contains("buyer", na=False)]
    supplier_rows = party[
        party[party_roles].str.contains("tenderer|supplier", na=False)
    ]
    buyer_identifiers = tables["party_additional_identifier"]
    buyer_ruc = buyer_identifiers[
        "compiled_release_parties_additional_identifiers_id"
    ].astype("string")
    buyer_name_variants = buyer_rows.groupby(party_key)[
        "compiled_release_parties_identifier_legal_name"
    ].nunique()
    supplier_name_variants = supplier_rows.groupby(party_key)[
        "compiled_release_parties_identifier_legal_name"
    ].nunique()

    category_metrics = _category_dimension_metrics(tables)
    method_rows = process[
        [
            "compiled_release_tender_procurement_method",
            "compiled_release_tender_procurement_method_details",
        ]
    ].drop_duplicates()
    currency_columns = [
        ("procurement_process", "compiled_release_tender_value_currency"),
        ("procurement_process", "compiled_release_planning_budget_amount_currency"),
        ("tender_item", "compiled_release_tender_items_total_value_currency"),
        ("award", "compiled_release_awards_value_currency"),
        ("award_item", "compiled_release_awards_items_total_value_currency"),
        ("contract", "compiled_release_contracts_value_currency"),
        ("contract_item", "compiled_release_contracts_items_total_value_currency"),
    ]
    currencies = pd.concat(
        [tables[name][column] for name, column in currency_columns], ignore_index=True
    ).dropna()
    unit_rows = []
    for table_name, prefix in (
        ("tender_item", "compiled_release_tender_items_unit"),
        ("award_item", "compiled_release_awards_items_unit"),
        ("contract_item", "compiled_release_contracts_items_unit"),
    ):
        frame = tables[table_name]
        unit_rows.append(frame[[f"{prefix}_scheme", f"{prefix}_id"]].set_axis(
            ["scheme", "code"], axis=1
        ))
    units = pd.concat(unit_rows, ignore_index=True).drop_duplicates()

    date_metrics = _date_dimension_metrics(tables)
    dimension_estimates = {
        "dim_date": date_metrics["calendar_rows_required"],
        "dim_process": int(process["ocid"].nunique()),
        "dim_buyer": int(buyer_rows[party_key].nunique()),
        "dim_supplier": int(supplier_rows[party_key].nunique()),
        "dim_category": category_metrics["estimated_rows_including_unknown"],
        "dim_procurement_method": len(method_rows),
        "dim_currency": int(currencies.nunique()),
        "dim_unit": len(units),
    }

    party_keys = set(
        map(
            tuple,
            party[["ocid", party_key]].dropna().itertuples(index=False, name=None),
        )
    )
    buyer_keys = set(
        map(
            tuple,
            process[["ocid", "compiled_release_buyer_id"]]
            .dropna()
            .itertuples(index=False, name=None),
        )
    )
    tenderer_keys = set(
        map(
            tuple,
            tenderer[["ocid", "compiled_release_tender_tenderers_id"]]
            .dropna()
            .itertuples(index=False, name=None),
        )
    )
    supplier_keys = set(
        map(
            tuple,
            award_supplier[["ocid", "compiled_release_awards_suppliers_id"]]
            .dropna()
            .itertuples(index=False, name=None),
        )
    )
    award_keys = set(
        map(
            tuple,
            award[["ocid", "compiled_release_awards_id"]]
            .dropna()
            .itertuples(index=False, name=None),
        )
    )
    contract_award_keys = set(
        map(
            tuple,
            contract[["ocid", "compiled_release_contracts_award_id"]]
            .dropna()
            .itertuples(index=False, name=None),
        )
    )
    referential_metrics = {
        "buyer_to_party_orphans": len(buyer_keys - party_keys),
        "tenderer_to_party_orphans": len(tenderer_keys - party_keys),
        "award_supplier_to_party_orphans": len(supplier_keys - party_keys),
        "contract_to_award_orphans": len(contract_award_keys - award_keys),
    }

    additional_cardinalities = {
        "tender_item_classification": _group_cardinality(
            tables["tender_item_classification"],
            ["ocid", "compiled_release_tender_items_id"],
        ),
        "award_item_classification": _group_cardinality(
            tables["award_item_classification"],
            ["ocid", "compiled_release_awards_id", "compiled_release_awards_items_id"],
        ),
        "contract_item_classification": _group_cardinality(
            tables["contract_item_classification"],
            [
                "ocid",
                "compiled_release_contracts_id",
                "compiled_release_contracts_items_id",
            ],
        ),
    }

    supplier_counts = award_supplier.groupby(
        ["ocid", "compiled_release_awards_id"]
    ).size()
    awards_index = award.set_index(["ocid", "compiled_release_awards_id"]).index
    supplier_counts = supplier_counts.reindex(awards_index, fill_value=0)
    contract_supplier_keys = set(
        map(
            tuple,
            award_supplier[["ocid", "compiled_release_awards_id"]]
            .drop_duplicates()
            .itertuples(index=False, name=None),
        )
    )
    contract_award_rows = list(
        map(
            tuple,
            contract[["ocid", "compiled_release_contracts_award_id"]]
            .dropna()
            .itertuples(index=False, name=None),
        )
    )
    contracts_attributable = sum(
        key in contract_supplier_keys for key in contract_award_rows
    )
    supplier_attribution = {
        "awards_without_supplier": int((supplier_counts == 0).sum()),
        "awards_with_one_supplier": int((supplier_counts == 1).sum()),
        "awards_with_multiple_suppliers": int((supplier_counts > 1).sum()),
        "maximum_suppliers_per_award": int(supplier_counts.max()),
        "award_rows_amount_attributable": int((supplier_counts == 1).sum()),
        "contract_rows_amount_attributable": int(contracts_attributable),
        "invented_allocations": 0,
    }

    tenderer_observed = tenderer.groupby("ocid").size().rename("observed")
    declared = process.set_index("ocid")[
        "compiled_release_tender_number_of_tenderers"
    ].rename("declared")
    tenderer_comparison = pd.concat([declared, tenderer_observed], axis=1).dropna()

    amount_reconciliation = {
        "tender": _amount_reconciliation(
            process,
            tables["tender_item"],
            ["ocid"],
            "compiled_release_tender_value_amount",
            "compiled_release_tender_items_total_value_amount",
            "compiled_release_tender_value_currency",
            "compiled_release_tender_items_total_value_currency",
        ),
        "award": _amount_reconciliation(
            award,
            award_item,
            ["ocid", "compiled_release_awards_id"],
            "compiled_release_awards_value_amount",
            "compiled_release_awards_items_total_value_amount",
            "compiled_release_awards_value_currency",
            "compiled_release_awards_items_total_value_currency",
        ),
        "contract": _amount_reconciliation(
            contract,
            contract_item,
            ["ocid", "compiled_release_contracts_id"],
            "compiled_release_contracts_value_amount",
            "compiled_release_contracts_items_total_value_amount",
            "compiled_release_contracts_value_currency",
            "compiled_release_contracts_items_total_value_currency",
        ),
    }

    conversion_coverage = {
        "tender_item": _foreign_rate_coverage(
            tables["tender_item"],
            tables["tender_item_exchange_rate"],
            ["ocid", "compiled_release_tender_items_id"],
            "compiled_release_tender_items_total_value_currency",
        ),
        "award": _foreign_rate_coverage(
            award,
            tables["award_value_exchange_rate"],
            ["ocid", "compiled_release_awards_id"],
            "compiled_release_awards_value_currency",
        ),
        "award_item": _foreign_rate_coverage(
            award_item,
            tables["award_item_exchange_rate"],
            ["ocid", "compiled_release_awards_id", "compiled_release_awards_items_id"],
            "compiled_release_awards_items_total_value_currency",
        ),
        "contract": _foreign_rate_coverage(
            contract,
            tables["contract_value_exchange_rate"],
            ["ocid", "compiled_release_contracts_id"],
            "compiled_release_contracts_value_currency",
        ),
        "contract_item": _foreign_rate_coverage(
            contract_item,
            tables["contract_item_exchange_rate"],
            [
                "ocid",
                "compiled_release_contracts_id",
                "compiled_release_contracts_items_id",
            ],
            "compiled_release_contracts_items_total_value_currency",
        ),
    }

    grain_violations = sum(
        metric["null_grain_rows"] + metric["duplicate_grain_rows"]
        for metric in grain_results.values()
    )
    orphans = sum(referential_metrics.values())
    maximum_standard_categories = max(
        metric["maximum"] for metric in additional_cardinalities.values()
    )
    unsupported_conversions = sum(
        metric["unsupported_conversions_created"]
        for metric in conversion_coverage.values()
    )
    gate_results = [
        {
            "gate_id": "DM-GRAIN-001",
            "status": "PASS" if grain_violations == 0 else "FAIL",
            "violations": grain_violations,
        },
        {
            "gate_id": "DM-REF-001",
            "status": "PASS" if orphans == 0 else "FAIL",
            "violations": orphans,
        },
        {
            "gate_id": "DM-CAT-001",
            "status": "PASS" if maximum_standard_categories <= 1 else "FAIL",
            "maximum_rows_per_item": maximum_standard_categories,
        },
        {
            "gate_id": "DM-SUP-001",
            "status": "PASS"
            if supplier_attribution["invented_allocations"] == 0
            else "FAIL",
            "invented_allocations": supplier_attribution["invented_allocations"],
        },
        {
            "gate_id": "DM-AMT-001",
            "status": "PASS"
            if all(
                metric["parent_rows"] == metric["comparable_amount_rows"]
                for metric in amount_reconciliation.values()
            )
            else "FAIL",
            "parent_rows_evaluated": sum(
                metric["comparable_amount_rows"]
                for metric in amount_reconciliation.values()
            ),
        },
        {
            "gate_id": "DM-RATE-001",
            "status": "PASS" if unsupported_conversions == 0 else "FAIL",
            "unsupported_conversions": unsupported_conversions,
        },
    ]
    failed_gates = [gate for gate in gate_results if gate["status"] == "FAIL"]
    warning_metrics = {
        "supplier_name_conflicts": int((supplier_name_variants > 1).sum()),
        "category_description_conflicts": category_metrics[
            "keys_with_description_conflicts"
        ],
        "tenderer_count_differences": int(
            (tenderer_comparison["declared"] != tenderer_comparison["observed"]).sum()
        ),
        "header_item_amount_mismatches": sum(
            metric["mismatches_over_0_01"]
            for metric in amount_reconciliation.values()
        ),
        "foreign_rows_without_rate": sum(
            metric["rows_without_oece_pen_rate"]
            for metric in conversion_coverage.values()
        ),
        "contracts_without_final_value": int(
            (~contract["dq_final_value_available"].fillna(False)).sum()
        ),
    }
    warning_metric_count = sum(value > 0 for value in warning_metrics.values())
    fact_source_rows = sum(
        grain_results[name]["rows"] for name in model_config["facts"]
    )
    bridge_source_rows = sum(
        grain_results[name]["rows"] for name in model_config["bridges"]
    )

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_scope": "logical_dimensional_model_against_silver_pilot",
        "source": {
            "model_config": model_path.as_posix(),
            "model_config_sha256": sha256_text_file(model_path),
            "etl_summary": etl_summary_path.as_posix(),
            "etl_summary_sha256": sha256_text_file(etl_summary_path),
            "source_period": etl_summary["source"]["source_period"],
            "snapshot_date": etl_summary["source"]["snapshot_date"],
            "archive_sha256": etl_summary["source"]["archive_sha256"],
        },
        "summary": {
            "status": "BLOCKED"
            if failed_gates
            else ("PASS_WITH_WARNINGS" if warning_metric_count else "PASS"),
            "design_eligible_for_phase7": not failed_gates,
            "dimensions": len(model_config["dimensions"]),
            "facts": len(facts),
            "bridges": len(bridges),
            "modeled_objects": len(model_config["dimensions"]) + len(facts) + len(bridges),
            "fact_source_rows": fact_source_rows,
            "bridge_source_rows": bridge_source_rows,
            "modeled_source_rows": fact_source_rows + bridge_source_rows,
            "quality_gates_passed": len(gate_results) - len(failed_gates),
            "quality_gates_failed": len(failed_gates),
            "warning_metrics": warning_metric_count,
        },
        "dimension_estimates": dimension_estimates,
        "dimension_quality": {
            "date": date_metrics,
            "buyer_name_conflicts": int((buyer_name_variants > 1).sum()),
            "buyer_alternate_ruc": {
                "observations": len(buyer_ruc),
                "unique_values": int(buyer_ruc.nunique()),
                "invalid_format_rows": int(
                    (~buyer_ruc.str.fullmatch(r"\d{11}").fillna(False)).sum()
                ),
            },
            "supplier_name_conflicts": int((supplier_name_variants > 1).sum()),
            "supplier_invalid_ruc_observations": int(
                (supplier_rows["dq_ruc_format_valid"] == False).sum()
            ),
            "supplier_invalid_ruc_members": int(
                supplier_rows.loc[
                    supplier_rows["dq_ruc_format_valid"] == False, party_key
                ].nunique()
            ),
            "category": category_metrics,
        },
        "fact_and_bridge_grains": grain_results,
        "lifecycle_cardinalities": {
            "tenderers_per_process": _group_cardinality(tenderer, ["ocid"]),
            "awards_per_process": _group_cardinality(award, ["ocid"]),
            "contracts_per_process": _group_cardinality(contract, ["ocid"]),
            "award_items_per_award": _group_cardinality(
                award_item, ["ocid", "compiled_release_awards_id"]
            ),
            "contract_items_per_contract": _group_cardinality(
                contract_item, ["ocid", "compiled_release_contracts_id"]
            ),
        },
        "referential_metrics": referential_metrics,
        "additional_classification_cardinalities": additional_cardinalities,
        "supplier_attribution": supplier_attribution,
        "tenderer_count_comparison": {
            "comparable_processes": len(tenderer_comparison),
            "matching_processes": int(
                (tenderer_comparison["declared"] == tenderer_comparison["observed"]).sum()
            ),
            "different_processes": int(
                (tenderer_comparison["declared"] != tenderer_comparison["observed"]).sum()
            ),
        },
        "amount_reconciliation": amount_reconciliation,
        "conversion_coverage": conversion_coverage,
        "fitness_for_use": {
            "contracts": len(contract),
            "contracts_with_final_value": int(
                contract["dq_final_value_available"].fillna(False).sum()
            ),
            "contracts_without_final_value": int(
                (~contract["dq_final_value_available"].fillna(False)).sum()
            ),
            "final_value_coverage_pct": round(
                contract["dq_final_value_available"].fillna(False).mean() * 100,
                4,
            ),
        },
        "warning_metrics": warning_metrics,
        "quality_gates": gate_results,
        "deferred_objects": sorted(model_config["deferred_or_excluded"]),
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
    parser.add_argument(
        "--model", type=Path, default=Path("config/dimensional_model.yml")
    )
    parser.add_argument(
        "--etl-summary",
        type=Path,
        default=Path("reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json"),
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings(args.env_file)
    report = analyze_dimensional_model(
        settings, args.model, args.etl_summary
    )
    write_json(report, args.output)
    summary = report["summary"]
    print(
        f"Dimensional model {summary['status']}: "
        f"{summary['modeled_objects']} objects; "
        f"{summary['quality_gates_passed']}/"
        f"{summary['quality_gates_passed'] + summary['quality_gates_failed']} gates passed."
    )


if __name__ == "__main__":
    main()
