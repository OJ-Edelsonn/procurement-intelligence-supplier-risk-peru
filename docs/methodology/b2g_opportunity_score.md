# Metodología del B2G Commercial Opportunity Score

## Propósito

El score prioriza relativamente categorías que una empresa podría investigar para vender al Estado. Es una herramienta de triage comercial, no una predicción de ventas, probabilidad de adjudicación, rentabilidad ni recomendación automática.

La versión piloto `b2g-opportunity-pilot-v1` utiliza los 87 mercados que aprobaron elegibilidad en Fase 11.

## Variables y ponderaciones

| Variable | Peso | Dirección | Justificación |
|---|---:|---|---|
| Tamaño del mercado | 30% | mayor favorece | aproxima escala de demanda observada |
| Frecuencia de ítems | 20% | mayor favorece | representa cantidad de eventos de compra observados |
| Diversidad de compradores | 20% | mayor favorece | reduce dependencia de una sola entidad |
| Ticket promedio por ítem | 15% | mayor favorece | aproxima escala media de transacción |
| Apertura relativa | 15% | menor HHI favorece | reduce dominancia monetaria observada de incumbentes |

No se asigna un proxy a crecimiento o recurrencia: ambas variables requieren periodos fuente comparables. Inventar sustitutos ocultaría la limitación principal del piloto.

## Normalización

Cada variable se convierte a un percentil 0–100 dentro de la población elegible:

```text
percentil = 100 × (rango_promedio - 1) / (N - 1)
score = Σ (percentil_variable × peso_variable)
```

Para HHI la dirección se invierte, de modo que menor concentración produce mayor componente de apertura. Los percentiles reducen el dominio de valores monetarios extremos y mantienen una explicación sencilla.

El resultado no debe compararse con otra versión o población sin recalibración.

## Bandas relativas

- `HIGHER_RELATIVE`: primeras posiciones hasta 20% de la población.
- `MEDIUM_RELATIVE`: siguiente tramo hasta 60%.
- `LOWER_RELATIVE`: posiciones restantes.

Estas bandas ordenan investigación. No significan que una categoría sea objetivamente buena, rentable o accesible para cualquier empresa.

## Sensibilidad

Se recalcula el score en tres escenarios:

| Escenario | Enfoque |
|---|---|
| `demand_heavy` | 65% combinado en tamaño y frecuencia |
| `accessibility_heavy` | 55% combinado en compradores y apertura |
| `balanced_equal` | 20% para cada variable |

Se publican correlación de rankings, coincidencia Top 10, cambio medio y cambio máximo. Un mercado con alto cambio de rango requiere revisar la preferencia de negocio antes de priorizarlo.

## Validación

- pesos de cada escenario suman 1;
- componentes y score permanecen entre 0 y 100;
- Python recalcula el score de cada categoría;
- los 87 mercados cuentan con validación individual;
- CSV, figuras, configuración y gate conservan hashes.

## Ejecución

```powershell
.\.venv\Scripts\run-opportunity-score.exe `
  --config config\opportunity_score.yml
```

## Limitaciones

- Un único periodo fuente impide medir crecimiento y recurrencia.
- El score no considera capacidades, costos, certificaciones o estrategia de una empresa concreta.
- No estima probabilidad de ganar ni retorno.
- HHI es descriptivo y no implica conducta del proveedor.
- Ponderaciones distintas pueden cambiar posiciones; la sensibilidad lo hace visible.
