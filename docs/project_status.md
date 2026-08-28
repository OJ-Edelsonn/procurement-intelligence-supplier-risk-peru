# Estado del proyecto

Fecha de corte documental: 2026-08-28.

| Fase | Entregable | Estado | Evidencia principal |
|---:|---|---|---|
| 0 | Caso de negocio y alcance | Completa | `docs/business_case.md` |
| 1 | Investigación y selección de fuentes | Completa | `config/source_registry.yml` |
| 2 | Descarga y profiling | Completa | `reports/profiling/` |
| 3 | Arquitectura | Completa | `docs/architecture/phase3_target_architecture.md` |
| 4 | Data Quality inicial | Completa | `reports/data_quality/` |
| 5 | ETL Python | Completa | `reports/etl/` |
| 6 | Modelo dimensional | Completa | `reports/modeling/` |
| 7 | Carga SQL Server | Completa | `reports/sql/*_sql_server_load.json` |
| 8 | Validación SQL y reconciliación | Completa | `reports/sql/*_phase8_validation.json` |
| 9 | EDA | Completa | `reports/eda/` |
| 10 | KPIs | Completa | `reports/kpis/` |
| 11 | Concentración | Completa | `reports/concentration/` |
| 12 | Opportunity Score | Completa | `reports/opportunity/` |
| 13 | Supplier Exposure Score | Completa | `reports/supplier_exposure/` |
| 14 | Power BI | Funcional, cierre diferido | 5 páginas pobladas; formato y QA visual pendientes |
| 15 | Automatización | Completa para el pipeline core | `reports/automation/phase15_pipeline_run.json` |
| 16 | Benchmark y resultados | Completa sin timing final de Power BI | `reports/benchmark/phase16_benchmark.json` |
| 17 | Documentación | Núcleo completo, cierre visual diferido | Falta incorporar el dashboard congelado y sus capturas finales |
| 18 | GitHub final | Preparación técnica completa, publicación diferida | CI, plantilla de PR, licencia, cita y checklist listos; requiere cerrar Fase 14 |
| 19 | CV, LinkedIn y entrevistas | Borrador verificable completo, cierre diferido | `docs/career/portfolio_and_interview_draft.md`; falta añadir el enlace y las capturas finales |

## Validación del cierre técnico independiente

- Suite local: 113 pruebas aprobadas.
- CI en GitHub: aprobado sobre el PR borrador de integración.
- Registro documental: sincronizado con su configuración canónica.
- Enlaces de fuentes: 20/20 accesibles el 2026-08-28.
- Pipeline core observado: 7 etapas ejecutadas, 5 evidencias reutilizadas, 0 fallos.
- Publicación final: deliberadamente no realizada mientras la Fase 14 continúe en QA visual.

## Pendiente que depende de Power BI

1. Corregir unidades automáticas en tarjetas y ejes.
2. Mejorar etiquetas truncadas y encabezados técnicos.
3. Revisar interacciones, filtros, orden y legibilidad.
4. Ejecutar actualización final y capturar las cinco páginas definitivas.
5. Generar `reports/powerbi/phase14_powerbi_validation.json` y cerrar la Fase 14.
6. Añadir al benchmark el tiempo de actualización final del dashboard.
7. Completar la guía visual, README y publicación final.

La ausencia de estos puntos no bloquea la reproducción de RAW → Silver → SQL → analítica, pero sí bloquea declarar terminado y publicado el proyecto completo.
