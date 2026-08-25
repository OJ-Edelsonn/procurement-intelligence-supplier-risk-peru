SET NOCOUNT ON;

WITH activity AS
(
    SELECT N'tender' AS stage, date.year_month,
           COUNT_BIG(*) AS event_count,
           SUM(fact.tender_amount_pen_published) AS amount_pen
    FROM dw.fact_procurement_process AS fact
    INNER JOIN dw.dim_date AS date ON date.date_key = fact.tender_published_date_key
    WHERE date.date_key <> 0
    GROUP BY date.year_month
    UNION ALL
    SELECT N'award', date.year_month, COUNT_BIG(*),
           SUM(fact.award_amount_pen_calculated)
    FROM dw.fact_award AS fact
    INNER JOIN dw.dim_date AS date ON date.date_key = fact.award_date_key
    WHERE date.date_key <> 0
    GROUP BY date.year_month
    UNION ALL
    SELECT N'contract', date.year_month, COUNT_BIG(*),
           SUM(fact.contract_amount_pen_calculated)
    FROM dw.fact_contract AS fact
    INNER JOIN dw.dim_date AS date ON date.date_key = fact.contract_signed_date_key
    WHERE date.date_key <> 0
    GROUP BY date.year_month
)
SELECT stage, year_month, event_count, amount_pen
FROM activity
ORDER BY year_month, stage;
