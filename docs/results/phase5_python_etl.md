# Fase 5 — ETL Python RAW a Silver

## Muestra procesada

| Atributo | Valor |
|---|---|
| Fuente | OECE, SEACE V3 OCDS |
| Periodo fuente | Julio de 2026 |
| Snapshot | 2026-08-19 |
| Archivo RAW | `2026-07_seace_v3_csv.zip` |
| SHA-256 RAW | `024ef9eb7a282de74559ea78ba149ff87aa041d7c92947795ac354d49f0ba4e8` |
| Contrato | `config/etl_silver.yml` |
| Tablas | 22 |
| Tiempo observado en la ejecución final | 59.3069 s |

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Filas RAW acumuladas | 231,123 |
| Filas Silver | 231,113 |
| Filas en cuarentena | 10 |
| Filas descartadas sin trazabilidad | 0 |
| Clasificaciones normalizadas | 2,135 |
| RUC inválidos señalizados | 1,797 |
| Montos de licitación cero señalizados | 1,752 |
| `finalValue` ausentes señalizados | 1,116 |
| Tamaño ZIP RAW | 8,052,765 bytes |
| Tamaño CSV descomprimido | 65,839,313 bytes |
| Tamaño Parquet total | 9,084,200 bytes |
| Reducción frente a CSV descomprimido | 86.2025% |
| Estado del lote | `PASS_WITH_WARNINGS` |
| Elegible para promoción | Sí |

La reconciliación cierra exactamente: `231,123 RAW = 231,113 Silver + 10 cuarentena`. No se descartó ninguna fila sin registro de tratamiento.

El conjunto Parquet es 12.8085% mayor que el ZIP ya comprimido, pero 86.2025% menor que sus CSV descomprimidos. La elección de Parquet se justifica además por tipos, lectura columnar y metadatos; no se presenta como una mejora frente al ZIP en tamaño puro.

## Comparación antes y después

| Regla | Métrica | RAW antes | Silver después |
|---|---|---:|---:|
| `DQ-UNIQ-001` | Incumplimientos del grano candidato | 11 | 0 |
| `DQ-DUP-001` | Duplicados exactos adicionales | 10 | 0 |
| `DQ-CAT-001` | Clasificaciones incompletas | 2,135 | 0 |
| `DQ-ID-001` | RUC con formato inválido señalizados | 1,797 | 1,797 |
| `DQ-FIT-001` | `finalValue` ausente señalizado | 1,116 | 1,116 |
| `DQ-BIZ-001` | Valor de licitación cero señalizado | 1,752 | 1,752 |

Las tres primeras métricas se resolvieron mediante deduplicación controlada o un miembro desconocido explícito. Las demás permanecen iguales porque se conservaron los valores publicados y se añadieron banderas; reducir esos conteos sin una fuente confiable habría sido una corrección artificial.

La completitud técnica de los tres componentes de clasificación pasa de 90.3139% a 100% al representar la ausencia mediante “Sin clasificar”. Esto no mejora la completitud del publicador: las 2,135 ausencias originales siguen identificables mediante la bandera de calidad.

## Reconciliación por tabla

| Tabla RAW | Tabla Silver | RAW | Silver | Cuarentena | Clasificación desconocida |
|---|---|---:|---:|---:|---:|
| `records.csv` | `procurement_process` | 6,452 | 6,452 | 0 | 0 |
| `releases.csv` | `release_history` | 80,789 | 80,789 | 0 | 0 |
| `com_sources.csv` | `process_source` | 6,452 | 6,452 | 0 | 0 |
| `com_parties.csv` | `party` | 40,567 | 40,567 | 0 | 0 |
| `com_par_additionalIdentifiers.csv` | `party_additional_identifier` | 6,452 | 6,452 | 0 | 0 |
| `com_ten_tenderers.csv` | `tenderer` | 34,115 | 34,115 | 0 | 0 |
| `com_ten_documents.csv` | `tender_document` | 24,516 | 24,516 | 0 | 0 |
| `com_ten_items.csv` | `tender_item` | 7,359 | 7,359 | 0 | 1,281 |
| `com_ten_ite_additionalClassific.csv` | `tender_item_classification` | 6,078 | 6,078 | 0 | 1 |
| `com_ten_ite_tot_exchangeRates.csv` | `tender_item_exchange_rate` | 120 | 110 | 10 | 0 |
| `com_awards.csv` | `award` | 3,397 | 3,397 | 0 | 0 |
| `com_awa_suppliers.csv` | `award_supplier` | 3,396 | 3,396 | 0 | 0 |
| `com_awa_items.csv` | `award_item` | 3,590 | 3,590 | 0 | 648 |
| `com_awa_ite_additionalClassific.csv` | `award_item_classification` | 2,942 | 2,942 | 0 | 0 |
| `com_awa_ite_tot_exchangeRates.csv` | `award_item_exchange_rate` | 86 | 86 | 0 | 0 |
| `com_awa_val_exchangeRates.csv` | `award_value_exchange_rate` | 86 | 86 | 0 | 0 |
| `com_contracts.csv` | `contract` | 1,119 | 1,119 | 0 | 0 |
| `com_con_documents.csv` | `contract_document` | 1,414 | 1,414 | 0 | 0 |
| `com_con_items.csv` | `contract_item` | 1,139 | 1,139 | 0 | 205 |
| `com_con_ite_additionalClassific.csv` | `contract_item_classification` | 934 | 934 | 0 | 0 |
| `com_con_ite_tot_exchangeRates.csv` | `contract_item_exchange_rate` | 60 | 60 | 0 | 0 |
| `com_con_val_exchangeRates.csv` | `contract_value_exchange_rate` | 60 | 60 | 0 | 0 |
| **Total** |  | **231,123** | **231,113** | **10** | **2,135** |

## Validaciones realizadas

- Lectura física de los 22 Parquet y reconciliación contra el manifiesto.
- Lectura física de la cuarentena y confirmación de 10 filas.
- Tipos Arrow confirmados, incluidos `decimal128(38,14)`, `int64`, `bool`, `date32` y timestamps UTC.
- Linaje obligatorio presente en cada tabla y en cuarentena.
- Hash RAW posterior igual al hash registrado antes del ETL.
- Cuatro métricas bloqueantes posteriores iguales a cero.
- Resumen versionado sin rutas locales absolutas.
- Pruebas unitarias de deduplicación, clasificación, RUC, tipos y reconciliación.

## Interpretación y riesgos remanentes

- La promoción técnica a Silver es válida, pero `PASS_WITH_WARNINGS` conserva limitaciones reales.
- Los 1,797 identificadores señalizados requieren una fuente registral autorizada antes de cualquier enriquecimiento; no se deben corregir por inferencia.
- Los 1,752 montos cero deben segmentarse o excluirse solo mediante una regla de KPI aprobada.
- Con 3 de 1,119 valores finales informados en RAW, `finalValue` sigue sin ser apto para medir ejecución contractual.
- El siguiente modelado debe separar los granos de proceso, parte, ítem, adjudicación y contrato para evitar dobles conteos.

## Evidencia

- Fuente y adquisición: `docs/data_sources/source_registry.md`.
- Contrato ETL: `config/etl_silver.yml`.
- Metodología: `docs/methodology/python_etl_silver.md`.
- Resumen reproducible: `reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json`.
- Manifiesto completo local: `${DATA_ROOT}/metadata/oece/ocds/seace_v3/2026/07/snapshot_date=2026-08-19/etl_phase5_full.json`.
- Cuarentena local: `${DATA_ROOT}/interim/quarantine/DQ-DUP-001/ingestion_run_id=fa582ba3-0cbb-5b98-b483-5a3c9f9ef945/`.
