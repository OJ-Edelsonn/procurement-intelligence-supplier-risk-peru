# Fase 16 — Resultado de benchmark

## Resumen

| Métrica | Resultado |
|---|---:|
| Estado | `PASS` |
| Corrida automatizada observada | 477.8074 s |
| Consultas SQL medidas | 3 |
| Métricas cuantitativas publicadas | 20 |
| Filas RAW | 231,123 |
| Filas Silver | 231,113 |
| Filas en cuarentena | 10 |
| Reducción Parquet vs. CSV descomprimido | 86.2025% |
| Monto licitado analizado | S/ 6,924,924,015.38 |
| Mercados puntuados | 87 |
| Proveedores puntuados | 179 |
| Actualización final de Power BI | 200 s |
| Páginas/visuales Power BI validados | 5 / 30 |

## Latencia SQL local

| Consulta | Mediana | p95 |
|---|---:|---:|
| Resumen ejecutivo DW | 116.7365 ms | 117.5650 ms |
| Ranking de proveedores | 29.3226 ms | 33.6775 ms |
| Concentración por categoría | 215.1486 ms | 228.4843 ms |

Estas cifras no son un SLA. Dependen del equipo, SQL Server Express, caché y carga concurrente de la ejecución final del 2026-08-31.

## Declaración responsable

No existe una línea base manual comparable. En consecuencia, el proyecto no afirma horas ahorradas ni porcentaje de reducción. La evidencia permite afirmar que el flujo core se ejecuta mediante un comando, conserva logs y termina sin intervención intermedia.

## Evidencia

- `config/benchmark.yml`.
- `reports/benchmark/phase16_benchmark.json`.
- `reports/benchmark/phase16_benchmark.md`.
- `src/procurement_intelligence/benchmark/run_benchmark.py`.

La actualización final del dashboard congelado se observó una vez en el equipo local y tardó 200 segundos. Es evidencia de esta ejecución, no un SLA.
