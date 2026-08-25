SET NOCOUNT ON;

WITH award AS
(
    SELECT process_key, COUNT_BIG(*) AS award_count
    FROM dw.fact_award
    GROUP BY process_key
),
contract AS
(
    SELECT process_key, COUNT_BIG(*) AS contract_count
    FROM dw.fact_contract
    GROUP BY process_key
)
SELECT
    process.process_key,
    process.tenderer_count_declared,
    process.tenderer_count_observed,
    COALESCE(award.award_count, 0) AS award_count,
    COALESCE(contract.contract_count, 0) AS contract_count
FROM dw.fact_procurement_process AS process
LEFT JOIN award ON award.process_key = process.process_key
LEFT JOIN contract ON contract.process_key = process.process_key
ORDER BY process.process_key;
