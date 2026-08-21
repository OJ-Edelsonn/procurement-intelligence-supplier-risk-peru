SET NOCOUNT ON;

WITH process AS
(
    SELECT buyer_key, COUNT_BIG(*) AS process_count,
           SUM(tender_amount_pen_published) AS tender_amount_pen
    FROM dw.fact_procurement_process
    GROUP BY buyer_key
),
award AS
(
    SELECT buyer_key, COUNT_BIG(*) AS award_count,
           SUM(award_amount_pen_calculated) AS award_amount_pen
    FROM dw.fact_award
    GROUP BY buyer_key
),
contract AS
(
    SELECT buyer_key, COUNT_BIG(*) AS contract_count,
           SUM(contract_amount_pen_calculated) AS contract_amount_pen
    FROM dw.fact_contract
    GROUP BY buyer_key
)
SELECT
    buyer.buyer_key,
    COALESCE(buyer.display_name, buyer.legal_name, N'Sin nombre') AS buyer_name,
    buyer.department_name_raw,
    COALESCE(process.process_count, 0) AS process_count,
    process.tender_amount_pen,
    COALESCE(award.award_count, 0) AS award_count,
    award.award_amount_pen,
    COALESCE(contract.contract_count, 0) AS contract_count,
    contract.contract_amount_pen
FROM dw.dim_buyer AS buyer
LEFT JOIN process ON process.buyer_key = buyer.buyer_key
LEFT JOIN award ON award.buyer_key = buyer.buyer_key
LEFT JOIN contract ON contract.buyer_key = buyer.buyer_key
WHERE buyer.buyer_key <> 0
ORDER BY process.tender_amount_pen DESC, buyer.buyer_key;
