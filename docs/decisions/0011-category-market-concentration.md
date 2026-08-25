# ADR 0011: Concentración por categoría estándar y monto atribuible

- Estado: aceptada
- Fecha: 2026-08-24

## Contexto

Calcular una participación sobre todo el gasto público mezclaría mercados no comparables. Además, los bridges no pueden recibir montos y una adjudicación con múltiples proveedores no permite asignar valor sin una regla oficial.

## Decisión

1. Definir cada categoría estándar y periodo fuente como un mercado descriptivo.
2. Usar monto positivo PEN a nivel de ítem adjudicado.
3. Atribuir monto solo cuando el hecho ya identifica un proveedor único.
4. Calcular Top 1/3/5/10, HHI y número efectivo de proveedores.
5. Exigir umbrales de proveedores, compradores, ítems y cobertura para rankings interpretables.
6. Recalcular HHI independientemente en Python y versionar DAX equivalente.
7. No usar bandas legales ni inferir conducta anticompetitiva.

## Consecuencias

- La concentración tiene mercado y denominador explícitos.
- Se evita replicar montos a través de bridges.
- Categorías estrechas o con poca observación permanecen visibles pero no se priorizan.
- Los resultados son utilizables como insumo transparente de Fase 12, no como recomendación autónoma.

## Alternativas descartadas

- **Mercado nacional agregado:** mezcla categorías no sustituibles.
- **Número de adjudicaciones en lugar de monto:** ignora diferencias materiales de escala.
- **Reparto igual entre múltiples proveedores:** inventa asignaciones.
- **Etiquetas legales de concentración:** exceden el alcance analítico del dataset.
