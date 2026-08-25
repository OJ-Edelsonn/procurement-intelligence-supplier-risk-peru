# Procurement Intelligence & Supplier Risk — Perú

Solución end-to-end de Data/BI para analizar contratación pública peruana, inteligencia comercial y exposición a proveedores usando datos abiertos oficiales de OECE/SEACE.

> Estado: Fase 13 completada. El Supplier Operational and Commercial Exposure Score piloto puntúa 179 proveedores elegibles y valida 179/179 cálculos. No constituye una calificación crediticia, evaluación legal, acusación de irregularidad ni predicción de fraude.

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
reports/                    Resúmenes reproducibles sin datos crudos
src/                        Extracción, calidad y transformación reproducibles
sql/                        DDL y reconciliaciones versionadas para SQL Server
tests/                      Pruebas automatizadas
.env.example                Variables locales de ejemplo
requirements.txt            Dependencias de ejecución
requirements-dev.txt        Herramientas de desarrollo y análisis
```

La carpeta Power BI se incorporará cuando contenga artefactos reales. Los datos crudos, archivos locales de SQL Server y `.pbix` no se versionan en Git.

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

## Ejecutar ETL Python a Silver

```powershell
$archive = "C:\Data\procurement-intelligence-supplier-risk-peru\raw\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\2026-07_seace_v3_csv.zip"

.\.venv\Scripts\python.exe -m procurement_intelligence.transformation.transform_ocds_silver `
  $archive `
  --config config\etl_silver.yml `
  --source-period 2026-07 `
  --snapshot-date 2026-08-19 `
  --env-file .env `
  --summary-output reports\etl\oece_ocds_seace_v3_2026_07_etl_summary.json
```

El piloto reconcilia 231,123 filas RAW en 231,113 filas Silver y 10 filas en cuarentena. El estado posterior es `PASS_WITH_WARNINGS` y las cuatro métricas bloqueantes quedan en cero. La metodología está en [docs/methodology/python_etl_silver.md](docs/methodology/python_etl_silver.md) y el resultado en [docs/results/phase5_python_etl.md](docs/results/phase5_python_etl.md).

## Validar el modelo dimensional

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.modeling.validate_dimensional_model `
  --model config\dimensional_model.yml `
  --etl-summary reports\etl\oece_ocds_seace_v3_2026_07_etl_summary.json `
  --env-file .env `
  --output reports\modeling\oece_ocds_seace_v3_2026_07_dimensional_model_analysis.json
```

El diseño aprobado usa una constelación de hechos para no mezclar procesos, ítems, adjudicaciones y contratos. Las seis puertas lógicas pasan y el diseño queda elegible para generar DDL en la Fase 7. Véanse la [arquitectura dimensional](docs/architecture/phase6_dimensional_model.md), el [diccionario](docs/data_dictionary/dimensional_model.md) y los [resultados de validación](docs/results/phase6_dimensional_model_analysis.md).

## Cargar SQL Server

Confirmar que el servicio `SQL Server (SQLEXPRESS)` esté iniciado y que `.env` contenga la configuración local sin credenciales versionadas.

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.loading.load_sql_server `
  --create-database `
  --output reports\sql\oece_ocds_seace_v3_2026_07_sql_server_load.json
```

Una repetición exacta valida hashes y conteos y termina `SKIPPED_IDEMPOTENT`. Para reemplazar conscientemente otro snapshot se requiere `--replace-snapshot`. El lote final cargó 231,113 filas staging y 87,159 filas `dw` en 233.9022 segundos, con 0 reconciliaciones fallidas y 0 constraints violados. Véanse la [metodología](docs/methodology/sql_server_load.md), el [diccionario físico](docs/data_dictionary/sql_server_physical_model.md) y los [resultados](docs/results/phase7_sql_server_load.md).

## Validar SQL Server y reconciliar capas

La Fase 8 es de solo lectura y requiere el servicio `SQL Server (SQLEXPRESS)` iniciado:

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.validation.validate_sql_server `
  --config config\sql_validation.yml `
  --env-file .env `
  --output reports\sql\oece_ocds_seace_v3_2026_07_phase8_validation.json
```

El piloto ejecutó 45 reglas de estructura, grano, integridad, linaje, atribución y cálculo. Además aprobó 38 reconciliaciones de filas, 52 controles monetarios por moneda, 14 controles de artefactos y 9 comparaciones Python↔SQL. El resultado `PASS_WITH_WARNINGS` conserva nueve hallazgos reales sin bloquear el inicio de EDA. Véanse la [metodología](docs/methodology/sql_validation_quality_reconciliation.md), el [catálogo de reglas](docs/data_dictionary/sql_validation_catalog.md) y los [resultados](docs/results/phase8_sql_validation.md).

## Ejecutar el análisis exploratorio

La Fase 9 exige primero la puerta aprobada de la Fase 8 y consulta únicamente el modelo `dw` activo:

```powershell
.\.venv\Scripts\run-procurement-eda.exe `
  --config config\eda.yml `
  --env-file .env
```

La ejecución validada procesó 10 datasets analíticos, creó 7 figuras PNG y dejó evidencia JSON y Markdown con hashes de configuración, SQL, ejecutor y gráficos. El alcance corresponde solo a `source_period=2026-07`; por ello no se calculan crecimiento ni comparaciones interanuales. Véanse la [metodología](docs/methodology/exploratory_data_analysis.md), el [diccionario de datasets](docs/data_dictionary/eda_datasets.md) y los [resultados](docs/results/phase9_eda.md).

## Calcular KPIs gobernados

```powershell
.\.venv\Scripts\run-procurement-kpis.exe `
  --config config\kpis.yml `
  --env-file .env
```

La Fase 10 publica 21 indicadores con grano, unidad y denominador explícitos, genera rankings Top 20 y reconcilia siete totales contra el EDA. También versiona medidas DAX equivalentes para Power BI. Crecimiento, YoY, geografía, HHI y scores permanecen bloqueados hasta sus fases correspondientes. Véanse la [metodología](docs/methodology/governed_kpi_framework.md), el [catálogo](docs/data_dictionary/kpi_catalog.md) y los [resultados](docs/results/phase10_kpis.md).

## Analizar concentración de mercado

```powershell
.\.venv\Scripts\run-market-concentration.exe `
  --config config\market_concentration.yml `
  --env-file .env
```

La Fase 11 define cada categoría estándar como un mercado descriptivo, calcula Top 1/3/5/10, HHI y proveedores efectivos, y valida 772/772 distribuciones en Python. Solo 87 mercados cumplen los mínimos de proveedores, compradores, ítems y cobertura. Véanse la [metodología](docs/methodology/market_concentration.md), el [diccionario](docs/data_dictionary/market_concentration.md) y los [resultados](docs/results/phase11_market_concentration.md).

## Calcular el B2G Opportunity Score

```powershell
.\.venv\Scripts\run-opportunity-score.exe `
  --config config\opportunity_score.yml
```

La Fase 12 normaliza tamaño, frecuencia, compradores, ticket y apertura mediante percentiles, aplica pesos explícitos y compara tres escenarios. La versión piloto puntúa 87 mercados y exporta JSON, Markdown, CSV y tres figuras. Véanse la [metodología](docs/methodology/b2g_opportunity_score.md), el [diccionario](docs/data_dictionary/opportunity_score.md) y los [resultados](docs/results/phase12_opportunity_score.md).

## Calcular exposición operativa y comercial de proveedores

```powershell
.\.venv\Scripts\run-supplier-exposure.exe `
  --config config\supplier_exposure_score.yml `
  --env-file .env
```

La Fase 13 reconstruye los hechos auditados desde Silver, exige coberturas mínimas y combina cinco percentiles con pesos explícitos. Puntúa 179 proveedores, valida todos los cálculos y compara tres escenarios. Sanciones, penalidades, historia, solvencia y fraude se excluyen por falta de evidencia o por interpretación improcedente. Véanse la [metodología](docs/methodology/supplier_exposure_score.md), el [diccionario](docs/data_dictionary/supplier_exposure_score.md) y los [resultados](docs/results/phase13_supplier_exposure.md).

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
