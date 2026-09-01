# ADR 0016 — Benchmark basado en evidencia sin línea base inventada

## Contexto

El proyecto necesita resultados cuantificables para portafolio y CV, pero no existe una medición manual previa comparable.

## Decisión

Publicar tiempos observados, volúmenes, calidad, compresión, métricas de negocio y latencia SQL con artefacto y hash. Declarar la línea base manual como `NOT_AVAILABLE` y `time_savings_claimed: false`.

## Consecuencias

Se pueden comunicar resultados verificables del sistema, incluido el refresco final de Power BI de 200 segundos, pero no horas ahorradas, reducción porcentual, adopción empresarial ni impacto comercial realizado. La medición de Power BI es una observación local única y no un SLA.
