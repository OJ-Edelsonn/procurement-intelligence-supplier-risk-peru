# Alcance y limitaciones

## Alcance funcional del MVP

- Perfilado y descarga controlada de datos OCDS oficiales.
- Transformaciones reproducibles con Python.
- Persistencia analítica en SQL Server Express.
- Modelo semántico y visualización en Power BI Desktop.
- Indicadores descriptivos de demanda, competencia, concentración y exposición.
- Trazabilidad técnica, pruebas y documentación de decisiones.

## Cobertura temporal

| Uso | Desde | Hasta | Tratamiento |
|---|---:|---:|---|
| Histórico | 2023-01-01 | 2025-12-31 | Años completos |
| YTD actual | 2026-01-01 | 2026-07-31 | Periodo parcial |
| Comparación YTD | 2025-01-01 | 2025-07-31 | Mismo corte mensual |

## Limitaciones conocidas

- La publicación abierta puede tener correcciones, rezagos o cambios de esquema; cada extracción debe versionarse.
- Un procedimiento puede contener múltiples ítems, adjudicaciones, proveedores y contratos. Sumar columnas después de joins muchos-a-muchos puede duplicar montos.
- La ausencia de registros no demuestra ausencia de actividad; puede responder a cobertura, reglas de publicación o calidad de origen.
- Las señales de concentración o exposición son descriptivas y requieren contexto. No constituyen una acusación de fraude, colusión o incumplimiento.
- Las órdenes y otros archivos complementarios no se integrarán al universo OCDS hasta validar llaves, cobertura y granularidad.
- SQL Server Express impone límites de capacidad; el diseño deberá monitorear tamaño y rendimiento.
- Los archivos crudos permanecerán fuera de Git y, por decisión pendiente, en una ruta local fuera de OneDrive.

## Reglas para comunicar resultados

- Mostrar moneda, periodo, universo y denominador de cada métrica.
- Diferenciar montos licitados, adjudicados y contratados.
- Evitar comparar un año completo con un YTD.
- Permitir trazabilidad hacia entidad, proveedor, proceso e ítem cuando la fuente lo soporte.
- Publicar advertencias cuando la cobertura o calidad limite una conclusión.
