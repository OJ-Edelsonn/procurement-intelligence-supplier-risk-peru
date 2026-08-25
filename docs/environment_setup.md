# Entorno de desarrollo

## Estrategia

El proyecto usa un entorno virtual `.venv` para evitar modificar el Python global y aislar versiones. `pip` descarga los paquetes desde Python Package Index (PyPI) y resuelve sus dependencias transitivas.

Las dependencias se separan en:

- `requirements.txt`: ejecución de ingesta, transformación y acceso a datos.
- `requirements-dev.txt`: lo anterior más JupyterLab y pytest.

## Instalación en Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

No es obligatorio activar el entorno. Para activarlo:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Responsabilidad de cada paquete

| Paquete | Uso previsto |
|---|---|
| numpy | Operaciones numéricas y base de cálculo vectorizado |
| pandas | Tablas, perfilado, limpieza y conciliación |
| openpyxl | Lectura/escritura de archivos XLSX |
| pyarrow | Parquet y procesamiento columnar |
| SQLAlchemy | Capa de conexión y carga SQL |
| pyodbc | Driver Python hacia SQL Server mediante ODBC |
| python-dotenv | Configuración local desde `.env` |
| PyYAML | Lectura de configuración YAML |
| requests | Descargas HTTP controladas |
| matplotlib | Visualizaciones estáticas reproducibles del EDA |
| jupyterlab | Exploración y notebooks reproducibles |
| pytest | Pruebas automatizadas |

## Verificación rápida

```powershell
.\.venv\Scripts\python.exe -c "import numpy, pandas, openpyxl, pyarrow, sqlalchemy, pyodbc, yaml, requests, matplotlib; print('PASS')"
.\.venv\Scripts\python.exe -m jupyter --version
.\.venv\Scripts\python.exe -m pytest --version
```

## SQL Server local

La Fase 7 fue validada con SQL Server 2022 Express de 64 bits, `ODBC Driver 18 for SQL Server` y autenticación integrada de Windows. Antes de cargar, iniciar `SQL Server (SQLEXPRESS)` desde `services.msc` o SQL Server Configuration Manager.

Variables esperadas en `.env`:

```dotenv
SQL_SERVER=localhost\SQLEXPRESS
SQL_DATABASE=ProcurementIntelligence
SQL_DRIVER=ODBC Driver 18 for SQL Server
SQL_TRUSTED_CONNECTION=yes
SQL_ENCRYPT=yes
SQL_TRUST_SERVER_CERTIFICATE=yes
```

No añadir usuario ni contraseña al repositorio. Verificación sin mostrar la cadena:

```powershell
.\.venv\Scripts\python.exe -c "from procurement_intelligence.settings import load_sql_server_settings; from procurement_intelligence.loading.sql_server import connect_sql_server; c=connect_sql_server(load_sql_server_settings(),'master'); print(c.cursor().execute('SELECT 1').fetchval()); c.close()"
```

## Validación SQL de solo lectura

Después de cargar el snapshot, la Fase 8 comprueba el lote sin modificar la base:

```powershell
.\.venv\Scripts\validate-sql-server.exe `
  --env-file .env `
  --output reports\sql\oece_ocds_seace_v3_2026_07_phase8_validation.json
```

Código de salida 0 significa `PASS` o `PASS_WITH_WARNINGS`; 1 indica un fallo bloqueante. Con `--strict-warnings`, las advertencias devuelven código 2 para escenarios de integración continua que requieran revisión manual.

## Análisis exploratorio reproducible

Con la puerta de Fase 8 aprobada y SQL Server iniciado:

```powershell
.\.venv\Scripts\run-procurement-eda.exe `
  --config config\eda.yml `
  --env-file .env
```

El comando escribe el resumen JSON, el informe Markdown y siete figuras bajo `reports/eda/`. Los argumentos `--output`, `--markdown-output` y `--figures-dir` permiten destinos alternativos dentro del proyecto; no cambian las consultas ni el contrato analítico.
