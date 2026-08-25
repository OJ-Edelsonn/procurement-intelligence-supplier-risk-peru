SET NOCOUNT ON;

SELECT a.award_fact_key, a.attributed_supplier_key AS supplier_key,
       s.display_name AS supplier_name, a.buyer_key,
       a.award_amount_pen_calculated AS amount_pen
FROM dw.fact_award AS a
JOIN dw.dim_supplier AS s ON s.supplier_key = a.attributed_supplier_key
WHERE a.source_period = '2026-07'
  AND a.attributed_supplier_key <> 0
  AND a.award_amount_pen_calculated > 0;
