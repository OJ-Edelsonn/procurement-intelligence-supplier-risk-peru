# Checklist de publicación final

## Datos y gobierno

- [ ] Registro de fuentes sincronizado y enlaces oficiales revisados.
- [ ] Ningún RAW, secreto, `.pbix`, base SQL local o ruta personal está versionado.
- [ ] Periodo, snapshot y limitaciones son consistentes en README, documentos y reportes.
- [ ] Montos de hechos distintos no se suman ni presentan como un único gasto.

## Ingeniería

- [ ] Suite completa en verde local y en CI.
- [ ] Pipeline estándar termina sin fallos.
- [ ] Benchmark regenerado después de la corrida definitiva.
- [ ] Instalación reproducida desde un entorno limpio.

## Power BI

- [ ] Unidades, etiquetas, encabezados, filtros e interacciones revisados.
- [ ] Actualización final completada y cronometrada.
- [ ] Cinco capturas definitivas incorporadas.
- [ ] Validación `phase14_powerbi_validation.json` en `PASS`.
- [ ] Archivo publicado o enlace documentado sin exponer credenciales.

## Portafolio

- [ ] README incluye arquitectura, resultados, capturas y pasos de reproducción.
- [ ] Licencias de código y datos se distinguen claramente.
- [ ] Bullets de CV coinciden con artefactos versionados.
- [ ] No se afirma ahorro manual, ventas, adopción ni impacto no observado.
- [ ] Release/tag creado solo después de aprobar los puntos anteriores.

