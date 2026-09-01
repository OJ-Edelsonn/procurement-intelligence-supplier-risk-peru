# Fase 14 — Cierre de Power BI

## Construido y verificado

- Proyecto PBIP versionable con 12 tablas semánticas, 5 páginas y 30 visuales nativos.
- Capa SQL `bi` con 3 tablas, 10 vistas, 266 filas de scores y 12 superficies de consulta.
- Modelo Import abierto correctamente en Power BI Desktop 2.157.879.0.
- Actualización final completada en 200 segundos y cinco páginas pobladas: Resumen Ejecutivo, Oportunidad de Mercado, Inteligencia de Proveedores, Exposición de Proveedores e Inteligencia de Compradores.
- Unidades de tarjetas y ejes, encabezados, etiquetas, ordenamientos y tablas revisados.
- Cinco capturas finales sin interfaz de edición, con resolución mínima de 1,364 × 789 píxeles.
- Política explícita de no habilitar geografía sin una dimensión UBIGEO gobernada.

## Estado

La fase está **completa**. `reports/powerbi/phase14_powerbi_validation.json` terminó `PASS` con 8/8 controles: estructura PBIP, nombres de página, inventario visual, orden de rankings, capturas, actualización final y revisión visual colaborativa.

## Protección durante la automatización

La Fase 15 no regenera el proyecto PBIP. `--include-powerbi` despliega únicamente la capa semántica SQL. Esta separación evita sobrescribir el trabajo manual pendiente.

## Evidencia disponible

- `config/powerbi_dashboard.yml`.
- `powerbi/project/ProcurementIntelligence.pbip`.
- `reports/powerbi/phase14_semantic_layer_load.json`.
- `reports/powerbi/phase14_powerbi_validation.json`.
- `reports/powerbi/screenshots/`.

La publicación en Power BI Service o mediante enlace público permanece como una actividad de distribución posterior y no altera el cierre técnico local.
