SET NOCOUNT ON;

DECLARE @snapshot_date date =
(
    SELECT TOP (1) snapshot_date
    FROM audit.load_batch
    WHERE status = 'SUCCEEDED'
    ORDER BY load_batch_id DESC
);

WITH metrics AS
(
    SELECT N'tender_zero_original' AS metric_id,
           SUM(CASE WHEN tender_amount_original = 0 THEN 1 ELSE 0 END) AS numerator,
           COUNT_BIG(*) AS denominator,
           N'Procesos con monto original de licitación igual a cero.' AS interpretation
    FROM dw.fact_procurement_process
    UNION ALL
    SELECT N'tenderer_declared_observed_difference',
           SUM(CASE WHEN tenderer_count_declared IS NOT NULL AND tenderer_count_declared <> tenderer_count_observed THEN 1 ELSE 0 END),
           SUM(CASE WHEN tenderer_count_declared IS NOT NULL THEN 1 ELSE 0 END),
           N'Procesos comparables cuyo conteo declarado difiere del detalle observado.'
    FROM dw.fact_procurement_process
    UNION ALL
    SELECT N'tender_item_standard_category_unknown',
           SUM(CASE WHEN standard_category_key = 0 THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Ítems de licitación sin clasificación estándar.'
    FROM dw.fact_tender_item
    UNION ALL
    SELECT N'award_item_standard_category_unknown',
           SUM(CASE WHEN standard_category_key = 0 THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Ítems adjudicados sin clasificación estándar.'
    FROM dw.fact_award_item
    UNION ALL
    SELECT N'contract_item_standard_category_unknown',
           SUM(CASE WHEN standard_category_key = 0 THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Ítems contractuales sin clasificación estándar.'
    FROM dw.fact_contract_item
    UNION ALL
    SELECT N'award_supplier_not_attributable',
           SUM(CASE WHEN dq_supplier_amount_attributable = 0 THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Adjudicaciones sin atribución monetaria segura a un proveedor único.'
    FROM dw.fact_award
    UNION ALL
    SELECT N'contract_pen_missing',
           SUM(CASE WHEN contract_amount_pen_calculated IS NULL THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Contratos sin monto PEN calculable con evidencia OECE.'
    FROM dw.fact_contract
    UNION ALL
    SELECT N'contract_final_value_missing',
           SUM(CASE WHEN dq_final_value_available = 0 THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Contratos sin valor final de implementación.'
    FROM dw.fact_contract
    UNION ALL
    SELECT N'buyer_department_raw_missing',
           SUM(CASE WHEN department_name_raw IS NULL OR LTRIM(RTRIM(department_name_raw)) = N'' THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Compradores sin departamento publicado; el texto todavía no está homologado con UBIGEO.'
    FROM dw.dim_buyer WHERE buyer_key <> 0
    UNION ALL
    SELECT N'contract_signed_after_snapshot',
           SUM(CASE WHEN date.full_date > @snapshot_date THEN 1 ELSE 0 END), COUNT_BIG(*),
           N'Contratos cuya fecha de firma publicada es posterior al snapshot.'
    FROM dw.fact_contract AS contract
    INNER JOIN dw.dim_date AS date ON date.date_key = contract.contract_signed_date_key
)
SELECT
    metric_id,
    numerator,
    denominator,
    CONVERT(decimal(12,4), 100.0 * numerator / NULLIF(denominator, 0)) AS metric_pct,
    interpretation
FROM metrics
ORDER BY metric_id;
