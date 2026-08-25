SET NOCOUNT ON;

WITH item_base AS
(
    SELECT f.standard_category_key AS category_key,
           f.buyer_key, f.attributed_supplier_key AS supplier_key,
           f.total_amount_pen_calculated AS amount_pen
    FROM dw.fact_award_item AS f
    WHERE f.source_period = '2026-07'
      AND f.standard_category_key <> 0
),
category_stats AS
(
    SELECT category_key,
           COUNT_BIG(*) AS award_item_count,
           COUNT_BIG(DISTINCT NULLIF(buyer_key, 0)) AS buyer_count,
           SUM(amount_pen) AS total_category_amount_pen,
           SUM(CASE WHEN supplier_key <> 0 AND amount_pen > 0 THEN amount_pen ELSE 0 END) AS attributable_amount_pen
    FROM item_base
    GROUP BY category_key
),
supplier_totals AS
(
    SELECT category_key, supplier_key, SUM(amount_pen) AS supplier_amount_pen
    FROM item_base
    WHERE supplier_key <> 0 AND amount_pen > 0
    GROUP BY category_key, supplier_key
),
shares AS
(
    SELECT s.category_key, s.supplier_key, s.supplier_amount_pen,
           100.0 * s.supplier_amount_pen / NULLIF(c.attributable_amount_pen, 0) AS supplier_share_pct,
           ROW_NUMBER() OVER
             (PARTITION BY s.category_key ORDER BY s.supplier_amount_pen DESC, s.supplier_key) AS supplier_rank
    FROM supplier_totals AS s
    JOIN category_stats AS c ON c.category_key = s.category_key
    WHERE c.attributable_amount_pen > 0
),
indices AS
(
    SELECT category_key,
           COUNT_BIG(*) AS supplier_count,
           SUM(POWER(supplier_share_pct, 2)) AS hhi,
           SUM(CASE WHEN supplier_rank <= 1 THEN supplier_share_pct ELSE 0 END) AS top1_share_pct,
           SUM(CASE WHEN supplier_rank <= 3 THEN supplier_share_pct ELSE 0 END) AS top3_share_pct,
           SUM(CASE WHEN supplier_rank <= 5 THEN supplier_share_pct ELSE 0 END) AS top5_share_pct,
           SUM(CASE WHEN supplier_rank <= 10 THEN supplier_share_pct ELSE 0 END) AS top10_share_pct
    FROM shares
    GROUP BY category_key
)
SELECT c.category_key, d.classification_code, d.classification_description,
       c.award_item_count, c.buyer_count, i.supplier_count,
       c.total_category_amount_pen, c.attributable_amount_pen,
       CAST(100.0 * c.attributable_amount_pen / NULLIF(c.total_category_amount_pen, 0) AS decimal(18,6)) AS attributable_amount_coverage_pct,
       CAST(i.top1_share_pct AS decimal(18,6)) AS top1_share_pct,
       CAST(i.top3_share_pct AS decimal(18,6)) AS top3_share_pct,
       CAST(i.top5_share_pct AS decimal(18,6)) AS top5_share_pct,
       CAST(i.top10_share_pct AS decimal(18,6)) AS top10_share_pct,
       CAST(i.hhi AS decimal(18,6)) AS hhi,
       CAST(10000.0 / NULLIF(i.hhi, 0) AS decimal(18,6)) AS effective_supplier_count,
       CONVERT(bit, CASE WHEN i.supplier_count >= 3
                          AND c.buyer_count >= 2
                          AND c.award_item_count >= 5
                          AND 100.0 * c.attributable_amount_pen / NULLIF(c.total_category_amount_pen, 0) >= 95.0
                         THEN 1 ELSE 0 END) AS is_analysis_eligible
FROM category_stats AS c
JOIN indices AS i ON i.category_key = c.category_key
JOIN dw.dim_category AS d ON d.category_key = c.category_key
WHERE c.attributable_amount_pen > 0
ORDER BY c.attributable_amount_pen DESC, c.category_key;
