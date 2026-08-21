# Metodología de carga a SQL Server

## Problema que resuelve

Silver contiene 22 tablas Parquet tipadas, pero Power BI y las validaciones SQL necesitan un modelo relacional con claves, restricciones, índices y auditoría. La Fase 7 materializa esa transición sin modificar RAW ni Silver.

## Flujo físico

```text
22 Parquet Silver
    -> stg: réplica tipada y trazable
    -> Python: claves, canonización y medidas controladas
    -> dw: 8 dimensiones + 6 hechos + 2 puentes
    -> audit: lote, hashes, tiempos y conteos por tabla
```

Los esquemas cumplen responsabilidades distintas:

- `stg`: evidencia relacional del snapshot Silver; no contiene reglas analíticas nuevas.
- `dw`: constelación aprobada en Fase 6, con granos y restricciones explícitas.
- `audit`: ejecución, idempotencia y reconciliación técnica.

## Contratos gobernados

- Modelo lógico: `config/dimensional_model.yml`.
- Contrato físico: `config/sql_server.yml`.
- DDL versionado: `sql/ddl/`.
- Cargador: `src/procurement_intelligence/loading/load_sql_server.py`.

El lote guarda hashes del resumen ETL, modelo lógico, contrato físico y cada script DDL. El `ddl_bundle_sha256` evita considerar equivalente una carga cuyo SQL haya cambiado.

## Tipos de staging

| Arrow | SQL Server | Razón |
|---|---|---|
| string | `nvarchar(max)` | preservar texto Unicode sin truncar Silver |
| decimal128(38,14) | `decimal(38,14)` | conservar importes, cantidades y tasas |
| int64 | `bigint` | conservar posiciones y conteos fuente |
| boolean | `bit` | banderas DQ |
| date32 | `date` | snapshot |
| timestamp UTC | `datetime2(6)` | conservar microsegundos; el nombre declara UTC |

El cargador normaliza timestamps con zona a UTC sin zona antes de enviarlos a `datetime2(6)`. No convierte ni reescribe el Parquet.

## Estrategia de carga

El MVP usa `replace_current_snapshot`:

1. verifica hashes y evidencia de Fase 6;
2. crea la base solo cuando falta y nunca permite una base de sistema;
3. aplica DDL idempotente;
4. adquiere un `sp_getapplock` exclusivo;
5. prepara 22 tablas `stg`;
6. carga dimensiones, hechos y puentes en orden de dependencias;
7. compara las 38 tablas contra sus filas esperadas;
8. confirma una sola transacción.

Si falla cualquier tabla, SQL Server revierte staging y DW. Auditoría se actualiza mediante una conexión separada para conservar la causa del fallo.

Una base poblada con otro contrato requiere `--replace-snapshot`; no se borra implícitamente. Una repetición exacta valida hashes y conteos persistidos y termina como `SKIPPED_IDEMPOTENT`.

## Claves y reglas principales

- Las claves sustitutas son determinísticas para un mismo snapshot.
- Cada dimensión contiene exactamente un miembro técnico 0.
- Los hechos conservan su clave natural degenerada y una restricción `UNIQUE` de grano.
- Los puentes no contienen importes.
- Un monto solo se atribuye a proveedor cuando la adjudicación tiene exactamente uno.
- PEN solo se calcula con moneda PEN o tasa OECE disponible.
- Los índices siguen los filtros previstos por fecha, comprador, proveedor y categoría.

## Seguridad

- Autenticación integrada de Windows; no hay usuario ni password en código.
- `.env` no se versiona.
- Se rechazan `master`, `model`, `msdb` y `tempdb` como destino.
- Los identificadores SQL se validan y escapan antes de construir DDL dinámico de staging.
- Solo se modifican la base configurada y los esquemas `stg`, `dw` y `audit`.

## Ejecución

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.loading.load_sql_server `
  --create-database `
  --output reports\sql\oece_ocds_seace_v3_2026_07_sql_server_load.json
```

Para reemplazar conscientemente otro snapshot:

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.loading.load_sql_server `
  --create-database `
  --replace-snapshot `
  --output reports\sql\oece_ocds_seace_v3_2026_07_sql_server_load.json
```

El modo `--dry-run` construye y reconcilia todos los DataFrames sin conectarse a SQL Server.

## Conceptos para entrevista

- **Idempotencia:** repetir el mismo lote no duplica hechos; verifica evidencia y omite la escritura.
- **Atomicidad:** staging y DW se confirman juntos o se revierten juntos.
- **Grano:** una restricción natural por hecho evita cargar dos filas para el mismo evento lógico.
- **Auditoría separada:** un fallo debe dejar evidencia aunque la transacción de datos se revierta.
- **Clave desconocida:** preserva integridad referencial sin inventar una entidad real.

La carga incremental histórica se evaluará en la Fase 15. Para el volumen piloto, el reemplazo completo es más simple de explicar, probar y recuperar.
