# Diccionario físico de SQL Server

## Base y esquemas

- Base local: `ProcurementIntelligence`.
- Motor validado: SQL Server 2022 Express, 64 bits.
- `stg`: 22 tablas derivadas uno-a-uno de Silver.
- `dw`: 16 tablas dimensionales.
- `audit`: 2 tablas de ejecución.

Los tamaños declarados completos están en `sql/ddl`; este documento resume propósito y restricciones.

## Auditoría

| Tabla | Grano | Uso |
|---|---|---|
| `audit.load_batch` | un intento de carga | fuente, periodo, snapshot, hashes, estado, duración y totales |
| `audit.load_table` | tabla por lote | filas esperadas/cargadas y duración individual |

`ddl_bundle_sha256` representa los cuatro DDL ejecutados. Los fallos permanecen registrados aunque las tablas de datos hayan hecho rollback.

## Staging

Cada tabla `stg` conserva exactamente los nombres normalizados y el linaje de su Parquet Silver. La tabla se recrea dentro de la transacción del snapshot para reflejar su esquema tipado actual.

| Familia | Tablas |
|---|---|
| Proceso e historia | `procurement_process`, `release_history`, `process_source` |
| Partes | `party`, `party_additional_identifier`, `tenderer` |
| Licitación | `tender_document`, `tender_item`, clasificación y tasa de ítem |
| Adjudicación | `award`, `award_supplier`, `award_item`, clasificación y tasas |
| Contrato | `contract`, `contract_document`, `contract_item`, clasificación y tasas |

## Dimensiones

| Tabla | PK | Restricción natural | Filas lote 4 |
|---|---|---|---:|
| `dw.dim_date` | `date_key` | `full_date` | 2,136 |
| `dw.dim_process` | `process_key` | `ocid` | 6,453 |
| `dw.dim_buyer` | `buyer_key` | `source_party_id` | 1,451 |
| `dw.dim_supplier` | `supplier_key` | `source_party_id` | 12,821 |
| `dw.dim_category` | `category_key` | esquema + código | 3,690 |
| `dw.dim_procurement_method` | `procurement_method_key` | método + detalle | 20 |
| `dw.dim_currency` | `currency_key` | código | 5 |
| `dw.dim_unit` | `unit_key` | esquema + código | 16 |

Los conteos incluyen el miembro técnico 0, salvo categoría, cuyo registro `UNKNOWN/__UNCLASSIFIED__` ya formaba parte de las 3,690 claves observadas.

## Hechos

| Tabla | Grano físico único | Filas lote 4 |
|---|---|---:|
| `dw.fact_procurement_process` | proceso | 6,452 |
| `dw.fact_tender_item` | proceso + ítem | 7,359 |
| `dw.fact_award` | proceso + adjudicación | 3,397 |
| `dw.fact_award_item` | proceso + adjudicación + ítem | 3,590 |
| `dw.fact_contract` | proceso + contrato | 1,119 |
| `dw.fact_contract_item` | proceso + contrato + ítem | 1,139 |

Todos incluyen claves foráneas, clave técnica del hecho, conteo igual a 1, medidas de su grano, banderas DQ y linaje Silver.

## Puentes

| Tabla | Grano | Filas lote 4 |
|---|---|---:|
| `dw.bridge_process_tenderer` | proceso + ofertante | 34,115 |
| `dw.bridge_award_supplier` | proceso + adjudicación + proveedor | 3,396 |

Solo admiten `participation_count = 1`. No existe columna monetaria.

## Convenciones físicas

- Importes, cantidades y tasas: `decimal(38,14)`.
- Claves sustitutas de dimensiones: `int`; hechos y puentes: `bigint`.
- Fechas role-playing: `int YYYYMMDD`, con 0 para desconocido.
- Timestamps de linaje: `datetime2(6)` interpretado como UTC.
- IDs: `nvarchar` con límites definidos por dominio.
- Descripciones extensas: `nvarchar(max)`.
- Banderas: `bit`.

El diccionario lógico y la aditividad permanecen en `docs/data_dictionary/dimensional_model.md`.
