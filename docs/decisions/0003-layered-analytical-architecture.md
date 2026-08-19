# ADR 0003: Arquitectura analítica por capas y consumo gobernado

- Estado: aceptada
- Fecha: 2026-08-19

## Contexto

El piloto OCDS contiene 22 tablas con distintas granularidades y relaciones uno-a-muchos. Cargar archivos directamente a Power BI o construir una tabla plana duplicaría procedimientos y montos, dificultaría la auditoría y mezclaría releases históricos con records compilados.

## Decisión

1. Adoptar el flujo RAW/Bronze → Staging/Silver → SQL `stg` → SQL `dw` → Power BI.
2. Mantener metadatos y auditoría como un flujo transversal, con cuarentena para fallos recuperables.
3. Usar `records.csv` como raíz consolidada por `ocid` y conservar `releases.csv` como historial técnico.
4. Modelar procesos, ítems, adjudicaciones, contratos y sus relaciones como hechos/puentes separados.
5. Permitir que Power BI consuma únicamente vistas gobernadas del esquema `dw`.
6. Mantener RAW, Parquet, bases y PBIX fuera de Git; versionar código, DDL, reglas y documentación.

## Consecuencias

- Los KPIs serán reproducibles y reconciliables con la fuente.
- Se requiere más disciplina de ETL y pruebas que una importación directa.
- Cada medida deberá declarar grano, fecha y moneda.
- Agregar una fuente complementaria exigirá registrarla, perfilarla y demostrar reconciliación antes de integrarla.
- El diseño puede migrar de SQL Server Express sin cambiar los contratos lógicos.

## Alternativas descartadas

- **Una tabla plana universal:** introduce duplicación por proveedores, ítems y documentos.
- **Power BI conectado a CSV/ZIP:** dispersa transformación y calidad dentro del reporte.
- **Usar releases como hechos:** contabiliza revisiones del mismo proceso como observaciones independientes.
- **Guardar RAW en Git/OneDrive:** aumenta riesgos de tamaño, sincronización, privacidad y sobrescritura.
