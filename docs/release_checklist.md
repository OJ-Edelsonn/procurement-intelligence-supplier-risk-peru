# Checklist de publicación final

## Datos y gobierno

- [x] Registro de fuentes sincronizado y enlaces oficiales revisados (20/20 el 2026-08-28).
- [x] Ningún RAW, secreto, `.pbix`, base SQL local o ruta personal está versionado.
- [x] Periodo, snapshot y limitaciones son consistentes en README, documentos y reportes.
- [x] Montos de hechos distintos no se suman ni presentan como un único gasto.

## Ingeniería

- [x] Suite completa en verde local (116 pruebas); CI previo aprobado y nueva ejecución requerida al publicar la rama final.
- [x] Pipeline estándar termina sin fallos.
- [x] Benchmark regenerado después de la corrida definitiva.
- [x] Instalación y pruebas reproducidas en un runner Linux limpio mediante CI.

## Power BI

- [x] Unidades, etiquetas, encabezados, filtros e interacciones revisados.
- [x] Actualización final completada y cronometrada: 200 segundos.
- [x] Cinco capturas definitivas incorporadas.
- [x] Validación `phase14_powerbi_validation.json` en `PASS`.
- [ ] Archivo publicado o enlace documentado sin exponer credenciales.

## Portafolio

- [x] README incluye arquitectura, resultados, capturas y pasos de reproducción.
- [x] Licencias de código y datos se distinguen claramente.
- [x] Bullets de CV coinciden con artefactos versionados.
- [x] No se afirma ahorro manual, ventas, adopción ni impacto no observado.
- [ ] Release/tag creado solo después de aprobar los puntos anteriores.
