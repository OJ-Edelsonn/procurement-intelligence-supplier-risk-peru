# Fase 7 — DDL y carga SQL Server

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Estado final | `PASS` |
| Base | `ProcurementIntelligence` |
| Motor | SQL Server 2022 Express 64-bit |
| Lote vigente | 4 |
| Modo | `replace_snapshot` atómico |
| Esquemas | 3 |
| Tablas staging | 22 |
| Tablas dimensionales | 16 |
| Tablas de auditoría | 2 |
| Reconciliaciones fallidas | 0 |
| Violaciones de constraints | 0 |

La base fue creada durante la primera ejecución de Fase 7. El lote final reutilizó esa base y reemplazó el snapshot dentro de una transacción.

## Filas cargadas

| Capa | Filas |
|---|---:|
| Silver → `stg` | 231,113 |
| Dimensiones | 26,592 |
| Hechos | 23,056 |
| Puentes | 37,511 |
| Total `dw` | 87,159 |

Los 23,056 hechos y 37,511 puentes coinciden con la evidencia de Fase 6. Los miembros técnicos explican la diferencia entre estimaciones de negocio y filas físicas de dimensiones.

## Rendimiento del lote 4

| Etapa | Segundos |
|---|---:|
| Construcción dimensional Python | 50.3862 |
| DDL, staging, DW y reconciliación SQL | 183.5160 |
| Total end-to-end | 233.9022 |

Equivale a 3 minutos y 53.90 segundos en el equipo local. No existe una línea base manual comparable, por lo que no se atribuye ahorro manual.

Tablas con mayor duración de inserción:

| Tabla | Filas | Segundos |
|---|---:|---:|
| `stg.release_history` | 80,789 | 40.77 |
| `stg.party` | 40,567 | 25.72 |
| `stg.tenderer` | 34,115 | 15.70 |
| `stg.tender_document` | 24,516 | 14.44 |
| `dw.bridge_process_tenderer` | 34,115 | 13.89 |

## Idempotencia

La reejecución con los mismos hashes validó las 38 tablas y terminó `SKIPPED_IDEMPOTENT` en 2.4882 segundos. Antes de optimizar el orden de verificación tardaba 64.0447 segundos; la reducción medida fue 96.115% sin cambiar datos.

Solo existe un lote vigente con el contrato físico final. La repetición no creó otro lote exitoso ni duplicó hechos.

## Fallos preservados y correcciones

Se conservaron dos intentos fallidos en `audit.load_batch`:

1. ODBC dimensionó un buffer textual desde la primera fila y falló ante una cadena posterior más larga. Se declaró el tamaño máximo real mediante `setinputsizes`; una prueba de 6,452 filas pasó antes de reintentar.
2. El miembro `__UNKNOWN__` excedió `nvarchar(10)` en `dim_currency.currency_code`. Se amplió a `nvarchar(20)` con migración idempotente.

Ambos intentos hicieron rollback completo. No dejaron staging parcial ni filas DW. Después se ejecutó una prueba transaccional de las 16 tablas dimensionales y todas pasaron antes del lote final.

## Auditoría y trazabilidad

- 38 métricas de tabla para el lote 4.
- Hash del archivo OECE, resumen ETL, modelo lógico y contrato físico.
- Hash individual de los cuatro DDL y `ddl_bundle_sha256`.
- Inicio, fin, duración, modo y conteos por capa.
- 0 claves sin resolver en puentes y 0 columnas monetarias en puentes.

La fase no incorpora una fuente externa nueva. Los datos derivan del mismo snapshot OECE/SEACE registrado en `docs/data_sources/source_registry.md`.

## Almacenamiento observado

SQL Server tenía asignados 328 MB al archivo de datos y 520 MB al log después de las cargas y rollbacks. Son tamaños asignados, no una medición del payload neto ni del límite consumido permanentemente.

## Pruebas

- 48 pruebas pytest.
- `compileall` de código y pruebas.
- `pip check` sin dependencias rotas.
- Dry run completo.
- Inserción real de prueba de 6,452 filas staging con rollback.
- Inserción real de 16 tablas DW con rollback.
- Lote 4 completo con commit.
- 38/38 conteos reconciliados.
- `DBCC CHECKCONSTRAINTS`: 0 violaciones.
- Reejecución idempotente: 2.4882 segundos.

## Limitaciones

- El servicio `SQLEXPRESS` se inicia manualmente en este equipo.
- La estrategia actual reemplaza el snapshot; todavía no conserva historia mensual DW.
- Staging prioriza preservación mediante `nvarchar(max)`, no mínima ocupación.
- SQL Server Express tiene límite operativo de 10 GB por base.
- La validación analítica SQL y comparación Python↔SQL pertenecen a la Fase 8.

## Evidencia

- `reports/sql/oece_ocds_seace_v3_2026_07_sql_server_load.json`.
- `config/sql_server.yml`.
- `sql/ddl/`.
- `sql/validation/phase7_load_reconciliation.sql`.
- `docs/methodology/sql_server_load.md`.
