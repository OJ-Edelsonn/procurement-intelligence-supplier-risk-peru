"""Evaluate governed data quality rules against an OECE OCDS CSV archive."""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zipfile import ZipFile, ZipInfo

import pandas as pd
import yaml

from procurement_intelligence.extraction.download_ocds import (
    sha256_file,
    sha256_text_file,
)
from procurement_intelligence.profiling.profile_ocds_csv import CANDIDATE_GRAINS

SUPPORTED_RULE_TYPES = {
    "candidate_grains",
    "classification_completeness",
    "conditional_not_null",
    "exact_duplicates",
    "foreign_keys",
    "minimum_coverage",
    "not_null",
    "numeric_min",
    "ordered_datetimes",
    "parseable_datetime",
    "peru_ruc",
    "required_columns",
    "required_tables",
    "root_references",
}
SUPPORTED_SEVERITIES = {"critical", "error", "warning", "info"}
RULE_ID_PATTERN = re.compile(r"^DQ-[A-Z]+-[0-9]{3}$")


def load_quality_config(path: Path) -> dict[str, Any]:
    """Load and structurally validate the governed rule catalog."""

    with path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    validate_quality_config(config)
    return config


def validate_quality_config(config: dict[str, Any]) -> None:
    """Reject incomplete, duplicate, or unsupported rules."""

    if not isinstance(config, dict):
        raise ValueError("quality config root must be a mapping")
    framework = config.get("framework")
    rules = config.get("rules")
    if not isinstance(framework, dict):
        raise ValueError("framework must be a mapping")
    if not isinstance(rules, list) or not rules:
        raise ValueError("rules must be a non-empty list")
    blocking = framework.get("blocking_severities")
    if not isinstance(blocking, list) or not set(blocking) <= SUPPORTED_SEVERITIES:
        raise ValueError("blocking_severities contains unsupported values")

    rule_ids: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("each rule must be a mapping")
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not RULE_ID_PATTERN.fullmatch(rule_id):
            raise ValueError(f"invalid rule_id: {rule_id!r}")
        if rule_id in rule_ids:
            raise ValueError(f"duplicate rule_id: {rule_id}")
        rule_ids.add(rule_id)
        if rule.get("type") not in SUPPORTED_RULE_TYPES:
            raise ValueError(f"{rule_id} uses an unsupported rule type")
        if rule.get("severity") not in SUPPORTED_SEVERITIES:
            raise ValueError(f"{rule_id} uses an unsupported severity")
        for field in ("name", "dimension", "description"):
            if not isinstance(rule.get(field), str) or not rule[field].strip():
                raise ValueError(f"{rule_id}.{field} must be non-empty text")
        threshold = rule.get("threshold")
        if not isinstance(threshold, dict) or not threshold:
            raise ValueError(f"{rule_id}.threshold must be a non-empty mapping")
        if not ({"max_invalid_count", "max_invalid_pct", "min_coverage_pct"} & threshold.keys()):
            raise ValueError(f"{rule_id} has no supported threshold")


def _detect_encoding(archive: ZipFile, member: ZipInfo) -> str:
    with archive.open(member) as source_file:
        sample = source_file.read(64 * 1024)
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not detect text encoding for {member.filename}")


def read_archive(archive_path: Path) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Read every CSV member as strings without mutating source values."""

    tables: dict[str, pd.DataFrame] = {}
    encodings: dict[str, str] = {}
    with ZipFile(archive_path) as archive:
        members = sorted(
            (member for member in archive.infolist() if member.filename.lower().endswith(".csv")),
            key=lambda member: member.filename,
        )
        for member in members:
            table_name = Path(member.filename).name
            if table_name in tables:
                raise ValueError(f"Duplicate CSV member name: {table_name}")
            encoding = _detect_encoding(archive, member)
            with archive.open(member) as source_file:
                tables[table_name] = pd.read_csv(
                    source_file,
                    encoding=encoding,
                    dtype="string",
                    low_memory=False,
                )
            encodings[table_name] = encoding
    return tables, encodings


def _threshold_passed(
    threshold: dict[str, Any], invalid_rows: int, rows_evaluated: int
) -> bool:
    invalid_pct = (invalid_rows / rows_evaluated * 100) if rows_evaluated else 0.0
    checks: list[bool] = []
    if "max_invalid_count" in threshold:
        checks.append(invalid_rows <= int(threshold["max_invalid_count"]))
    if "max_invalid_pct" in threshold:
        checks.append(invalid_pct <= float(threshold["max_invalid_pct"]))
    if "min_coverage_pct" in threshold:
        coverage_pct = 100 - invalid_pct
        checks.append(coverage_pct >= float(threshold["min_coverage_pct"]))
    return all(checks)


def _missing_target(
    tables: dict[str, pd.DataFrame], table: str, columns: list[str]
) -> list[str]:
    if table not in tables:
        return [f"{table}::<missing table>"]
    return [f"{table}::{column}" for column in columns if column not in tables[table]]


def _required_tables(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    expected = rule["parameters"]["tables"]
    missing = sorted(set(expected) - set(tables))
    return len(missing), len(expected), {"missing_tables": missing}


def _required_columns(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    missing: list[str] = []
    expected_count = 0
    for target in rule["parameters"]["targets"]:
        expected_count += len(target["columns"])
        missing.extend(_missing_target(tables, target["table"], target["columns"]))
    return len(missing), expected_count, {"missing_columns": sorted(missing)}


def _not_null(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    invalid_rows = 0
    rows_evaluated = 0
    target_results = []
    for target in rule["parameters"]["targets"]:
        table_name = target["table"]
        missing = _missing_target(tables, table_name, target["columns"])
        if missing:
            invalid_rows += len(missing)
            rows_evaluated += len(missing)
            target_results.append({"table": table_name, "missing": missing})
            continue
        dataframe = tables[table_name]
        invalid = int(dataframe[target["columns"]].isna().any(axis=1).sum())
        invalid_rows += invalid
        rows_evaluated += len(dataframe)
        target_results.append(
            {"table": table_name, "rows": len(dataframe), "invalid_rows": invalid}
        )
    return invalid_rows, rows_evaluated, {"targets": target_results}


def _candidate_grains(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    invalid_rows = 0
    rows_evaluated = 0
    target_results = []
    for table_name, columns in CANDIDATE_GRAINS.items():
        missing = _missing_target(tables, table_name, columns)
        if missing:
            invalid_rows += len(missing)
            rows_evaluated += len(missing)
            target_results.append({"table": table_name, "missing": missing})
            continue
        dataframe = tables[table_name]
        null_key_rows = int(dataframe[columns].isna().any(axis=1).sum())
        duplicate_key_rows = int(dataframe.duplicated(subset=columns).sum())
        invalid_rows += null_key_rows + duplicate_key_rows
        rows_evaluated += len(dataframe)
        target_results.append(
            {
                "table": table_name,
                "rows": len(dataframe),
                "null_key_rows": null_key_rows,
                "additional_duplicate_key_rows": duplicate_key_rows,
            }
        )
    return invalid_rows, rows_evaluated, {"targets": target_results}


def _exact_duplicates(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    configured_tables = rule["parameters"].get("tables", "all")
    table_names = sorted(tables) if configured_tables == "all" else configured_tables
    invalid_rows = 0
    rows_evaluated = 0
    target_results = []
    for table_name in table_names:
        if table_name not in tables:
            invalid_rows += 1
            rows_evaluated += 1
            target_results.append({"table": table_name, "missing": True})
            continue
        dataframe = tables[table_name]
        additional_duplicates = int(dataframe.duplicated().sum())
        affected_rows = int(dataframe.duplicated(keep=False).sum())
        invalid_rows += additional_duplicates
        rows_evaluated += len(dataframe)
        target_results.append(
            {
                "table": table_name,
                "rows": len(dataframe),
                "additional_duplicate_rows": additional_duplicates,
                "affected_rows": affected_rows,
            }
        )
    return invalid_rows, rows_evaluated, {"targets": target_results}


def _root_references(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    parameters = rule["parameters"]
    root_name = parameters["root_table"]
    keys = parameters["keys"]
    if root_name not in tables:
        return 1, 1, {"missing_root_table": root_name, "checks": []}
    root = tables[root_name]
    invalid_rows = 0
    rows_evaluated = 0
    checks = []
    for table_name, dataframe in sorted(tables.items()):
        if table_name == root_name:
            continue
        for key in keys:
            if key not in dataframe or key not in root:
                continue
            child_values = dataframe[key].dropna()
            parent_values = set(root[key].dropna())
            missing = int((~child_values.isin(parent_values)).sum())
            invalid_rows += missing
            rows_evaluated += len(child_values)
            checks.append(
                {
                    "table": table_name,
                    "key": key,
                    "rows_evaluated": len(child_values),
                    "missing_parent_rows": missing,
                }
            )
    return invalid_rows, rows_evaluated, {"checks": checks, "check_count": len(checks)}


def _foreign_keys(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    invalid_rows = 0
    rows_evaluated = 0
    checks = []
    for relationship in rule["parameters"]["relationships"]:
        child_name = relationship["child_table"]
        parent_name = relationship["parent_table"]
        child_columns = relationship["child_columns"]
        parent_columns = relationship["parent_columns"]
        missing = _missing_target(tables, child_name, child_columns)
        missing.extend(_missing_target(tables, parent_name, parent_columns))
        if missing:
            invalid_rows += len(missing)
            rows_evaluated += len(missing)
            checks.append({"name": relationship["name"], "missing": missing})
            continue
        child = tables[child_name]
        parent = tables[parent_name]
        complete_child = child.loc[child[child_columns].notna().all(axis=1), child_columns]
        parent_keys = set(map(tuple, parent[parent_columns].dropna().itertuples(index=False, name=None)))
        child_keys = list(map(tuple, complete_child.itertuples(index=False, name=None)))
        orphan_rows = sum(key not in parent_keys for key in child_keys)
        invalid_rows += orphan_rows
        rows_evaluated += len(child_keys)
        checks.append(
            {
                "name": relationship["name"],
                "rows_evaluated": len(child_keys),
                "orphan_rows": orphan_rows,
            }
        )
    return invalid_rows, rows_evaluated, {"checks": checks, "check_count": len(checks)}


def _numeric_min(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    parameters = rule["parameters"]
    minimum = float(parameters["minimum"])
    inclusive = bool(parameters.get("inclusive", True))
    allow_null = bool(parameters.get("allow_null", True))
    invalid_rows = 0
    rows_evaluated = 0
    target_results = []
    for target in parameters["targets"]:
        table_name = target["table"]
        column = target["column"]
        missing = _missing_target(tables, table_name, [column])
        if missing:
            invalid_rows += 1
            rows_evaluated += 1
            target_results.append({"table": table_name, "column": column, "missing": True})
            continue
        source_values = tables[table_name][column]
        null_invalid = 0 if allow_null else int(source_values.isna().sum())
        values = source_values.dropna()
        numeric = pd.to_numeric(values, errors="coerce")
        parse_invalid = int(numeric.isna().sum())
        below = numeric < minimum if inclusive else numeric <= minimum
        range_invalid = int(below.fillna(False).sum())
        invalid = null_invalid + parse_invalid + range_invalid
        invalid_rows += invalid
        rows_evaluated += len(values) if allow_null else len(source_values)
        target_results.append(
            {
                "table": table_name,
                "column": column,
                "rows_evaluated": len(values) if allow_null else len(source_values),
                "null_invalid_rows": null_invalid,
                "parse_invalid_rows": parse_invalid,
                "range_invalid_rows": range_invalid,
            }
        )
    return invalid_rows, rows_evaluated, {"targets": target_results}


def _parseable_datetime(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    invalid_rows = 0
    rows_evaluated = 0
    target_results = []
    for target in rule["parameters"]["targets"]:
        table_name = target["table"]
        column = target["column"]
        missing = _missing_target(tables, table_name, [column])
        if missing:
            invalid_rows += 1
            rows_evaluated += 1
            target_results.append({"table": table_name, "column": column, "missing": True})
            continue
        values = tables[table_name][column].dropna()
        parsed = pd.to_datetime(values, errors="coerce", utc=True, format="mixed")
        invalid = int(parsed.isna().sum())
        invalid_rows += invalid
        rows_evaluated += len(values)
        target_results.append(
            {
                "table": table_name,
                "column": column,
                "rows_evaluated": len(values),
                "invalid_rows": invalid,
            }
        )
    return invalid_rows, rows_evaluated, {"targets": target_results}


def _ordered_datetimes(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    invalid_rows = 0
    rows_evaluated = 0
    pair_results = []
    for pair in rule["parameters"]["pairs"]:
        table_name = pair["table"]
        start_column = pair["start_column"]
        end_column = pair["end_column"]
        missing = _missing_target(tables, table_name, [start_column, end_column])
        if missing:
            invalid_rows += len(missing)
            rows_evaluated += len(missing)
            pair_results.append({"table": table_name, "missing": missing})
            continue
        dataframe = tables[table_name]
        starts = pd.to_datetime(
            dataframe[start_column], errors="coerce", utc=True, format="mixed"
        )
        ends = pd.to_datetime(
            dataframe[end_column], errors="coerce", utc=True, format="mixed"
        )
        comparable = starts.notna() & ends.notna()
        invalid = int((comparable & (starts > ends)).sum())
        invalid_rows += invalid
        rows_evaluated += int(comparable.sum())
        pair_results.append(
            {
                "table": table_name,
                "start_column": start_column,
                "end_column": end_column,
                "rows_evaluated": int(comparable.sum()),
                "invalid_rows": invalid,
            }
        )
    return invalid_rows, rows_evaluated, {"pairs": pair_results}


def _conditional_not_null(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    invalid_rows = 0
    rows_evaluated = 0
    target_results = []
    for target in rule["parameters"]["targets"]:
        table_name = target["table"]
        condition = target["condition_column"]
        required = target["required_column"]
        missing = _missing_target(tables, table_name, [condition, required])
        if missing:
            invalid_rows += len(missing)
            rows_evaluated += len(missing)
            target_results.append({"table": table_name, "missing": missing})
            continue
        dataframe = tables[table_name]
        applicable = dataframe[condition].notna()
        invalid = int((applicable & dataframe[required].isna()).sum())
        invalid_rows += invalid
        rows_evaluated += int(applicable.sum())
        target_results.append(
            {
                "table": table_name,
                "rows_evaluated": int(applicable.sum()),
                "invalid_rows": invalid,
            }
        )
    return invalid_rows, rows_evaluated, {"targets": target_results}


def _peru_ruc(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    parameters = rule["parameters"]
    table_name = parameters["table"]
    scheme_column = parameters["scheme_column"]
    identifier_column = parameters["identifier_column"]
    missing = _missing_target(tables, table_name, [scheme_column, identifier_column])
    if missing:
        return len(missing), len(missing), {"missing": missing}
    dataframe = tables[table_name]
    applicable = dataframe[scheme_column].str.upper().eq(parameters["scheme_value"].upper()).fillna(False)
    identifiers = dataframe.loc[applicable, identifier_column]
    normalized = identifiers.fillna("").str.strip()
    format_valid = normalized.str.fullmatch(r"\d{11}")
    invalid_length = int(normalized.str.len().ne(11).sum())
    non_digit = int((normalized.str.len().eq(11) & ~normalized.str.fullmatch(r"\d{11}")).sum())
    format_invalid = int((~format_valid).sum())
    return format_invalid, len(identifiers), {
        "scheme": parameters["scheme_value"],
        "rows_evaluated": len(identifiers),
        "format_invalid_rows": format_invalid,
        "invalid_length_rows": invalid_length,
        "non_digit_rows_with_length_11": non_digit,
    }


def _classification_completeness(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    invalid_rows = 0
    rows_evaluated = 0
    target_results = []
    for target in rule["parameters"]["targets"]:
        table_name = target["table"]
        columns = target["columns"]
        missing = _missing_target(tables, table_name, columns)
        if missing:
            invalid_rows += len(missing)
            rows_evaluated += len(missing)
            target_results.append({"table": table_name, "missing": missing})
            continue
        dataframe = tables[table_name]
        invalid = int(dataframe[columns].isna().any(axis=1).sum())
        invalid_rows += invalid
        rows_evaluated += len(dataframe)
        target_results.append(
            {"table": table_name, "rows": len(dataframe), "invalid_rows": invalid}
        )
    return invalid_rows, rows_evaluated, {"targets": target_results}


def _minimum_coverage(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> tuple[int, int, dict[str, Any]]:
    parameters = rule["parameters"]
    table_name = parameters["table"]
    column = parameters["column"]
    missing = _missing_target(tables, table_name, [column])
    if missing:
        return len(missing), len(missing), {"missing": missing, "coverage_pct": 0.0}
    dataframe = tables[table_name]
    invalid = int(dataframe[column].isna().sum())
    coverage = ((len(dataframe) - invalid) / len(dataframe) * 100) if len(dataframe) else 0.0
    return invalid, len(dataframe), {"coverage_pct": round(coverage, 4)}


EVALUATORS: dict[
    str, Callable[[dict[str, Any], dict[str, pd.DataFrame]], tuple[int, int, dict[str, Any]]]
] = {
    "candidate_grains": _candidate_grains,
    "classification_completeness": _classification_completeness,
    "conditional_not_null": _conditional_not_null,
    "exact_duplicates": _exact_duplicates,
    "foreign_keys": _foreign_keys,
    "minimum_coverage": _minimum_coverage,
    "not_null": _not_null,
    "numeric_min": _numeric_min,
    "ordered_datetimes": _ordered_datetimes,
    "parseable_datetime": _parseable_datetime,
    "peru_ruc": _peru_ruc,
    "required_columns": _required_columns,
    "required_tables": _required_tables,
    "root_references": _root_references,
}


def evaluate_rule(
    rule: dict[str, Any], tables: dict[str, pd.DataFrame]
) -> dict[str, Any]:
    """Evaluate one configured rule and return a normalized result."""

    invalid_rows, rows_evaluated, details = EVALUATORS[rule["type"]](rule, tables)
    invalid_pct = (invalid_rows / rows_evaluated * 100) if rows_evaluated else 0.0
    passed = _threshold_passed(rule["threshold"], invalid_rows, rows_evaluated)
    return {
        "rule_id": rule["rule_id"],
        "name": rule["name"],
        "dimension": rule["dimension"],
        "type": rule["type"],
        "severity": rule["severity"],
        "status": "PASS" if passed else "FAIL",
        "rows_evaluated": rows_evaluated,
        "invalid_rows": invalid_rows,
        "invalid_pct": round(invalid_pct, 4),
        "threshold": rule["threshold"],
        "description": rule["description"],
        "details": details,
        "post_treatment": {
            "status": "NOT_EVALUATED",
            "reason": "No transformations are applied during Phase 4.",
        },
    }


def evaluate_archive(
    archive_path: Path, config_path: Path, source_period: str, snapshot_date: str
) -> dict[str, Any]:
    """Evaluate every rule and summarize promotion eligibility."""

    started = time.perf_counter()
    config = load_quality_config(config_path)
    tables, encodings = read_archive(archive_path)
    results = [evaluate_rule(rule, tables) for rule in config["rules"]]
    blocking_severities = set(config["framework"]["blocking_severities"])
    failures = [result for result in results if result["status"] == "FAIL"]
    blocking_failures = [
        result for result in failures if result["severity"] in blocking_severities
    ]
    warning_failures = [
        result for result in failures if result["severity"] == "warning"
    ]
    if blocking_failures:
        overall_status = "BLOCKED"
    elif warning_failures:
        overall_status = "PASS_WITH_WARNINGS"
    else:
        overall_status = "PASS"
    return {
        "schema_version": "1.0",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "source_id": config["framework"]["source_id"],
            "source_period": source_period,
            "snapshot_date": snapshot_date,
            "archive_filename": archive_path.name,
            "archive_size_bytes": archive_path.stat().st_size,
            "archive_sha256": sha256_file(archive_path),
            "rule_config": str(config_path),
            "rule_config_sha256": sha256_text_file(config_path),
        },
        "summary": {
            "overall_status": overall_status,
            "promotion_eligible": not blocking_failures,
            "rule_count": len(results),
            "passed_rules": len(results) - len(failures),
            "failed_rules": len(failures),
            "blocking_failures": len(blocking_failures),
            "warning_failures": len(warning_failures),
            "tables_evaluated": len(tables),
            "rows_across_tables": sum(len(dataframe) for dataframe in tables.values()),
            "duration_seconds": round(time.perf_counter() - started, 4),
        },
        "table_encodings": encodings,
        "results": results,
    }


def repository_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Remove volatile/local fields while retaining auditable rule evidence."""

    summary = dict(report["summary"])
    summary.pop("duration_seconds", None)
    source = dict(report["source"])
    source["rule_config"] = Path(source["rule_config"]).as_posix()
    return {
        "schema_version": report["schema_version"],
        "source": source,
        "summary": summary,
        "results": report["results"],
    }


def write_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--rules", type=Path, default=Path("config/data_quality_rules.yml")
    )
    parser.add_argument("--source-period", required=True)
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate_archive(
        args.archive, args.rules, args.source_period, args.snapshot_date
    )
    write_json(report, args.output)
    if args.summary_output:
        write_json(repository_summary(report), args.summary_output)
    summary = report["summary"]
    print(
        f"Data quality {summary['overall_status']}: "
        f"{summary['passed_rules']}/{summary['rule_count']} rules passed; "
        f"{summary['blocking_failures']} blocking failures."
    )


if __name__ == "__main__":
    main()
