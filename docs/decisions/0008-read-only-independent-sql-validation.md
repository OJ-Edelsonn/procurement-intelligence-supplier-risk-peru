# ADR 0008: Validación SQL independiente y de solo lectura

- Estado: aceptada
- Fecha: 2026-08-21

## Contexto

La auditoría de carga de Fase 7 registra los conteos esperados por el mismo proceso que escribe las tablas. Repetir únicamente esos valores sería una comprobación circular. Al mismo tiempo, modificar el DW durante una validación mezclaría diagnóstico con tratamiento.

## Decisión

1. Ejecutar la Fase 8 sin modificar `stg`, `dw` ni `audit`.
2. Gobernar severidades y catálogo en `config/sql_validation.yml`.
3. Expresar integridad y lógica de negocio en T-SQL versionado.
4. Comparar filas contra auditoría y contra evidencia Python independiente.
5. Recalcular desde Silver los controles monetarios por moneda.
6. Tratar grano, referencias, linaje, atribución y reconciliaciones como bloqueantes.
7. Tratar incidencias oficiales preservadas como advertencias, sin elevarlas ni ocultarlas.
8. Versionar un JSON con hashes de entradas y scripts como evidencia de la corrida.

## Consecuencias

- La validación detecta tanto corrupción física como divergencia entre Python y SQL.
- No existe riesgo de que el propio diagnóstico “corrija” la evidencia.
- Los montos no se mezclan entre monedas durante la reconciliación.
- `PASS_WITH_WARNINGS` comunica aptitud técnica sin fingir datos perfectos.
- La corrida histórica reside por ahora en reportes versionados, no en una nueva tabla SQL.

## Alternativas descartadas

- **Validar solo constraints:** no detecta fórmulas, atribución ni diferencias entre capas.
- **Confiar solo en `audit.load_table`:** sería circular respecto del cargador.
- **Corregir datos en el script de validación:** rompe separación de responsabilidades y trazabilidad.
- **Convertir toda advertencia en bloqueo:** impediría analizar un snapshot técnicamente consistente por limitaciones conocidas del publicador.
- **Sumar moneda original sin agrupar:** produce un control sin significado financiero y puede ocultar compensaciones.
