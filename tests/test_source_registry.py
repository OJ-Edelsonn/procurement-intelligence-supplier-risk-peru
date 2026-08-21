from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from procurement_intelligence.documentation.source_registry import (
    collect_verifiable_urls,
    load_registry,
    render_registry,
    validate_registry,
)

REGISTRY_PATH = Path("config/source_registry.yml")
DOCUMENT_PATH = Path("docs/data_sources/source_registry.md")


def test_source_registry_is_valid_and_has_pilot_evidence() -> None:
    registry = load_registry(REGISTRY_PATH)
    source_ids = {source["source_id"] for source in registry["sources"]}

    assert "oece_ocds_seace_v3_bulk" in source_ids
    assert "project_github_repository" in source_ids
    assert len(registry["acquisition_events"]) == 1
    assert registry["acquisition_events"][0]["status"] == "verified"
    assert registry["acquisition_events"][0]["silver_etl_evidence"][
        "promotion_eligible"
    ] is True
    assert registry["registry"]["last_automated_link_check"]["passed"] == 20


def test_generated_document_matches_registry() -> None:
    registry = load_registry(REGISTRY_PATH)

    assert DOCUMENT_PATH.read_text(encoding="utf-8") == render_registry(registry)


def test_verifiable_urls_include_official_pages_and_acquisition_endpoints() -> None:
    registry = load_registry(REGISTRY_PATH)
    urls = {url for _, url in collect_verifiable_urls(registry)}

    assert "https://contratacionesabiertas.oece.gob.pe/descargas" in urls
    assert (
        "https://contratacionesabiertas.oece.gob.pe/api/v1/file/"
        "seace_v3/csv/2026/07"
    ) in urls
    assert all(url.startswith("https://") for url in urls)


def test_candidate_source_cannot_be_marked_as_used() -> None:
    registry = deepcopy(load_registry(REGISTRY_PATH))
    candidate = next(
        source
        for source in registry["sources"]
        if source["status"] == "candidate_not_ingested"
    )
    candidate["used_in_project"] = True

    with pytest.raises(ValueError, match="cannot be candidate and used"):
        validate_registry(registry)


def test_acquisition_requires_valid_sha256() -> None:
    registry = deepcopy(load_registry(REGISTRY_PATH))
    registry["acquisition_events"][0]["evidence"][0]["sha256_local_file"] = "bad"

    with pytest.raises(ValueError, match="invalid local SHA-256"):
        validate_registry(registry)
