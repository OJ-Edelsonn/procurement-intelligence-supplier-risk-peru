SET NOCOUNT ON;

WITH supplier_totals AS
(
    SELECT f.standard_category_key AS category_key,
           f.attributed_supplier_key AS supplier_key,
           SUM(f.total_amount_pen_calculated) AS supplier_amount_pen
    FROM dw.fact_award_item AS f
    WHERE f.source_period = '2026-07'
      AND f.standard_category_key <> 0
      AND f.attributed_supplier_key <> 0
      AND f.total_amount_pen_calculated > 0
    GROUP BY f.standard_category_key, f.attributed_supplier_key
),
shares AS
(
    SELECT category_key, supplier_key, supplier_amount_pen,
           SUM(supplier_amount_pen) OVER (PARTITION BY category_key) AS market_amount_pen,
           ROW_NUMBER() OVER
             (PARTITION BY category_key ORDER BY supplier_amount_pen DESC, supplier_key) AS supplier_rank
    FROM supplier_totals
)
SELECT s.category_key, c.classification_code,
       s.supplier_key, p.display_name AS supplier_name,
       s.supplier_amount_pen, s.market_amount_pen,
       CAST(100.0 * s.supplier_amount_pen / NULLIF(s.market_amount_pen, 0) AS decimal(18,6)) AS supplier_share_pct,
       s.supplier_rank
FROM shares AS s
JOIN dw.dim_category AS c ON c.category_key = s.category_key
JOIN dw.dim_supplier AS p ON p.supplier_key = s.supplier_key
ORDER BY s.category_key, s.supplier_rank;
