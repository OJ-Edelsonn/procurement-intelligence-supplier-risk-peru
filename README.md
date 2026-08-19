# Procurement Intelligence & Supplier Risk — Perú

Solución end-to-end de Data/BI para analizar contratación pública peruana, inteligencia comercial y exposición a proveedores usando datos abiertos oficiales de OECE/SEACE.

> Estado: inicialización técnica y definición del MVP. Todavía no se publican resultados analíticos ni métricas de negocio.

## Problema de negocio

Los datos de contratación pública están distribuidos en archivos y estructuras con granularidades distintas. El proyecto busca convertirlos en información trazable para responder, entre otras, estas preguntas:

- ¿Dónde se concentra la demanda pública por entidad, categoría, proveedor y periodo?
- ¿Qué proveedores o categorías presentan señales de concentración y dependencia?
- ¿Cómo cambian los montos y la competencia entre periodos comparables?
- ¿Qué oportunidades comerciales pueden priorizarse sin confundir procedimientos, contratos y órdenes?

## Alcance aprobado del MVP

- Universo principal: procedimientos publicados bajo OCDS.
- Periodo histórico completo: 2023–2025.
- Periodo YTD: enero–julio de 2026.
- Comparación interanual válida: enero–julio de 2025 frente a enero–julio de 2026.
- Fuente principal: portal de Contrataciones Abiertas de OECE.
- Fuentes XLSX complementarias: validación y análisis separados cuando la granularidad no sea compatible.
- Órdenes de compra/servicio y sanciones: módulos posteriores, sin mezclarlos prematuramente con el universo OCDS.

Los detalles y las exclusiones están en [docs/scope_and_limitations.md](docs/scope_and_limitations.md).

## Arquitectura objetivo

```text
OECE/SEACE -> Python (ingesta y calidad) -> Parquet/CSV controlado
           -> SQL Server (modelo analítico) -> Power BI (KPIs y narrativa)
           -> pruebas, documentación y trazabilidad en Git/GitHub
```

## Preparación local

Requisito: Python 3.11 de 64 bits.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

La activación es opcional si se invoca directamente `.\.venv\Scripts\python.exe`. Las instrucciones y criterios de verificación están en [docs/environment_setup.md](docs/environment_setup.md).

## Estructura inicial

```text
config/                     Configuración versionable sin secretos
docs/                       Caso de negocio, fuentes, decisiones y límites
.env.example                Variables locales de ejemplo
requirements.txt            Dependencias de ejecución
requirements-dev.txt        Herramientas de desarrollo y análisis
```

Las carpetas de código, SQL, pruebas y Power BI se incorporarán cuando contengan artefactos reales. Los datos crudos y archivos `.pbix` no se versionarán en Git.

## Fuentes oficiales

- [Portal de Contrataciones Abiertas de OECE](https://contratacionesabiertas.oece.gob.pe/)
- [Descargas OCDS](https://contratacionesabiertas.oece.gob.pe/descargas)
- [API OCDS](https://contratacionesabiertas.oece.gob.pe/api)

La evaluación de fuentes y sus limitaciones está en [docs/data_sources.md](docs/data_sources.md).

## Reproducibilidad y calidad

- Entorno Python aislado por proyecto.
- Dependencias directas versionadas.
- Configuración local y secretos fuera de Git.
- Comparaciones YTD con igual corte temporal.
- Pruebas de esquema, unicidad, completitud y reconciliación antes de publicar KPIs.

## Licencias

El código del repositorio se publica bajo licencia MIT. Los datos conservan los términos, atribución y licencia definidos por cada fuente oficial; no quedan relicenciados por este proyecto.
