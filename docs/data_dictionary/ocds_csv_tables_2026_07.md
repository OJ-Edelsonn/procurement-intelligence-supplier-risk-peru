# Inventario de tablas OCDS CSV — piloto 2026-07

Los nombres y conteos provienen del ZIP oficial `2026-07_seace_v3_csv.zip`. “Grano candidato” describe la combinación mínima observada en el piloto; todavía no es una clave definitiva del Data Warehouse.

| Tabla | Filas | Columnas | Grano candidato resumido |
|---|---:|---:|---|
| `records.csv` | 6,452 | 38 | `ocid` |
| `releases.csv` | 80,789 | 7 | `ocid + release_details_id` |
| `com_sources.csv` | 6,452 | 5 | `ocid + source_id` |
| `com_parties.csv` | 40,567 | 16 | `ocid + party_id` |
| `com_par_additionalIdentifiers.csv` | 6,452 | 6 | `ocid + party_id + additional_id + scheme` |
| `com_ten_tenderers.csv` | 34,115 | 5 | `ocid + tenderer_id` |
| `com_ten_documents.csv` | 24,516 | 12 | `ocid + tender_document_id` |
| `com_ten_items.csv` | 7,359 | 18 | `ocid + tender_item_id` |
| `com_ten_ite_additionalClassific.csv` | 6,078 | 7 | `ocid + tender_item_id + classification_id` |
| `com_ten_ite_tot_exchangeRates.csv` | 120 | 6 | `ocid + tender_item_id + currency` |
| `com_awards.csv` | 3,397 | 7 | `ocid + award_id` |
| `com_awa_suppliers.csv` | 3,396 | 5 | `ocid + award_id + supplier_id` |
| `com_awa_items.csv` | 3,590 | 18 | `ocid + award_id + award_item_id` |
| `com_awa_ite_additionalClassific.csv` | 2,942 | 7 | `ocid + award_id + item_id + classification_id` |
| `com_awa_ite_tot_exchangeRates.csv` | 86 | 6 | `ocid + award_id + item_id + currency` |
| `com_awa_val_exchangeRates.csv` | 86 | 5 | `ocid + award_id + currency` |
| `com_contracts.csv` | 1,119 | 17 | `ocid + contract_id` |
| `com_con_documents.csv` | 1,414 | 10 | `ocid + contract_id + document_id` |
| `com_con_items.csv` | 1,139 | 18 | `ocid + contract_id + item_id` |
| `com_con_ite_additionalClassific.csv` | 934 | 7 | `ocid + contract_id + item_id + classification_id` |
| `com_con_ite_tot_exchangeRates.csv` | 60 | 6 | `ocid + contract_id + item_id + currency` |
| `com_con_val_exchangeRates.csv` | 60 | 5 | `ocid + contract_id + currency` |

## Campos útiles confirmados

### Proceso y comprador

- `ocid`.
- `compiledRelease/buyer/id` y `compiledRelease/buyer/name`.
- `compiledRelease/tender/procuringEntity/id` y `name`.
- `compiledRelease/tender/procurementMethodDetails`.
- `compiledRelease/tender/mainProcurementCategory`.
- `compiledRelease/tender/value/amount` y `amount_PEN`.
- fechas de publicación, convocatoria, consultas y actualización.

### Partes y proveedores

- identificador, esquema, nombre legal y roles de las partes.
- dirección, departamento y país cuando están disponibles.
- proveedor adjudicado por `award_id`.
- ofertante por procedimiento.

### Ítems, adjudicaciones y contratos

- descripción, clasificación, cantidad, unidad, estado y valor del ítem.
- valor, moneda y fecha de adjudicación.
- contrato vinculado mediante `awardID`, con valor, periodo y fecha de firma.

## Advertencias de modelado

- `records.csv` es único por `ocid`; `releases.csv` conserva múltiples actualizaciones del mismo proceso.
- Partes, documentos, ítems, proveedores, adjudicaciones y contratos son relaciones uno-a-muchos.
- No unir tablas solo por `ocid` y luego sumar montos: se producirían duplicaciones por productos cartesianos.
- El campo `implementation/finalValue` tiene cobertura casi nula en el piloto y no debe sostener KPIs de ejecución.
- La clasificación principal de ítems de licitación tiene 17.41% de nulos en la muestra.
