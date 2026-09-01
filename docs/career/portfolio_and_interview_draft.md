# Borrador de portafolio, CV e entrevista

El cierre visual, las capturas de Power BI y el proyecto PBIP están disponibles en el [repositorio público](https://github.com/OJ-Edelsonn/procurement-intelligence-supplier-risk-peru). La versión estable está documentada en el release [v1.0.0](https://github.com/OJ-Edelsonn/procurement-intelligence-supplier-risk-peru/releases/tag/v1.0.0); su difusión en LinkedIn queda como actividad opcional.

## Bullets de CV en español

- Diseñé una solución Data/BI end-to-end con Python, SQL Server y Power BI sobre 231,123 filas reales de 22 tablas OCDS de OECE/SEACE, modelando 16 objetos dimensionales y publicando 21 KPIs gobernados sobre S/ 6,924.9 millones licitados.
- Orquesté 12 etapas core con gates de calidad, hashes y logs; una corrida observada ejecutó 7 etapas, validó y reutilizó 5 artefactos aprobados y terminó sin fallos en 477.81 segundos, sin afirmar ahorro por ausencia de línea base manual.
- Analicé 772 mercados públicos, prioricé 87 mediante un Opportunity Score con sensibilidad y evalué 179 proveedores mediante un indicador limitado de exposición operativa/comercial, manteniendo separadas las interpretaciones legales, crediticias y de fraude.

## CV bullets in English

- Built an end-to-end Python, SQL Server and Power BI analytics solution over 231,123 real records from 22 OECE/SEACE OCDS tables, modeling 16 dimensional objects and publishing 21 governed KPIs across PEN 6.925B in observed tender value.
- Orchestrated 12 core stages with quality gates, artifact hashes and run logs; one observed run executed 7 stages, validated and reused 5 approved artifacts, and completed with zero failures in 477.81 seconds without claiming unmeasured manual savings.
- Analyzed 772 public-procurement markets, prioritized 87 through a sensitivity-tested Opportunity Score, and evaluated 179 suppliers with a deliberately limited operational/commercial exposure indicator.

## Descripción breve para LinkedIn

Proyecto de Procurement Intelligence con datos abiertos oficiales del Perú. Implementa trazabilidad de fuentes, profiling, Data Quality, ETL a Parquet, modelo dimensional en SQL Server, reconciliación independiente, EDA, KPIs, concentración, scores transparentes, automatización y un dashboard Power BI de cinco páginas. El repositorio separa evidencia observada de inferencias y documenta explícitamente los análisis bloqueados por falta de historia o geografía gobernada.

## Preguntas de entrevista

### ¿Por qué no utilizaste una tabla plana?

El dataset contiene granos distintos: proceso, ítem, adjudicación, contrato, partes y clasificaciones. Una tabla plana duplicaría montos y produciría KPIs incorrectos. Por eso usé hechos separados, dimensiones conformadas y puentes sin columnas monetarias.

### ¿Cómo validaste los resultados?

Cada capa tiene un gate: reglas RAW, reconciliación Silver, validación del diseño dimensional, conteos y constraints SQL, conciliación financiera, y comparación SQL–Python. Los KPIs críticos pueden verificarse fuera de Power BI.

### ¿Por qué el Opportunity Score no incluye crecimiento?

El piloto contiene un solo periodo fuente. Agregar un proxy habría convertido ausencia de historia en una señal inventada. El score solo usa componentes observables y conserva sensibilidad a los pesos.

### ¿El Supplier Exposure Score mide riesgo del proveedor?

No. Mide exposición relativa observada en materialidad, dependencia y concentración para una muestra y periodo. No incluye solvencia, sanciones, comportamiento histórico ni evidencia legal; por eso se comunica como indicador operativo/comercial limitado.

### ¿Cuánto tiempo ahorra la automatización?

No se puede afirmar todavía: no se midió una ejecución manual comparable. Sí se puede demostrar que 12 etapas core están encadenadas, que la corrida observada no requirió intervención intermedia y que terminó sin fallos en 477.81 segundos.

### ¿Qué mejorarías para producción?

Incorporaría historia incremental, secretos administrados, orquestación programada, monitoreo, pruebas de carga, una dimensión UBIGEO oficial, actualización controlada de Power BI Service y políticas de retención. Antes mediría volumen y frecuencia para justificar cada componente.
