from __future__ import annotations

import hashlib
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from procurement_intelligence.extraction.download_ocds import (
    build_file_url,
    download_file,
    sha256_file,
    sha256_single_zip_member,
)


def test_build_file_url_for_official_monthly_csv() -> None:
    assert build_file_url("seace_v3", "csv", 2026, 7) == (
        "https://contratacionesabiertas.oece.gob.pe/"
        "api/v1/file/seace_v3/csv/2026/07"
    )


def test_build_file_url_rejects_invalid_month() -> None:
    with pytest.raises(ValueError, match="month"):
        build_file_url("seace_v3", "csv", 2026, 13)


def test_sha256_file(tmp_path) -> None:
    source = tmp_path / "sample.bin"
    source.write_bytes(b"official-source-sample")
    assert sha256_file(source) == hashlib.sha256(source.read_bytes()).hexdigest()


def test_download_file_reuses_existing_raw_file(tmp_path) -> None:
    destination = tmp_path / "snapshot.zip"
    destination.write_bytes(b"immutable")

    result = download_file("https://example.invalid/snapshot.zip", destination)

    assert result.status == "reused"
    assert result.size_bytes == len(b"immutable")
    assert result.elapsed_seconds >= 0
    assert destination.read_bytes() == b"immutable"


def test_sha256_single_zip_member_hashes_uncompressed_payload(tmp_path) -> None:
    archive_path = tmp_path / "snapshot.zip"
    payload = b'{"releases": []}'
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("snapshot.json", payload)

    digest, member_name, size_bytes = sha256_single_zip_member(
        archive_path, ".json"
    )

    assert digest == hashlib.sha256(payload).hexdigest()
    assert member_name == "snapshot.json"
    assert size_bytes == len(payload)
