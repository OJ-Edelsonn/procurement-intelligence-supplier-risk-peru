# ADR 0012: Opportunity Score transparente basado en percentiles

- Estado: aceptada para piloto
- Fecha: 2026-08-24

## Contexto

Las variables candidatas tienen escalas y colas muy diferentes. El piloto no posee historia comparable para crecimiento o recurrencia y no existe información sobre capacidades de una empresa específica.

## Decisión

1. Puntuar únicamente los 87 mercados elegibles de Fase 11.
2. Usar tamaño, frecuencia, compradores, ticket y apertura relativa.
3. Normalizar con percentiles 0–100 dentro de la población.
4. Aplicar pesos 30/20/20/15/15 explícitos.
5. Excluir crecimiento y recurrencia sin proxies.
6. Recalcular tres escenarios de sensibilidad.
7. Publicar score, componentes, ranking, banda y estabilidad.
8. Etiquetar la versión como piloto y prohibir afirmaciones de ventas o rentabilidad.

## Consecuencias

- El cálculo puede explicarse y reproducirse sin Machine Learning.
- Los outliers monetarios no dominan linealmente el score.
- Las posiciones dependen de la población y la versión.
- La sensibilidad distingue resultados robustos de los dependientes de pesos.

## Alternativas descartadas

- **Min-max sobre montos crudos:** excesivamente sensible a outliers.
- **Modelo de Machine Learning:** no existe una variable objetivo de éxito comercial.
- **Imputar crecimiento:** fabricaría señal temporal.
- **Score universal:** ignora estrategia y capacidades de cada empresa.
