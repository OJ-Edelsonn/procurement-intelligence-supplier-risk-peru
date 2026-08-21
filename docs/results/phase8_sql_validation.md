# Fase 8 — Validación SQL, calidad y reconciliación avanzada

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Estado | `PASS_WITH_WARNINGS` |
| Elegible para análisis | Sí |
| Lote validado | 4 |
| Reglas SQL | 45 |
| Reglas sin casos | 36 |
| Advertencias con casos | 9 |
| Fallos bloqueantes | 0 |
| Reconciliaciones totales | 113/113 PASS |
| Duración | 8.2023 s |

El estado no indica datos perfectos. Indica que estructura, grano, referencias, linaje, atribución, cálculos y reconciliaciones pasan, mientras nueve limitaciones reales permanecen visibles.

## Reconciliaciones

| Tipo | Comparaciones | Fallos |
|---|---:|---:|
| Filas Python↔auditoría↔SQL | 38 | 0 |
| Importes Silver↔`stg`/`dw`, por moneda | 52 | 0 |
| Identidad, hashes y totales de artefactos | 14 | 0 |
| Incidencias Python↔SQL | 9 | 0 |

Las 231,113 filas staging y las 87,159 filas `dw` coinciden tabla por tabla. `DBCC CHECKCONSTRAINTS` devolvió cero filas y las 55 claves foráneas permanecen habilitadas y confiables.

## Advertencias observadas

| Regla | Casos | Denominador | Lectura correcta |
|---|---:|---:|---|
| RUC publicado con formato estructural inválido | 1,776 | 12,820 proveedores | No implica invalidez legal ni fraude |
| Conflictos de nombre de proveedor | 4 | 12,820 proveedores | Canonización conservó la señal |
| Conflictos de descripción de categoría | 3 | 3,689 categorías conocidas | Misma clave con variantes oficiales |
| Ofertantes declarados ≠ observados | 53 | 4,243 comparables | Diferencia header–detalle |
| Licitación header–ítems > 0.01 | 67 | 6,452 | Diferencia preservada |
| Adjudicación header–ítems > 0.01 | 1 | 3,397 | Diferencia preservada |
| Filas extranjeras sin tasa PEN | 10 | 412 filas en moneda extranjera | No se inventó tasa |
| Contratos sin valor final | 1,116 | 1,119 | KPI de ejecución sigue aplazado |
| Licitaciones con monto cero | 1,752 | 6,452 | Filas marcadas, no eliminadas |

Los contratos header–ítems tuvieron 0 diferencias superiores a 0.01 y se observaron 0 importes negativos. Esas reglas pasaron.

## Incidencias durante el desarrollo

1. La primera ejecución reutilizó un nombre de tabla temporal entre dos scripts ODBC. SQL Server resolvió el esquema anterior y rechazó una columna. Se aislaron los nombres y se eliminan explícitamente al terminar. No hubo escritura en la base.
2. La siguiente ejecución produjo 38 falsos positivos al multiplicar dos `decimal(38,14)`: SQL Server redujo la escala intermedia. La regla se ajustó para conservar 14 decimales; los valores almacenados no cambiaron.

Después de ambas correcciones se repitió el contrato completo y el resultado quedó sin fallos bloqueantes.

## Trazabilidad de fuente

La fase no incorpora fuentes ni datasets nuevos. Valida el mismo snapshot oficial OECE/SEACE registrado en `docs/data_sources/source_registry.md`. El reporte conserva hashes de:

- configuración de Fase 8;
- cinco scripts SQL;
- resumen ETL;
- análisis dimensional;
- evidencia de carga SQL.

## Interpretación profesional

La evidencia permite afirmar que se implementaron 45 reglas y 113 reconciliaciones reproducibles, no que se corrigieron 1,776 proveedores ni que una empresa tomó decisiones con el resultado. Las advertencias describen observaciones del dataset público.

## Pruebas

- ejecución real sobre SQL Server 2022 Express;
- 45/45 reglas ejecutadas;
- 0 fallos bloqueantes;
- 113/113 reconciliaciones aprobadas;
- `DBCC CHECKCONSTRAINTS` sin violaciones;
- suite Python completa;
- verificación de hashes y ausencia de rutas privadas en la evidencia.

## Limitaciones

- Piloto de un mes; la estabilidad temporal se comprobará al ampliar periodos.
- La consistencia entre capas no certifica exactitud legal del dato oficial.
- `finalValue` no es apto para un KPI de ejecución con esta cobertura.
- La fase habilita EDA, pero no define todavía KPIs ni scores.

## Evidencia

- `reports/sql/oece_ocds_seace_v3_2026_07_phase8_validation.json`.
- `config/sql_validation.yml`.
- `sql/validation/phase8_*.sql`.
- `docs/data_dictionary/sql_validation_catalog.md`.
