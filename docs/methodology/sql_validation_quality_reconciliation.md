# Validación SQL, calidad y reconciliación avanzada

## Problema que resuelve

Una carga que termina sin error no demuestra por sí sola que el modelo sea correcto. La Fase 8 comprueba, de forma independiente y reproducible, que SQL Server conserva el grano, las relaciones, las reglas de atribución, los cálculos y los totales que fueron aprobados en Python.

El contrato canónico está en `config/sql_validation.yml`; las reglas se ejecutan desde `src/procurement_intelligence/validation/validate_sql_server.py` y su lógica observable permanece en `sql/validation/phase8_*.sql`.

## Triangulación de evidencia

La validación no confía en un único conteo:

```text
Silver Parquet y reportes Python
             ↓ expectativa externa
SQL Server actual ↔ audit.load_table de Fase 7
             ↓
      reporte de Fase 8
```

Para cada tabla se comparan cuatro valores: filas físicas mediante `COUNT_BIG`, filas esperadas y cargadas de auditoría, y filas esperadas desde los artefactos Python. Una coincidencia entre SQL y su propia auditoría no basta si contradice Silver o el análisis dimensional.

## Familias de controles

| Familia | Qué comprueba | Efecto |
|---|---|---|
| Estructura | 22 tablas `stg`, 16 `dw`, PK, `UNIQUE`, `CHECK`, FK e índices clustered | Bloqueante |
| Auditoría | lote exitoso, 38 tablas auditadas y conteos físicos iguales | Bloqueante |
| Dimensiones | un miembro 0 por dimensión y calendario continuo | Bloqueante |
| Grano | unicidad de los seis hechos y dos puentes | Bloqueante |
| Referencial | `DBCC CHECKCONSTRAINTS` y contrato→adjudicación | Bloqueante |
| Linaje | fuente, periodo, snapshot y corrida iguales al lote activo | Bloqueante |
| Negocio | conteos de puentes y atribución monetaria con proveedor único | Bloqueante |
| Cálculo | conversión PEN, reconciliación header–ítem y banderas DQ | Bloqueante |
| Calidad observada | RUC, conflictos, montos discordantes, tasas faltantes y cobertura | Advertencia |

Los controles bloqueantes usan tolerancia cero porque una sola infracción puede duplicar montos, romper una relación o hacer irreproducible un cálculo. Las advertencias también hacen visible cada caso, pero no rechazan el snapshot cuando la incidencia proviene del dato oficial y la limitación está documentada.

## Reconciliación monetaria

Los importes originales se reconcilian por `control_id + currency_code`; nunca se presenta como total de negocio una suma que mezcle PEN, USD, EUR o GBP.

Para siete medidas se calcula en forma independiente:

- cantidad de filas;
- cantidad de importes no nulos;
- suma decimal exacta a escala 14;
- comparación Silver↔`stg` y Silver↔`dw`.

Los controles abarcan licitación y presupuesto de proceso, ítems de licitación, adjudicación, ítems adjudicados, contrato e ítems contractuales. El resultado genera 52 comparaciones porque las combinaciones reales control–moneda se contrastan en dos capas SQL.

### Precisión decimal en conversiones

SQL Server reduce la escala intermedia cuando multiplica dos `decimal(38,14)`. La regla de conversión usa operandos acotados antes de multiplicar y vuelve a `decimal(38,14)`, evitando que una reducción interna a seis decimales produzca falsos positivos. No se redondean ni modifican los importes almacenados.

## Reglas de atribución

Un puente resuelve una relación muchos-a-muchos, pero no autoriza a repetir el monto del padre. Por ello:

- `bridge_process_tenderer` y `bridge_award_supplier` no pueden contener columnas monetarias;
- una adjudicación recibe `attributed_supplier_key` solo cuando existe exactamente un proveedor oficial;
- los ítems adjudicados heredan esa decisión;
- contratos e ítems contractuales heredan únicamente una adjudicación resuelta;
- cualquier otro caso conserva la clave desconocida 0.

Esta regla previene doble conteo y no inventa una distribución entre proveedores.

## Estados

- `BLOCKED`: existe una regla `error` fallida o cualquier reconciliación externa falla.
- `PASS_WITH_WARNINGS`: no existe fallo bloqueante, pero hay incidencias oficiales observadas.
- `PASS`: no existen fallos ni advertencias con casos.

`promotion_eligible=true` significa que el DW es técnicamente apto para iniciar análisis. No significa que cada campo sea apto para cualquier KPI. Por ejemplo, la baja cobertura de `finalValue` mantiene ese KPI aplazado.

## Ejecución

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.validation.validate_sql_server `
  --config config\sql_validation.yml `
  --env-file .env `
  --output reports\sql\oece_ocds_seace_v3_2026_07_phase8_validation.json
```

El comando instalado equivalente es:

```powershell
.\.venv\Scripts\validate-sql-server.exe `
  --output reports\sql\oece_ocds_seace_v3_2026_07_phase8_validation.json
```

`--strict-warnings` devuelve código 2 cuando existen advertencias. Sin esa opción, un resultado `PASS_WITH_WARNINGS` devuelve código 0; un `BLOCKED` siempre devuelve código 1.

La ejecución es de solo lectura: consulta `stg`, `dw`, `audit` y metadatos del motor, pero no altera tablas ni convierte los hallazgos en correcciones silenciosas.

## Qué comprender para una entrevista

1. **Reconciliación independiente:** validar SQL contra una expectativa generada fuera de SQL evita una comprobación circular.
2. **Grano antes del monto:** una suma solo es segura si la tabla y sus relaciones conservan la unidad de observación.
3. **Advertencia no es fallo técnico:** una incidencia oficial puede mantenerse visible sin invalidar todo el lote.
4. **Control total no es KPI:** una suma usada para demostrar igualdad técnica no necesariamente tiene interpretación de negocio.
5. **Trazabilidad:** cada resultado conserva hashes de configuración, scripts y evidencias de fases anteriores.

## Limitaciones

- La evidencia corresponde al piloto OECE/SEACE de julio de 2026.
- Las reglas prueban consistencia y reproducibilidad, no veracidad legal del dato publicado.
- El formato estructural de RUC no sustituye una consulta registral vigente.
- La fase no crea KPIs, métricas de concentración ni scores.
- La persistencia histórica de ejecuciones de validación en SQL se evaluará con la automatización de la Fase 15; por ahora el JSON versionado es la evidencia.
