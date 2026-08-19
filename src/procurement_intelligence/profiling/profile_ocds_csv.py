"""Profile the relational CSV tables contained in an OECE OCDS archive."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile, ZipInfo

import pandas as pd

from procurement_intelligence.extraction.download_ocds import sha256_file

KEY_COLUMNS = {
    "ocid",
    "compiledRelease/id",
    "release/id",
    "id",
}

CANDIDATE_GRAINS = {
    "records.csv": ["ocid"],
    "releases.csv": ["ocid", "releases/0/details/id"],
    "com_sources.csv": ["ocid", "compiledRelease/sources/0/id"],
    "com_parties.csv": ["ocid", "compiledRelease/parties/0/id"],
    "com_par_additionalIdentifiers.csv": [
        "ocid",
        "compiledRelease/parties/0/id",
        "compiledRelease/parties/0/additionalIdentifiers/0/id",
        "compiledRelease/parties/0/additionalIdentifiers/0/scheme",
    ],
    "com_ten_tenderers.csv": [
        "ocid",
        "compiledRelease/tender/tenderers/0/id",
    ],
    "com_ten_documents.csv": ["ocid", "compiledRelease/tender/documents/0/id"],
    "com_ten_items.csv": ["ocid", "compiledRelease/tender/items/0/id"],
    "com_ten_ite_additionalClassific.csv": [
        "ocid",
        "compiledRelease/tender/items/0/id",
        "compiledRelease/tender/items/0/additionalClassifications/0/id",
    ],
    "com_ten_ite_tot_exchangeRates.csv": [
        "ocid",
        "compiledRelease/tender/items/0/id",
        "compiledRelease/tender/items/0/totalValue/exchangeRates/0/currency",
    ],
    "com_awards.csv": ["ocid", "compiledRelease/awards/0/id"],
    "com_awa_suppliers.csv": [
        "ocid",
        "compiledRelease/awards/0/id",
        "compiledRelease/awards/0/suppliers/0/id",
    ],
    "com_awa_items.csv": [
        "ocid",
        "compiledRelease/awards/0/id",
        "compiledRelease/awards/0/items/0/id",
    ],
    "com_awa_ite_additionalClassific.csv": [
        "ocid",
        "compiledRelease/awards/0/id",
        "compiledRelease/awards/0/items/0/id",
        "compiledRelease/awards/0/items/0/additionalClassifications/0/id",
    ],
    "com_awa_ite_tot_exchangeRates.csv": [
        "ocid",
        "compiledRelease/awards/0/id",
        "compiledRelease/awards/0/items/0/id",
        "compiledRelease/awards/0/items/0/totalValue/exchangeRates/0/currency",
    ],
    "com_awa_val_exchangeRates.csv": [
        "ocid",
        "compiledRelease/awards/0/id",
        "compiledRelease/awards/0/value/exchangeRates/0/currency",
    ],
    "com_contracts.csv": ["ocid", "compiledRelease/contracts/0/id"],
    "com_con_documents.csv": [
        "ocid",
        "compiledRelease/contracts/0/id",
        "compiledRelease/contracts/0/documents/0/id",
    ],
    "com_con_items.csv": [
        "ocid",
        "compiledRelease/contracts/0/id",
        "compiledRelease/contracts/0/items/0/id",
    ],
    "com_con_ite_additionalClassific.csv": [
        "ocid",
        "compiledRelease/contracts/0/id",
        "compiledRelease/contracts/0/items/0/id",
        "compiledRelease/contracts/0/items/0/additionalClassifications/0/id",
    ],
    "com_con_ite_tot_exchangeRates.csv": [
        "ocid",
        "compiledRelease/contracts/0/id",
        "compiledRelease/contracts/0/items/0/id",
        "compiledRelease/contracts/0/items/0/totalValue/exchangeRates/0/currency",
    ],
    "com_con_val_exchangeRates.csv": [
        "ocid",
        "compiledRelease/contracts/0/id",
        "compiledRelease/contracts/0/value/exchangeRates/0/currency",
    ],
}


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


def _column_profile(series: pd.Series) -> dict[str, Any]:
    row_count = len(series)
    null_count = int(series.isna().sum())
    non_null_count = row_count - null_count
    distinct_count = int(series.nunique(dropna=True))
    return {
        "name": str(series.name),
        "pandas_dtype": str(series.dtype),
        "null_count": null_count,
        "null_pct": round((null_count / row_count * 100) if row_count else 0.0, 4),
        "non_null_count": non_null_count,
        "distinct_count": distinct_count,
        "distinct_pct_of_non_null": round(
            (distinct_count / non_null_count * 100) if non_null_count else 0.0,
            4,
        ),
    }


def _key_profile(dataframe: pd.DataFrame, column: str) -> dict[str, Any]:
    series = dataframe[column]
    non_null = series.dropna()
    distinct_count = int(non_null.nunique())
    return {
        "null_count": int(series.isna().sum()),
        "distinct_count": distinct_count,
        "duplicate_non_null_count": int(len(non_null) - distinct_count),
        "is_unique_and_complete": bool(
            len(series) > 0 and len(non_null) == len(series) and non_null.is_unique
        ),
    }


def _candidate_grain_profile(
    dataframe: pd.DataFrame,
    table_name: str,
) -> dict[str, Any] | None:
    columns = CANDIDATE_GRAINS.get(table_name)
    if not columns:
        return None
    missing_columns = [column for column in columns if column not in dataframe.columns]
    if missing_columns:
        return {
            "columns": columns,
            "missing_columns": missing_columns,
            "null_key_rows": None,
            "duplicate_key_rows": None,
            "is_unique_and_complete": False,
        }

    null_key_rows = int(dataframe[columns].isna().any(axis=1).sum())
    duplicate_key_rows = int(dataframe.duplicated(subset=columns).sum())
    return {
        "columns": columns,
        "missing_columns": [],
        "null_key_rows": null_key_rows,
        "duplicate_key_rows": duplicate_key_rows,
        "is_unique_and_complete": bool(
            len(dataframe) > 0 and null_key_rows == 0 and duplicate_key_rows == 0
        ),
    }


def profile_member(archive: ZipFile, member: ZipInfo) -> dict[str, Any]:
    """Read one CSV member and calculate reproducible structural quality metrics."""

    encoding = _detect_encoding(archive, member)
    with archive.open(member) as source_file:
        dataframe = pd.read_csv(
            source_file,
            encoding=encoding,
            sep=",",
            low_memory=False,
        )

    dataframe.columns = [str(column) for column in dataframe.columns]
    row_count, column_count = dataframe.shape
    null_cells = int(dataframe.isna().sum().sum())
    total_cells = int(row_count * column_count)
    duplicate_rows = int(dataframe.duplicated().sum())
    empty_rows = int(dataframe.isna().all(axis=1).sum())
    available_key_columns = [
        column for column in dataframe.columns if column in KEY_COLUMNS
    ]

    return {
        "table": member.filename,
        "uncompressed_size_bytes": member.file_size,
        "encoding": encoding,
        "row_count": int(row_count),
        "column_count": int(column_count),
        "total_cells": total_cells,
        "null_cells": null_cells,
        "null_pct": round((null_cells / total_cells * 100) if total_cells else 0.0, 4),
        "duplicate_rows": duplicate_rows,
        "duplicate_row_pct": round(
            (duplicate_rows / row_count * 100) if row_count else 0.0,
            4,
        ),
        "empty_rows": empty_rows,
        "memory_usage_bytes": int(dataframe.memory_usage(index=True, deep=True).sum()),
        "key_profiles": {
            column: _key_profile(dataframe, column)
            for column in available_key_columns
        },
        "candidate_grain": _candidate_grain_profile(dataframe, member.filename),
        "columns": [_column_profile(dataframe[column]) for column in dataframe.columns],
    }


def _read_string_column(
    archive: ZipFile,
    member: ZipInfo,
    column: str,
) -> pd.Series:
    encoding = _detect_encoding(archive, member)
    with archive.open(member) as source_file:
        dataframe = pd.read_csv(
            source_file,
            encoding=encoding,
            sep=",",
            usecols=[column],
            dtype="string",
        )
    return dataframe[column]


def _referential_integrity_profile(
    archive: ZipFile,
    members: list[ZipInfo],
    table_profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    members_by_name = {member.filename: member for member in members}
    root_member = members_by_name.get("records.csv")
    if root_member is None:
        return {
            "root_table": None,
            "all_checks_passed": False,
            "checks": [],
            "note": "records.csv was not found; child-to-root checks were not possible.",
        }

    root_values = {
        key: set(_read_string_column(archive, root_member, key).dropna())
        for key in ("ocid", "compiledRelease/id")
    }
    checks: list[dict[str, Any]] = []
    for table_profile in table_profiles:
        table_name = table_profile["table"]
        if table_name == "records.csv":
            continue
        member = members_by_name[table_name]
        for key in ("ocid", "compiledRelease/id"):
            if key not in table_profile["key_profiles"]:
                continue
            values = _read_string_column(archive, member, key)
            non_null = values.dropna()
            missing = non_null[~non_null.isin(root_values[key])]
            checks.append(
                {
                    "child_table": table_name,
                    "child_column": key,
                    "parent_table": "records.csv",
                    "parent_column": key,
                    "child_non_null_rows": int(len(non_null)),
                    "missing_parent_rows": int(len(missing)),
                    "missing_parent_distinct_values": int(missing.nunique()),
                    "passed": bool(missing.empty),
                }
            )

    return {
        "root_table": "records.csv",
        "all_checks_passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def profile_archive(archive_path: Path) -> dict[str, Any]:
    """Profile every CSV table in an official archive."""

    started = time.perf_counter()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)

    with ZipFile(archive_path) as archive:
        members = sorted(
            (
                member
                for member in archive.infolist()
                if not member.is_dir() and member.filename.lower().endswith(".csv")
            ),
            key=lambda member: member.filename,
        )
        if not members:
            raise ValueError("The archive does not contain CSV tables.")
        table_profiles = [profile_member(archive, member) for member in members]
        referential_integrity = _referential_integrity_profile(
            archive, members, table_profiles
        )

    total_rows = sum(table["row_count"] for table in table_profiles)
    total_cells = sum(table["total_cells"] for table in table_profiles)
    total_null_cells = sum(table["null_cells"] for table in table_profiles)
    total_duplicate_rows = sum(table["duplicate_rows"] for table in table_profiles)

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "publisher": "OECE",
            "archive_filename": archive_path.name,
            "archive_size_bytes": archive_path.stat().st_size,
            "archive_sha256": sha256_file(archive_path),
        },
        "summary": {
            "table_count": len(table_profiles),
            "total_rows_across_tables": total_rows,
            "total_cells": total_cells,
            "total_null_cells": total_null_cells,
            "overall_null_pct": round(
                (total_null_cells / total_cells * 100) if total_cells else 0.0,
                4,
            ),
            "total_duplicate_rows_within_tables": total_duplicate_rows,
            "total_uncompressed_size_bytes": sum(
                table["uncompressed_size_bytes"] for table in table_profiles
            ),
            "estimated_dataframe_memory_bytes": sum(
                table["memory_usage_bytes"] for table in table_profiles
            ),
            "profiling_duration_seconds": round(time.perf_counter() - started, 4),
        },
        "referential_integrity": referential_integrity,
        "tables": table_profiles,
    }


def write_profile(profile: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def repository_summary(profile: dict[str, Any]) -> dict[str, Any]:
    """Create a compact, path-free profile suitable for version control."""

    return {
        "schema_version": profile["schema_version"],
        "generated_at_utc": profile["generated_at_utc"],
        "source": profile["source"],
        "summary": profile["summary"],
        "referential_integrity": profile["referential_integrity"],
        "tables": [
            {
                "table": table["table"],
                "row_count": table["row_count"],
                "column_count": table["column_count"],
                "null_cells": table["null_cells"],
                "null_pct": table["null_pct"],
                "duplicate_rows": table["duplicate_rows"],
                "duplicate_row_pct": table["duplicate_row_pct"],
                "key_profiles": table["key_profiles"],
                "candidate_grain": table["candidate_grain"],
            }
            for table in profile["tables"]
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile all CSV tables in one OECE OCDS ZIP archive."
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = profile_archive(args.archive)
    write_profile(profile, args.output)
    if args.summary_output:
        write_profile(repository_summary(profile), args.summary_output)
    print(json.dumps(profile["summary"], ensure_ascii=False, indent=2))
    print(f"Profile: {args.output}")
    if args.summary_output:
        print(f"Summary: {args.summary_output}")


if __name__ == "__main__":
    main()
