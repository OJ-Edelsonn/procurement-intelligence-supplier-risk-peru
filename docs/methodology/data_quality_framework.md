# Marco inicial de Data Quality

## Propósito

La Fase 4 convierte los hallazgos de profiling en reglas ejecutables y gobernadas. El objetivo no es “limpiar” RAW, sino decidir con evidencia si un snapshot puede promoverse a Staging/Silver y qué tratamiento requiere.

El catálogo canónico está en `config/data_quality_rules.yml`; el motor está en `src/procurement_intelligence/validation/validate_ocds_csv.py`.

## Dimensiones evaluadas

| Dimensión | Pregunta que responde | Ejemplos |
|---|---|---|
| Esquema | ¿Llegaron las tablas y columnas esperadas? | 22 tablas, columnas raíz del MVP |
| Completitud | ¿Están informados los campos necesarios? | compradores, montos, proveedores, clasificaciones |
| Unicidad | ¿Cada fila respeta su grano? | `ocid`, adjudicación, contrato, ítem, tasa |
| Integridad referencial | ¿Cada hijo conserva su padre? | proceso, parte, ítem, adjudicación, contrato |
| Validez | ¿El valor cumple formato y dominio? | números, fechas, tasas y RUC |
| Consistencia | ¿Campos relacionados concuerdan? | monto-moneda y orden inicio-fin |
| Aptitud para uso | ¿La cobertura permite el KPI previsto? | ofertantes, valor final y monto positivo |

## Severidades y promoción

| Severidad | Efecto |
|---|---|
| `critical` | El lote no es legible o perdió un componente indispensable. |
| `error` | Bloquea la promoción a Silver hasta resolver o aislar la incidencia. |
| `warning` | Exige tratamiento o limitación documentada, pero no bloquea por sí sola. |
| `info` | Métrica de monitoreo; no bloquea. |

Estado del lote:

- `BLOCKED`: existe al menos un `critical` o `error` fallido.
- `PASS_WITH_WARNINGS`: no hay fallos bloqueantes, pero sí advertencias fallidas.
- `PASS`: todas las reglas están dentro del umbral.

El estado del lote no es el estado de la fase. Encontrar una incidencia real y reportarla correctamente es un resultado válido de Data Quality.

## Justificación inicial de umbrales

- **Tolerancia cero en esquema, campos obligatorios, claves, referencias, fechas, números y monto-moneda:** una sola incidencia puede romper el grano, perder una relación o producir un cálculo incorrecto. Por eso estas reglas son bloqueantes.
- **Tolerancia cero con severidad warning en duplicados, formato RUC, clasificación y montos cero:** cualquier caso debe quedar visible, pero su existencia no permite concluir que toda la fila sea inutilizable.
- **`finalValue` con piso diagnóstico de 5%:** no representa un nivel aceptable para publicar un KPI; solo detecta si el campo tiene una presencia mínima que justifique estudiarlo. Aun si pasara 5%, necesitaría una evaluación de cobertura mucho más exigente antes de usarse.
- **Número de ofertantes con piso exploratorio de 60%:** exige mayoría de procesos informados para análisis preliminar. El KPI siempre deberá mostrar denominador y cobertura; el umbral definitivo se revisará con 2023–julio 2026.

Los umbrales son versionados y deben revisarse con evidencia histórica. Cambiar un umbral crea una nueva decisión metodológica; no se modifica para forzar un resultado PASS.

## Catálogo de reglas

| ID | Dimensión | Severidad | Control |
|---|---|---|---|
| `DQ-SCHEMA-001` | Esquema | Critical | Presencia de las 22 tablas |
| `DQ-SCHEMA-002` | Esquema | Critical | Columnas raíz necesarias para el MVP |
| `DQ-COMP-001` | Completitud | Error | Campos obligatorios en procesos, adjudicaciones, proveedores y contratos |
| `DQ-UNIQ-001` | Unicidad | Error | Granos candidatos completos y únicos |
| `DQ-DUP-001` | Unicidad | Warning | Filas exactas adicionales |
| `DQ-REF-001` | Integridad | Error | OCID y compiled release contra `records.csv` |
| `DQ-REF-002` | Integridad | Error | 16 relaciones profundas padre-hijo |
| `DQ-VALID-001` | Validez | Error | Numéricos convertibles y no negativos |
| `DQ-VALID-002` | Validez | Error | Tasas de cambio positivas |
| `DQ-TEMP-001` | Validez | Error | Fechas interpretables |
| `DQ-TEMP-002` | Consistencia | Error | Inicio menor o igual al fin |
| `DQ-CONS-001` | Consistencia | Error | Moneda presente cuando existe monto |
| `DQ-ID-001` | Validez | Warning | Formato estructural de 11 dígitos para `PE-RUC` |
| `DQ-CAT-001` | Completitud | Warning | Código, descripción y esquema de clasificación |
| `DQ-FIT-001` | Aptitud | Warning | Cobertura mínima de `finalValue` |
| `DQ-FIT-002` | Aptitud | Info | Cobertura mínima de número de ofertantes |
| `DQ-BIZ-001` | Aptitud | Warning | Valor de licitación estrictamente positivo |

## Cálculos relevantes

### Filas inválidas y porcentaje

```text
invalid_pct = invalid_rows / rows_evaluated * 100
```

Los conteos de reglas no se suman como “registros únicos con error”: una fila puede incumplir varias reglas y algunas reglas evalúan celdas, claves o relaciones.

### Unicidad

Para cada grano candidato se miden:

- filas con al menos un componente de clave nulo;
- filas duplicadas adicionales respecto de la primera aparición.

RAW permanece intacto. La futura deduplicación debe conservar conteos antes/después y una razón reproducible.

### Integridad referencial

Se comparan tuplas de claves, no solamente `ocid`. Por ejemplo, una clasificación de adjudicación debe encontrar el mismo `ocid + award_id + item_id` en la tabla padre de ítems.

### RUC

La regla se aplica solo cuando el publicador declara `scheme=PE-RUC`:

1. exactamente 11 caracteres;
2. todos los caracteres deben ser numéricos.

[SUNAT documenta oficialmente la estructura de 11 dígitos](https://centrovirtual.sunat.gob.pe/tramites/inscribete-ruc) y ofrece un [servicio oficial de consulta registral](https://www.gob.pe/565-consultar-el-estado-del-ruc). Esta fase no consulta masivamente ese servicio ni utiliza un algoritmo de checksum sin documentación oficial. Una falla estructural no demuestra fraude, sanción ni identidad legal inválida.

### Aptitud para uso

Una columna puede ser técnicamente válida pero no apta para cierto KPI. `finalValue`, por ejemplo, puede contener valores correctos y a la vez tener cobertura insuficiente para analizar ejecución contractual.

## Métricas antes y después

La Fase 4 establece el **antes** sobre RAW. No se inventa un “después” porque todavía no existe transformación:

| Momento | Estado |
|---|---|
| Baseline RAW | Evaluado y versionado |
| Post-tratamiento Silver | `NOT_EVALUATED` dentro del artefacto histórico de Fase 4; evaluado por el reporte de Fase 5 |

El JSON de Fase 4 conserva explícitamente el estado que tenía antes de transformar. La comparación posterior está en `reports/etl/oece_ocds_seace_v3_2026_07_etl_summary.json`: registra filas RAW, aceptadas, deduplicadas, clasificadas como desconocidas y enviadas a cuarentena sin reescribir la línea base.

## Reproducibilidad

```powershell
$archive = "C:\Data\procurement-intelligence-supplier-risk-peru\raw\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\2026-07_seace_v3_csv.zip"
$quality = "C:\Data\procurement-intelligence-supplier-risk-peru\metadata\oece\ocds\seace_v3\2026\07\snapshot_date=2026-08-19\quality_phase4_full.json"

.\.venv\Scripts\python.exe -m procurement_intelligence.validation.validate_ocds_csv `
  $archive `
  --rules config\data_quality_rules.yml `
  --source-period 2026-07 `
  --snapshot-date 2026-08-19 `
  --output $quality `
  --summary-output reports\data_quality\oece_ocds_seace_v3_2026_07_quality_summary.json
```

El reporte completo permanece junto a metadatos locales. El resumen versionado conserva el hash del ZIP y del catálogo, pero no rutas privadas ni registros individuales.

## Limitaciones

- Los umbrales son iniciales y se validaron con un solo mes.
- La ausencia de errores de formato no garantiza exactitud semántica del publicador.
- Los montos cero pueden responder a estados o reglas del proceso y requieren análisis antes de excluirlos.
- La regla estructural de RUC no sustituye una consulta vigente y autorizada a SUNAT.
- Ninguna señal constituye evaluación legal, crediticia ni predicción de fraude.
