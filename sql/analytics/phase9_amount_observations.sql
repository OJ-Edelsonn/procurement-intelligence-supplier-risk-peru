SET NOCOUNT ON;

SELECT N'tender' AS stage,
       procurement_process_fact_key AS fact_key,
       tender_amount_pen_published AS amount_pen
FROM dw.fact_procurement_process
UNION ALL
SELECT N'award', award_fact_key, award_amount_pen_calculated
FROM dw.fact_award
UNION ALL
SELECT N'contract', contract_fact_key, contract_amount_pen_calculated
FROM dw.fact_contract;
