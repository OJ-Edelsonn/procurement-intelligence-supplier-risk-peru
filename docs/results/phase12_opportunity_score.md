# Fase 12 — B2G Commercial Opportunity Score

## Resultado ejecutivo

| Métrica | Resultado |
|---|---:|
| Estado | `PASS_PILOT` |
| Versión | `b2g-opportunity-pilot-v1` |
| Mercados puntuados | 87 |
| Validaciones | 87/87 |
| Banda relativa superior | 17 |
| Banda relativa media | 35 |
| Banda relativa inferior | 35 |
| Escenarios de sensibilidad | 3 |
| Figuras | 3 |

## Primer resultado

La categoría `72141107`, servicios de construcción y reparación de puentes, ocupa la posición 1 con score 96.57. Sus cinco componentes están por encima del percentil 91 y conserva la posición 1 en los tres escenarios.

Este resultado significa “mayor prioridad relativa para investigación bajo la metodología piloto”; no significa venta esperada, facilidad de adjudicación ni retorno garantizado.

## Top 10

| Rank | Código | Categoría | Score |
|---:|---|---|---:|
| 1 | 72141107 | Construcción y reparación de puentes | 96.57 |
| 2 | 72141121 | Construcción de tuberías principales de agua | 93.90 |
| 3 | 72153102 | Construcción de campos deportivos interiores | 91.69 |
| 4 | 72141003 | Mantenimiento de pistas y carreteras | 90.81 |
| 5 | 72121406 | Construcción de escuelas | 90.58 |
| 6 | 15101505 | Diesel | 87.62 |
| 7 | 72141128 | Remodelación o construcción de plazas públicas | 86.86 |
| 8 | 72141001 | Construcción de pistas y carreteras nuevas | 82.09 |
| 9 | 81101508 | Ingeniería arquitectónica | 81.16 |
| 10 | 80131502 | Alquiler de instalaciones comerciales o industriales | 80.35 |

## Sensibilidad

| Escenario | Correlación | Top 10 común | Cambio medio de rank | Cambio máximo |
|---|---:|---:|---:|---:|
| Demanda intensiva | 0.9972 | 10/10 | 1.24 | 5 |
| Accesibilidad intensiva | 0.9652 | 9/10 | 5.21 | 16 |
| Pesos iguales | 0.9970 | 10/10 | 1.43 | 6 |

El escenario de accesibilidad produce la mayor variación, por lo que preferencias sobre apertura y diversidad de compradores deben discutirse antes de una decisión real.

## Variables excluidas

- Crecimiento: sin periodos comparables.
- Recurrencia: sin historia multi-periodo.
- Geografía: sin dimensión UBIGEO gobernada.
- Sanciones: fuente no ingerida y no corresponde al objetivo de oportunidad.

## Evidencia

- `config/opportunity_score.yml`.
- `reports/opportunity/oece_ocds_seace_v3_2026_07_opportunity_score.json`.
- `reports/opportunity/oece_ocds_seace_v3_2026_07_opportunity_score.csv`.
- `reports/opportunity/figures/`.

No se incorporó una fuente nueva.
