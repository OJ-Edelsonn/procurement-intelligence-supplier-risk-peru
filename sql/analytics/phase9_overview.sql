SET NOCOUNT ON;

DECLARE @batch_id bigint =
(
    SELECT MAX(load_batch_id)
    FROM audit.load_batch
    WHERE status = 'SUCCEEDED'
);

SELECT
    batch.load_batch_id,
    batch.source_id,
    batch.source_period,
    CONVERT(char(10), batch.snapshot_date, 23) AS snapshot_date,
    (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process) AS process_count,
    (SELECT COUNT_BIG(*) FROM dw.fact_tender_item) AS tender_item_count,
    (SELECT COUNT_BIG(*) FROM dw.fact_award) AS award_count,
    (SELECT COUNT_BIG(*) FROM dw.fact_contract) AS contract_count,
    (SELECT COUNT_BIG(*) FROM dw.dim_buyer WHERE buyer_key <> 0) AS known_buyer_count,
    (SELECT COUNT_BIG(*) FROM dw.dim_supplier WHERE supplier_key <> 0) AS known_supplier_count,
    (SELECT COUNT_BIG(*) FROM dw.dim_category WHERE category_key <> 0) AS known_category_count,
    (SELECT SUM(tender_amount_pen_published) FROM dw.fact_procurement_process) AS tender_amount_pen,
    (SELECT SUM(award_amount_pen_calculated) FROM dw.fact_award) AS award_amount_pen,
    (SELECT SUM(contract_amount_pen_calculated) FROM dw.fact_contract) AS contract_amount_pen,
    (SELECT CONVERT(char(10), MIN(date.full_date), 23) FROM dw.fact_procurement_process AS fact INNER JOIN dw.dim_date AS date ON date.date_key = fact.tender_published_date_key WHERE date.date_key <> 0) AS tender_min_date,
    (SELECT CONVERT(char(10), MAX(date.full_date), 23) FROM dw.fact_procurement_process AS fact INNER JOIN dw.dim_date AS date ON date.date_key = fact.tender_published_date_key WHERE date.date_key <> 0) AS tender_max_date,
    (SELECT CONVERT(char(10), MIN(date.full_date), 23) FROM dw.fact_award AS fact INNER JOIN dw.dim_date AS date ON date.date_key = fact.award_date_key WHERE date.date_key <> 0) AS award_min_date,
    (SELECT CONVERT(char(10), MAX(date.full_date), 23) FROM dw.fact_award AS fact INNER JOIN dw.dim_date AS date ON date.date_key = fact.award_date_key WHERE date.date_key <> 0) AS award_max_date,
    (SELECT CONVERT(char(10), MIN(date.full_date), 23) FROM dw.fact_contract AS fact INNER JOIN dw.dim_date AS date ON date.date_key = fact.contract_signed_date_key WHERE date.date_key <> 0) AS contract_min_date,
    (SELECT CONVERT(char(10), MAX(date.full_date), 23) FROM dw.fact_contract AS fact INNER JOIN dw.dim_date AS date ON date.date_key = fact.contract_signed_date_key WHERE date.date_key <> 0) AS contract_max_date,
    (SELECT COUNT_BIG(DISTINCT process_key) FROM dw.bridge_process_tenderer) AS processes_with_tenderers,
    (SELECT COUNT_BIG(DISTINCT process_key) FROM dw.fact_award) AS processes_with_awards,
    (SELECT COUNT_BIG(DISTINCT process_key) FROM dw.fact_contract) AS processes_with_contracts
FROM audit.load_batch AS batch
WHERE batch.load_batch_id = @batch_id;
