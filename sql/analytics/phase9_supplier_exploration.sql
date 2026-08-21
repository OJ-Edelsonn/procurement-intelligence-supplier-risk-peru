SET NOCOUNT ON;

WITH award AS
(
    SELECT attributed_supplier_key AS supplier_key,
           COUNT_BIG(*) AS award_count,
           COUNT_BIG(DISTINCT buyer_key) AS buyer_count,
           SUM(award_amount_pen_calculated) AS award_amount_pen
    FROM dw.fact_award
    WHERE attributed_supplier_key <> 0
    GROUP BY attributed_supplier_key
),
contract AS
(
    SELECT attributed_supplier_key AS supplier_key,
           COUNT_BIG(*) AS contract_count,
           SUM(contract_amount_pen_calculated) AS contract_amount_pen
    FROM dw.fact_contract
    WHERE attributed_supplier_key <> 0
    GROUP BY attributed_supplier_key
)
SELECT
    supplier.supplier_key,
    COALESCE(supplier.display_name, supplier.legal_name, N'Sin nombre') AS supplier_name,
    award.award_count,
    award.buyer_count,
    award.award_amount_pen,
    COALESCE(contract.contract_count, 0) AS contract_count,
    contract.contract_amount_pen
FROM award
INNER JOIN dw.dim_supplier AS supplier ON supplier.supplier_key = award.supplier_key
LEFT JOIN contract ON contract.supplier_key = award.supplier_key
ORDER BY award.award_amount_pen DESC, supplier.supplier_key;
