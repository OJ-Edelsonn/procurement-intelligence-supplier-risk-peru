SET NOCOUNT ON;
SET XACT_ABORT ON;

WITH controls AS
(
    SELECT N'process_tender_amount' AS control_id, N'STG' AS layer,
           COALESCE(NULLIF(LTRIM(RTRIM(compiled_release_tender_value_currency)), N''), N'__UNKNOWN__') AS currency_code,
           compiled_release_tender_value_amount AS amount
    FROM stg.procurement_process
    UNION ALL
    SELECT N'process_tender_amount', N'DW', currency.currency_code, fact.tender_amount_original
    FROM dw.fact_procurement_process AS fact
    INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.tender_currency_key

    UNION ALL
    SELECT N'process_budget_amount', N'STG',
           COALESCE(NULLIF(LTRIM(RTRIM(compiled_release_planning_budget_amount_currency)), N''), N'__UNKNOWN__'),
           compiled_release_planning_budget_amount_amount
    FROM stg.procurement_process
    UNION ALL
    SELECT N'process_budget_amount', N'DW', currency.currency_code, fact.planning_budget_amount_original
    FROM dw.fact_procurement_process AS fact
    INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.budget_currency_key

    UNION ALL
    SELECT N'tender_item_amount', N'STG',
           COALESCE(NULLIF(LTRIM(RTRIM(compiled_release_tender_items_total_value_currency)), N''), N'__UNKNOWN__'),
           compiled_release_tender_items_total_value_amount
    FROM stg.tender_item
    UNION ALL
    SELECT N'tender_item_amount', N'DW', currency.currency_code, fact.total_amount_original
    FROM dw.fact_tender_item AS fact
    INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key

    UNION ALL
    SELECT N'award_amount', N'STG',
           COALESCE(NULLIF(LTRIM(RTRIM(compiled_release_awards_value_currency)), N''), N'__UNKNOWN__'),
           compiled_release_awards_value_amount
    FROM stg.award
    UNION ALL
    SELECT N'award_amount', N'DW', currency.currency_code, fact.award_amount_original
    FROM dw.fact_award AS fact
    INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key

    UNION ALL
    SELECT N'award_item_amount', N'STG',
           COALESCE(NULLIF(LTRIM(RTRIM(compiled_release_awards_items_total_value_currency)), N''), N'__UNKNOWN__'),
           compiled_release_awards_items_total_value_amount
    FROM stg.award_item
    UNION ALL
    SELECT N'award_item_amount', N'DW', currency.currency_code, fact.total_amount_original
    FROM dw.fact_award_item AS fact
    INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key

    UNION ALL
    SELECT N'contract_amount', N'STG',
           COALESCE(NULLIF(LTRIM(RTRIM(compiled_release_contracts_value_currency)), N''), N'__UNKNOWN__'),
           compiled_release_contracts_value_amount
    FROM stg.contract
    UNION ALL
    SELECT N'contract_amount', N'DW', currency.currency_code, fact.contract_amount_original
    FROM dw.fact_contract AS fact
    INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key

    UNION ALL
    SELECT N'contract_item_amount', N'STG',
           COALESCE(NULLIF(LTRIM(RTRIM(compiled_release_contracts_items_total_value_currency)), N''), N'__UNKNOWN__'),
           compiled_release_contracts_items_total_value_amount
    FROM stg.contract_item
    UNION ALL
    SELECT N'contract_item_amount', N'DW', currency.currency_code, fact.total_amount_original
    FROM dw.fact_contract_item AS fact
    INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
)
SELECT
    control_id,
    layer,
    currency_code,
    COUNT_BIG(*) AS row_count,
    COUNT_BIG(amount) AS amount_non_null_rows,
    SUM(amount) AS amount_sum
FROM controls
GROUP BY control_id, layer, currency_code
ORDER BY control_id, layer, currency_code;
