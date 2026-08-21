# Fase 6 — Validación del modelo dimensional

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Arquitectura | Constelación de hechos |
| Dimensiones | 8 |
| Hechos | 6 |
| Puentes | 2 |
| Objetos lógicos | 16 |
| Filas fuente de hechos | 23,056 |
| Filas fuente de puentes | 37,511 |
| Puertas aprobadas | 6/6 |
| Puertas fallidas | 0 |
| Estado | `PASS_WITH_WARNINGS` |
| Elegible para Fase 7 | Sí |

El estado contiene advertencias porque el modelo conserva incidencias reales; no existe un fallo estructural que impida diseñar el DDL.

La Fase 6 no incorpora una fuente externa nueva. Todo el análisis deriva de la adquisición OECE/SEACE de julio de 2026 ya registrada, identificada por el hash de archivo `024ef9eb7a282de74559ea78ba149ff87aa041d7c92947795ac354d49f0ba4e8`; sus URL, condiciones y evidencias permanecen centralizadas en `docs/data_sources/source_registry.md`.

## Puertas

| ID | Control | Resultado |
|---|---|---|
| `DM-GRAIN-001` | granos completos y únicos en 6 hechos y 2 puentes | PASS, 0 violaciones |
| `DM-REF-001` | comprador/parte, ofertante/parte, proveedor/parte y contrato/adjudicación | PASS, 0 huérfanos |
| `DM-CAT-001` | máximo una clasificación estándar por ítem | PASS, máximo 1 |
| `DM-SUP-001` | atribución solo con proveedor único | PASS, 0 asignaciones inventadas |
| `DM-AMT-001` | diferencias cabecera/ítem medidas para todos los padres | PASS, 10,968/10,968 evaluados |
| `DM-RATE-001` | no convertir moneda sin tasa OECE | PASS, 0 conversiones no sustentadas |

## Tamaño estimado de dimensiones

| Dimensión | Filas piloto |
|---|---:|
| Fecha | 2,135 días calendario |
| Proceso | 6,452 |
| Comprador | 1,450 |
| Proveedor/ofertante | 12,820 |
| Categoría | 3,690 |
| Método | 19 |
| Moneda | 4 |
| Unidad | 15 |

El calendario cubre del 2026-02-02 al 2031-12-07 porque los periodos contractuales contienen fechas futuras. No se corta artificialmente en 2026.

## Cardinalidades de ciclo de vida

| Relación | Máximo observado | Padres con múltiples hijos |
|---|---:|---:|
| Ofertantes por proceso | 80 | 3,611 |
| Adjudicaciones por proceso | 5 | 38 |
| Contratos por proceso | 4 | 13 |
| Ítems por adjudicación | 32 | 77 |
| Ítems por contrato | 5 | 12 |

Estas relaciones descartan una tabla ancha o un hecho único a nivel de proceso.

## Dimensiones y calidad de identidad

- Compradores: 0 conflictos de nombre.
- Identificadores alternativos de comprador: 6,452 observaciones, 1,450 RUC únicos y 0 formatos inválidos.
- Proveedores: 4 claves con dos variantes de nombre.
- Proveedores `PE-RUC`: 1,797 observaciones inválidas, correspondientes a miembros que deben conservar su señal DQ.
- Categorías: 22,042 observaciones, 3,690 claves conformadas y 3 conflictos de descripción.
- 2,135 observaciones de categoría convergen al miembro “Sin clasificar”.

## Reconciliación de montos

| Nivel | Padres | Exactos | Dentro de 0.01 | Diferencias > 0.01 | Máxima diferencia |
|---|---:|---:|---:|---:|---:|
| Licitación | 6,452 | 6,385 | 6,385 | 67 | 17,723,529.41 |
| Adjudicación | 3,397 | 3,394 | 3,396 | 1 | 72,000.00 |
| Contrato | 1,119 | 1,119 | 1,119 | 0 | 0.00 |

Las monedas de cabecera e ítem coinciden en todos los casos. Las diferencias se almacenarán como auditoría y no se corregirán reemplazando un monto con el otro.

## Conversión a PEN

| Hecho | Filas extranjeras | Con tasa OECE | Sin tasa |
|---|---:|---:|---:|
| Ítem de licitación | 112 | 110 | 2 |
| Adjudicación | 86 | 86 | 0 |
| Ítem de adjudicación | 86 | 86 | 0 |
| Contrato | 64 | 60 | 4 |
| Ítem de contrato | 64 | 60 | 4 |

Los faltantes no reciben conversión. El monto PEN será nulo y quedará señalizado.

## Atribución de proveedor

- 3,396 adjudicaciones tienen un proveedor y pueden atribuirse.
- Una adjudicación no informa proveedor y usará `supplier_key = 0`.
- No hay adjudicaciones con múltiples proveedores en el piloto.
- Los 1,119 contratos referencian adjudicaciones con proveedor único.
- Los puentes conservan participación; no contienen medidas monetarias.

## Advertencias preservadas

- 53 procesos difieren entre ofertantes declarados y observados.
- 68 cabeceras presentan diferencia de monto superior a 0.01 frente a sus ítems.
- 10 observaciones extranjeras de hechos/ítems no tienen tasa, contando cada grano por separado.
- Cuatro identidades de proveedor y tres categorías presentan variantes textuales.
- 1,116 contratos no tienen `finalValue`; cobertura 0.2681%.

Los conteos pertenecen a métricas y granos diferentes; no deben sumarse como “filas únicas con error”.

## Conclusión

El modelo de constelación se ajusta a los datos Silver y protege contra doble contabilización. La Fase 7 puede generar DDL y cargas desde el contrato, siempre que conserve las puertas, el miembro desconocido y las restricciones de aditividad.

## Evidencia

- Contrato: `config/dimensional_model.yml`.
- Validador: `src/procurement_intelligence/modeling/validate_dimensional_model.py`.
- Reporte: `reports/modeling/oece_ocds_seace_v3_2026_07_dimensional_model_analysis.json`.
- Arquitectura: `docs/architecture/phase6_dimensional_model.md`.
- Diccionario: `docs/data_dictionary/dimensional_model.md`.
