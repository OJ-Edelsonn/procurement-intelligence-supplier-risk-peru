# Fase 15 — Resultado de automatización

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Estado | `PASS_WITH_WARNINGS` |
| Pasos configurados | 14 |
| Pasos ejecutados | 7 |
| Artefactos válidos reutilizados | 5 |
| Grupos opcionales omitidos | 2 |
| Fallos | 0 |
| Duración observada | 477.8074 s |
| Intervenciones durante la corrida | 0 |

La corrida reprodujo, en orden, el registro de fuentes, validación SQL, EDA, KPIs, concentración, Opportunity Score y Supplier Exposure. Reutilizó profiling, calidad RAW, ETL Silver, análisis dimensional y carga SQL previamente aprobados. Descarga y Power BI permanecieron fuera de alcance por opción explícita.

## Advertencias aceptadas

- Calidad RAW: `DQ-UNIQ-001` identifica diez duplicados adicionales conocidos.
- Silver: las diez filas se conservan en cuarentena y la promoción queda aprobada.
- Modelo dimensional y validación SQL: estados con advertencias documentadas, sin fallos bloqueantes.
- Supplier Exposure: `PASS_LIMITED` por su alcance relativo y la ausencia de variables legales, crediticias o históricas.

## Verificación

- Prueba real contra SQL Server local.
- 0 pasos fallidos.
- 102 pruebas automatizadas aprobadas después de la corrida.
- Reporte: `reports/automation/phase15_pipeline_run.json`.
- Contrato: `config/pipeline.yml`.
- Código: `src/procurement_intelligence/automation/run_pipeline.py`.

No se afirma ahorro de tiempo: la ejecución manual comparable no fue medida antes de automatizar.

