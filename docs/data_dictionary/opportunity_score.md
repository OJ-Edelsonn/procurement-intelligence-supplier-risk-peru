# Diccionario del B2G Opportunity Score

Grano del dataset: una categoría estándar elegible del snapshot `2026-07`.

## Campos de identidad y entrada

| Campo | Definición |
|---|---|
| `category_key` | clave sustituta de categoría |
| `classification_code` | código estándar publicado |
| `attributable_amount_pen` | tamaño monetario del mercado |
| `award_item_count` | frecuencia observada |
| `buyer_count` | diversidad de compradores |
| `hhi` | concentración monetaria de Fase 11 |
| `average_ticket` | monto atribuible / ítems |

## Componentes

Los campos `component_*` son percentiles 0–100:

- `component_market_size`;
- `component_frequency`;
- `component_buyer_breadth`;
- `component_average_ticket`;
- `component_market_openness`.

## Resultados

| Campo | Definición |
|---|---|
| `score_baseline` | suma ponderada base |
| `rank_baseline` | posición descendente |
| `opportunity_band` | banda relativa por ranking |
| `score_demand_heavy` | score del escenario de demanda |
| `score_accessibility_heavy` | score del escenario de accesibilidad |
| `score_balanced_equal` | score con pesos iguales |
| `scenario_score_range` | máximo menos mínimo entre escenarios |
| `maximum_absolute_rank_shift` | mayor diferencia de posiciones entre escenarios |

El CSV de salida contiene las 87 filas y está preparado como tabla importable en Power BI. El score debe filtrarse siempre por `score_version` y `source_period` en futuras ampliaciones.
