# Procurement Intelligence & Supplier Risk — Perú

Solución end-to-end de Data/BI para analizar contratación pública peruana, inteligencia comercial y exposición a proveedores usando datos abiertos oficiales de OECE/SEACE.

> Estado: Fase 4 completada en el snapshot piloto: marco inicial de Data Quality, 17 reglas ejecutables y baseline antes del ETL. Todavía no se publican KPIs de negocio.

## Problema de negocio

Los datos de contratación pública están distribuidos en archivos y estructuras con granularidades distintas. El proyecto busca convertirlos en información trazable para responder, entre otras, estas preguntas:

- ¿Dónde se concentra la demanda pública por entidad, categoría, proveedor y periodo?
- ¿Qué proveedores o categorías presentan señales de concentración y dependencia?
- ¿Cómo cambian los montos y la competencia entre periodos comparables?
- ¿Qué oportunidades comerciales pueden priorizarse sin confundir procedimientos, contratos y órdenes?

## Alcance aprobado del MVP

- Universo principal: procedimientos publicados bajo OCDS.
- Periodo histórico completo: 2023–2025.
- Periodo YTD: enero–julio de 2026.
- Comparación interanual válida: enero–julio de 2025 frente a enero–julio de 2026.
- Fuente principal: portal de Contrataciones Abiertas de OECE.
- Fuentes XLSX complementarias: validación y análisis separados cuando la granularidad no sea compatible.
- Órdenes de compra/servicio y sanciones: módulos posteriores, sin mezclarlos prematuramente con el universo OCDS.

Los detalles y las exclusiones están en [docs/scope_and_limitations.md](docs/scope_and_limitations.md).

## Arquitectura objetivo

```text
OECE/SEACE -> RAW inmutable -> Python (calidad) -> Parquet tipado
           -> SQL Server stg/audit/dw -> Power BI (KPIs y narrativa)
           -> pruebas, documentación y trazabilidad en Git/GitHub
```

La especificación de capas, granos, linaje, modelo dimensional y puertas de calidad está en [docs/architecture/phase3_target_architecture.md](docs/architecture/phase3_target_architecture.md).

## Preparación local

Requisito: Python 3.11 de 64 bits.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

La activación es opcional si se invoca directamente `.\.venv\Scripts\python.exe`. Las instrucciones y criterios de verificación están en [docs/environment_setup.md](docs/environment_setup.md).

## Estructura inicial

```text
config/                     Configuración versionable sin secretos
docs/                       Arquitectura, fuentes, decisiones, resultados y límites
reports/profiling/          Resúmenes de calidad sin datos crudos
src/                        Extracción y perfilado reproducibles
tests/                      Pruebas automatizadas
.env.example                Variables locales de ejemplo
requirements.txt            Dependencias de ejecución
requirements-dev.txt        Herramientas de desarrollo y análisis
```

Las carpetas SQL y Power BI se incorporarán cuando contengan artefactos reales. Los datos crudos y archivos `.pbix` no se versionarán en Git.

## Reproducir la ingesta piloto

1. Copiar `.env.example` como `.env` y confirmar que `DATA_ROOT` apunta fuera de OneDrive.
2. Descargar primero el JSON canónico y después las tablas CSV:

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.extraction.download_ocds --format json --year 2026 --month 7 --snapshot-date 2026-08-19 --env-file .env
.\.venv\Scripts\python.exe -m procurement_intelligence.extraction.download_ocds --format csv --year 2026 --month 7 --snapshot-date 2026-08-19 --env-file .env
```

3. Generar el perfil estructural:

```powershell
$archive = "C:\Data\procurement-intelligence-supplier-risk-peru\raw\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\2026-07_seace_v3_csv.zip"
$profile = "C:\Data\procurement-intelligence-supplier-risk-peru\metadata\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\profile_csv_full.json"
.\.venv\Scripts\python.exe -m procurement_intelligence.profiling.profile_ocds_csv $archive --output $profile --summary-output reports\profiling\oece_ocds_seace_v3_2026_07_summary.json
```

El detalle metodológico está en [docs/methodology/data_download_and_profiling.md](docs/methodology/data_download_and_profiling.md) y los resultados del piloto en [docs/results/phase2_data_profiling.md](docs/results/phase2_data_profiling.md).

## Ejecutar Data Quality inicial

```powershell
$archive = "C:\Data\procurement-intelligence-supplier-risk-peru\raw\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\2026-07_seace_v3_csv.zip"
$quality = "C:\Data\procurement-intelligence-supplier-risk-peru\metadata\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\quality_phase4_full.json"

.\.venv\Scripts\python.exe -m procurement_intelligence.validation.validate_ocds_csv `
  $archive `
  --rules config\data_quality_rules.yml `
  --source-period 2026-07 `
  --snapshot-date 2026-08-19 `
  --output $quality `
  --summary-output reports\data_quality\oece_ocds_seace_v3_2026_07_quality_summary.json
```

El piloto queda deliberadamente `BLOCKED` para promoción a Silver por 10 duplicados adicionales y una clave de clasificación nula. Esto demuestra que la puerta de calidad funciona antes del ETL. La metodología y severidades están en [docs/methodology/data_quality_framework.md](docs/methodology/data_quality_framework.md), y los resultados en [docs/results/phase4_initial_data_quality.md](docs/results/phase4_initial_data_quality.md).

## Fuentes oficiales y trazabilidad

- [Portal de Contrataciones Abiertas de OECE](https://contratacionesabiertas.oece.gob.pe/)
- [Descargas OCDS](https://contratacionesabiertas.oece.gob.pe/descargas)
- [API OCDS](https://contratacionesabiertas.oece.gob.pe/api)

El [registro maestro de fuentes](docs/data_sources/source_registry.md) separa fuentes usadas, documentación de referencia y candidatas no ingeridas. Incluye publicador, enlaces, cobertura, limitaciones, método de acceso, revisión y evidencia del snapshot piloto. La fuente canónica estructurada es `config/source_registry.yml`.

Validar que el documento y el registro siguen sincronizados:

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.documentation.source_registry --check
```

Para volver a comprobar las URL concretas sin descargar el cuerpo de los archivos:

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.documentation.source_registry --check-links
```

## Reproducibilidad y calidad

- Entorno Python aislado por proyecto.
- Dependencias directas versionadas.
- Configuración local y secretos fuera de Git.
- Comparaciones YTD con igual corte temporal.
- Pruebas de esquema, unicidad, completitud y reconciliación antes de publicar KPIs.
- RAW particionado por periodo fuente y fecha de snapshot, sin sobrescritura.
- Hash local para cada archivo y validación del checksum oficial sobre el JSON descomprimido.

## Licencias

El código del repositorio se publica bajo licencia MIT. Los datos conservan los términos, atribución y licencia definidos por cada fuente oficial; no quedan relicenciados por este proyecto.
