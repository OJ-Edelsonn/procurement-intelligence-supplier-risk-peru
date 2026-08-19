# Descarga y perfilado OCDS

## Objetivo

Construir una entrada RAW inmutable y auditable antes de diseñar el Data Warehouse. La prueba piloto utiliza procesos SEACE V3 segmentados por OECE en julio de 2026 y descargados el 19 de agosto de 2026.

## Endpoints confirmados

| Artefacto | Endpoint oficial |
|---|---|
| CSV ZIP | `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/csv/2026/07` |
| JSON ZIP | `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/json/2026/07` |
| SHA | `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/sha/2026/07` |

Los enlaces se verificaron en la página oficial de [Descargas OCDS](https://contratacionesabiertas.oece.gob.pe/descargas). OECE indica que el mes corresponde principalmente a la fecha de inicio de convocatoria para SEACE V3 y, si no existe, a la fecha de publicación del proceso.

## Estructura local

```text
C:\Data\procurement-intelligence-supplier-risk-peru\
├── raw\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\
├── interim\
├── processed\
├── metadata\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\
└── logs\
```

La partición separa el periodo fuente de la fecha de captura. Esto permite conservar revisiones publicadas posteriormente sin sobrescribir un RAW anterior.

## Controles de descarga

1. Construcción del endpoint solo para fuentes, formatos, años y meses permitidos.
2. Descarga en streaming hacia un archivo temporal `.part`.
3. Movimiento atómico al nombre definitivo únicamente después de completar la respuesta.
4. Reutilización de un RAW existente; nunca se sobrescribe.
5. SHA-256 local de cada archivo descargado.
6. Manifiesto JSON con URL, tamaño, hash, timestamp y estado.
7. Validación del checksum publicado cuando su alcance es aplicable.

## Alcance real del archivo SHA

La prueba mostró que el digest oficial no corresponde al ZIP CSV ni al ZIP JSON. Coincide exactamente con el contenido del único archivo JSON después de descomprimirlo:

```text
SHA oficial:          ef6c3b3bc5ace5b4a81b1e2efbac222f72b6bd958af3483ca1d03723426d6d95
SHA payload JSON:     ef6c3b3bc5ace5b4a81b1e2efbac222f72b6bd958af3483ca1d03723426d6d95
SHA ZIP JSON local:   d737e3670cb6ba7f30db7a3b0cc6adafae6ca052df24cc7927668dcfc6698e57
SHA ZIP CSV local:    024ef9eb7a282de74559ea78ba149ff87aa041d7c92947795ac354d49f0ba4e8
```

Por evidencia observada, el JSON descomprimido se usa como ancla canónica de integridad. Los ZIP conservan una huella local, pero no se presenta esa huella como checksum oficial.

## Perfilado

El perfilador lee directamente las tablas CSV dentro del ZIP y registra:

- filas, columnas y tamaño por tabla;
- tipos inferidos;
- nulos por columna;
- filas duplicadas;
- cardinalidad de identificadores;
- unicidad y completitud de granos candidatos;
- relaciones de `ocid` y `compiledRelease/id` contra `records.csv`;
- tiempo y memoria estimada del procesamiento.

El perfil completo permanece bajo `DATA_ROOT/metadata`. Solo el resumen sin registros fuente se versiona en `reports/profiling`.

## Límites

- Un porcentaje global de nulos mezcla tablas y campos opcionales; no es por sí solo una métrica de calidad de negocio.
- La suma de filas de las 22 tablas no representa 231,123 procesos, porque combina releases, partes, documentos, ítems, adjudicaciones y contratos.
- Las llaves son candidatas derivadas del esquema y deberán formalizarse en la arquitectura y controles de calidad.
- El piloto valida julio de 2026; aún debe comprobarse la estabilidad de esquema entre meses y años.
