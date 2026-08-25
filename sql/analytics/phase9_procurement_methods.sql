SET NOCOUNT ON;

SELECT
    method.procurement_method,
    method.procurement_method_details,
    COUNT_BIG(*) AS process_count,
    SUM(process.tender_amount_pen_published) AS tender_amount_pen
FROM dw.fact_procurement_process AS process
INNER JOIN dw.dim_procurement_method AS method
  ON method.procurement_method_key = process.procurement_method_key
GROUP BY method.procurement_method, method.procurement_method_details
ORDER BY process_count DESC, method.procurement_method_details;
