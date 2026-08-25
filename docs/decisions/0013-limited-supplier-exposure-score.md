# ADR 0013: Score limitado de exposición operativa y comercial

- Estado: aceptada para piloto
- Fecha: 2026-08-24

## Contexto

El prompt solicita Supplier Risk, pero el snapshot activo no contiene sanciones, penalidades, historia multi-periodo ni información crediticia. Usar esos conceptos sin datos produciría una calificación engañosa. SQL Server Express, además, presentó presión de memoria al extraer ítems completos, aunque la capa Silver auditada permanece disponible.

## Decisión

1. Cambiar el nombre operativo a Supplier Operational and Commercial Exposure Score.
2. Puntuar solo proveedores con dos o más adjudicaciones y coberturas suficientes.
3. Usar cinco señales descriptivas: materialidad, dependencia de comprador, dependencia de categoría, concentración de adjudicaciones y amplitud de compradores.
4. Normalizar por percentiles, publicar pesos y ejecutar tres escenarios.
5. Excluir sanciones, penalidades, recurrencia, cambios abruptos y solvencia.
6. Incluir la advertencia no crediticia/legal/fraude en configuración e informes.
7. Reconstruir la corrida oficial desde Silver y reconciliarla contra el gate dimensional.
8. Mantener SQL equivalentes versionados para uso cuando la instancia tenga memoria disponible.

## Consecuencias

- El resultado es auditable, explicable y adecuado para priorizar revisión.
- No debe denominarse score legal, crediticio, de integridad o fraude.
- La posición depende de población, periodo y pesos; el escenario de materialidad muestra sensibilidad alta.
- Una futura versión con sanciones o historia requiere fuentes, validación y una nueva versión metodológica.

## Alternativas descartadas

- **Inventar proxies de sanción o fraude:** carece de evidencia y puede causar daño reputacional.
- **Puntuar proveedores con una adjudicación:** confunde observación puntual con patrón.
- **Sumar montos de adjudicación e ítems:** duplica dinero entre granos.
- **Esperar a SQL Server:** innecesario porque Silver puede reconstruir exactamente el modelo auditado.
