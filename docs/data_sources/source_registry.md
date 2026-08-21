# Registro maestro de fuentes y trazabilidad

> Documento generado desde `config/source_registry.yml`. No editar manualmente.

## Control del documento

| Campo | Valor |
|---|---|
| Versión del esquema | 1.0 |
| Última revisión | 2026-08-20 |
| Responsable | Procurement Intelligence & Supplier Risk - Perú |
| Repositorio | <https://github.com/OJ-Edelsonn/procurement-intelligence-supplier-risk-peru> |
| Último control automático de enlaces | PASS el 2026-08-20; 20/20 mediante HTTP GET con redirecciones habilitadas |

## Política de uso

- No presentar una fuente candidata como utilizada.
- Registrar una evidencia de adquisición por cada snapshot efectivamente descargado.
- Conservar URL, periodo, fecha de snapshot, tamaño y SHA-256 de cada archivo RAW.
- Mantener los términos y la atribución del publicador; el código MIT no relicencia los datos.
- Validar granularidad y cobertura antes de combinar fuentes.

## Estados

| Estado | Significado |
|---|---|
| `active_used` | Fuente o repositorio utilizado y con trazabilidad activa. |
| `reference_only` | Documentación consultada; no agrega observaciones al dataset. |
| `candidate_not_ingested` | Fuente evaluada, pero aún no descargada ni integrada. |

## Índice de fuentes

| ID | Fuente | Publicador | Categoría | Estado | Usada |
|---|---|---|---|---|---|
| `oece_ocds_seace_v3_bulk` | Descargas masivas OCDS de SEACE V3 | Organismo Especializado para las Contrataciones Públicas Eficientes (OECE) | `primary_data` | `active_used` | Sí |
| `oece_ocds_data_dictionary` | Diccionario de datos OCDS de OECE | Organismo Especializado para las Contrataciones Públicas Eficientes (OECE) | `reference_documentation` | `reference_only` | Sí |
| `ocp_ocds_standard` | Open Contracting Data Standard (OCDS) | Open Contracting Partnership (OCP) | `reference_documentation` | `reference_only` | Sí |
| `oece_complementary_open_data` | Portal de Datos Abiertos del OECE | Organismo Especializado para las Contrataciones Públicas Eficientes (OECE) | `complementary_data` | `candidate_not_ingested` | No |
| `peru_national_open_data_seace_catalog` | Catálogo Nacional de Datos Abiertos - búsqueda SEACE | Plataforma Nacional de Datos Abiertos del Estado peruano | `discovery_catalog` | `candidate_not_ingested` | No |
| `inei_ubigeo_open_data` | Código de ubicación geográfica en el Perú (UBIGEO) | Instituto Nacional de Estadística e Informática (INEI) | `reference_dimension` | `candidate_not_ingested` | No |
| `sunat_ruc_structure_and_consultation` | Estructura y consulta oficial del RUC | Superintendencia Nacional de Aduanas y de Administración Tributaria (SUNAT) | `reference_documentation` | `reference_only` | Sí |
| `project_github_repository` | Repositorio del proyecto | Edelson Anghuelo Orihuela Jara | `project_provenance` | `active_used` | Sí |

## Descargas masivas OCDS de SEACE V3

- **ID:** `oece_ocds_seace_v3_bulk`
- **Publicador:** Organismo Especializado para las Contrataciones Públicas Eficientes (OECE)
- **Autoridad:** `official_publisher`
- **Estado:** `active_used`
- **Propósito:** Fuente principal del MVP para procedimientos, partes, licitaciones, adjudicaciones y contratos.

### Alcance

- Archivos compilados por año y mes de convocatoria del procedimiento.
- Si no existe fecha de convocatoria, OECE segmenta por fecha de publicación del proceso.
- El alcance analítico aprobado comprende 2023-2025 completos y enero-julio de 2026.
- SEACE V2 y SEACE V3 son universos publicados por separado; el MVP usa SEACE V3.

### Limitaciones

- La suma de filas entre tablas no equivale al número de procedimientos.
- Los releases conservan historia, pero no constituyen por sí solos un hecho de gasto.
- La cobertura de campos de ejecución contractual debe medirse antes de crear KPIs.

### Enlaces oficiales

- Portal: <https://contratacionesabiertas.oece.gob.pe/>
- Downloads: <https://contratacionesabiertas.oece.gob.pe/descargas>
- Api Documentation: <https://contratacionesabiertas.oece.gob.pe/api>

### Endpoints documentados

- Csv: `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/csv/{year}/{month}`
- Csv Spanish: `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/csv/{year}/{month}/es`
- Json: `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/json/{year}/{month}`
- Sha: `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/sha/{year}/{month}`
- Xlsx: `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/xlsx/{year}/{month}`
- Xlsx Spanish: `https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/xlsx/{year}/{month}/es`

- **Formatos:** CSV_ZIP, JSON_ZIP, XLSX_ZIP, SHA256
- **Acceso:** Descarga HTTPS mediante endpoints mensuales documentados por OECE.
- **Actualización:** Publicación por cortes mensuales; verificar la fecha de actualización mostrada por el portal en cada adquisición.
- **Licencia/términos:** No se identificó una licencia de datos explícita en las páginas verificadas; conservar atribución y revisar términos antes de redistribuir.
- **Verificación de enlaces:** PASS el 2026-08-19 mediante HTTP GET y revisión del portal/API oficial.

## Diccionario de datos OCDS de OECE

- **ID:** `oece_ocds_data_dictionary`
- **Publicador:** Organismo Especializado para las Contrataciones Públicas Eficientes (OECE)
- **Autoridad:** `official_publisher`
- **Estado:** `reference_only`
- **Propósito:** Documentar el significado y la estructura de los campos publicados por OECE.

### Alcance

- Diccionario oficial disponible en XLSX y PDF desde la página de descargas OCDS.

### Limitaciones

- La semántica documentada no sustituye el perfilado del archivo realmente descargado.

### Enlaces oficiales

- Xlsx: <https://contratacionesabiertas.oece.gob.pe/downloads/Diccionario%20de%20datos%20OCDS.xlsx>
- Pdf: <https://contratacionesabiertas.oece.gob.pe/downloads/Diccionario%20de%20datos%20OCDS.pdf>

- **Formatos:** XLSX, PDF
- **Acceso:** Descarga HTTPS desde el portal oficial.
- **Actualización:** No declarada en la página verificada.
- **Licencia/términos:** No confirmados; conservar atribución al OECE.
- **Verificación de enlaces:** PASS el 2026-08-19 mediante HTTP GET; tipo de contenido y tamaño verificados.

## Open Contracting Data Standard (OCDS)

- **ID:** `ocp_ocds_standard`
- **Publicador:** Open Contracting Partnership (OCP)
- **Autoridad:** `standards_publisher`
- **Estado:** `reference_only`
- **Propósito:** Referencia normativa del esquema OCDS, OCID, releases y records usados por OECE.

### Alcance

- Documentación de la versión vigente publicada bajo la ruta latest en español.
- Guía conceptual sobre paquetes de releases y records.

### Limitaciones

- La ruta latest puede cambiar de versión; cada ingesta debe conservar la versión declarada en el payload.

### Enlaces oficiales

- Standard: <https://standard.open-contracting.org/latest/es/>
- Releases And Records: <https://standard.open-contracting.org/latest/es/primer/releases_and_records/>
- Ocid: <https://standard.open-contracting.org/1.1/es/schema/identifiers/#contracting-process-identifier-ocid>
- Releases Reference: <https://standard.open-contracting.org/latest/es/schema/reference/>
- Records Reference: <https://standard.open-contracting.org/latest/es/schema/records_reference/>

- **Formatos:** HTML, JSON_SCHEMA
- **Acceso:** Consulta web.
- **Actualización:** Gestionada por OCP; verificar la versión declarada al usarla.
- **Licencia/términos:** Consultar la licencia de la versión OCDS utilizada en el sitio oficial.
- **Verificación de enlaces:** PASS el 2026-08-19 mediante HTTP GET de la documentación principal y la guía.

## Portal de Datos Abiertos del OECE

- **ID:** `oece_complementary_open_data`
- **Publicador:** Organismo Especializado para las Contrataciones Públicas Eficientes (OECE)
- **Autoridad:** `official_publisher`
- **Estado:** `candidate_not_ingested`
- **Propósito:** Candidato para validaciones y módulos separados de PAC, proveedores, consorcios, órdenes, entidades y otros conjuntos.

### Alcance

- La ficha oficial declara información desde 2018.
- La actualización declarada es mensual, dentro de los primeros cinco días del mes.
- Incluye PAC, procedimientos, contratos, proveedores, consorcios, entidades, órdenes y otros conjuntos.

### Limitaciones

- La ficha indica que no incluye procedimientos en curso ni información incompleta de adjudicación.
- No se combinará con OCDS hasta validar llaves, periodo y granularidad.
- La URL interna del servicio puede cambiar; se conserva la ficha estable de gob.pe.

### Enlaces oficiales

- Service Landing: <https://www.gob.pe/14272-acceder-al-portal-de-datos-abiertos-del-oece>

- **Formatos:** XLSX, OTHER_TABULAR
- **Acceso:** Acceso a través de la ficha oficial de servicio.
- **Actualización:** Mensual, dentro de los primeros cinco días, según la ficha oficial.
- **Licencia/términos:** No confirmados; revisar por dataset antes de usar.
- **Verificación de enlaces:** PASS el 2026-08-19 mediante HTTP GET y revisión de la ficha oficial.

## Catálogo Nacional de Datos Abiertos - búsqueda SEACE

- **ID:** `peru_national_open_data_seace_catalog`
- **Publicador:** Plataforma Nacional de Datos Abiertos del Estado peruano
- **Autoridad:** `official_government_catalog`
- **Estado:** `candidate_not_ingested`
- **Propósito:** Descubrir fichas oficiales complementarias y sus metadatos sin sustituir al publicador de cada dataset.

### Alcance

- Resultados catalogados relacionados con SEACE, OECE y contratación pública.

### Limitaciones

- Es un catálogo; la autoridad, cobertura y licencia deben verificarse en cada ficha individual.

### Enlaces oficiales

- Search: <https://www.datosabiertos.gob.pe/?query=seace&sort_by=changed&sort_order=DESC>

- **Formatos:** HTML, DATASET_METADATA
- **Acceso:** Consulta web del catálogo nacional.
- **Actualización:** Variable por dataset.
- **Licencia/términos:** Variable por dataset; revisar la ficha específica.
- **Verificación de enlaces:** PASS el 2026-08-19 mediante HTTP GET y revisión de resultados.

## Código de ubicación geográfica en el Perú (UBIGEO)

- **ID:** `inei_ubigeo_open_data`
- **Publicador:** Instituto Nacional de Estadística e Informática (INEI)
- **Autoridad:** `official_publisher`
- **Estado:** `candidate_not_ingested`
- **Propósito:** Candidato para normalizar departamento, provincia y distrito en una futura dimensión geográfica.

### Alcance

- Ficha de dataset y diccionario de códigos de ubicación geográfica del Perú.
- El portal IDE INEI ofrece capas geográficas descargables como referencia complementaria.

### Limitaciones

- Aún no se ha descargado ni conciliado con las direcciones de OECE.
- Debe fijarse versión y vigencia antes de poblar la dimensión geográfica.

### Enlaces oficiales

- Dataset: <https://www.datosabiertos.gob.pe/dataset/c%C3%B3digo-de-ubicaci%C3%B3n-geogr%C3%A1fica-en-el-per%C3%BA-instituto-nacional-de-estad%C3%ADstica-e-inform%C3%A1tica>
- Geospatial Portal: <https://ide.inei.gob.pe/>

- **Formatos:** TABULAR_DATASET, DATA_DICTIONARY, GEOSPATIAL
- **Acceso:** Descarga desde portales oficiales.
- **Actualización:** Verificar vigencia en cada versión publicada.
- **Licencia/términos:** Revisar la ficha y los metadatos del recurso antes de usar.
- **Verificación de enlaces:** PARTIAL el 2026-08-19 mediante Revisión de resultados oficiales; pendiente verificar los recursos descargables.

## Estructura y consulta oficial del RUC

- **ID:** `sunat_ruc_structure_and_consultation`
- **Publicador:** Superintendencia Nacional de Aduanas y de Administración Tributaria (SUNAT)
- **Autoridad:** `official_publisher`
- **Estado:** `reference_only`
- **Propósito:** Sustentar la validación estructural de 11 dígitos y documentar el canal oficial para una futura consulta registral.

### Alcance

- SUNAT declara que el RUC es un identificador único de 11 dígitos.
- La ficha de gob.pe permite consultar estado y condición de un RUC mediante el servicio oficial.

### Limitaciones

- La Fase 4 valida estructura, no estado activo, habido ni identidad registral.
- No se realiza consulta masiva al servicio ni se almacena información adicional de SUNAT.
- No se usa un algoritmo de checksum como validación oficial porque no se identificó su documentación primaria.

### Enlaces oficiales

- Ruc Structure: <https://centrovirtual.sunat.gob.pe/tramites/inscribete-ruc>
- Official Query: <https://www.gob.pe/565-consultar-el-estado-del-ruc>

- **Formatos:** HTML
- **Acceso:** Consulta web oficial; sin extracción masiva en esta fase.
- **Actualización:** Verificar vigencia antes de realizar una consulta registral.
- **Licencia/términos:** Consulta informativa sujeta a las condiciones del servicio oficial.
- **Verificación de enlaces:** PASS el 2026-08-20 mediante HTTP GET y revisión de las páginas oficiales.

## Repositorio del proyecto

- **ID:** `project_github_repository`
- **Publicador:** Edelson Anghuelo Orihuela Jara
- **Autoridad:** `project_owner`
- **Estado:** `active_used`
- **Propósito:** Conservar código, documentación, pruebas y decisiones que permiten reproducir el tratamiento de datos.

### Alcance

- No almacena datos RAW ni archivos PBIX.
- Versiona configuración no sensible, manifiestos resumidos, documentación y código.

### Limitaciones

- El repositorio demuestra el procesamiento, pero no sustituye los archivos RAW conservados fuera de Git.

### Enlaces oficiales

- Repository: <https://github.com/OJ-Edelsonn/procurement-intelligence-supplier-risk-peru>

- **Formatos:** GIT, MARKDOWN, PYTHON, YAML
- **Acceso:** Git y HTTPS.
- **Actualización:** Por cambios versionados del proyecto.
- **Licencia/términos:** Código bajo MIT; datos sujetos a los términos de sus publicadores.
- **Verificación de enlaces:** PASS el 2026-08-19 mediante HTTP GET del repositorio.

## Evidencia de adquisiciones

### oece_ocds_seace_v3_2026_07_2026_08_19

| Campo | Valor |
|---|---|
| Fuente | `oece_ocds_seace_v3_bulk` |
| Periodo fuente | 2026-07 |
| Fecha de snapshot | 2026-08-19 |
| Estado | `verified` |
| Ruta RAW | `${DATA_ROOT}/raw/oece/ocds/seace_v3/2026/07/snapshot_date=2026-08-19` |
| Ruta de metadatos | `${DATA_ROOT}/metadata/oece/ocds/seace_v3/2026/07/snapshot_date=2026-08-19` |

| Artefacto | Formato | Bytes | SHA-256 local | URL oficial |
|---|---|---:|---|---|
| `2026-07_seace_v3_csv.zip` | CSV_ZIP | 8,052,765 | `024ef9eb7a282de74559ea78ba149ff87aa041d7c92947795ac354d49f0ba4e8` | <https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/csv/2026/07> |
| `2026-07_seace_v3_json.zip` | JSON_ZIP | 7,718,087 | `d737e3670cb6ba7f30db7a3b0cc6adafae6ca052df24cc7927668dcfc6698e57` | <https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/json/2026/07> |
| `2026-07_seace_v3.sha` | SHA256 | 64 | `9176f15ebb122c5238ac33a76650406a82b7ac0c30fc9b2ff1d32de236cda297` | <https://contratacionesabiertas.oece.gob.pe/api/v1/file/seace_v3/sha/2026/07> |

**Checksum del publicador**

- `2026-07_seace_v3_json.zip`: PASS; SHA-256 del payload JSON descomprimido `ef6c3b3bc5ace5b4a81b1e2efbac222f72b6bd958af3483ca1d03723426d6d95`; 76,209,866 bytes.

**Evidencia de perfilado**

- Reporte: `reports/profiling/oece_ocds_seace_v3_2026_07_summary.json`
- 22 tablas; 6,452 records raíz; 80,789 releases; 231,123 filas acumuladas; 41 controles referenciales aprobados.

**Evidencia de Data Quality RAW**

- Reporte: `reports/data_quality/oece_ocds_seace_v3_2026_07_quality_summary.json`
- Estado `BLOCKED`; 11/17 reglas aprobadas; 6 fallidas; 1 fallo bloqueante.

**Evidencia de ETL Silver**

- Reporte: `reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json`
- Contrato: `config/etl_silver.yml`
- Estado `PASS_WITH_WARNINGS`; promoción elegible: Sí.
- 22 tablas; 231,123 filas RAW; 231,113 filas Silver; 10 filas en cuarentena; 2,135 clasificaciones normalizadas como desconocidas.

## Procedimiento para incorporar una fuente

1. Añadir la ficha y sus URL oficiales a `config/source_registry.yml`.
2. Mantenerla como `candidate_not_ingested` hasta descargar y validar un snapshot.
3. Crear un evento de adquisición con periodo, fecha, tamaño, hash y rutas de evidencia.
4. Ejecutar la validación y regenerar este documento.
5. Revisar granularidad, cobertura, licencia y reconciliación antes de integrarla al modelo.
