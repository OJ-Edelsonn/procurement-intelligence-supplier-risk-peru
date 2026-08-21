# Catálogo de reglas de validación SQL

## Contrato

Cada regla devuelve `rule_id`, filas evaluadas, infracciones, valor observado, valor esperado y detalle. La severidad y el nombre se gobiernan desde `config/sql_validation.yml`.

## Reglas bloqueantes

| ID | Control |
|---|---|
| `SQL-BATCH-001` | Existe un lote SQL exitoso vigente |
| `SQL-STRUCT-001` | Existen 22 tablas staging |
| `SQL-STRUCT-002` | Existen 16 tablas dimensionales |
| `SQL-STRUCT-003` | Las 16 tablas `dw` tienen PK |
| `SQL-STRUCT-004` | Existen 16 restricciones de unicidad gobernadas |
| `SQL-STRUCT-005` | Existen 9 restricciones `CHECK` gobernadas |
| `SQL-STRUCT-006` | Existen 55 FK habilitadas y confiables |
| `SQL-STRUCT-007` | Ninguna tabla `dw` es heap |
| `SQL-AUDIT-001` | Las 38 métricas de carga son completas y exitosas |
| `SQL-AUDIT-002` | Las filas físicas coinciden con auditoría |
| `SQL-DIM-001` | Cada dimensión contiene exactamente una clave 0 |
| `SQL-DIM-002` | El calendario es continuo y sus atributos concuerdan |
| `SQL-GRAIN-001` | Grano único de proceso |
| `SQL-GRAIN-002` | Grano único de ítem de licitación |
| `SQL-GRAIN-003` | Grano único de adjudicación |
| `SQL-GRAIN-004` | Grano único de ítem adjudicado |
| `SQL-GRAIN-005` | Grano único de contrato |
| `SQL-GRAIN-006` | Grano único de ítem contractual |
| `SQL-GRAIN-007` | Grano único de participación de ofertante |
| `SQL-GRAIN-008` | Grano único de proveedor adjudicado |
| `SQL-REF-001` | `DBCC CHECKCONSTRAINTS` no devuelve violaciones |
| `SQL-REF-002` | Contratos con `award_id` resuelven la adjudicación del mismo proceso |
| `SQL-LINEAGE-001` | Linaje de hechos y puentes coincide con el lote activo |
| `SQL-BRIDGE-001` | Los puentes factless no contienen medidas monetarias |
| `SQL-BUS-001` | Conteo observado de ofertantes coincide con su puente |
| `SQL-BUS-002` | Conteo de proveedores adjudicados coincide con su puente |
| `SQL-BUS-003` | Adjudicación atribuida solo con proveedor único |
| `SQL-BUS-004` | Ítem adjudicado hereda atribución aprobada |
| `SQL-BUS-005` | Contrato hereda atribución aprobada |
| `SQL-BUS-006` | Ítem contractual hereda atribución aprobada |
| `SQL-CALC-001` | Conversión PEN y bandera de disponibilidad son reproducibles |
| `SQL-CALC-002` | Sumas de ítems, diferencias y tolerancia 0.01 son reproducibles |
| `SQL-CALC-003` | Banderas de clasificación coinciden con clave 0 |
| `SQL-CALC-004` | Bandera de monto cero coincide con el valor |

## Reglas de advertencia

| ID | Control | Interpretación |
|---|---|---|
| `SQL-WARN-001` | RUC de proveedor con formato publicado inválido | Calidad estructural, no juicio legal |
| `SQL-WARN-002` | Conflicto de nombres de proveedor | Variantes conservadas y canonización visible |
| `SQL-WARN-003` | Conflicto de descripción de categoría | Misma clave con textos oficiales distintos |
| `SQL-WARN-004` | Ofertantes declarados ≠ observados | Diferencia entre header y detalle |
| `SQL-WARN-005` | Licitación header–ítem difiere más de S/ 0.01 | Se conserva la diferencia, no se fuerza igualdad |
| `SQL-WARN-006` | Adjudicación header–ítem difiere más de S/ 0.01 | Se conserva la diferencia |
| `SQL-WARN-007` | Contrato header–ítem difiere más de S/ 0.01 | Se conserva la diferencia |
| `SQL-WARN-008` | Moneda extranjera sin tasa PEN publicada | No se inventa conversión |
| `SQL-WARN-009` | Contrato sin valor final | KPI de ejecución aplazado |
| `SQL-WARN-010` | Monto negativo | Incidencia observable; cero casos en el piloto |
| `SQL-WARN-011` | Licitación con monto cero | Caso explícitamente marcado, no descartado |

## Reconciliaciones adicionales

Las 45 reglas se complementan con:

- 38 comparaciones de filas Python↔auditoría↔SQL;
- 52 comparaciones monetarias por control, moneda y capa;
- 14 comparaciones de identidad, hashes y totales de artefactos;
- 9 comparaciones exactas de incidencias Python↔SQL.

Estas reconciliaciones son bloqueantes aunque no pertenezcan al catálogo de advertencias.
