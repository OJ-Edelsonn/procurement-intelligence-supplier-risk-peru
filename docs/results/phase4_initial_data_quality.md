# Fase 4 — Data Quality inicial

## Muestra evaluada

| Atributo | Valor |
|---|---|
| Fuente | OECE, SEACE V3 OCDS |
| Periodo fuente | Julio de 2026 |
| Snapshot | 2026-08-19 |
| Archivo | `2026-07_seace_v3_csv.zip` |
| SHA-256 | `024ef9eb7a282de74559ea78ba149ff87aa041d7c92947795ac354d49f0ba4e8` |
| Tablas | 22 |
| Filas acumuladas | 231,123 |
| Reglas | 17 |
| Tiempo de validación | 28.5337 s |

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Reglas aprobadas | 11 |
| Reglas fallidas | 6 |
| Fallos bloqueantes | 1 |
| Advertencias fallidas | 5 |
| Estado del lote | `BLOCKED` |
| Elegible para promover a Silver | No, hasta tratar `DQ-UNIQ-001` |

El lote queda bloqueado por diseño: la Fase 5 debe resolver la unicidad antes de generar Silver. Esto no significa que el proyecto o la Fase 4 hayan fallado.

## Controles aprobados

- 22/22 tablas y 18/18 columnas raíz esperadas.
- Campos obligatorios: 0 filas incompletas entre 14,364 observaciones de tabla evaluadas.
- 41 controles de referencia a `records.csv`: 0 huérfanos entre 368,553 referencias.
- 16 relaciones profundas: 0 huérfanos entre 64,987 referencias.
- 46,953 valores numéricos evaluados: 0 no convertibles o negativos.
- 412 tasas de cambio: 0 nulas, no numéricas o menores/iguales a cero entre las informadas.
- 47,223 fechas no nulas: 0 fechas no interpretables.
- 11,675 pares temporales comparables: 0 secuencias inicio-fin invertidas.
- 23,059 casos monto-moneda: 0 monedas faltantes cuando existe monto.
- Número de ofertantes: 65.7626% de cobertura, superior al umbral inicial de 60%.

## Incidencias encontradas

| Regla | Severidad | Hallazgo | Interpretación |
|---|---|---:|---|
| `DQ-UNIQ-001` | Error | 11 incumplimientos | 1 clave nula y 10 filas duplicadas adicionales; bloquea Silver |
| `DQ-DUP-001` | Warning | 10 duplicados adicionales | 20 filas participan en 10 pares idénticos de tasas de licitación |
| `DQ-ID-001` | Warning | 1,797 de 34,115 (`5.2675%`) | Identificadores etiquetados `PE-RUC` que no cumplen formato |
| `DQ-CAT-001` | Warning | 2,135 de 22,042 (`9.6861%`) | Clasificaciones incompletas entre los seis conjuntos de ítems |
| `DQ-FIT-001` | Warning | Cobertura `0.2681%` | `finalValue` no es apto para KPIs de ejecución |
| `DQ-BIZ-001` | Warning | 1,752 de 6,452 (`27.1544%`) | Valor de licitación igual a cero; requiere interpretación de negocio |

### Unicidad

- `com_ten_ite_additionalClassific.csv`: 1 fila sin identificador de clasificación dentro del grano candidato.
- `com_ten_ite_tot_exchangeRates.csv`: 10 filas exactas adicionales; 20 filas están involucradas.
- Las otras 20 tablas respetan el grano candidato observado.

Tratamiento propuesto para Fase 5:

1. conservar los 120 registros RAW de tasas;
2. deduplicar por grano completo en Silver;
3. producir 110 filas aceptadas y registrar 10 duplicados adicionales;
4. asignar la clasificación incompleta a cuarentena o “Sin clasificar”, sin inventar un código;
5. volver a ejecutar `DQ-UNIQ-001` y `DQ-DUP-001` sobre el resultado.

### Identificadores PE-RUC

Entre 34,115 filas declaradas `PE-RUC`:

- 1,654 tienen longitud distinta de 11;
- 143 tienen longitud 11, pero incluyen caracteres no numéricos;
- 32,318 filas sí cumplen la estructura de 11 dígitos numéricos;
- no se modificó ni descartó ningún identificador.

El hallazgo sugiere que algunos identificadores de ofertantes/proveedores podrían usar códigos distintos pese al esquema publicado. Debe conservarse el valor original y asignarse una categoría técnica de validez, no reemplazarse automáticamente.

### Clasificación

| Tabla | Filas incompletas |
|---|---:|
| Ítems de licitación | 1,281 |
| Clasificaciones adicionales de licitación | 1 |
| Ítems de adjudicación | 648 |
| Ítems de contrato | 205 |
| Clasificaciones adicionales de adjudicación | 0 |
| Clasificaciones adicionales de contrato | 0 |
| **Total** | **2,135** |

La dimensión de categoría deberá incluir “Sin clasificar”. Este miembro hace visible la ausencia; no imputa UNSPSC ni corrige el origen.

### Aptitud de KPIs

- `implementation/finalValue`: 3 de 1,119 contratos informados; no apto para medir ejecución final.
- `numberOfTenderers`: 4,243 de 6,452 procesos informados; aptitud parcial para competencia, con cobertura visible.
- valor de licitación: 1,752 ceros. Se puede medir demanda publicada, pero el gasto monetario debe filtrar o segmentar ceros con una regla aprobada.

## Baseline antes/después

| Métrica | RAW antes | Silver después |
|---|---:|---|
| Duplicados exactos adicionales | 10 | Pendiente Fase 5 |
| Claves de grano nulas | 1 | Pendiente Fase 5 |
| `PE-RUC` con formato inválido | 1,797 | Pendiente Fase 5; no se corregirá sin fuente confiable |
| Clasificaciones incompletas | 2,135 | Pendiente Fase 5 |
| Montos de licitación cero | 1,752 | Pendiente regla de tratamiento; no se eliminarán automáticamente |

No se reporta una mejora ficticia. La comparación posterior se completará cuando exista Silver.

## Conclusión

La estructura, los campos críticos, las fechas, los montos y las relaciones presentan buena integridad en el piloto. El lote todavía no debe promoverse porque la unicidad exige una regla reproducible de deduplicación y tratamiento de clave nula. Las demás advertencias deben convertirse en atributos de calidad o limitaciones de KPI, no en eliminaciones silenciosas.

## Evidencia

- Catálogo: `config/data_quality_rules.yml`.
- Resumen reproducible: `reports/data_quality/oece_ocds_seace_v3_2026_07_quality_summary.json`.
- Reporte completo local: `${DATA_ROOT}/metadata/oece/ocds/seace_v3/2026/07/snapshot_date=2026-08-19/quality_phase4_full.json`.
- Metodología: `docs/methodology/data_quality_framework.md`.
