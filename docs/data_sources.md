# Fuentes de datos

## Fuente principal: OECE OCDS

El Portal de Contrataciones Abiertas de OECE publica información de contratación estatal en el estándar Open Contracting Data Standard (OCDS). Para el MVP será la fuente analítica principal porque ofrece relaciones explícitas entre partes, planificación, licitación, adjudicaciones y contratos.

- Portal: <https://contratacionesabiertas.oece.gob.pe/>
- Descargas: <https://contratacionesabiertas.oece.gob.pe/descargas>
- API: <https://contratacionesabiertas.oece.gob.pe/api>

Campos conceptuales prioritarios:

- `ocid` como identificador del proceso OCDS.
- Comprador y entidades participantes.
- Fechas, método y estado de licitación.
- Ítems y clasificación disponible.
- Proveedores adjudicados, valores y moneda.
- Contratos vinculados a adjudicaciones.

Antes de implementar la ingesta se conservarán el archivo fuente, su URL, fecha de descarga, tamaño, hash y periodo declarado.

## Fuentes complementarias OECE/SEACE

Los XLSX de convocatorias, adjudicaciones, contratos, órdenes, PAC, ofertas, proveedores y otros módulos se usarán para validación o análisis independiente. No se asumirán equivalencias entre archivos: cada conjunto requiere perfilado de granularidad, llaves, cobertura temporal y reglas de reconciliación.

## Universos separados

- Procedimientos OCDS: universo principal del MVP.
- Órdenes de compra y servicio: módulo posterior; su cobertura y clasificación no son equivalentes al universo OCDS.
- Sanciones y penalidades: señal complementaria posterior, con tratamiento legal y temporal explícito.
- PAC: planificación; no sustituye adjudicaciones ni contratos ejecutados.

## Controles mínimos de fuente

1. Confirmar que el enlace y el archivo pertenecen al dominio oficial.
2. Registrar periodo, versión, formato, tamaño y hash.
3. Verificar esquema antes de concatenar meses o años.
4. Medir duplicados, nulos y rupturas de relación.
5. Conciliar conteos y montos por niveles compatibles.
6. Mantener la licencia y atribución indicadas por el publicador.

## Política temporal

El corte aprobado es 31 de julio de 2026. Los años 2023–2025 se analizarán completos; 2026 se tratará como YTD. Toda comparación con 2026 deberá usar el mismo intervalo de meses del año comparado.
