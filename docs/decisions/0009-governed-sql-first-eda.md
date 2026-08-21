# ADR 0009: EDA gobernado SQL-first y reproducible

- Estado: aceptada
- Fecha: 2026-08-20

## Contexto

El modelo validado contiene hechos con granos distintos. Un EDA basado en joins ad hoc o en un notebook manual podría duplicar montos, mezclar etapas y producir resultados difíciles de repetir. Además, el piloto solo contiene un periodo fuente.

## Decisión

1. Exigir la puerta aprobada de Fase 8 antes de ejecutar EDA.
2. Definir datasets SQL pequeños y explícitos sobre `dw`.
3. Usar Python/pandas para perfiles y Matplotlib para figuras.
4. Generar JSON, Markdown y PNG desde un único comando.
5. Conservar ceros, faltantes y outliers; documentar su cobertura.
6. Mantener rankings como exploración, no KPI ni recomendación.
7. Bloquear conceptualmente crecimiento y YoY con un solo `source_period`.
8. Posponer HHI, concentración y scores a sus fases aprobadas.

## Consecuencias

- Cada cifra puede rastrearse a consulta, grano y lote.
- Las figuras se reconstruyen sin intervención manual.
- El EDA no modifica SQL Server ni RAW.
- Matplotlib se incorpora como dependencia directa y versionada.
- Las imágenes ocupan espacio en Git, pero son pequeñas, auditables y útiles para portafolio.

## Alternativas descartadas

- **Notebook único:** facilita exploración inicial, pero dificulta ejecución no interactiva, testing y generación estable.
- **Exportar una tabla ancha:** reintroduce joins muchos-a-muchos y riesgo de duplicación.
- **Calcular KPIs durante EDA:** salta la fase metodológica y confunde observación con definición de negocio.
- **Eliminar outliers automáticamente:** podría borrar contrataciones reales sin evidencia de error.
- **Inferir crecimiento desde fechas internas:** confunde fecha de negocio con snapshots históricos comparables.
