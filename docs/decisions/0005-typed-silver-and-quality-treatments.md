# ADR 0005: Parquet tipado y tratamientos de calidad en Silver

- Estado: aceptada
- Fecha: 2026-08-20

## Contexto

La puerta de la Fase 4 bloqueó el lote piloto por 10 duplicados exactos adicionales y una clave de clasificación nula. También identificó RUC con formato inválido, clasificaciones incompletas, montos cero y baja cobertura de `finalValue`. La capa Silver debe resolver lo estructural sin ocultar ni reinterpretar los datos publicados.

## Decisión

1. Generar una tabla Parquet por cada una de las 22 tablas CSV y particionarla por periodo y fecha de snapshot.
2. Usar nombres `lower_snake_case` y tipos Arrow estrictos; representar números no enteros como `decimal128(38,14)` sin redondeo.
3. Conservar la primera fila de cada duplicado exacto y enviar las 10 ocurrencias adicionales a una cuarentena trazable.
4. Representar componentes nulos de clasificación mediante el miembro explícito `__UNCLASSIFIED__ / Sin clasificar / UNKNOWN` y una bandera de procedencia.
5. Preservar RUC, montos cero y `finalValue` nulos, añadiendo banderas técnicas en lugar de modificar o eliminar valores.
6. Agregar nueve campos de linaje a cada fila y derivar un `ingestion_run_id` determinístico del snapshot y el contrato.
7. Exigir cero duplicados, granos nulos, granos repetidos y clasificaciones incompletas después del tratamiento para promover el lote.
8. Mantener RAW fuera de Git e inmutable; versionar solo el contrato, el código, las pruebas, la documentación y un resumen sin rutas privadas.

## Consecuencias

- El snapshot piloto pasa de `BLOCKED` a `PASS_WITH_WARNINGS` y queda elegible para el modelado.
- La reconciliación permite explicar cada diferencia de filas mediante la cuarentena.
- Los consumidores pueden filtrar o segmentar por banderas sin perder el dato original.
- El almacenamiento tipado reduce conversiones ambiguas y ocupa 86.2025% menos que los CSV descomprimidos en el piloto.
- Cada periodo adicional debe verificar schema drift y ejecutar la misma comparación antes/después.

## Alternativas descartadas

- **Eliminar todos los registros con advertencias:** introduciría sesgo y perdería observaciones válidas.
- **Corregir RUC o clasificaciones por inferencia:** no existe evidencia oficial suficiente para hacerlo de forma general.
- **Usar `float64` para montos y tasas:** puede introducir errores binarios y redondeos no autorizados.
- **Cargar directamente a SQL Server:** mezclaría transformación, calidad y persistencia antes de estabilizar el contrato Silver.
- **Mantener nombres JSON sin normalizar:** complica SQL, pruebas y consumo posterior.
