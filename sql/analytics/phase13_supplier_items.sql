SET NOCOUNT ON;

SELECT attributed_supplier_key AS supplier_key,
       standard_category_key,
       total_amount_pen_calculated AS amount_pen
FROM dw.fact_award_item
WHERE source_period = '2026-07'
  AND attributed_supplier_key <> 0
  AND total_amount_pen_calculated > 0;
