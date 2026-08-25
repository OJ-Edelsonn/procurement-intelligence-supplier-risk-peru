# Metodología de Market Concentration

## Objetivo

La Fase 11 mide cómo se distribuye el monto de ítems adjudicados entre proveedores dentro de una categoría estándar. El resultado describe estructura observada y sirve como variable para inteligencia de mercado; no constituye una evaluación legal ni una acusación de conducta.

## Definición de mercado

```text
mercado = categoría estándar gobernada × source_period
```

La unidad monetaria es `fact_award_item.total_amount_pen_calculated`. Solo ingresan a las participaciones montos positivos atribuibles a exactamente un proveedor oficial. La categoría desconocida se excluye y su pérdida de cobertura permanece cuantificada.

No se utiliza el total de contratación pública como un único mercado porque proveedores de categorías diferentes no necesariamente compiten entre sí.

## Métricas

Para cada proveedor `i` en el mercado:

```text
share_i = monto_i / monto_atribuible_mercado
HHI = Σ (share_i × 100)²
proveedores_efectivos = 10,000 / HHI
```

- Top 1, 3, 5 y 10 share acumulan las mayores participaciones.
- HHI varía entre valores cercanos a 0 y 10,000; aumenta cuando la distribución se concentra.
- El número efectivo expresa cuántos proveedores de igual tamaño producirían un HHI equivalente.
- No se adoptan bandas regulatorias o legales. Se publican el valor y sus componentes.

## Elegibilidad descriptiva

Un mercado entra en rankings interpretables cuando cumple simultáneamente:

- al menos 3 proveedores;
- al menos 2 compradores;
- al menos 5 ítems adjudicados;
- al menos 95% de cobertura monetaria atribuible.

Los demás mercados permanecen en la evidencia, pero no se usan para conclusiones comparativas. Un mercado con un único proveedor puede reflejar baja cobertura, especialización o alcance estrecho; no prueba ausencia de competencia.

## Validación independiente

Python vuelve a sumar las participaciones y recalcula HHI para cada categoría. La fase falla si:

- las participaciones no suman 100% dentro de tolerancia `0.001`;
- HHI SQL y Python difieren más de `0.001`;
- el número de filas proveedor no coincide con el conteo SQL.

## Power BI

`powerbi/dax/phase11_concentration_measures.dax` implementa monto atribuible, shares, Top N, HHI y proveedores efectivos. Estas medidas requieren contexto de una categoría estándar; un HHI agregado sin mercado filtrado no es interpretable.

## Ejecución

```powershell
.\.venv\Scripts\run-market-concentration.exe `
  --config config\market_concentration.yml `
  --env-file .env
```

## Limitaciones

- Existe un solo periodo fuente; no se mide persistencia.
- La clasificación estándar cubre 81.9499% de los ítems adjudicados.
- HHI monetario no captura calidad, capacidad, condiciones técnicas ni participación de postores no adjudicados.
- Una adjudicación o ítem de gran magnitud puede dominar el snapshot.
- El análisis no determina colusión, irregularidad, poder de mercado jurídico ni riesgo legal.
