"""Download immutable monthly OCDS snapshots from the official OECE portal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import requests

from procurement_intelligence.settings import Settings, load_settings

BASE_URL = "https://contratacionesabiertas.oece.gob.pe/api/v1/file"
USER_AGENT = "procurement-intelligence-supplier-risk-peru/0.1"
SUPPORTED_SOURCES = {"seace_v2", "seace_v3"}
SUPPORTED_FORMATS = {"csv", "xlsx", "json"}


@dataclass(frozen=True)
class DownloadedFile:
    """Auditable result for one source file."""

    url: str
    local_path: str
    status: str
    size_bytes: int
    sha256: str
    content_type: str | None
    content_disposition: str | None
    last_modified: str | None
    etag: str | None
    elapsed_seconds: float


def build_file_url(
    source: str,
    file_format: str,
    year: int,
    month: int,
    language: str | None = None,
) -> str:
    """Build a documented OECE monthly file endpoint."""

    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    if file_format not in SUPPORTED_FORMATS | {"sha"}:
        raise ValueError(f"Unsupported format: {file_format}")
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if year < 2000:
        raise ValueError("year must be 2000 or later")
    if language not in {None, "es"}:
        raise ValueError("language must be omitted or 'es'")
    if language and file_format in {"json", "sha"}:
        raise ValueError(f"Language variant is not available for {file_format}")

    url = f"{BASE_URL}/{source}/{file_format}/{year}/{month:02d}"
    return f"{url}/{language}" if language else url


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a SHA-256 digest without loading the full file in memory."""

    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text_file(path: Path) -> str:
    """Hash UTF-8 text with LF newlines for cross-platform reproducibility."""

    normalized = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace(
        "\r", "\n"
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sha256_single_zip_member(
    archive_path: Path,
    expected_suffix: str,
    chunk_size: int = 1024 * 1024,
) -> tuple[str, str, int]:
    """Hash the uncompressed payload when an archive contains one target member."""

    with ZipFile(archive_path) as archive:
        matching_members = [
            member
            for member in archive.infolist()
            if not member.is_dir() and member.filename.lower().endswith(expected_suffix)
        ]
        if len(matching_members) != 1:
            raise ValueError(
                f"Expected one {expected_suffix} member, found {len(matching_members)}."
            )

        member = matching_members[0]
        digest = hashlib.sha256()
        with archive.open(member) as source_file:
            for chunk in iter(lambda: source_file.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest(), member.filename, member.file_size


def _existing_file_result(url: str, destination: Path) -> DownloadedFile:
    started = time.perf_counter()
    file_sha256 = sha256_file(destination)
    return DownloadedFile(
        url=url,
        local_path=str(destination),
        status="reused",
        size_bytes=destination.stat().st_size,
        sha256=file_sha256,
        content_type=None,
        content_disposition=None,
        last_modified=None,
        etag=None,
        elapsed_seconds=round(time.perf_counter() - started, 4),
    )


def download_file(
    url: str,
    destination: Path,
    timeout_seconds: int = 120,
) -> DownloadedFile:
    """Stream a file atomically; reuse but never overwrite an existing RAW file."""

    if destination.exists():
        return _existing_file_result(url, destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f"{destination.name}.part")
    temporary.unlink(missing_ok=True)
    digest = hashlib.sha256()
    size_bytes = 0
    started = time.perf_counter()

    try:
        with requests.get(
            url,
            stream=True,
            timeout=timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        ) as response:
            response.raise_for_status()
            with temporary.open("xb") as target_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    target_file.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)

            os.replace(temporary, destination)
            return DownloadedFile(
                url=url,
                local_path=str(destination),
                status="downloaded",
                size_bytes=size_bytes,
                sha256=digest.hexdigest(),
                content_type=response.headers.get("content-type"),
                content_disposition=response.headers.get("content-disposition"),
                last_modified=response.headers.get("last-modified"),
                etag=response.headers.get("etag"),
                elapsed_seconds=round(time.perf_counter() - started, 4),
            )
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _snapshot_directory(
    settings: Settings,
    source: str,
    year: int,
    month: int,
    snapshot_date: date,
) -> Path:
    return (
        settings.raw_root
        / "oece"
        / "ocds"
        / source
        / str(year)
        / f"{month:02d}"
        / f"snapshot_date={snapshot_date.isoformat()}"
    )


def _metadata_directory(
    settings: Settings,
    source: str,
    year: int,
    month: int,
    snapshot_date: date,
) -> Path:
    return (
        settings.metadata_root
        / "oece"
        / "ocds"
        / source
        / str(year)
        / f"{month:02d}"
        / f"snapshot_date={snapshot_date.isoformat()}"
    )


def download_snapshot(
    settings: Settings,
    source: str,
    file_format: str,
    year: int,
    month: int,
    snapshot_date: date,
    language: str | None = None,
) -> dict[str, Any]:
    """Download a monthly archive plus its publisher checksum and write a manifest."""

    suffix = f"_{language}" if language else ""
    archive_name = f"{year}-{month:02d}_{source}_{file_format}{suffix}.zip"
    sha_name = f"{year}-{month:02d}_{source}.sha"
    raw_directory = _snapshot_directory(settings, source, year, month, snapshot_date)

    archive = download_file(
        build_file_url(source, file_format, year, month, language),
        raw_directory / archive_name,
    )
    checksum = download_file(
        build_file_url(source, "sha", year, month),
        raw_directory / sha_name,
    )

    expected_sha256 = Path(checksum.local_path).read_text(encoding="ascii").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("The publisher checksum is not a 64-character SHA-256 digest.")

    publisher_verification: dict[str, Any]
    if file_format == "json":
        payload_sha256, payload_member, payload_size = sha256_single_zip_member(
            Path(archive.local_path), ".json"
        )
        checksum_verified: bool | None = payload_sha256 == expected_sha256
        publisher_verification = {
            "scope": "uncompressed_json_payload",
            "member": payload_member,
            "size_bytes": payload_size,
            "calculated_sha256": payload_sha256,
            "verified": checksum_verified,
        }
        if not checksum_verified:
            raise ValueError(
                "Publisher SHA-256 verification failed for the JSON payload. "
                "RAW files were preserved for investigation."
            )
    else:
        checksum_verified = None
        publisher_verification = {
            "scope": "uncompressed_json_payload",
            "member": None,
            "size_bytes": None,
            "calculated_sha256": None,
            "verified": None,
            "note": (
                "The OECE .sha digest applies to the uncompressed canonical JSON "
                "payload and cannot directly verify this archive format."
            ),
        }

    manifest = {
        "schema_version": "1.0",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "publisher": "Organismo Especializado para las Contrataciones Públicas Eficientes (OECE)",
        "source": source,
        "year": year,
        "month": month,
        "snapshot_date": snapshot_date.isoformat(),
        "format": file_format,
        "language": language,
        "archive": asdict(archive),
        "publisher_checksum": asdict(checksum),
        "expected_sha256": expected_sha256,
        "checksum_verified": checksum_verified,
        "publisher_verification": publisher_verification,
    }
    metadata_directory = _metadata_directory(
        settings, source, year, month, snapshot_date
    )
    metadata_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = metadata_directory / f"download_manifest_{file_format}{suffix}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and verify one immutable OECE OCDS monthly snapshot."
    )
    parser.add_argument("--source", default="seace_v3", choices=sorted(SUPPORTED_SOURCES))
    parser.add_argument("--format", default="csv", choices=sorted(SUPPORTED_FORMATS))
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--snapshot-date", type=date.fromisoformat, required=True)
    parser.add_argument("--language", choices=["es"])
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = download_snapshot(
        settings=load_settings(args.env_file),
        source=args.source,
        file_format=args.format,
        year=args.year,
        month=args.month,
        snapshot_date=args.snapshot_date,
        language=args.language,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
