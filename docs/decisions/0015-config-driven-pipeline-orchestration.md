# ADR 0015 — Orquestación local gobernada por configuración

## Contexto

Las fases 1–14 disponían de comandos reproducibles, pero no existía un punto de entrada único ni evidencia integrada de ejecución.

## Decisión

Usar `config/pipeline.yml` como contrato de orden, argumentos, artefactos y estados aceptables. El orquestador ejecuta módulos aislados, detiene el flujo ante el primer gate no aceptado, registra hashes y permite reutilización explícita de artefactos válidos.

Descarga y capa semántica de Power BI son opcionales. La generación PBIP se mantiene fuera de la corrida para proteger ediciones manuales.

## Consecuencias

El pipeline core puede repetirse con un comando y auditarse sin adoptar todavía Airflow, Prefect o un servicio cloud. Un nuevo periodo exige actualizar contratos; no se infiere automáticamente.

