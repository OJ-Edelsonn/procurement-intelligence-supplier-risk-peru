# Checklist de publicación final

## Datos y gobierno

- [x] Registro de fuentes sincronizado y enlaces oficiales revisados (20/20 el 2026-08-28).
- [x] Ningún RAW, secreto, `.pbix`, base SQL local o ruta personal está versionado.
- [x] Periodo, snapshot y limitaciones son consistentes en README, documentos y reportes.
- [x] Montos de hechos distintos no se suman ni presentan como un único gasto.

## Ingeniería

- [x] Suite completa en verde local y en CI (113 pruebas).
- [x] Pipeline estándar termina sin fallos.
- [x] Benchmark regenerado después de la corrida definitiva.
- [x] Instalación y pruebas reproducidas en un runner Linux limpio mediante CI.

## Power BI

- [ ] Unidades, etiquetas, encabezados, filtros e interacciones revisados.
- [ ] Actualización final completada y cronometrada.
- [ ] Cinco capturas definitivas incorporadas.
- [ ] Validación `phase14_powerbi_validation.json` en `PASS`.
- [ ] Archivo publicado o enlace documentado sin exponer credenciales.

## Portafolio

- [ ] README incluye arquitectura, resultados, capturas y pasos de reproducción.
- [x] Licencias de código y datos se distinguen claramente.
- [x] Bullets de CV coinciden con artefactos versionados.
- [x] No se afirma ahorro manual, ventas, adopción ni impacto no observado.
- [ ] Release/tag creado solo después de aprobar los puntos anteriores.
