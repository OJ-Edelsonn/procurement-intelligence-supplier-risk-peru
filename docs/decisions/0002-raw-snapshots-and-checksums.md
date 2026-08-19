# ADR 0002: Snapshots RAW y alcance del checksum OECE

- Estado: aceptada
- Fecha: 2026-08-19

## Contexto

OECE ofrece CSV, JSON, XLSX y un archivo SHA por fuente, año y mes. En el piloto, el SHA publicado no coincidió con los archivos ZIP, pero sí con el JSON descomprimido.

## Decisión

1. Particionar RAW por fuente, periodo y `snapshot_date`.
2. Prohibir la sobrescritura de archivos RAW existentes.
3. Calcular SHA-256 local para cada archivo físico.
4. Descargar JSON y validar el SHA oficial contra su payload descomprimido.
5. Usar el CSV oficial para perfilado relacional y ETL, conservando su hash como huella local.
6. Registrar manifiestos por formato para no confundir validación oficial y huella local.

## Consecuencias

- Se conserva evidencia de revisiones de la fuente.
- La ingesta requiere temporalmente ambos formatos en el piloto.
- Un checksum CSV local detecta cambios entre ejecuciones, pero no se etiqueta como checksum publicado por OECE.
- La arquitectura futura podrá escoger un formato operativo sin perder el JSON canónico de auditoría.
