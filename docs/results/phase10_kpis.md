# Fase 10 — KPIs gobernados

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Estado | `PASS` |
| Datasets SQL | 4 |
| KPIs publicables | 21 |
| KPIs bloqueados | 7 |
| Reconciliaciones críticas | 7/7 |
| Fallos de reconciliación | 0 |
| Source periods | 1 |

## Resultados principales

| KPI | Valor | Cobertura |
|---|---:|---:|
| Procesos publicados | 6,452 | 6,452/6,452 |
| Monto licitado PEN | S/ 6,924.92 M | 6,452/6,452 |
| Ticket promedio licitado | S/ 1.07 M | 6,452/6,452 |
| Compradores observados | 1,450 | claves conocidas |
| Adjudicaciones | 3,397 | 3,397/3,397 |
| Monto adjudicado PEN | S/ 2,375.75 M | 3,397/3,397 |
| Ticket promedio adjudicado | S/ 699,366.56 | 3,397/3,397 |
| Proveedores adjudicados atribuibles | 2,960 | proveedor único |
| Contratos | 1,119 | 1,119/1,119 |
| Monto contractual PEN | S/ 652.17 M | 1,115/1,119 |
| Ticket promedio contractual | S/ 584,905.28 | 1,115/1,119 |

Los tres montos pertenecen a etapas y granos distintos. No se suman entre sí.

## Cobertura analítica

- 100% de procesos y adjudicaciones tienen monto PEN calculable.
- 99.6425% de contratos tienen monto PEN calculable.
- 99.9706% de adjudicaciones permiten atribución a un proveedor único.
- 65.7626% de procesos tienen ofertantes observados; en ese subconjunto el promedio es 8.0403.
- 81.9499% de ítems adjudicados tienen categoría estándar conocida.
- 27.1544% de procesos tienen monto original de licitación igual a cero.

## Límites de publicación

- `award_process_presence_pct` y `contract_process_presence_pct` expresan presencia del componente, no conversión causal.
- Los tickets promedio son sensibles a la cola derecha y deben leerse junto con la mediana del EDA.
- Los rankings Top 20 corresponden al snapshot piloto.
- Crecimiento, YoY, HHI, participación de mercado, geografía y scores continúan bloqueados o diferidos.

## Pruebas y evidencia

- Las cuatro consultas SQL se ejecutaron de manera independiente.
- Siete totales críticos coinciden exactamente con Fase 9.
- El contrato valida unicidad, unidades y separación entre métricas publicables y bloqueadas.
- El catálogo DAX conserva las fronteras de fase.
- No se incorporó una fuente nueva; se reutiliza el snapshot OECE/SEACE registrado.

Artefactos:

- `config/kpis.yml`.
- `reports/kpis/oece_ocds_seace_v3_2026_07_kpi_summary.json`.
- `reports/kpis/oece_ocds_seace_v3_2026_07_kpi_report.md`.
- `powerbi/dax/phase10_kpi_measures.dax`.
