# Índice de documentación

## Orientación

- [Caso de negocio](business_case.md)
- [Alcance y limitaciones](scope_and_limitations.md)
- [Estado del proyecto](project_status.md)
- [Arquitectura end-to-end](architecture/phase3_target_architecture.md)

## Fuentes y contratos de datos

- [Fuentes de datos](data_sources.md)
- [Registro maestro de fuentes](data_sources/source_registry.md)
- [Diccionario OCDS del piloto](data_dictionary/ocds_csv_tables_2026_07.md)
- [Modelo dimensional lógico](data_dictionary/dimensional_model.md)
- [Modelo físico SQL Server](data_dictionary/sql_server_physical_model.md)
- [Catálogo de KPIs](data_dictionary/kpi_catalog.md)

## Metodologías

- [Descarga y profiling](methodology/data_download_and_profiling.md)
- [Data Quality](methodology/data_quality_framework.md)
- [ETL Python a Silver](methodology/python_etl_silver.md)
- [Carga SQL Server](methodology/sql_server_load.md)
- [Validación y reconciliación SQL](methodology/sql_validation_quality_reconciliation.md)
- [EDA](methodology/exploratory_data_analysis.md)
- [KPIs gobernados](methodology/governed_kpi_framework.md)
- [Concentración de mercado](methodology/market_concentration.md)
- [Opportunity Score](methodology/b2g_opportunity_score.md)
- [Supplier Exposure Score](methodology/supplier_exposure_score.md)
- [Automatización](methodology/pipeline_automation.md)
- [Benchmark y medición](methodology/benchmark_and_measurement.md)

## Operación

- [Preparación del entorno](environment_setup.md)
- [Runbook del pipeline](operations/pipeline_runbook.md)

## Resultados

Los resultados por fase se conservan en [`docs/results/`](results/). Las evidencias de máquina se encuentran bajo [`reports/`](../reports/) y cada resultado identifica sus artefactos fuente.

## Decisiones

Los ADR de [`docs/decisions/`](decisions/) explican por qué se eligieron las capas, puertas de calidad, modelos, scores, Power BI, automatización y política de medición.

