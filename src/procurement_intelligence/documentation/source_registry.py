"""Validate and render the governed registry of data sources."""

from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

ALLOWED_STATUSES = {"active_used", "reference_only", "candidate_not_ingested"}
ALLOWED_LINK_RESULTS = {"PASS", "PARTIAL", "FAIL"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
USER_AGENT = "procurement-intelligence-source-audit/0.1"


def load_registry(path: Path) -> dict[str, Any]:
    """Load a YAML source registry and validate its structure."""

    with path.open(encoding="utf-8") as registry_file:
        registry = yaml.safe_load(registry_file)
    validate_registry(registry)
    return registry


def _require_text(mapping: dict[str, Any], field: str, context: str) -> None:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{field} must be non-empty text")


def _validate_urls(urls: dict[str, Any], context: str) -> None:
    if not isinstance(urls, dict) or not urls:
        raise ValueError(f"{context} must contain at least one URL")
    for label, url in urls.items():
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(f"{context}.{label} must be an HTTPS URL")


def validate_registry(data: dict[str, Any]) -> None:
    """Fail fast when provenance fields are missing or contradictory."""

    if not isinstance(data, dict):
        raise ValueError("registry root must be a mapping")
    metadata = data.get("registry")
    sources = data.get("sources")
    events = data.get("acquisition_events")
    if not isinstance(metadata, dict):
        raise ValueError("registry metadata must be a mapping")
    for field in ("schema_version", "title", "owner", "repository"):
        _require_text(metadata, field, "registry")
    link_check = metadata.get("last_automated_link_check")
    if not isinstance(link_check, dict):
        raise ValueError("registry.last_automated_link_check must be a mapping")
    for field in ("method", "result"):
        _require_text(link_check, field, "registry.last_automated_link_check")
    if link_check["result"] not in ALLOWED_LINK_RESULTS:
        raise ValueError("registry.last_automated_link_check.result is invalid")
    if not all(
        isinstance(link_check.get(field), int) and link_check[field] >= 0
        for field in ("passed", "total")
    ):
        raise ValueError("registry.last_automated_link_check counts are invalid")
    if link_check["passed"] > link_check["total"]:
        raise ValueError("registry.last_automated_link_check passed exceeds total")
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources must be a non-empty list")
    if not isinstance(events, list):
        raise ValueError("acquisition_events must be a list")

    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("each source must be a mapping")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise ValueError(f"invalid source_id: {source_id!r}")
        if source_id in source_ids:
            raise ValueError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        context = f"source[{source_id}]"
        for field in (
            "name",
            "publisher",
            "authority",
            "category",
            "status",
            "purpose",
            "access_method",
            "update_frequency",
            "license_or_terms",
        ):
            _require_text(source, field, context)
        if source["status"] not in ALLOWED_STATUSES:
            raise ValueError(f"{context}.status is not allowed")
        if not isinstance(source.get("used_in_project"), bool):
            raise ValueError(f"{context}.used_in_project must be boolean")
        if source["status"] == "candidate_not_ingested" and source["used_in_project"]:
            raise ValueError(f"{context} cannot be candidate and used")
        _validate_urls(source.get("official_urls"), f"{context}.official_urls")
        verification = source.get("last_link_verification")
        if not isinstance(verification, dict):
            raise ValueError(f"{context}.last_link_verification must be a mapping")
        if verification.get("result") not in ALLOWED_LINK_RESULTS:
            raise ValueError(f"{context}.last_link_verification.result is invalid")

    acquisition_ids: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("each acquisition event must be a mapping")
        acquisition_id = event.get("acquisition_id")
        if not isinstance(acquisition_id, str) or not SOURCE_ID_PATTERN.fullmatch(
            acquisition_id
        ):
            raise ValueError(f"invalid acquisition_id: {acquisition_id!r}")
        if acquisition_id in acquisition_ids:
            raise ValueError(f"duplicate acquisition_id: {acquisition_id}")
        acquisition_ids.add(acquisition_id)
        if event.get("source_id") not in source_ids:
            raise ValueError(f"{acquisition_id} references an unknown source")
        evidence = event.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"{acquisition_id} must contain evidence")
        for artifact in evidence:
            _require_text(artifact, "artifact", f"event[{acquisition_id}].evidence")
            _require_text(artifact, "format", f"event[{acquisition_id}].evidence")
            if not isinstance(artifact.get("size_bytes"), int) or artifact["size_bytes"] <= 0:
                raise ValueError(f"{acquisition_id} artifact size must be positive")
            if not SHA256_PATTERN.fullmatch(str(artifact.get("sha256_local_file", ""))):
                raise ValueError(f"{acquisition_id} has an invalid local SHA-256")
            _validate_urls({"url": artifact.get("url")}, f"event[{acquisition_id}]")
            publisher_sha = artifact.get("publisher_sha256_uncompressed_payload")
            if publisher_sha is not None and not SHA256_PATTERN.fullmatch(
                str(publisher_sha)
            ):
                raise ValueError(f"{acquisition_id} has an invalid publisher SHA-256")
        for block_name, integer_fields in (
            (
                "data_quality_evidence",
                ("rules", "rules_passed", "rules_failed", "blocking_failures"),
            ),
            (
                "silver_etl_evidence",
                (
                    "tables",
                    "raw_rows",
                    "silver_rows",
                    "quarantine_rows",
                    "classification_rows_normalized",
                ),
            ),
        ):
            block = event.get(block_name)
            if block is None:
                continue
            if not isinstance(block, dict):
                raise ValueError(f"{acquisition_id}.{block_name} must be a mapping")
            for field in ("report", "status"):
                _require_text(block, field, f"event[{acquisition_id}].{block_name}")
            for field in integer_fields:
                if not isinstance(block.get(field), int) or block[field] < 0:
                    raise ValueError(
                        f"{acquisition_id}.{block_name}.{field} must be non-negative"
                    )
        silver = event.get("silver_etl_evidence")
        if silver is not None:
            _require_text(
                silver, "config", f"event[{acquisition_id}].silver_etl_evidence"
            )
            if not isinstance(silver.get("promotion_eligible"), bool):
                raise ValueError(
                    f"{acquisition_id}.silver_etl_evidence.promotion_eligible "
                    "must be boolean"
                )
            if silver["raw_rows"] != silver["silver_rows"] + silver["quarantine_rows"]:
                raise ValueError(
                    f"{acquisition_id}.silver_etl_evidence row reconciliation failed"
                )
        quality = event.get("data_quality_evidence")
        if quality is not None and quality["rules"] != (
            quality["rules_passed"] + quality["rules_failed"]
        ):
            raise ValueError(
                f"{acquisition_id}.data_quality_evidence rule reconciliation failed"
            )


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _bullets(values: Iterable[str]) -> list[str]:
    return [f"- {value}" for value in values]


def collect_verifiable_urls(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Return unique concrete URLs from source cards and acquisition evidence."""

    validate_registry(data)
    urls: dict[str, str] = {}
    for source in data["sources"]:
        for label, url in source["official_urls"].items():
            urls.setdefault(url, f"{source['source_id']}.{label}")
    for event in data["acquisition_events"]:
        for artifact in event["evidence"]:
            urls.setdefault(
                artifact["url"], f"{event['acquisition_id']}.{artifact['artifact']}"
            )
    return sorted(((context, url) for url, context in urls.items()), key=lambda row: row[0])


def check_links(
    data: dict[str, Any], timeout_seconds: float = 30, max_workers: int = 6
) -> list[dict[str, Any]]:
    """Check concrete registry URLs without downloading response bodies."""

    def check_one(context: str, url: str) -> dict[str, Any]:
        try:
            with requests.get(
                url,
                stream=True,
                timeout=timeout_seconds,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as response:
                return {
                    "context": context,
                    "url": url,
                    "status_code": response.status_code,
                    "final_url": response.url,
                    "passed": 200 <= response.status_code < 400,
                    "error": None,
                }
        except requests.RequestException as exc:
            return {
                "context": context,
                "url": url,
                "status_code": None,
                "final_url": None,
                "passed": False,
                "error": type(exc).__name__,
            }

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_one, context, url): (context, url)
            for context, url in collect_verifiable_urls(data)
        }
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda result: result["context"])


def render_registry(data: dict[str, Any]) -> str:
    """Render a deterministic, review-friendly Markdown document."""

    validate_registry(data)
    metadata = data["registry"]
    link_check = metadata["last_automated_link_check"]
    sources = data["sources"]
    events = data["acquisition_events"]
    lines = [
        "# Registro maestro de fuentes y trazabilidad",
        "",
        "> Documento generado desde `config/source_registry.yml`. No editar manualmente.",
        "",
        "## Control del documento",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Versión del esquema | {metadata['schema_version']} |",
        f"| Última revisión | {metadata['last_reviewed']} |",
        f"| Responsable | {metadata['owner']} |",
        f"| Repositorio | <{metadata['repository']}> |",
        f"| Último control automático de enlaces | {link_check['result']} el "
        f"{link_check['date']}; {link_check['passed']}/{link_check['total']} "
        f"mediante {link_check['method']} |",
        "",
        "## Política de uso",
        "",
        *_bullets(metadata["policy"]),
        "",
        "## Estados",
        "",
        "| Estado | Significado |",
        "|---|---|",
        "| `active_used` | Fuente o repositorio utilizado y con trazabilidad activa. |",
        "| `reference_only` | Documentación consultada; no agrega observaciones al dataset. |",
        "| `candidate_not_ingested` | Fuente evaluada, pero aún no descargada ni integrada. |",
        "",
        "## Índice de fuentes",
        "",
        "| ID | Fuente | Publicador | Categoría | Estado | Usada |",
        "|---|---|---|---|---|---|",
    ]
    for source in sources:
        used = "Sí" if source["used_in_project"] else "No"
        lines.append(
            f"| `{source['source_id']}` | {source['name']} | {source['publisher']} | "
            f"`{source['category']}` | `{source['status']}` | {used} |"
        )

    for source in sources:
        verification = source["last_link_verification"]
        lines.extend(
            [
                "",
                f"## {source['name']}",
                "",
                f"- **ID:** `{source['source_id']}`",
                f"- **Publicador:** {source['publisher']}",
                f"- **Autoridad:** `{source['authority']}`",
                f"- **Estado:** `{source['status']}`",
                f"- **Propósito:** {source['purpose']}",
                "",
                "### Alcance",
                "",
                *_bullets(source["scope_and_coverage"]),
                "",
                "### Limitaciones",
                "",
                *_bullets(source["limitations"]),
                "",
                "### Enlaces oficiales",
                "",
            ]
        )
        for label, url in source["official_urls"].items():
            lines.append(f"- {_label(label)}: <{url}>")
        if source.get("endpoint_templates"):
            lines.extend(["", "### Endpoints documentados", ""])
            for label, url in source["endpoint_templates"].items():
                lines.append(f"- {_label(label)}: `{url}`")
        lines.extend(
            [
                "",
                f"- **Formatos:** {', '.join(source['formats'])}",
                f"- **Acceso:** {source['access_method']}",
                f"- **Actualización:** {source['update_frequency']}",
                f"- **Licencia/términos:** {source['license_or_terms']}",
                f"- **Verificación de enlaces:** {verification['result']} el "
                f"{verification['date']} mediante {verification['method']}.",
            ]
        )

    lines.extend(["", "## Evidencia de adquisiciones", ""])
    for event in events:
        lines.extend(
            [
                f"### {event['acquisition_id']}",
                "",
                "| Campo | Valor |",
                "|---|---|",
                f"| Fuente | `{event['source_id']}` |",
                f"| Periodo fuente | {event['source_period']} |",
                f"| Fecha de snapshot | {event['snapshot_date']} |",
                f"| Estado | `{event['status']}` |",
                f"| Ruta RAW | `{event['raw_path_pattern']}` |",
                f"| Ruta de metadatos | `{event['metadata_path_pattern']}` |",
                "",
                "| Artefacto | Formato | Bytes | SHA-256 local | URL oficial |",
                "|---|---|---:|---|---|",
            ]
        )
        for artifact in event["evidence"]:
            lines.append(
                f"| `{artifact['artifact']}` | {artifact['format']} | "
                f"{artifact['size_bytes']:,} | `{artifact['sha256_local_file']}` | "
                f"<{artifact['url']}> |"
            )
        verified = [
            artifact
            for artifact in event["evidence"]
            if artifact.get("publisher_checksum_applies")
        ]
        if verified:
            lines.extend(["", "**Checksum del publicador**", ""])
            for artifact in verified:
                result = "PASS" if artifact.get("publisher_checksum_verified") else "FAIL"
                lines.append(
                    f"- `{artifact['artifact']}`: {result}; SHA-256 del payload JSON "
                    f"descomprimido `{artifact['publisher_sha256_uncompressed_payload']}`; "
                    f"{artifact['uncompressed_payload_size_bytes']:,} bytes."
                )
        profile = event.get("profiling_evidence")
        if profile:
            lines.extend(
                [
                    "",
                    "**Evidencia de perfilado**",
                    "",
                    f"- Reporte: `{profile['report']}`",
                    f"- {profile['tables']:,} tablas; {profile['root_records']:,} records raíz; "
                    f"{profile['releases']:,} releases; {profile['rows_across_tables']:,} filas "
                    f"acumuladas; {profile['referential_checks_passed']:,} controles "
                    "referenciales aprobados.",
                ]
            )
        quality = event.get("data_quality_evidence")
        if quality:
            lines.extend(
                [
                    "",
                    "**Evidencia de Data Quality RAW**",
                    "",
                    f"- Reporte: `{quality['report']}`",
                    f"- Estado `{quality['status']}`; {quality['rules_passed']:,}/"
                    f"{quality['rules']:,} reglas aprobadas; "
                    f"{quality['rules_failed']:,} fallidas; "
                    f"{quality['blocking_failures']:,} fallo bloqueante.",
                ]
            )
        silver = event.get("silver_etl_evidence")
        if silver:
            eligible = "Sí" if silver["promotion_eligible"] else "No"
            lines.extend(
                [
                    "",
                    "**Evidencia de ETL Silver**",
                    "",
                    f"- Reporte: `{silver['report']}`",
                    f"- Contrato: `{silver['config']}`",
                    f"- Estado `{silver['status']}`; promoción elegible: {eligible}.",
                    f"- {silver['tables']:,} tablas; {silver['raw_rows']:,} filas RAW; "
                    f"{silver['silver_rows']:,} filas Silver; "
                    f"{silver['quarantine_rows']:,} filas en cuarentena; "
                    f"{silver['classification_rows_normalized']:,} clasificaciones "
                    "normalizadas como desconocidas.",
                ]
            )

    lines.extend(
        [
            "",
            "## Procedimiento para incorporar una fuente",
            "",
            "1. Añadir la ficha y sus URL oficiales a `config/source_registry.yml`.",
            "2. Mantenerla como `candidate_not_ingested` hasta descargar y validar un snapshot.",
            "3. Crear un evento de adquisición con periodo, fecha, tamaño, hash y rutas de evidencia.",
            "4. Ejecutar la validación y regenerar este documento.",
            "5. Revisar granularidad, cobertura, licencia y reconciliación antes de integrarla al modelo.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path, default=Path("config/source_registry.yml")
    )
    parser.add_argument(
        "--document",
        type=Path,
        default=Path("docs/data_sources/source_registry.md"),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed document differs from the registry.",
    )
    parser.add_argument(
        "--check-links",
        action="store_true",
        help="Verify concrete official and acquisition URLs over HTTPS.",
    )
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    registry = load_registry(args.registry)
    rendered = render_registry(registry)
    if args.check:
        if not args.document.exists() or args.document.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "The generated source registry is missing or stale. Regenerate it."
            )
        print(f"PASS: {args.document} matches {args.registry}")
    if args.check_links:
        results = check_links(registry, timeout_seconds=args.timeout)
        for result in results:
            status = result["status_code"] or result["error"]
            outcome = "PASS" if result["passed"] else "FAIL"
            print(f"{outcome}: {result['context']} [{status}] {result['url']}")
        failed = [result for result in results if not result["passed"]]
        print(
            f"Link summary: {len(results) - len(failed)}/{len(results)} passed, "
            f"{len(failed)} failed."
        )
        if failed:
            raise SystemExit("One or more registry links failed validation.")
    if args.check or args.check_links:
        return
    print(rendered, end="")


if __name__ == "__main__":
    main()
