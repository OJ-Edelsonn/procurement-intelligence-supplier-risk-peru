# Fase 15 — Automatización reproducible

## Objetivo

Convertir los comandos independientes de las fases anteriores en una sola ejecución gobernada, auditable y segura para el snapshot vigente.

## Contrato

`config/pipeline.yml` define orden, módulo Python, argumentos, artefacto esperado, ruta del estado y estados aceptables. El ejecutor no interpreta un código de salida cero como evidencia suficiente: cuando corresponde, abre el JSON generado, valida su estado y calcula SHA-256.

## Flujo

1. comprobar que el registro de fuentes y su documento coinciden;
2. opcionalmente descargar el snapshot inmutable;
3. perfilar y evaluar calidad RAW;
4. transformar a Silver y validar el modelo dimensional;
5. cargar y reconciliar SQL Server;
6. ejecutar EDA, KPIs, concentración y scores;
7. opcionalmente actualizar la capa semántica SQL para Power BI.

La generación del esqueleto PBIP no forma parte de la corrida normal porque volver a generarlo eliminaría modificaciones visuales manuales. Power BI se habilita únicamente con `--include-powerbi` y dicha opción actualiza la capa semántica, no publica el informe.

## Reutilización e idempotencia

Los artefactos upstream costosos pueden declararse `reuse_if_valid`. Solo se reutilizan si existen y su estado está permitido. La calidad RAW del piloto conserva `BLOCKED` porque `DQ-UNIQ-001` detecta diez duplicados adicionales; la política permite exclusivamente ese bloqueante conocido y exige después un ETL Silver promovible con las diez filas en cuarentena.

Para un entorno limpio, la ausencia de artefactos dispara la ejecución. Para el snapshot ya validado, la reutilización evita reescribir Silver y mantiene coherente el lote SQL auditado. `--force` debe reservarse para una recarga revisada.

## Observabilidad

Cada corrida produce:

- fecha, duración y selección de etapas;
- comando sanitizado;
- código de salida y cola de stdout/stderr;
- resultado por etapa;
- ruta, estado y SHA-256 del artefacto;
- conteos de pasos ejecutados, reutilizados, omitidos y fallidos;
- log local bajo `logs/pipeline/`, excluido de Git.

El reporte se escribe incluso cuando una etapa falla y el pipeline se detiene en el primer gate no aceptado.

## Limitaciones

- La configuración vigente representa un snapshot mensual piloto, no un calendario histórico completo.
- La descarga se excluye por defecto para no depender de red al repetir análisis.
- La actualización/publicación en Power BI Service no está implementada.
- No existe orquestador externo ni programación horaria; el comando local es el mecanismo reproducible del MVP.

