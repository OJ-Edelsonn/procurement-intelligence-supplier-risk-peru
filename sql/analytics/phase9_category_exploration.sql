SET NOCOUNT ON;

SELECT
    category.category_key,
    category.classification_code,
    category.classification_description,
    COUNT_BIG(*) AS award_item_count,
    COUNT_BIG(DISTINCT item.buyer_key) AS buyer_count,
    SUM(item.total_amount_pen_calculated) AS award_item_amount_pen
FROM dw.fact_award_item AS item
INNER JOIN dw.dim_category AS category
  ON category.category_key = item.standard_category_key
WHERE category.category_key <> 0
GROUP BY
    category.category_key,
    category.classification_code,
    category.classification_description
ORDER BY award_item_amount_pen DESC, category.category_key;
