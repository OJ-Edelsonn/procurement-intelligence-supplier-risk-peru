# ADR 0004: Puertas de Data Quality antes de Silver

- Estado: aceptada
- Fecha: 2026-08-20

## Contexto

El piloto contiene relaciones consistentes y medidas utilizables, pero también duplicados, claves incompletas, identificadores no conformes y campos con cobertura insuficiente. Continuar directamente al ETL ocultaría la diferencia entre un defecto bloqueante y una limitación analítica.

## Decisión

1. Versionar las reglas en YAML y ejecutarlas fuera de Power BI.
2. Usar severidades `critical`, `error`, `warning` e `info`.
3. Bloquear promoción cuando falle una regla `critical` o `error`.
4. Conservar RAW intacto y registrar el tratamiento en Silver.
5. Mantener métricas antes/después por regla, sin sumar incidencias como filas únicas.
6. Tratar cobertura insuficiente como aptitud para uso, no automáticamente como dato inválido.
7. No corregir RUC, clasificaciones o montos cero sin una regla y evidencia confiables.

## Consecuencias

- El lote piloto queda `BLOCKED` hasta resolver la unicidad en Fase 5.
- Los KPIs futuros podrán declarar qué reglas y cobertura los respaldan.
- Las advertencias no se confunden con fraude, sanción ni error legal.
- Incorporar otro mes o fuente exige ejecutar el mismo catálogo y revisar schema drift.

## Alternativas descartadas

- **Limpiar primero y medir después:** pierde la línea base y oculta descartes.
- **Un único porcentaje global de calidad:** mezcla granularidades y dimensiones no comparables.
- **Eliminar toda fila incompleta:** puede sesgar mercado, proveedores y categorías.
- **Validar únicamente en Power BI:** dificulta automatización, trazabilidad y pruebas.
