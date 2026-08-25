# Fase 11 — Market Concentration

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Estado | `PASS` |
| Mercados con monto atribuible | 772 |
| Mercados elegibles | 87 |
| Mercados no elegibles | 685 |
| Mercados con un proveedor | 497 |
| Validaciones HHI | 772/772 |
| Cobertura monetaria atribuible en categorías conocidas | 99.9979% |
| Figuras | 3 |

La baja cantidad de mercados elegibles frente al total muestra por qué era necesario aplicar mínimos de observación antes de comparar concentración.

## Distribución elegible

- HHI mediano: 2,244.50.
- Número efectivo mediano de proveedores: 4.46.
- Estos valores resumen los 87 mercados elegibles y no se interpretan como umbrales legales.

## Ejemplos principales

| Categoría | Monto atribuible | Proveedores | Top 1 | Top 3 | HHI | Proveedores efectivos |
|---|---:|---:|---:|---:|---:|---:|
| Construcción de pistas y carreteras nuevas | S/ 505.08 M | 39 | 50.63% | 89.54% | 4,009.95 | 2.49 |
| Construcción y reparación de puentes | S/ 145.20 M | 87 | 3.43% | 9.54% | 159.01 | 62.89 |
| Renovación y reparación de edificios | S/ 131.28 M | 29 | 87.60% | 96.29% | 7,739.91 | 1.29 |

Mercados con muchos proveedores pueden seguir concentrados si uno absorbe gran parte del monto. Por ello `supplier_count` no sustituye HHI.

## Mayor HHI elegible observado

La categoría `78181901`, reparación del sistema de frenos y rueda de ala giratoria de aeronaves, registra HHI 9,199.05, Top 1 de 95.88%, cuatro proveedores y S/ 14.25 M. Es un hallazgo descriptivo del snapshot; no permite inferir irregularidad ni condiciones competitivas sin contexto técnico y temporal adicional.

## Calidad y límites

- 497 mercados tienen un solo proveedor con monto positivo y no entran al ranking elegible.
- La cobertura monetaria de atribución dentro de categorías conocidas es 99.9979%.
- La cobertura de clasificación por filas sigue siendo 81.9499%.
- El análisis utiliza una sola publicación mensual y no demuestra persistencia.
- No se incorporó una fuente nueva.

## Evidencia

- `config/market_concentration.yml`.
- `reports/concentration/oece_ocds_seace_v3_2026_07_market_concentration.json`.
- `reports/concentration/oece_ocds_seace_v3_2026_07_market_concentration.md`.
- `reports/concentration/figures/`.
- `powerbi/dax/phase11_concentration_measures.dax`.
