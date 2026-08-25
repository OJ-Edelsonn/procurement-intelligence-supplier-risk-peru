# Diccionario — Supplier Exposure Score

Grano del CSV: un proveedor elegible en el periodo `2026-07`.

| Campo | Tipo lógico | Definición |
|---|---|---|
| `supplier_key` | entero | clave sustituta del proveedor |
| `supplier_name` | texto | nombre canónico de `dim_supplier` |
| `award_count` | entero | adjudicaciones positivas atribuibles |
| `buyer_count` | entero | compradores conocidos distintos |
| `award_amount_pen` | decimal | suma de cabeceras de adjudicación en PEN calculado |
| `average_award_ticket_pen` | decimal | monto adjudicado / adjudicaciones |
| `known_buyer_amount_pen` | decimal | monto asociado a comprador conocido |
| `top_buyer_share_pct` | porcentaje | participación monetaria del principal comprador |
| `award_hhi` | decimal 0–10,000 | concentración de montos entre adjudicaciones del proveedor |
| `award_item_count` | entero | ítems adjudicados positivos atribuibles |
| `award_item_amount_pen` | decimal | monto total de ítems atribuibles; no se suma a cabeceras |
| `known_category_item_amount_pen` | decimal | monto de ítems con categoría estándar conocida |
| `category_count` | entero | categorías estándar conocidas distintas |
| `top_category_share_pct` | porcentaje | participación de la categoría principal sobre ítems conocidos |
| `contract_count` | entero | contratos observados atribuibles; contexto, no componente |
| `contract_amount_pen` | decimal | monto contractual calculado; contexto, no componente |
| `known_buyer_amount_coverage_pct` | porcentaje | cobertura de comprador sobre monto adjudicado |
| `known_category_item_amount_coverage_pct` | porcentaje | cobertura de categoría sobre monto de ítems |
| `effective_award_count` | decimal | `10000 / award_hhi` |
| `is_score_eligible` | booleano | cumplimiento de los tres criterios de elegibilidad |
| `component_*` | decimal 0–100 | percentil del componente indicado |
| `score_baseline` | decimal 0–100 | suma ponderada base |
| `rank_baseline` | entero | posición descendente del score base |
| `score_*` / `rank_*` | decimal / entero | resultado de cada escenario de sensibilidad |
| `exposure_band` | categoría | banda relativa por percentil de ranking |
| `maximum_absolute_rank_shift` | entero | rango máximo de posiciones entre escenarios |
| `scenario_score_range` | decimal | máximo menos mínimo score entre escenarios |

Los porcentajes pueden ser 100% sin implicar anomalía: indican dependencia completa en la muestra observada. Las columnas de contratos no intervienen en el score base.
