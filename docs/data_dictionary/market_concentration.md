# Diccionario de Market Concentration

## Dataset `category_concentration`

Grano: una categoría estándar con monto positivo atribuible durante `source_period=2026-07`.

| Campo | Definición |
|---|---|
| `category_key` | clave sustituta de categoría |
| `award_item_count` | ítems conocidos de la categoría |
| `buyer_count` | compradores conocidos distintos |
| `supplier_count` | proveedores atribuibles con monto positivo |
| `total_category_amount_pen` | monto PEN de ítems conocidos, antes del filtro de atribución |
| `attributable_amount_pen` | monto PEN usado como denominador de shares |
| `attributable_amount_coverage_pct` | monto atribuible / monto total conocido |
| `top1_share_pct` | participación del principal proveedor |
| `top3_share_pct` | participación acumulada de tres proveedores |
| `top5_share_pct` | participación acumulada de cinco proveedores |
| `top10_share_pct` | participación acumulada de diez proveedores |
| `hhi` | suma de shares porcentuales al cuadrado |
| `effective_supplier_count` | `10,000 / HHI` |
| `is_analysis_eligible` | cumplimiento de los cuatro umbrales metodológicos |

## Dataset `category_supplier_shares`

Grano: un proveedor atribuible con monto positivo dentro de una categoría estándar.

| Campo | Definición |
|---|---|
| `supplier_amount_pen` | monto de ítems atribuible al proveedor |
| `market_amount_pen` | monto atribuible total de la categoría |
| `supplier_share_pct` | participación porcentual |
| `supplier_rank` | posición determinística por monto descendente y clave |

## Reglas de uso

- No sumar shares entre categorías.
- No promediar HHI sin identificar el universo de mercados.
- No presentar HHI como una propiedad intrínseca del proveedor.
- Mostrar monto, proveedores, compradores, cobertura y periodo junto al índice.
