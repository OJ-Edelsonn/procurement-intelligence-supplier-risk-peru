# Contribuir

## Alcance

Los cambios deben conservar trazabilidad, granularidad y reproducibilidad. No añadir datos personales, secretos, RAW, archivos `.pbix` ni archivos locales de SQL Server.

## Flujo

1. Crear una rama breve y descriptiva.
2. Actualizar configuración, código, pruebas y documentación como una unidad coherente.
3. Ejecutar `python -m pytest -q`.
4. Validar el registro de fuentes con `python -m procurement_intelligence.documentation.source_registry --check`.
5. Explicar en el PR qué cambió, qué evidencia lo respalda y qué limitaciones permanecen.

## Datos y métricas

- Una fuente nueva debe incorporarse a `config/source_registry.yml` antes de usarse.
- No mezclar hechos de procedimiento, ítem, adjudicación y contrato.
- No introducir proxies para historia, geografía, sanciones o riesgo cuando la fuente no los respalda.
- No afirmar ahorro, ventas, adopción o impacto empresarial sin medición real.
- Los artefactos generados deben conservar periodo, snapshot, hash y estado de calidad cuando corresponda.

## Commits

Se prefieren commits pequeños con prefijos como `feat:`, `fix:`, `test:`, `docs:`, `data:` y `chore:`. No combinar trabajo no relacionado.

