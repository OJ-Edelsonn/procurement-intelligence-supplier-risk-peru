# Fase 16 — Benchmark y resultados verificables

- Estado: **PASS**
- Periodo fuente: `2026-07`
- Corrida automatizada observada: **477.81 s**
- Pasos ejecutados/reutilizados: **7 / 5**
- Línea base manual: **no disponible; no se calcula ni se afirma ahorro de tiempo**.

## Tiempos registrados en artefactos

| Componente | Segundos | Evidencia |
|---|---:|---|
| Perfilado RAW | 45.7273 | `reports/profiling/oece_ocds_seace_v3_2026_07_summary.json` |
| Calidad inicial RAW | 76.7619 | `${DATA_ROOT}/metadata/oece/ocds/seace_v3/2026/07/snapshot_date=2026-08-19/quality_phase4_full.json` |
| ETL Silver | 59.3069 | `reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json` |
| Construcción y carga SQL | 233.9022 | `reports/sql/oece_ocds_seace_v3_2026_07_sql_server_load.json` |
| Validación SQL avanzada | 170.7731 | `reports/sql/oece_ocds_seace_v3_2026_07_phase8_validation.json` |
| EDA | 31.2914 | `reports/eda/oece_ocds_seace_v3_2026_07_eda_summary.json` |
| KPIs gobernados | 2.1825 | `reports/kpis/oece_ocds_seace_v3_2026_07_kpi_summary.json` |
| Concentración de mercado | 17.8820 | `reports/concentration/oece_ocds_seace_v3_2026_07_market_concentration.json` |
| Opportunity Score | 14.0990 | `reports/opportunity/oece_ocds_seace_v3_2026_07_opportunity_score.json` |
| Supplier Exposure Score | 111.2510 | `reports/supplier_exposure/oece_ocds_seace_v3_2026_07_supplier_exposure.json` |
| Actualización final de Power BI | 200.0000 | `reports/powerbi/phase14_powerbi_validation.json` |

La suma de componentes procede de ejecuciones documentadas distintas y no se presenta como una única corrida end-to-end.

## Benchmark SQL de solo lectura

| Consulta | Filas | Mediana ms | p95 ms |
|---|---:|---:|---:|
| Resumen ejecutivo DW | 1 | 116.7365 | 117.5650 |
| Ranking de proveedores | 20 | 29.3226 | 33.6775 |
| Concentración por categoría | 772 | 215.1486 | 228.4843 |

## Resultados cuantitativos

| Métrica | Valor | Unidad |
|---|---:|---|
| Tablas RAW perfiladas | 22 | tables |
| Filas RAW | 231,123 | rows |
| Filas Silver | 231,113 | rows |
| Filas en cuarentena | 10 | rows |
| Categorías normalizadas | 2,135 | rows |
| Tamaño Parquet | 9,084,200 | bytes |
| Reducción Parquet vs. CSV descomprimido | 86.2025 | percent |
| Filas staging SQL | 231,113 | rows |
| Objetos dimensionales | 16 | objects |
| KPIs publicados | 21 | metrics |
| Procesos analizados | 6,452 | processes |
| Monto licitado analizado | 6,924,924,015.3800 | PEN |
| Compradores observados | 1,450 | buyers |
| Proveedores adjudicados atribuibles | 2,960 | suppliers |
| Mercados analizados | 772 | markets |
| Mercados puntuados | 87 | markets |
| Proveedores puntuados | 179 | suppliers |
| Páginas Power BI validadas | 5 | pages |
| Visuales Power BI validados | 30 | visuals |
| Capturas finales Power BI | 5 | screenshots |

## Interpretación responsable

Los tiempos corresponden al equipo y la instancia SQL local utilizados en esta ejecución; no son un SLA. No existe una medición manual comparable, por lo que no se declara reducción porcentual de tiempo. Los montos de licitación, adjudicación y contrato pertenecen a hechos distintos y no deben sumarse.
