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

La conexión real a SQL Server se probará cuando exista la base del proyecto. El controlador configurado es `ODBC Driver 18 for SQL Server` y la instancia local prevista es `localhost\SQLEXPRESS`.
