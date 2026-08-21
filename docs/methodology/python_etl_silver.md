# ETL Python de RAW a Silver

## Propósito y alcance

La Fase 5 transforma el ZIP CSV oficial conservado en RAW en 22 tablas Parquet tipadas. El proceso resuelve el bloqueo de unicidad detectado en la Fase 4, hace visibles las limitaciones de calidad y agrega linaje fila a fila.

Esta fase no construye todavía el modelo dimensional, no carga SQL Server y no calcula KPIs. RAW es inmutable: el ETL solo lo lee y escribe en `interim/staging`, `interim/quarantine` y `metadata` fuera del repositorio.

## Contrato gobernado

El contrato canónico es `config/etl_silver.yml`. Define:

- las 22 tablas de entrada y su nombre estable en Silver;
- tipos lógicos y físicos;
- precisión decimal, compresión y tamaño de row group;
- tratamientos autorizados para duplicados, clasificaciones y señales de calidad;
- métricas que deben ser cero para promover el lote.

El validador rechaza configuraciones incompletas, nombres de salida duplicados, precisión fuera del límite de Arrow o tablas de clasificación no mapeadas.

## Flujo

```text
ZIP CSV RAW (solo lectura)
  -> validar contrato y correspondencia de 22 tablas
  -> recortar espacios de borde y medir cambios
  -> medir grano y duplicados antes
  -> aplicar tratamientos autorizados
  -> convertir nombres y tipos estrictos
  -> agregar banderas de calidad y linaje
  -> escribir Parquet atómico por tabla
  -> reconciliar filas y volver a medir después
  -> escribir cuarentena y manifiestos
```

Cada salida usa particiones legibles:

```text
${DATA_ROOT}/interim/staging/oece_ocds/<tabla>/source_period=YYYY-MM/snapshot_date=YYYY-MM-DD/part-00000.parquet
```

Los duplicados aislados se escriben en:

```text
${DATA_ROOT}/interim/quarantine/DQ-DUP-001/ingestion_run_id=<uuid>/<tabla>.parquet
```

## Nombres y tipos

Los paths OCDS se convierten a `lower_snake_case`; por ejemplo, `compiledRelease/tender/value/amount` pasa a `compiled_release_tender_value_amount`. El ETL falla si dos columnas convergen al mismo nombre.

| Concepto | Tipo Parquet | Criterio |
|---|---|---|
| Montos, cantidades y tasas | `decimal128(38,14)` | Preserva la precisión observada sin redondeo de negocio. |
| Posiciones, duraciones y conteos | `int64` | Rechaza valores no numéricos o fraccionarios. |
| Indicadores | `bool` | Solo admite valores booleanos gobernados. |
| Fechas de negocio | `timestamp[us, UTC]` | Rechaza fechas no interpretables. |
| Fecha de snapshot | `date32` | Partición y linaje del lote. |
| Identificadores y texto | `string` | Evita perder ceros o reinterpretar códigos. |

La compresión es Zstandard y cada tabla usa un row group máximo de 50,000 filas.

## Tratamientos autorizados

| Hallazgo RAW | Tratamiento Silver | Evidencia conservada |
|---|---|---|
| Duplicados exactos adicionales en tasas de ítem de licitación | Conservar la primera ocurrencia y enviar las demás a cuarentena. | Fila RAW original, regla, razón y linaje. |
| Clasificación incompleta | Completar solo componentes nulos con `__UNCLASSIFIED__`, `Sin clasificar` y `UNKNOWN`. | `dq_classification_was_missing=true`. |
| RUC con formato distinto de 11 dígitos numéricos | Mantener el identificador publicado. | `dq_ruc_format_valid=false`; `null` si el esquema no es `PE-RUC`. |
| Valor de licitación igual a cero | Mantener el valor. | `dq_tender_value_is_zero=true`. |
| `finalValue` ausente | Mantener el nulo. | `dq_final_value_available=false`. |

El miembro “Sin clasificar” no imputa UNSPSC. Las banderas RUC, monto cero y valor final tampoco afirman fraude, error legal ni desempeño contractual.

## Linaje por fila

Todas las tablas aceptadas y la cuarentena incluyen:

- `source_id`;
- `source_period`;
- `snapshot_date`;
- `ingestion_run_id`;
- `source_file_name`;
- `source_file_sha256`;
- `source_table_name`;
- `source_row_number`;
- `loaded_at_utc`.

`source_row_number` es la posición de datos dentro del CSV, empezando en 1 después de la cabecera. El `ingestion_run_id` es UUID5 determinístico de fuente, periodo, snapshot, hash RAW y hash del contrato; un mismo lote y contrato reciben el mismo identificador.

## Escritura segura e idempotencia

- Cada Parquet se crea primero como archivo temporal y se reemplaza atómicamente.
- Una salida existente detiene la ejecución salvo que el operador use `--overwrite` explícitamente.
- La opción de sobrescritura alcanza únicamente las rutas Silver calculadas para el mismo periodo y snapshot; nunca el RAW.
- El manifiesto completo queda bajo `${DATA_ROOT}/metadata`; el resumen versionado elimina rutas absolutas privadas.
- El CLI registra inicio y resultado por tabla; el manifiesto conserva filas, bytes, hashes, duración, tipos y métricas antes/después.

## Puerta posterior

El lote es elegible para promoción solo si quedan en cero:

- duplicados exactos adicionales;
- claves de grano nulas;
- granos candidatos duplicados;
- clasificaciones incompletas.

Las advertencias preservadas producen `PASS_WITH_WARNINGS`, no un `PASS` ficticio.

## Reproducción

```powershell
$archive = "C:\Data\procurement-intelligence-supplier-risk-peru\raw\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\2026-07_seace_v3_csv.zip"

.\.venv\Scripts\python.exe -m procurement_intelligence.transformation.transform_ocds_silver `
  $archive `
  --config config\etl_silver.yml `
  --source-period 2026-07 `
  --snapshot-date 2026-08-19 `
  --env-file .env `
  --summary-output reports\etl\oece_ocds_seace_v3_2026_07_etl_summary.json
```

No usar `--overwrite` en la primera ejecución. En una repetición controlada, revisar primero que las rutas correspondan al mismo lote.

## Limitaciones

- El contrato se validó con el snapshot piloto de julio de 2026; cada mes adicional debe pasar controles de schema drift.
- `decimal128(38,14)` conserva la precisión publicada, pero una regla monetaria futura deberá definir escala de presentación sin alterar la capa Silver.
- Silver resuelve calidad estructural para el modelado; no convierte automáticamente todos los campos en aptos para KPIs.
- La baja cobertura de `finalValue` continúa impidiendo un KPI representativo de ejecución final.
