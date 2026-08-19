# Fase 2 — Descarga y Data Profiling

## Muestra validada

| Atributo | Valor |
|---|---|
| Fuente | OECE, Portal de Contrataciones Abiertas |
| Sistema | SEACE V3 |
| Periodo segmentado | Julio de 2026 |
| Fecha de snapshot | 2026-08-19 |
| Formatos RAW | CSV ZIP, JSON ZIP y SHA |
| Tamaño ZIP CSV | 8,052,765 bytes |
| Tamaño ZIP JSON | 7,718,087 bytes |
| Tamaño JSON descomprimido | 76,209,866 bytes |
| Checksum oficial JSON | PASS |

## Resultado estructural

| Métrica | Resultado |
|---|---:|
| Tablas CSV | 22 |
| Procesos compilados únicos (`records.csv`) | 6,452 |
| Releases | 80,789 |
| Filas acumuladas entre tablas | 231,123 |
| Celdas perfiladas | 2,359,020 |
| Celdas nulas | 304,801 |
| Nulos globales, solo referencia estructural | 12.9207% |
| Duplicados exactos adicionales | 10 |
| Tamaño CSV descomprimido | 65,839,313 bytes |
| Memoria estimada de DataFrames | 79,694,079 bytes |
| Tiempo de perfilado con controles referenciales | 45.7273 s |

La suma de filas no debe interpretarse como cantidad de procedimientos. La unidad raíz validada es 6,452 `ocid`; las demás filas corresponden a distintas granularidades.

## Integridad y granularidad

- `records.csv`: `ocid` completo y único, 6,452 de 6,452.
- 41 controles hijo-padre de `ocid` y `compiledRelease/id`: **PASS**, sin huérfanos.
- 20 de 22 granos candidatos: completos y únicos.
- `com_ten_ite_tot_exchangeRates.csv`: 10 duplicados exactos adicionales en 120 filas; son 10 grupos repetidos dos veces.
- `com_ten_ite_additionalClassific.csv`: una fila con `scheme=UNSPSC`, pero sin identificador ni descripción de clasificación.
- No se encontraron columnas 100% nulas.

## Cobertura relevante para el MVP

- Compradores: 1,450 identificadores distintos en `records.csv`.
- Procesos con adjudicación: 3,343 `ocid`; 3,397 filas de adjudicación.
- Filas de proveedor adjudicado: 3,396; 2,960 identificadores de proveedor distintos en esta tabla.
- Procesos con contrato: 1,102 `ocid`; 1,119 contratos.
- Ítems de licitación: 7,359.
- Clasificación principal de ítem: 1,281 nulos, equivalentes a 17.41%.
- Valor de licitación y `amount_PEN`: completos en los 6,452 registros raíz.
- Número de ofertantes: 34.24% de nulos.
- Método de contratación genérico: 63.48% de nulos, aunque `procurementMethodDetails` está completo.
- Presupuesto de planificación: 82.92% de nulos.
- Valor final de implementación contractual: 99.73% de nulos; fecha final de implementación: 99.91% de nulos.

## Interpretación

El piloto confirma que el MVP es técnicamente viable para demanda, categorías, adjudicaciones, proveedores, compradores y contratos. No confirma todavía viabilidad para ejecución contractual final, porque los campos de implementación casi no tienen cobertura.

Los nulos de partes y direcciones deben analizarse por rol. Mezclar compradores, ofertantes y proveedores en una sola tasa de completitud produciría una conclusión engañosa.

## Decisiones para la siguiente fase

1. Mantener `records.csv` como tabla raíz de la capa de staging.
2. Conservar `releases.csv` para trazabilidad temporal, sin usarlo directamente como hecho de gasto.
3. Separar tablas hijas por adjudicación, contrato, ítem, parte y documento.
4. Crear una regla de deduplicación controlada para las tasas de cambio, conservando métricas antes/después.
5. Tratar la clasificación faltante como dimensión “sin clasificar”, sin inventar códigos.
6. No diseñar KPIs de ejecución con `finalValue` hasta incorporar otra fuente oficial o demostrar cobertura suficiente.
