# ADR 0006: Constelación dimensional por grano de ciclo de vida

- Estado: aceptada
- Fecha: 2026-08-20

## Contexto

Los datos Silver contienen procesos, ofertantes, ítems, adjudicaciones, proveedores y contratos con relaciones uno-a-muchos. Una fila por proceso no puede conservar simultáneamente sus medidas nativas sin agregar o repetir importes. Releases y documentos agregan historia y evidencia, pero no son hechos monetarios.

## Decisión

1. Implementar una constelación con 8 dimensiones, 6 hechos y 2 puentes factless.
2. Separar cabeceras e ítems de licitación, adjudicación y contrato.
3. Usar `dim_process` para identidad transversal del OCID y dimensiones conformadas para fecha, comprador, proveedor, categoría, método, moneda y unidad.
4. Modelar CUBSO y UNSPSC como roles de una dimensión de categoría.
5. Usar SCD Tipo 1 para identidades sin fechas efectivas oficiales, preservando conflictos y linaje.
6. Reservar clave sustituta 0 para desconocido, sin clasificar o no atribuible.
7. Atribuir un monto a proveedor solo cuando exista exactamente un proveedor oficial.
8. Prohibir medidas monetarias en puentes.
9. Mantener monto original y PEN; dejar PEN nulo cuando falte tasa OECE.
10. Mantener releases, documentos y tasas como Staging/Audit o insumos de derivación.

## Consecuencias

- El proceso completo puede analizarse aunque no tenga adjudicación o contrato.
- Los montos de demanda, adjudicación y formalización no se mezclan.
- El análisis por proveedor evita replicar importes de consorcios o relaciones múltiples.
- Power BI necesitará medidas explícitas por hecho y dimensiones role-playing.
- La Fase 7 debe generar DDL, restricciones y cargas a partir del contrato gobernado.

## Alternativas descartadas

- **Tabla ancha por OCID:** multiplica o agrega hijos y oculta diferencias de grano.
- **Hecho único de ciclo de vida:** mezcla procesos con cero, una o varias adjudicaciones/contratos.
- **Modelo de releases como estrella principal:** convierte actualizaciones en aparentes transacciones económicas.
- **Asignación igual entre proveedores:** inventa una distribución no publicada.
- **SCD Tipo 2 por snapshot:** confunde fecha de observación con vigencia legal del atributo.
