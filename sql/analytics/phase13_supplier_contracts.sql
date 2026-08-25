SET NOCOUNT ON;

SELECT contract_fact_key, attributed_supplier_key AS supplier_key,
       contract_amount_pen_calculated AS amount_pen
FROM dw.fact_contract
WHERE source_period = '2026-07'
  AND attributed_supplier_key <> 0;
