# Fase 14 — Estado funcional de Power BI

## Construido y verificado

- Proyecto PBIP versionable con 12 tablas semánticas, 5 páginas y 30 visuales nativos.
- Capa SQL `bi` con 3 tablas, 10 vistas, 266 filas de scores y 12 superficies de consulta.
- Modelo Import abierto correctamente en Power BI Desktop 2.157.879.0.
- Actualización completada y las cinco páginas pobladas: Resumen Ejecutivo, Oportunidad de Mercado, Supplier Intelligence, Supplier Exposure y Buyer Intelligence.
- Política explícita de no habilitar geografía sin una dimensión UBIGEO gobernada.

## Estado

La fase está **funcional pero no cerrada**. La revisión confirmó datos, medidas y visuales conectados; quedan pendientes unidades automáticas, etiquetas truncadas, encabezados técnicos, interacciones, actualización final y evidencia de validación definitiva.

## Protección durante la automatización

La Fase 15 no regenera el proyecto PBIP. `--include-powerbi` despliega únicamente la capa semántica SQL. Esta separación evita sobrescribir el trabajo manual pendiente.

## Evidencia disponible

- `config/powerbi_dashboard.yml`.
- `powerbi/project/ProcurementIntelligence.pbip`.
- `reports/powerbi/phase14_semantic_layer_load.json`.
- `reports/powerbi/screenshots/`.

El cierre requiere `reports/powerbi/phase14_powerbi_validation.json` y capturas finales posteriores al formato.

