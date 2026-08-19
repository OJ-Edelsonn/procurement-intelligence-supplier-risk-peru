from __future__ import annotations

from zipfile import ZIP_DEFLATED, ZipFile

from procurement_intelligence.profiling.profile_ocds_csv import profile_archive


def test_profile_archive_reports_structure_and_quality(tmp_path) -> None:
    archive_path = tmp_path / "sample.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "records.csv",
            "ocid,compiledRelease/id,buyer,value\n"
            "ocds-1,release-1,Buyer A,10\n"
            "ocds-2,release-2,,20\n"
            "ocds-2,release-2,,20\n",
        )
        archive.writestr(
            "parties.csv",
            "ocid,compiledRelease/id,party_id\n"
            "ocds-1,release-1,p-1\n"
            "ocds-2,release-2,p-2\n",
        )

    profile = profile_archive(archive_path)

    assert profile["summary"]["table_count"] == 2
    assert profile["summary"]["total_rows_across_tables"] == 5
    assert profile["summary"]["profiling_duration_seconds"] >= 0
    assert profile["referential_integrity"]["all_checks_passed"] is True
    assert all(
        check["missing_parent_rows"] == 0
        for check in profile["referential_integrity"]["checks"]
    )
    records = next(
        table for table in profile["tables"] if table["table"] == "records.csv"
    )
    assert records["row_count"] == 3
    assert records["column_count"] == 4
    assert records["duplicate_rows"] == 1
    assert records["candidate_grain"]["duplicate_key_rows"] == 1
    assert records["candidate_grain"]["is_unique_and_complete"] is False
    assert records["key_profiles"]["ocid"]["distinct_count"] == 2
    buyer = next(column for column in records["columns"] if column["name"] == "buyer")
    assert buyer["null_count"] == 2
