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
| jupyterlab | Exploración y notebooks reproducibles |
| pytest | Pruebas automatizadas |

## Verificación rápida

```powershell
.\.venv\Scripts\python.exe -c "import numpy, pandas, openpyxl, pyarrow, sqlalchemy, pyodbc, yaml, requests; print('PASS')"
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
