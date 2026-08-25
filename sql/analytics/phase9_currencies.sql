SET NOCOUNT ON;

SELECT N'tender' AS stage, currency.currency_code,
       COUNT_BIG(*) AS row_count,
       SUM(fact.tender_amount_original) AS amount_original,
       SUM(fact.tender_amount_pen_published) AS amount_pen,
       SUM(CASE WHEN fact.tender_amount_pen_published IS NULL THEN 1 ELSE 0 END) AS missing_pen_rows
FROM dw.fact_procurement_process AS fact
INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.tender_currency_key
GROUP BY currency.currency_code
UNION ALL
SELECT N'award', currency.currency_code, COUNT_BIG(*),
       SUM(fact.award_amount_original), SUM(fact.award_amount_pen_calculated),
       SUM(CASE WHEN fact.award_amount_pen_calculated IS NULL THEN 1 ELSE 0 END)
FROM dw.fact_award AS fact
INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
GROUP BY currency.currency_code
UNION ALL
SELECT N'contract', currency.currency_code, COUNT_BIG(*),
       SUM(fact.contract_amount_original), SUM(fact.contract_amount_pen_calculated),
       SUM(CASE WHEN fact.contract_amount_pen_calculated IS NULL THEN 1 ELSE 0 END)
FROM dw.fact_contract AS fact
INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
GROUP BY currency.currency_code
ORDER BY stage, currency_code;
