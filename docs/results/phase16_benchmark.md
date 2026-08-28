# Fase 16 — Resultado de benchmark

## Resumen

| Métrica | Resultado |
|---|---:|
| Estado | `PASS` |
| Corrida automatizada observada | 477.8074 s |
| Consultas SQL medidas | 3 |
| Métricas cuantitativas publicadas | 17 |
| Filas RAW | 231,123 |
| Filas Silver | 231,113 |
| Filas en cuarentena | 10 |
| Reducción Parquet vs. CSV descomprimido | 86.2025% |
| Monto licitado analizado | S/ 6,924,924,015.38 |
| Mercados puntuados | 87 |
| Proveedores puntuados | 179 |

## Latencia SQL local

| Consulta | Mediana | p95 |
|---|---:|---:|
| Resumen ejecutivo DW | 207.5345 ms | 253.1050 ms |
| Ranking de proveedores | 66.0369 ms | 68.4676 ms |
| Concentración por categoría | 385.0194 ms | 388.2884 ms |

Estas cifras no son un SLA. Dependen del equipo, SQL Server Express, caché y carga concurrente de la ejecución del 2026-08-28.

## Declaración responsable

No existe una línea base manual comparable. En consecuencia, el proyecto no afirma horas ahorradas ni porcentaje de reducción. La evidencia permite afirmar que el flujo core se ejecuta mediante un comando, conserva logs y termina sin intervención intermedia.

## Evidencia

- `config/benchmark.yml`.
- `reports/benchmark/phase16_benchmark.json`.
- `reports/benchmark/phase16_benchmark.md`.
- `src/procurement_intelligence/benchmark/run_benchmark.py`.

El tiempo de actualización final de Power BI queda pendiente hasta congelar el dashboard.

