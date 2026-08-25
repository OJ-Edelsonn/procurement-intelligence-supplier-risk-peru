SET NOCOUNT ON;

SELECT TOP (20) c.category_key, c.classification_code, c.classification_description,
       COUNT_BIG(*) AS award_item_count,
       COUNT_BIG(DISTINCT f.process_key) AS process_count,
       COUNT_BIG(DISTINCT NULLIF(f.buyer_key, 0)) AS buyer_count,
       COUNT_BIG(DISTINCT NULLIF(f.attributed_supplier_key, 0)) AS supplier_count,
       SUM(f.total_amount_pen_calculated) AS award_item_amount_pen,
       AVG(f.total_amount_pen_calculated) AS average_award_item_ticket_pen
FROM dw.fact_award_item AS f
JOIN dw.dim_category AS c ON c.category_key = f.standard_category_key
WHERE f.source_period = '2026-07' AND f.standard_category_key <> 0
GROUP BY c.category_key, c.classification_code, c.classification_description
ORDER BY award_item_amount_pen DESC, c.category_key;
