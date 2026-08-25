SET NOCOUNT ON;

WITH process_scope AS
(
    SELECT process_key, buyer_key, tender_amount_pen_published,
           tenderer_count_observed, dq_tender_value_is_zero
    FROM dw.fact_procurement_process
    WHERE source_period = '2026-07'
),
award_scope AS
(
    SELECT process_key, attributed_supplier_key, award_amount_pen_calculated
    FROM dw.fact_award
    WHERE source_period = '2026-07'
),
contract_scope AS
(
    SELECT process_key, contract_amount_pen_calculated
    FROM dw.fact_contract
    WHERE source_period = '2026-07'
),
award_item_scope AS
(
    SELECT standard_category_key
    FROM dw.fact_award_item
    WHERE source_period = '2026-07'
),
base AS
(
    SELECT
        (SELECT COUNT_BIG(*) FROM process_scope) AS process_rows,
        (SELECT COUNT_BIG(tender_amount_pen_published) FROM process_scope) AS process_pen_rows,
        (SELECT SUM(tender_amount_pen_published) FROM process_scope) AS tender_amount_pen,
        (SELECT SUM(CONVERT(bigint, dq_tender_value_is_zero)) FROM process_scope) AS zero_tender_rows,
        (SELECT COUNT_BIG(DISTINCT buyer_key) FROM process_scope WHERE buyer_key <> 0) AS active_buyers,
        (SELECT COUNT_BIG(*) FROM award_scope) AS award_rows,
        (SELECT COUNT_BIG(award_amount_pen_calculated) FROM award_scope) AS award_pen_rows,
        (SELECT SUM(award_amount_pen_calculated) FROM award_scope) AS award_amount_pen,
        (SELECT COUNT_BIG(*) FROM award_scope WHERE attributed_supplier_key <> 0) AS attributable_award_rows,
        (SELECT COUNT_BIG(DISTINCT attributed_supplier_key) FROM award_scope WHERE attributed_supplier_key <> 0) AS awarded_suppliers,
        (SELECT COUNT_BIG(*) FROM contract_scope) AS contract_rows,
        (SELECT COUNT_BIG(contract_amount_pen_calculated) FROM contract_scope) AS contract_pen_rows,
        (SELECT SUM(contract_amount_pen_calculated) FROM contract_scope) AS contract_amount_pen,
        (SELECT COUNT_BIG(*) FROM process_scope WHERE tenderer_count_observed > 0) AS competition_rows,
        (SELECT SUM(tenderer_count_observed) FROM process_scope WHERE tenderer_count_observed > 0) AS observed_tenderers,
        (SELECT COUNT_BIG(DISTINCT process_key) FROM award_scope) AS processes_with_awards,
        (SELECT COUNT_BIG(DISTINCT process_key) FROM contract_scope) AS processes_with_contracts,
        (SELECT COUNT_BIG(*) FROM award_item_scope) AS award_item_rows,
        (SELECT COUNT_BIG(*) FROM award_item_scope WHERE standard_category_key <> 0) AS classified_award_item_rows
)
SELECT metric_id, CAST(metric_value AS decimal(38,6)) AS metric_value,
       numerator, denominator, unit
FROM base
CROSS APPLY
(
    VALUES
      ('procurement_processes', CONVERT(decimal(38,14), process_rows), process_rows, process_rows, 'count'),
      ('tender_amount_pen', tender_amount_pen, process_pen_rows, process_rows, 'PEN'),
      ('tender_amount_pen_coverage_pct', 100.0 * process_pen_rows / NULLIF(process_rows, 0), process_pen_rows, process_rows, 'percent'),
      ('tender_zero_amount_pct', 100.0 * zero_tender_rows / NULLIF(process_rows, 0), zero_tender_rows, process_rows, 'percent'),
      ('average_tender_ticket_pen', tender_amount_pen / NULLIF(process_pen_rows, 0), process_pen_rows, process_rows, 'PEN'),
      ('active_buyers', CONVERT(decimal(38,14), active_buyers), active_buyers, active_buyers, 'count'),
      ('award_count', CONVERT(decimal(38,14), award_rows), award_rows, award_rows, 'count'),
      ('award_amount_pen', award_amount_pen, award_pen_rows, award_rows, 'PEN'),
      ('award_amount_pen_coverage_pct', 100.0 * award_pen_rows / NULLIF(award_rows, 0), award_pen_rows, award_rows, 'percent'),
      ('average_award_ticket_pen', award_amount_pen / NULLIF(award_pen_rows, 0), award_pen_rows, award_rows, 'PEN'),
      ('attributable_award_pct', 100.0 * attributable_award_rows / NULLIF(award_rows, 0), attributable_award_rows, award_rows, 'percent'),
      ('awarded_suppliers', CONVERT(decimal(38,14), awarded_suppliers), awarded_suppliers, awarded_suppliers, 'count'),
      ('contract_count', CONVERT(decimal(38,14), contract_rows), contract_rows, contract_rows, 'count'),
      ('contract_amount_pen', contract_amount_pen, contract_pen_rows, contract_rows, 'PEN'),
      ('contract_amount_pen_coverage_pct', 100.0 * contract_pen_rows / NULLIF(contract_rows, 0), contract_pen_rows, contract_rows, 'percent'),
      ('average_contract_ticket_pen', contract_amount_pen / NULLIF(contract_pen_rows, 0), contract_pen_rows, contract_rows, 'PEN'),
      ('competition_coverage_pct', 100.0 * competition_rows / NULLIF(process_rows, 0), competition_rows, process_rows, 'percent'),
      ('average_observed_tenderers', 1.0 * observed_tenderers / NULLIF(competition_rows, 0), observed_tenderers, competition_rows, 'tenderers'),
      ('award_process_presence_pct', 100.0 * processes_with_awards / NULLIF(process_rows, 0), processes_with_awards, process_rows, 'percent'),
      ('contract_process_presence_pct', 100.0 * processes_with_contracts / NULLIF(process_rows, 0), processes_with_contracts, process_rows, 'percent'),
      ('award_item_standard_category_coverage_pct', 100.0 * classified_award_item_rows / NULLIF(award_item_rows, 0), classified_award_item_rows, award_item_rows, 'percent')
) AS metrics(metric_id, metric_value, numerator, denominator, unit)
ORDER BY metric_id;
