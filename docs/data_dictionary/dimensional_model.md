# Diccionario lógico del modelo dimensional

## Convenciones

- Esquema objetivo: `dw`.
- Claves sustitutas: enteros; `0` representa desconocido, sin clasificar o no atribuible.
- Claves naturales y linaje nunca se eliminan.
- Importes: `decimal(38,14)` hasta definir escala de presentación.
- Fechas de negocio: claves `YYYYMMDD`; `0` cuando no están informadas.
- Los nombres SQL definitivos se materializarán en la Fase 7 desde `config/dimensional_model.yml`.

## Dimensiones

### `dw.dim_date`

| Columna | Propósito |
|---|---|
| `date_key` | PK `YYYYMMDD`; 0 desconocido |
| `full_date` | fecha calendario |
| `year`, `semester`, `quarter` | jerarquía anual |
| `month_number`, `month_name_es`, `year_month` | jerarquía mensual |
| `day_of_month`, `day_of_week_number`, `day_name_es` | detalle diario |
| `is_weekend` | sábado o domingo |
| `is_ytd_comparable_month` | identifica meses habilitados para comparación YTD |

### `dw.dim_process`

| Columna | Fuente/derivación |
|---|---|
| `process_key` | clave sustituta |
| `ocid` | `procurement_process.ocid`; clave natural |
| `compiled_release_id` | record compilado |
| `tender_id` | identificador de licitación |
| `tender_title`, `tender_description` | descriptores publicados |
| `initiation_type` | tipo de inicio OCDS |
| `main_procurement_category` | categoría general del proceso |
| `additional_procurement_categories` | categorías generales adicionales publicadas |
| `data_segmentation_id`, `data_segmentation_criteria` | segmentación OECE |

### `dw.dim_buyer`

| Columna | Fuente/derivación |
|---|---|
| `buyer_key` | clave sustituta |
| `source_party_id` | ID de parte con rol buyer; clave natural |
| `identifier_scheme`, `identifier_id` | identificador PE-CONSUCODE publicado |
| `alternate_ruc` | identificador adicional PE-RUC; 1,450 valores únicos y formato válido en el piloto |
| `display_name`, `legal_name` | nombre canónico Type 1 |
| `department_name_raw`, `province_name_raw`, `locality_name_raw` | geografía textual sin homologar |
| `country_name_raw` | país publicado |
| `name_variant_count`, `dq_name_conflict` | control de identidad |
| `first_observed_period`, `last_observed_period` | vigencia observada, no legal |
| `canonical_ingestion_run_id` | corrida que aportó los atributos canónicos |

### `dw.dim_supplier`

| Columna | Fuente/derivación |
|---|---|
| `supplier_key` | clave sustituta |
| `source_party_id` | ID de parte ofertante/proveedor; clave natural |
| `identifier_scheme`, `identifier_id` | identificador publicado |
| `display_name`, `legal_name` | nombre canónico Type 1 |
| `country_name_raw` | país publicado cuando existe |
| `dq_ruc_format_valid` | validación estructural, no registral |
| `name_variant_count`, `dq_name_conflict` | variantes observadas |
| `first_observed_period`, `last_observed_period` | observación del pipeline |
| `canonical_ingestion_run_id` | corrida que aportó los atributos canónicos |

### `dw.dim_category`

| Columna | Fuente/derivación |
|---|---|
| `category_key` | clave sustituta; 0 “Sin clasificar” |
| `classification_scheme` | `CUBSO`, `UNSPSC` o `UNKNOWN` |
| `classification_code` | código publicado o `__UNCLASSIFIED__` |
| `classification_description` | descripción canónica |
| `description_variant_count`, `dq_description_conflict` | conflictos publicados |
| `is_unknown` | miembro técnico de ausencia |

No se deriva jerarquía UNSPSC o CUBSO hasta ingerir y versionar un catálogo oficial.

### Dimensiones pequeñas

| Dimensión | Clave natural | Atributos |
|---|---|---|
| `dim_procurement_method` | método + detalle | método general y detalle OECE |
| `dim_currency` | código de moneda | código y nombre publicado |
| `dim_unit` | esquema + código | esquema, código y nombre de unidad |

## Hechos de cabecera

### `dw.fact_procurement_process`

Grano: un `ocid`.

| Grupo | Columnas principales |
|---|---|
| Claves | `process_key`, `buyer_key`, `procurement_method_key`, monedas y fechas de rol |
| Medidas | `process_count`, `planning_budget_amount_original`, `tender_amount_original`, `tender_amount_pen_published` |
| Competencia | `tenderer_count_declared`, `tenderer_count_observed` |
| Auditoría | suma de ítems, diferencia y bandera de conciliación 0.01 |
| Calidad | monto cero y coincidencia de número de ofertantes |

### `dw.fact_award`

Grano: `ocid + award_id`.

| Grupo | Columnas principales |
|---|---|
| Claves | `process_key`, `buyer_key`, `attributed_supplier_key`, método, moneda y fecha de adjudicación |
| Degeneradas | `award_id` |
| Medidas | `award_count`, `award_amount_original`, tasa y `award_amount_pen_calculated` |
| Atribución | `supplier_count`, `dq_supplier_amount_attributable` |
| Auditoría | suma de ítems, diferencia y conciliación 0.01 |

### `dw.fact_contract`

Grano: `ocid + contract_id`.

| Grupo | Columnas principales |
|---|---|
| Claves | proceso, comprador, proveedor atribuible, método, moneda y fechas de contrato |
| Degeneradas | `contract_id`, `award_id`, título y descripción |
| Medidas | `contract_count`, importe original, tasa, importe PEN y duración |
| Diagnóstico | `final_value_original`, disponible pero no apto para KPI |
| Auditoría | suma de ítems, diferencia y conciliación 0.01 |

## Hechos de ítem

| Tabla | Grano | Medidas | Dimensiones de categoría |
|---|---|---|---|
| `fact_tender_item` | `ocid + tender_item_id` | conteo, cantidad, importe original/PEN | CUBSO principal + UNSPSC estándar |
| `fact_award_item` | `ocid + award_id + item_id` | conteo, cantidad, importe original/PEN | CUBSO principal + UNSPSC estándar |
| `fact_contract_item` | `ocid + contract_id + item_id` | conteo, cantidad, importe original/PEN | CUBSO principal + UNSPSC estándar |

Cada hecho conserva posición, descripción, estado, unidad, moneda, tasa disponible y banderas de clasificación/conversión. `fact_award_item` y `fact_contract_item` solo heredan proveedor cuando la adjudicación tiene exactamente uno.

## Puentes factless

| Tabla | Grano | Medida permitida | Medidas prohibidas |
|---|---|---|---|
| `bridge_process_tenderer` | proceso + ofertante | `participation_count = 1` | montos de licitación |
| `bridge_award_supplier` | adjudicación + proveedor | `participation_count = 1` | montos adjudicados |

## Linaje común de hechos

| Columna | Uso |
|---|---|
| `source_id`, `source_period`, `snapshot_date` | origen y corte |
| `ingestion_run_id` | corrida idempotente |
| `source_file_name`, `source_file_sha256` | archivo físico |
| `source_table_name`, `source_row_number` | fila Silver de origen |
| `loaded_at_utc` | carga técnica |

Las dimensiones derivadas de Silver conservan `first_observed_period`,
`last_observed_period` y `canonical_ingestion_run_id`. `dim_date` se genera de
forma determinística y tendrá metadatos propios de la carga de Fase 7.

## Matriz Silver → DW

| Silver | Destino principal | Tratamiento |
|---|---|---|
| `procurement_process` | `dim_process`, `fact_procurement_process`, dimensiones buyer/método/moneda/fecha | separa descriptores y medidas |
| `party`, `party_additional_identifier` | `dim_buyer`, `dim_supplier` | filtra roles y canoniza Type 1 |
| `tenderer` | `bridge_process_tenderer` | participación sin monto |
| `tender_item` + clasificación/tasa | `fact_tender_item`, `dim_category`, `dim_unit` | dos roles de categoría y conversión controlada |
| `award` + tasa | `fact_award` | monto de cabecera una sola vez |
| `award_supplier` | `bridge_award_supplier` y atribución segura | 100% solo con un proveedor |
| `award_item` + clasificación/tasa | `fact_award_item` | grano de ítem independiente |
| `contract` + tasa | `fact_contract` | valor formalizado, no ejecución final |
| `contract_item` + clasificación/tasa | `fact_contract_item` | grano de ítem independiente |
| releases, fuentes y documentos | `stg`/`audit` | fuera del modelo monetario MVP |
