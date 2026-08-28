# ADR 0014 — PBIP versionable sobre modelo Import gobernado

## Contexto

Power BI debe ser reproducible y consumir los resultados validados sin trasladar transformaciones opacas al informe.

## Decisión

1. Versionar un proyecto PBIP de texto, no un binario PBIX.
2. Usar modo Import desde tablas y vistas del esquema `bi` en SQL Server.
3. Mantener medidas explícitas y separar montos por grano.
4. Omitir visualización geográfica hasta disponer de UBIGEO gobernado.
5. No regenerar automáticamente el PBIP después de iniciar ajustes manuales.

## Consecuencias

El modelo y el informe pueden revisarse en Git; la publicación sigue siendo manual. Los cambios visuales requieren QA en Desktop y el pipeline solo actualiza la capa semántica cuando se solicita explícitamente.

