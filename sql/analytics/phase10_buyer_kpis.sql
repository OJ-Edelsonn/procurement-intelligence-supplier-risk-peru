SET NOCOUNT ON;

WITH process_metrics AS
(
    SELECT buyer_key, COUNT_BIG(*) AS process_count,
           SUM(tender_amount_pen_published) AS tender_amount_pen,
           AVG(tender_amount_pen_published) AS average_tender_ticket_pen
    FROM dw.fact_procurement_process
    WHERE source_period = '2026-07' AND buyer_key <> 0
    GROUP BY buyer_key
),
award_metrics AS
(
    SELECT buyer_key, COUNT_BIG(*) AS award_count,
           SUM(award_amount_pen_calculated) AS award_amount_pen
    FROM dw.fact_award
    WHERE source_period = '2026-07' AND buyer_key <> 0
    GROUP BY buyer_key
),
contract_metrics AS
(
    SELECT buyer_key, COUNT_BIG(*) AS contract_count,
           SUM(contract_amount_pen_calculated) AS contract_amount_pen
    FROM dw.fact_contract
    WHERE source_period = '2026-07' AND buyer_key <> 0
    GROUP BY buyer_key
)
SELECT TOP (20) b.buyer_key, b.display_name AS buyer_name,
       COALESCE(p.process_count, 0) AS process_count,
       p.tender_amount_pen, p.average_tender_ticket_pen,
       COALESCE(a.award_count, 0) AS award_count, a.award_amount_pen,
       COALESCE(c.contract_count, 0) AS contract_count, c.contract_amount_pen
FROM dw.dim_buyer AS b
LEFT JOIN process_metrics AS p ON p.buyer_key = b.buyer_key
LEFT JOIN award_metrics AS a ON a.buyer_key = b.buyer_key
LEFT JOIN contract_metrics AS c ON c.buyer_key = b.buyer_key
WHERE b.buyer_key <> 0
  AND (p.buyer_key IS NOT NULL OR a.buyer_key IS NOT NULL OR c.buyer_key IS NOT NULL)
ORDER BY COALESCE(p.tender_amount_pen, 0) DESC, b.buyer_key;
