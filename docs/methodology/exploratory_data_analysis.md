# Metodología de Exploratory Data Analysis

## Propósito

La Fase 9 explora el lote SQL aprobado para comprender distribuciones, cobertura, valores extremos y aptitud analítica antes de definir KPIs. El EDA responde “qué contiene el piloto y qué limitaciones presenta”; no responde todavía “qué indicador oficial publicaremos”.

El contrato canónico es `config/eda.yml`, las consultas están en `sql/analytics/phase9_*.sql` y la ejecución reproducible reside en `src/procurement_intelligence/analytics/run_eda.py`.

## Enfoque SQL-first con visualización Python

```text
Fase 8 PASS_WITH_WARNINGS
        ↓ puerta obligatoria
SQL Server dw → 10 datasets EDA → pandas → perfiles y rankings
                                      ↓
                               Matplotlib → 7 figuras
                                      ↓
                           JSON + Markdown + hashes
```

SQL respeta el modelo dimensional y calcula cada agregado desde su hecho nativo. Python resume distribuciones, genera visuales y produce artefactos verificables. No se utiliza un notebook monolítico porque la misma ejecución debe funcionar desde terminal y pruebas automatizadas.

## Unidades de análisis

| Tema | Grano usado | Medida monetaria |
|---|---|---|
| Demanda | un proceso | monto licitado PEN publicado |
| Ítems demandados | un ítem de licitación | monto del ítem PEN cuando está disponible |
| Resultado adjudicado | una adjudicación | monto adjudicado PEN calculado |
| Proveedor atribuible | una adjudicación con proveedor único | monto adjudicado PEN |
| Formalización | un contrato | monto contractual PEN calculado |
| Categoría | un ítem adjudicado + categoría estándar | monto del ítem adjudicado PEN |
| Competencia | un proceso | ofertantes observados; sin replicar monto en el bridge |

Las sumas de licitación, adjudicación y contrato no se suman entre sí: representan etapas y granos diferentes.

## Tratamiento monetario

- La moneda original solo se agrupa dentro del mismo `currency_code`.
- Los perfiles comparables usan las columnas PEN gobernadas por el modelo.
- Un monto PEN faltante permanece nulo y reduce la cobertura publicada.
- Los ceros permanecen en estadísticas y conteos.
- Los histogramas logarítmicos muestran exclusivamente valores positivos; los ceros se informan en las tablas.
- Los valores extremos no se eliminan. Se cuantifican mediante percentiles y la cerca superior `Q3 + 1.5 × IQR`.

La cerca IQR sirve para localizar observaciones extremas, no para afirmar error ni excluir contrataciones de gran magnitud.

## Tratamiento temporal

`source_period=2026-07` identifica el archivo de publicación. Las fechas de licitación, adjudicación y contrato son fechas de negocio y abarcan otros meses; no crean por sí solas una serie de snapshots históricos.

Por existir un solo `source_period`:

- no se calcula crecimiento;
- no se calcula YoY;
- no se compara 2025 vs. 2026;
- la gráfica mensual solo describe fechas contenidas en el snapshot;
- se conserva como alerta cualquier fecha posterior a `snapshot_date`.

## Rankings exploratorios

Los Top 15 de comprador, proveedor y categoría sirven para detectar escala, revisar etiquetas y orientar preguntas de fases posteriores. No son todavía:

- KPIs aprobados;
- participación de mercado;
- HHI o concentración;
- oportunidades comerciales;
- recomendaciones;
- evaluaciones de riesgo.

El proveedor recibe monto únicamente cuando la adjudicación tiene un proveedor oficial único. Los puentes no se usan para replicar importes.

## Cobertura de calidad visible

El reporte vuelve a publicar denominadores para:

- licitaciones con monto cero;
- discrepancia de ofertantes declarados/observados;
- categorías estándar desconocidas;
- proveedor no atribuible;
- monto contractual PEN faltante;
- valor final contractual faltante;
- departamento crudo faltante;
- firma contractual posterior al snapshot.

La ausencia de departamento nulo no equivale a geografía homologada. El análisis territorial permanece aplazado hasta aprobar una dimensión UBIGEO oficial.

## Ejecución

```powershell
.\.venv\Scripts\python.exe -m procurement_intelligence.analytics.run_eda `
  --config config\eda.yml `
  --env-file .env
```

Comando instalado equivalente:

```powershell
.\.venv\Scripts\run-procurement-eda.exe
```

La ejecución es de solo lectura respecto de SQL Server. Sobrescribe únicamente los artefactos derivados definidos en `reports/eda`, que pueden reconstruirse desde el lote validado.

## Cómo explicarlo en una entrevista

1. Separé el EDA por grano para evitar doble conteo.
2. Usé SQL para preservar la semántica del DW y Python para perfiles/visualización.
3. Publiqué cobertura y denominador junto con cada limitación.
4. No eliminé outliers porque pueden representar contrataciones reales de gran escala.
5. No calculé crecimiento con un solo periodo fuente.
6. Diferencié hallazgo exploratorio de KPI, concentración y recomendación.

## Limitaciones

- Piloto de un solo periodo fuente.
- Un contrato tiene fecha de firma posterior al snapshot.
- La clasificación estándar falta en aproximadamente 18% de los ítems.
- Cuatro contratos no tienen monto PEN calculable.
- `finalValue` solo existe en tres contratos.
- El texto geográfico aún no está homologado contra UBIGEO.
