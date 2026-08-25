# Supplier Operational and Commercial Exposure Score

## Propósito y límite interpretativo

La Fase 13 ordena proveedores según exposición operativa y comercial **relativa** observada en la contratación pública del periodo `2026-07`. Sirve para orientar análisis y diversificación; no determina solvencia, legalidad, integridad ni conducta.

> El indicador no constituye una calificación crediticia, evaluación legal, acusación de irregularidad ni predicción de fraude.

## Universo y elegibilidad

El universo parte de adjudicaciones con monto PEN positivo y un único proveedor oficial atribuible. Un proveedor entra al score si cumple simultáneamente:

- al menos 2 adjudicaciones;
- cobertura monetaria de comprador conocido igual o mayor a 95%;
- cobertura monetaria de categoría conocida en ítems igual o mayor a 80%.

Compradores y categorías se agregan desde sus granos nativos. Los montos de cabecera e ítem nunca se suman entre sí.

## Componentes

| Componente | Campo | Dirección | Peso base |
|---|---|---|---:|
| Materialidad adjudicada | `award_amount_pen` | mayor = mayor exposición relativa | 20% |
| Dependencia del principal comprador | `top_buyer_share_pct` | mayor = mayor exposición | 30% |
| Dependencia de categoría | `top_category_share_pct` | mayor = mayor exposición | 25% |
| Concentración entre adjudicaciones | `award_hhi` | mayor = mayor exposición | 15% |
| Amplitud limitada de compradores | `buyer_count` | menor = mayor exposición | 10% |

Cada variable se convierte a un percentil 0–100 dentro de los proveedores elegibles. Los empates reciben el rango promedio. El score base es la suma ponderada de los cinco componentes.

`award_hhi` es la suma de los cuadrados de la participación porcentual de cada adjudicación en el monto adjudicado al proveedor. Mide concentración interna de sus adjudicaciones, no concentración del mercado ni conducta anticompetitiva.

## Bandas y sensibilidad

Las bandas dependen de la posición relativa:

- `HIGHER_RELATIVE`: primeros 20% del ranking;
- `MEDIUM_RELATIVE`: siguiente 40%;
- `LOWER_RELATIVE`: resto de la población.

Tres escenarios cambian los pesos: énfasis en dependencia, énfasis en materialidad y ponderación equitativa. Se publican correlación de rankings, coincidencia del Top 10 y desplazamientos. Una posición sensible no debe tratarse como estable.

## Ruta de datos y reproducibilidad

La corrida oficial reconstruye las tablas dimensionales desde los 22 Parquet Silver auditados y exige reconciliación con los conteos aprobados de Fase 6: 3,397 adjudicaciones, 3,590 ítems de adjudicación y 1,119 contratos. Esta ruta se usa porque la instancia local SQL Server Express registró presión de memoria; no modifica los datos ni la lógica dimensional.

Los tres SQL de `sql/analytics/phase13_supplier_*.sql` se conservan como contratos equivalentes para ejecutar directamente contra `dw`. El JSON registra hashes del ETL, gate dimensional, configuración, runner, CSV, SQL y figuras.

Como prueba independiente, la ruta `sql_server` se ejecutó después de optimizar los extractos y se compararon sus 179 filas × 36 columnas con la ruta Silver. La equivalencia pasó con tolerancia numérica `1e-9` y coincidencia exacta en campos textuales.

## Variables deliberadamente excluidas

- sanciones y penalidades: fuentes no ingeridas;
- cambios abruptos y recurrencia: solo existe un periodo fuente;
- solvencia o calidad crediticia: fuera del alcance y sin evidencia adecuada;
- inferencias de fraude, corrupción o ilegalidad: interpretación prohibida.

No se incorporó una fuente externa nueva. La procedencia continúa documentada en `docs/data_sources/source_registry.md` y `config/source_registry.yml`.
