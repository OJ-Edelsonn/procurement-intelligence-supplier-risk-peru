SET NOCOUNT ON;

WITH award_metrics AS
(
    SELECT attributed_supplier_key AS supplier_key,
           COUNT_BIG(*) AS award_count,
           COUNT_BIG(DISTINCT buyer_key) AS buyer_count,
           SUM(award_amount_pen_calculated) AS award_amount_pen,
           AVG(award_amount_pen_calculated) AS average_award_ticket_pen
    FROM dw.fact_award
    WHERE source_period = '2026-07' AND attributed_supplier_key <> 0
    GROUP BY attributed_supplier_key
),
contract_metrics AS
(
    SELECT attributed_supplier_key AS supplier_key,
           COUNT_BIG(*) AS contract_count,
           SUM(contract_amount_pen_calculated) AS contract_amount_pen
    FROM dw.fact_contract
    WHERE source_period = '2026-07' AND attributed_supplier_key <> 0
    GROUP BY attributed_supplier_key
)
SELECT TOP (20) s.supplier_key, s.display_name AS supplier_name,
       a.award_count, a.buyer_count, a.award_amount_pen,
       a.average_award_ticket_pen,
       COALESCE(c.contract_count, 0) AS contract_count,
       c.contract_amount_pen
FROM award_metrics AS a
JOIN dw.dim_supplier AS s ON s.supplier_key = a.supplier_key
LEFT JOIN contract_metrics AS c ON c.supplier_key = a.supplier_key
ORDER BY a.award_amount_pen DESC, s.supplier_key;
