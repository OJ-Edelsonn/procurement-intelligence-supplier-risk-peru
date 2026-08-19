# Caso de negocio

## Propósito

Construir una solución demostrable de Procurement Intelligence para Perú que transforme datos públicos de OECE/SEACE en señales de demanda, competencia, concentración y exposición a proveedores. El resultado debe ser útil para decisiones comerciales y de abastecimiento, además de auditable por un revisor técnico.

## Usuarios objetivo

- Líderes de compras y category managers.
- Equipos comerciales que atienden al sector público.
- Analistas de riesgo y compliance de proveedores.
- Equipos de Data/BI responsables de trazabilidad y calidad.

## Decisiones que debe soportar

1. Priorizar entidades y categorías con demanda relevante y recurrente.
2. Identificar concentración de adjudicaciones y dependencia de proveedores.
3. Comparar periodos homogéneos y detectar variaciones explicables.
4. Investigar oportunidades y riesgos hasta el registro fuente.
5. Distinguir evidencia, indicador descriptivo y señal de riesgo; una señal no implica fraude ni incumplimiento.

## Criterios de éxito del MVP

- Linaje desde cada KPI hasta los archivos y campos de origen.
- Modelo que respete las granularidades de procedimiento, adjudicación, contrato, ítem y parte.
- Comparación enero–julio 2025 vs. enero–julio 2026 sin sesgo por corte temporal.
- Reglas de calidad automatizadas antes de cargar el modelo analítico.
- Dashboard navegable con definiciones y limitaciones visibles.

## Fuera del MVP inicial

- Predicción de fraude o atribución causal.
- Integración de órdenes con procedimientos sin una llave oficial validada.
- Automatización productiva o actualización desatendida.
- Publicación de datos masivos en GitHub.
