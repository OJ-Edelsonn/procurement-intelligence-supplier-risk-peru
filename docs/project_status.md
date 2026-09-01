# Estado del proyecto

Fecha de corte documental: 2026-08-31.

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
| 14 | Power BI | Completa | 5 páginas, 30 visuales, 5 capturas y validación final `PASS` |
| 15 | Automatización | Completa para el pipeline core | `reports/automation/phase15_pipeline_run.json` |
| 16 | Benchmark y resultados | Completa | Incluye actualización final de Power BI en 200 s |
| 17 | Documentación | Completa | README, capturas, resultados y evidencia de validación sincronizados |
| 18 | GitHub final | Preparación técnica completa, publicación pendiente | CI, plantilla de PR, licencia, cita y checklist listos |
| 19 | CV, LinkedIn y entrevistas | Borrador verificable completo | Capturas disponibles; falta añadir el enlace público después de publicar |

## Validación del cierre técnico independiente

- Suite local: 116 pruebas aprobadas.
- CI en GitHub: aprobado sobre el PR borrador de integración.
- Registro documental: sincronizado con su configuración canónica.
- Enlaces de fuentes: 20/20 accesibles el 2026-08-28.
- Pipeline core observado: 7 etapas ejecutadas, 5 evidencias reutilizadas, 0 fallos.
- Power BI: actualización completa en 200 segundos; 8/8 validaciones y 5/5 capturas aprobadas.
- Publicación final: todavía no realizada; no forma parte de la validación técnica local.

## Cierre de Power BI

1. Se corrigieron unidades automáticas, etiquetas, encabezados y ordenamientos.
2. La actualización final contra `localhost\SQLEXPRESS` terminó sin errores en 200 segundos.
3. Las cinco capturas definitivas tienen al menos 1,364 × 789 píxeles y hashes registrados.
4. `reports/powerbi/phase14_powerbi_validation.json` terminó `PASS` con 8/8 controles.
5. El benchmark y el README incorporan la evidencia final.

Quedan fuera del cierre técnico la publicación en Power BI Service, el enlace público, el merge/release de GitHub y la incorporación de ese enlace a los materiales profesionales.
