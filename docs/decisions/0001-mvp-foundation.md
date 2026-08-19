# ADR 0001: Fundación del MVP

- Estado: aceptada
- Fecha: 2026-08-19

## Decisión

1. Centrar el MVP en procedimientos OCDS; tratar órdenes y riesgo V2 como módulos posteriores.
2. Analizar 2023–2025 completos y enero–julio de 2026, con comparación YTD homogénea.
3. Usar OCDS como fuente principal y XLSX complementarios para validación o universos separados.
4. Publicar el código en un repositorio público con licencia MIT.
5. Usar `main` como rama principal.
6. Aislar Python en `.venv` e instalar un conjunto mínimo de dependencias reproducibles.
7. Mantener datos masivos fuera de Git y definir su ruta local fuera de OneDrive antes de la ingesta.

## Consecuencias

- El primer entregable prioriza calidad, trazabilidad y granularidad antes que amplitud.
- Los indicadores deberán declarar universo, periodo y denominador.
- No se publicarán datos crudos ni archivos Power BI binarios en Git.
- Nuevas fuentes deberán justificar su valor y pasar controles antes de integrarse.
