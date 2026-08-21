# Diccionario de datasets EDA

## Contrato general

Los diez datasets se definen en `config/eda.yml`. Todos consultan `dw` o la identidad del lote en `audit`; ninguno consulta RAW o `stg` ni modifica SQL Server.

| Dataset | Grano de salida | Propósito |
|---|---|---|
| `overview` | una fila por lote | universo, totales de control, fechas y cobertura de etapas |
| `amount_observations` | una fila por hecho monetario | percentiles, ceros, faltantes, IQR e histogramas |
| `monthly_activity` | etapa + mes de negocio | actividad descriptiva dentro del snapshot |
| `buyer_exploration` | un comprador | procesos y montos por etapa sin mezclar hechos |
| `supplier_exploration` | un proveedor atribuible | adjudicaciones, compradores y contratos atribuibles |
| `category_exploration` | categoría estándar | ítems adjudicados, compradores y monto de ítems |
| `competition` | un proceso | ofertantes declarados/observados y presencia de hechos posteriores |
| `procurement_methods` | método + detalle | distribución de procesos y monto licitado |
| `currencies` | etapa + moneda | filas, monto original, monto PEN y cobertura |
| `quality_coverage` | una métrica de cobertura | numerador, denominador, porcentaje e interpretación |

## Perfiles monetarios generados

Para licitación, adjudicación y contrato se publican:

- filas totales y con PEN;
- faltantes y ceros;
- suma de control;
- mínimo, media, Q1, mediana y Q3;
- P90, P95 y P99;
- máximo;
- cerca superior IQR;
- filas por encima de la cerca y del P99.

Estas variables describen una distribución. No deben convertirse automáticamente en reglas de exclusión.

## Rankings

El JSON conserva Top 15; el Markdown muestra Top 10 para lectura rápida.

- Comprador: orden por monto licitado PEN desde `fact_procurement_process`.
- Proveedor: orden por monto adjudicado PEN desde `fact_award`, solo atribución segura.
- Categoría: orden por monto PEN del ítem adjudicado y clasificación estándar.

Los desempates físicos usan la clave sustituta para producir un orden determinístico.

## Trazabilidad

El artefacto JSON registra:

- lote, fuente, periodo y snapshot;
- hash de la puerta de Fase 8;
- hash del contrato EDA;
- hash del ejecutor Python;
- hash de cada consulta SQL;
- versión de Matplotlib;
- tamaño y hash de cada PNG.
