# Fase 16 — Metodología de benchmark y medición

## Principios

1. Usar únicamente artefactos gobernados y consultas SQL de solo lectura.
2. Separar tiempo de pared del orquestador y tiempos internos declarados por componentes.
3. No sumar montos de hechos diferentes.
4. No presentar una suma de tiempos históricos como una única corrida.
5. No calcular ahorro ni reducción porcentual sin una línea base manual observada.

## Tiempos

`config/benchmark.yml` declara cada artefacto y ruta JSON usada como evidencia. La corrida automatizada proviene del reporte de Fase 15. Los componentes proceden de ejecuciones documentadas y su suma se publica únicamente como referencia acumulada.

## SQL

Tres consultas representativas se ejecutan sobre una conexión reutilizada:

- resumen ejecutivo del DW;
- ranking de proveedores;
- concentración por categoría.

Cada consulta realiza un calentamiento y tres repeticiones. Se informan mínimo, media, mediana, p95 interpolado, máximo y muestras. Las consultas no modifican la base.

## Resultados de negocio y calidad

Los conteos, montos y porcentajes se extraen por ruta o identificador desde profiling, ETL, modelo dimensional, carga SQL, KPIs y scores. Cada métrica conserva ruta y SHA-256 del artefacto fuente.

## Límites de interpretación

El benchmark caracteriza un equipo local y SQL Server Express bajo su carga concreta. No representa capacidad de producción, concurrencia empresarial ni SLA. El dashboard congelado registró una actualización final manualmente cronometrada de 200 segundos; se conserva como una observación local única, no como compromiso de rendimiento.
