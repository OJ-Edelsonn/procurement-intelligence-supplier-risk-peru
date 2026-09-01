# Runbook del pipeline

## Prerrequisitos

1. Crear `.venv` e instalar `requirements-dev.txt`.
2. Configurar `.env` siguiendo `.env.example`.
3. Verificar que `SQL Server (SQLEXPRESS)` esté iniciado.
4. Confirmar que el snapshot RAW y los metadatos estén bajo `DATA_ROOT`.

## Ensayo seguro

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.automation.run_pipeline `
  --config config\pipeline.yml `
  --env-file .env `
  --dry-run
```

## Corrida estándar

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.automation.run_pipeline `
  --config config\pipeline.yml `
  --env-file .env
```

Descarga y Power BI se omiten. Los artefactos upstream válidos se reutilizan; SQL validation y la analítica se vuelven a ejecutar.

## Seleccionar un tramo

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.automation.run_pipeline `
  --from-step validate_sql_server `
  --to-step supplier_exposure
```

Los identificadores válidos y su orden están en `config/pipeline.yml`.

## Opciones explícitas

- `--include-download`: consulta la fuente oficial y aplica la lógica inmutable de descarga.
- `--include-powerbi`: despliega las tablas y vistas semánticas SQL; no modifica visuales ni publica.
- `--force`: ignora reutilización. Puede reescribir Silver y solicitar reemplazo del snapshot SQL; usar solo después de revisar fuente, periodo, checksum y destino.
- `--report`: permite conservar una evidencia alternativa sin reemplazar el reporte estándar.

## Evidencia y diagnóstico

- Reporte auditable: `reports/automation/phase15_pipeline_run.json`.
- Log local: `logs/pipeline/<run_id>.log`.
- `FAIL` indica código distinto de cero, artefacto ausente o estado no autorizado.
- `PASS_WITH_WARNINGS` conserva hallazgos aceptados y no equivale a ausencia de problemas de fuente.

Ante un fallo, revisar primero `step_id`, `error`, `stderr_tail` y el artefacto declarado. No usar `--force` para ocultar un gate rechazado.

## Nuevo periodo

El MVP no infiere periodos automáticamente. Antes de ejecutar otro corte se deben incorporar sus metadatos al registro maestro, ajustar los contratos que aún contienen el periodo piloto, validar el checksum y revisar si es comparable. Esto evita mezclar snapshots o declarar crecimiento sin historia suficiente.

