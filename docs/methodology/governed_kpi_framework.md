# Marco de KPIs gobernados

## Propósito

La Fase 10 convierte hallazgos exploratorios en métricas con definición, fórmula, grano, unidad, denominador y regla de cobertura. El contrato canónico es `config/kpis.yml`; cuatro consultas SQL calculan los resultados y `run_kpis.py` los reconcilia con la evidencia de las Fases 8 y 9.

## Principios

1. Cada monto permanece en su hecho nativo: proceso, adjudicación o contrato.
2. Las monedas solo se agregan en PEN cuando existe conversión gobernada.
3. El ticket promedio usa filas con PEN calculable y publica su denominador.
4. Las claves sustitutas desconocidas se excluyen de conteos de entidades.
5. Los porcentajes de presencia contractual describen cobertura observada; no son conversión causal.
6. Un solo `source_period` no habilita crecimiento, YoY ni recurrencia histórica.
7. Concentración y scores se implementan únicamente en sus fases metodológicas.

## Familias de medidas

| Familia | Grano | Ejemplos |
|---|---|---|
| Demanda | proceso | procesos, monto licitado, ticket promedio |
| Resultado | adjudicación | adjudicaciones, monto adjudicado, ticket promedio |
| Formalización | contrato | contratos, monto contractual, cobertura PEN |
| Comprador | comprador | compradores activos y ranking de demanda |
| Proveedor | proveedor atribuible | proveedores adjudicados y diversificación de compradores |
| Competencia | proceso | cobertura y promedio de ofertantes observados |
| Categoría | ítem adjudicado | monto y cobertura de clasificación estándar |
| Calidad | grano de la métrica | ceros, atribución y disponibilidad monetaria |

## Reglas de cobertura

- Una suma monetaria informa filas con PEN sobre filas totales.
- El ticket promedio divide la suma PEN entre filas con PEN, no entre todas las filas.
- La atribución a proveedor requiere exactamente un proveedor oficial en la adjudicación.
- La competencia se calcula sobre procesos con detalle observado; la cobertura muestra cuánto representa ese subconjunto.
- La clasificación estándar excluye el miembro desconocido del numerador, pero lo conserva en el denominador.

## Reconciliación

Siete métricas críticas se contrastan con el JSON de Fase 9: procesos, compradores, conteos y montos de licitación, adjudicación y contrato. Una diferencia mayor a `0.000001` bloquea la publicación.

## Power BI

`powerbi/dax/phase10_kpi_measures.dax` contiene medidas equivalentes sobre las tablas físicas del DW. Los porcentajes se modelan como fracciones DAX y se formatearán como porcentaje en Power BI. Las medidas no incluyen HHI, crecimiento ni scores.

## Ejecución

```powershell
.\.venv\Scripts\run-procurement-kpis.exe `
  --config config\kpis.yml `
  --env-file .env
```

El proceso es de solo lectura respecto de SQL Server y reemplaza únicamente artefactos derivados bajo `reports/kpis/`.

## Limitaciones

- Un snapshot de publicación no constituye una serie histórica.
- Las fechas de negocio internas no sustituyen periodos fuente comparables.
- El texto geográfico no está homologado con UBIGEO.
- El valor final de implementación contractual tiene cobertura insuficiente.
- Los rankings de un periodo no prueban liderazgo sostenido ni oportunidad comercial.
