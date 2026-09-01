# Fase 13 — Supplier Operational and Commercial Exposure Score

> El indicador no constituye una calificación crediticia, evaluación legal, acusación de irregularidad ni predicción de fraude.

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Estado | `PASS_LIMITED` |
| Versión | `supplier-exposure-pilot-v1` |
| Proveedores con adjudicación positiva atribuible | 2,960 |
| Proveedores con inputs completos | 2,475 |
| Proveedores elegibles puntuados | 179 |
| Validaciones aritméticas | 179/179 |
| Banda relativa superior | 35 |
| Banda relativa media | 73 |
| Banda relativa inferior | 71 |
| Escenarios de sensibilidad | 3 |
| Figuras | 3 |

## Primer resultado

`COTRINA AVILA JUANA GUADALUPE` ocupa la posición relativa 1 con score 80.97. Registra dos adjudicaciones, un comprador y concentración completa en su principal comprador y categoría dentro de la muestra. Conserva una variación máxima de una posición en los escenarios.

Esto indica exposición observada bajo la fórmula piloto. No prueba fragilidad financiera, irregularidad, incumplimiento ni conducta indebida.

## Sensibilidad

| Escenario | Correlación con base | Top 10 común | Cambio medio | Cambio máximo |
|---|---:|---:|---:|---:|
| Énfasis en dependencia | 0.9653 | 9/10 | 10.59 | 31 |
| Énfasis en materialidad | 0.8771 | 4/10 | 20.16 | 70 |
| Ponderación equitativa | 0.9923 | 8/10 | 4.72 | 24 |

La sensibilidad del escenario de materialidad es material. Antes de usar posiciones individuales debe acordarse si el objetivo es diversificación comercial, materialidad o dependencia.

## Calidad y ruta de ejecución

- Se reconstruyeron los hechos desde Silver y se reconciliaron 3,397 adjudicaciones, 3,590 ítems y 1,119 contratos con Fase 6.
- Solo se atribuyó dinero cuando existía un proveedor oficial único y valor PEN positivo.
- Los valores de comprador y categoría permanecieron en granos separados.
- Los SQL equivalentes se versionaron, pero la corrida reportada no los ejecutó debido a presión de memoria de SQL Server Express.
- Una segunda corrida temporal mediante SQL Server reprodujo las 179 filas y 36 columnas del CSV Silver con tolerancia `1e-9`; sus artefactos temporales se eliminaron después de validar la equivalencia.
- No se incorporó una fuente nueva; el registro maestro de fuentes mantiene la trazabilidad oficial.

## Evidencia

- `config/supplier_exposure_score.yml`.
- `reports/supplier_exposure/oece_ocds_seace_v3_2026_07_supplier_exposure.json`.
- `reports/supplier_exposure/oece_ocds_seace_v3_2026_07_supplier_exposure.csv`.
- `reports/supplier_exposure/oece_ocds_seace_v3_2026_07_supplier_exposure.md`.
- `reports/supplier_exposure/figures/`.
- `sql/analytics/phase13_supplier_*.sql`.
