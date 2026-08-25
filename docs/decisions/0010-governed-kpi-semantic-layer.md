# ADR 0010: Capa semántica de KPIs gobernados

- Estado: aceptada
- Fecha: 2026-08-24

## Contexto

El EDA encontró métricas descriptivas útiles, pero también granos incompatibles, un solo periodo fuente y coberturas incompletas. Publicar indicadores sin contrato permitiría sumar etapas, ocultar denominadores o presentar tendencias inexistentes.

## Decisión

1. Declarar cada KPI en YAML con dominio, grano, unidad y estado de publicación.
2. Calcular en SQL desde el hecho nativo y reconciliar en Python.
3. Mantener separados los montos licitado, adjudicado y contractual.
4. Publicar numerador y denominador junto con los porcentajes y tickets.
5. Versionar medidas DAX equivalentes para el futuro modelo Power BI.
6. Bloquear crecimiento, geografía, valor final, concentración y scores hasta cumplir sus prerrequisitos.

## Consecuencias

- Los indicadores son trazables y reproducibles.
- Power BI recibirá medidas ya definidas, no cálculos ad hoc.
- El dashboard piloto puede mostrar escala y cobertura sin afirmar tendencia.
- Algunas preguntas de negocio permanecen deliberadamente sin respuesta hasta cargar historia o fuentes adicionales.

## Alternativas descartadas

- **Una tabla ancha de KPIs:** mezcla granos y dificulta filtros dimensionales.
- **Calcular todo en Power BI:** reduce la validación independiente SQL↔Python↔DAX.
- **Usar fechas internas para YoY:** confunde fechas de negocio con snapshots comparables.
- **Ocultar métricas no disponibles:** se prefirió registrarlas como bloqueadas con motivo verificable.
