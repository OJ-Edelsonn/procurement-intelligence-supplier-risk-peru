# ADR 0007: Carga atómica de snapshot en SQL Server

- Estado: aceptada
- Fecha: 2026-08-20

## Contexto

El piloto cabe en SQL Server Express y el modelo de Fase 6 representa el estado compilado actual por grano, no una serie de snapshots mensuales duplicados. Una carga incremental antes de definir retención e historia agregaría complejidad y podría violar las claves naturales.

## Decisión

1. Cargar las 22 tablas Silver en `stg` y los 16 objetos dimensionales en `dw`.
2. Usar Python y `pyodbc` para inserción parametrizada; T-SQL para DDL, constraints, índices y auditoría.
3. Ejecutar staging y DW en una sola transacción protegida con `sp_getapplock`.
4. Registrar auditoría fuera de la transacción de datos para conservar fallos.
5. Omitir una repetición cuyo origen, modelos, DDL y conteos sean idénticos.
6. Requerir `--replace-snapshot` para reemplazar datos poblados con otro contrato.
7. Reservar historia incremental y orquestación programada para la Fase 15.

## Consecuencias

- Nunca queda un warehouse parcialmente cargado.
- La reejecución exacta no duplica filas.
- El reemplazo completo es sencillo de recuperar y defender para el volumen piloto.
- Staging usa más espacio que Parquet porque prioriza trazabilidad relacional.
- Un snapshot mayor exigirá reevaluar tiempo, log y límite de 10 GB de Express.

## Alternativas descartadas

- **Carga fila por fila:** demasiado lenta y sin ventaja para este volumen.
- **Truncado fuera de transacción:** expone tablas vacías ante un fallo.
- **Incremental por `source_period` inmediato:** el modelo actual no es un snapshot fact y podría duplicar el mismo OCID.
- **SQLAlchemy como única abstracción:** aporta poco para DDL específico, constraints y auditoría de SQL Server.
- **BCP sin capa Python:** dificulta aplicar las reglas dimensionales y conservar una interfaz única reproducible.
