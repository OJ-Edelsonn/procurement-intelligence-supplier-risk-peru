# Catálogo de KPIs — Fase 10

El contrato estructurado y versionable reside en `config/kpis.yml`. Los valores se calculan para `source_period=2026-07`.

## KPIs publicables

| KPI | Fórmula resumida | Grano | Unidad |
|---|---|---|---|
| `procurement_processes` | conteo de procesos | proceso | conteo |
| `tender_amount_pen` | suma de monto licitado PEN | proceso | PEN |
| `tender_amount_pen_coverage_pct` | procesos con PEN / procesos | proceso | % |
| `tender_zero_amount_pct` | procesos con monto original cero / procesos | proceso | % |
| `average_tender_ticket_pen` | monto licitado PEN / procesos con PEN | proceso | PEN |
| `active_buyers` | compradores distintos distintos de clave 0 | comprador | conteo |
| `award_count` | conteo de adjudicaciones | adjudicación | conteo |
| `award_amount_pen` | suma de monto adjudicado PEN | adjudicación | PEN |
| `award_amount_pen_coverage_pct` | adjudicaciones con PEN / adjudicaciones | adjudicación | % |
| `average_award_ticket_pen` | monto adjudicado PEN / adjudicaciones con PEN | adjudicación | PEN |
| `attributable_award_pct` | adjudicaciones con proveedor único / adjudicaciones | adjudicación | % |
| `awarded_suppliers` | proveedores atribuibles distintos | proveedor | conteo |
| `contract_count` | conteo de contratos | contrato | conteo |
| `contract_amount_pen` | suma de monto contractual PEN | contrato | PEN |
| `contract_amount_pen_coverage_pct` | contratos con PEN / contratos | contrato | % |
| `average_contract_ticket_pen` | monto contractual PEN / contratos con PEN | contrato | PEN |
| `competition_coverage_pct` | procesos con ofertantes observados / procesos | proceso | % |
| `average_observed_tenderers` | ofertantes observados / procesos con detalle | proceso | ofertantes |
| `award_process_presence_pct` | procesos con adjudicación / procesos | proceso | % |
| `contract_process_presence_pct` | procesos con contrato / procesos | proceso | % |
| `award_item_standard_category_coverage_pct` | ítems adjudicados clasificados / ítems adjudicados | ítem | % |

Los porcentajes de presencia no representan una tasa de conversión secuencial: las coberturas publicadas por OCDS pueden diferir entre componentes.

## Datasets de ranking

| Dataset | Grano | Orden |
|---|---|---|
| `buyer_kpis` | un comprador | monto licitado PEN descendente |
| `supplier_kpis` | un proveedor atribuible | monto adjudicado PEN descendente |
| `category_kpis` | una categoría estándar | monto de ítems adjudicados PEN descendente |

Cada ranking devuelve Top 20 para limitar transferencia y asegurar ejecución determinística. La consulta calcula sus métricas desde el hecho nativo antes de unir la dimensión.

## Métricas bloqueadas

| KPI | Motivo |
|---|---|
| crecimiento y YoY | solo existe un periodo fuente |
| gasto geográfico | falta dimensión UBIGEO gobernada |
| valor final contractual | cobertura 0.2681% |
| participación y HHI | corresponde a Fase 11 |
| Opportunity Score | corresponde a Fase 12 |
| Supplier Exposure Score | corresponde a Fase 13 |
