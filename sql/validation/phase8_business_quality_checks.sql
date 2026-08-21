SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @results TABLE
(
    rule_id varchar(40) NOT NULL,
    rows_evaluated bigint NOT NULL,
    violation_count bigint NOT NULL,
    observed_value nvarchar(100) NULL,
    expected_value nvarchar(100) NULL,
    details nvarchar(1000) NOT NULL
);

WITH bridge_counts AS
(
    SELECT process_key, COUNT_BIG(*) AS tenderer_count
    FROM dw.bridge_process_tenderer
    GROUP BY process_key
)
INSERT @results
SELECT
    'SQL-BUS-001',
    COUNT_BIG(*),
    SUM(CASE WHEN process.tenderer_count_observed <> COALESCE(bridge.tenderer_count, 0) THEN 1 ELSE 0 END),
    NULL,
    N'0',
    N'Observed tenderer count is recalculated from the factless participation bridge.'
FROM dw.fact_procurement_process AS process
LEFT JOIN bridge_counts AS bridge ON bridge.process_key = process.process_key;

WITH bridge_counts AS
(
    SELECT process_key, award_id, COUNT_BIG(*) AS supplier_count
    FROM dw.bridge_award_supplier
    GROUP BY process_key, award_id
)
INSERT @results
SELECT
    'SQL-BUS-002',
    COUNT_BIG(*),
    SUM(CASE WHEN award.supplier_count <> COALESCE(bridge.supplier_count, 0) THEN 1 ELSE 0 END),
    NULL,
    N'0',
    N'Award supplier count is recalculated from the factless supplier bridge.'
FROM dw.fact_award AS award
LEFT JOIN bridge_counts AS bridge
  ON bridge.process_key = award.process_key
 AND bridge.award_id = award.award_id;

WITH bridge_supplier AS
(
    SELECT process_key, award_id, COUNT_BIG(*) AS supplier_count, MAX(supplier_key) AS supplier_key
    FROM dw.bridge_award_supplier
    GROUP BY process_key, award_id
)
INSERT @results
SELECT
    'SQL-BUS-003',
    COUNT_BIG(*),
    SUM
    (
        CASE
            WHEN COALESCE(bridge.supplier_count, 0) = 1
             AND (award.attributed_supplier_key <> bridge.supplier_key OR award.dq_supplier_amount_attributable <> 1)
                THEN 1
            WHEN COALESCE(bridge.supplier_count, 0) <> 1
             AND (award.attributed_supplier_key <> 0 OR award.dq_supplier_amount_attributable <> 0)
                THEN 1
            ELSE 0
        END
    ),
    NULL,
    N'0',
    N'An award receives a supplier key only when exactly one official supplier exists.'
FROM dw.fact_award AS award
LEFT JOIN bridge_supplier AS bridge
  ON bridge.process_key = award.process_key
 AND bridge.award_id = award.award_id;

INSERT @results
SELECT
    'SQL-BUS-004',
    COUNT_BIG(*),
    SUM
    (
        CASE
            WHEN item.attributed_supplier_key <> award.attributed_supplier_key
              OR item.dq_supplier_amount_attributable <> award.dq_supplier_amount_attributable
                THEN 1
            ELSE 0
        END
    ),
    NULL,
    N'0',
    N'Award items inherit the governed supplier attribution from their parent award.'
FROM dw.fact_award_item AS item
INNER JOIN dw.fact_award AS award
  ON award.process_key = item.process_key
 AND award.award_id = item.award_id;

INSERT @results
SELECT
    'SQL-BUS-005',
    COUNT_BIG(*),
    SUM
    (
        CASE
            WHEN award.award_fact_key IS NOT NULL
             AND
             (
                 contract.attributed_supplier_key <> award.attributed_supplier_key
                 OR contract.dq_supplier_amount_attributable <> award.dq_supplier_amount_attributable
             )
                THEN 1
            WHEN award.award_fact_key IS NULL
             AND
             (
                 contract.attributed_supplier_key <> 0
                 OR contract.dq_supplier_amount_attributable <> 0
             )
                THEN 1
            ELSE 0
        END
    ),
    NULL,
    N'0',
    N'Contracts inherit attribution only from a resolved single-supplier award.'
FROM dw.fact_contract AS contract
LEFT JOIN dw.fact_award AS award
  ON award.process_key = contract.process_key
 AND award.award_id = contract.award_id;

INSERT @results
SELECT
    'SQL-BUS-006',
    COUNT_BIG(*),
    SUM
    (
        CASE
            WHEN item.attributed_supplier_key <> contract.attributed_supplier_key
              OR item.dq_supplier_amount_attributable <> contract.dq_supplier_amount_attributable
                THEN 1
            ELSE 0
        END
    ),
    NULL,
    N'0',
    N'Contract items inherit the governed supplier attribution from their parent contract.'
FROM dw.fact_contract_item AS item
INNER JOIN dw.fact_contract AS contract
  ON contract.process_key = item.process_key
 AND contract.contract_id = item.contract_id;

DECLARE @conversion_issues bigint =
(
    SELECT COUNT_BIG(*)
    FROM
    (
        SELECT currency.currency_code, fact.total_amount_original AS amount_original,
               fact.conversion_rate_to_pen, fact.total_amount_pen_calculated AS amount_pen,
               fact.dq_pen_conversion_available AS conversion_available
        FROM dw.fact_tender_item AS fact
        INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.award_amount_original, fact.conversion_rate_to_pen,
               fact.award_amount_pen_calculated, fact.dq_pen_conversion_available
        FROM dw.fact_award AS fact
        INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.total_amount_original, fact.conversion_rate_to_pen,
               fact.total_amount_pen_calculated, fact.dq_pen_conversion_available
        FROM dw.fact_award_item AS fact
        INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.contract_amount_original, fact.conversion_rate_to_pen,
               fact.contract_amount_pen_calculated, fact.dq_pen_conversion_available
        FROM dw.fact_contract AS fact
        INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.total_amount_original, fact.conversion_rate_to_pen,
               fact.total_amount_pen_calculated, fact.dq_pen_conversion_available
        FROM dw.fact_contract_item AS fact
        INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
    ) AS conversion
    WHERE
        (currency_code = N'PEN' AND (conversion_rate_to_pen IS NULL OR conversion_rate_to_pen <> CONVERT(decimal(38,14), 1)))
        OR
        (
            conversion_available
            <> CASE WHEN amount_original IS NOT NULL AND conversion_rate_to_pen IS NOT NULL THEN 1 ELSE 0 END
        )
        OR
        (
            conversion_available = 1
            AND amount_pen <>
                CONVERT
                (
                    decimal(38,14),
                    CONVERT(decimal(24,14), amount_original)
                    * CONVERT(decimal(18,14), conversion_rate_to_pen)
                )
        )
        OR
        (
            conversion_available = 0
            AND amount_pen IS NOT NULL
        )
);
DECLARE @conversion_rows bigint =
(
    SELECT
        (SELECT COUNT_BIG(*) FROM dw.fact_tender_item)
        + (SELECT COUNT_BIG(*) FROM dw.fact_award)
        + (SELECT COUNT_BIG(*) FROM dw.fact_award_item)
        + (SELECT COUNT_BIG(*) FROM dw.fact_contract)
        + (SELECT COUNT_BIG(*) FROM dw.fact_contract_item)
);
INSERT @results VALUES
('SQL-CALC-001', @conversion_rows, @conversion_issues, CONVERT(nvarchar(100), @conversion_issues), N'0', N'PEN conversion amount, rate and availability flag are mutually consistent.');

DECLARE @reconciliation_issues bigint = 0;

WITH child AS
(
    SELECT process_key, SUM(total_amount_original) AS item_sum
    FROM dw.fact_tender_item
    GROUP BY process_key
)
SELECT @reconciliation_issues = @reconciliation_issues + COUNT_BIG(*)
FROM dw.fact_procurement_process AS parent
LEFT JOIN child ON child.process_key = parent.process_key
WHERE
    (parent.tender_item_amount_sum_original <> child.item_sum)
 OR (parent.tender_item_amount_sum_original IS NULL AND child.item_sum IS NOT NULL)
 OR (parent.tender_item_amount_sum_original IS NOT NULL AND child.item_sum IS NULL)
 OR (parent.tender_amount_difference_original <> parent.tender_amount_original - child.item_sum)
 OR (parent.tender_amount_difference_original IS NULL AND parent.tender_amount_original - child.item_sum IS NOT NULL)
 OR (parent.tender_amount_difference_original IS NOT NULL AND parent.tender_amount_original - child.item_sum IS NULL)
 OR
    (
        parent.dq_tender_amount_reconciled_0_01
        <> CASE WHEN ABS(parent.tender_amount_original - child.item_sum) <= CONVERT(decimal(38,14), 0.01) THEN 1 ELSE 0 END
    );

WITH child AS
(
    SELECT process_key, award_id, SUM(total_amount_original) AS item_sum
    FROM dw.fact_award_item
    GROUP BY process_key, award_id
)
SELECT @reconciliation_issues = @reconciliation_issues + COUNT_BIG(*)
FROM dw.fact_award AS parent
LEFT JOIN child
  ON child.process_key = parent.process_key
 AND child.award_id = parent.award_id
WHERE
    (parent.award_item_amount_sum_original <> child.item_sum)
 OR (parent.award_item_amount_sum_original IS NULL AND child.item_sum IS NOT NULL)
 OR (parent.award_item_amount_sum_original IS NOT NULL AND child.item_sum IS NULL)
 OR (parent.award_amount_difference_original <> parent.award_amount_original - child.item_sum)
 OR (parent.award_amount_difference_original IS NULL AND parent.award_amount_original - child.item_sum IS NOT NULL)
 OR (parent.award_amount_difference_original IS NOT NULL AND parent.award_amount_original - child.item_sum IS NULL)
 OR
    (
        parent.dq_award_amount_reconciled_0_01
        <> CASE WHEN ABS(parent.award_amount_original - child.item_sum) <= CONVERT(decimal(38,14), 0.01) THEN 1 ELSE 0 END
    );

WITH child AS
(
    SELECT process_key, contract_id, SUM(total_amount_original) AS item_sum
    FROM dw.fact_contract_item
    GROUP BY process_key, contract_id
)
SELECT @reconciliation_issues = @reconciliation_issues + COUNT_BIG(*)
FROM dw.fact_contract AS parent
LEFT JOIN child
  ON child.process_key = parent.process_key
 AND child.contract_id = parent.contract_id
WHERE
    (parent.contract_item_amount_sum_original <> child.item_sum)
 OR (parent.contract_item_amount_sum_original IS NULL AND child.item_sum IS NOT NULL)
 OR (parent.contract_item_amount_sum_original IS NOT NULL AND child.item_sum IS NULL)
 OR (parent.contract_amount_difference_original <> parent.contract_amount_original - child.item_sum)
 OR (parent.contract_amount_difference_original IS NULL AND parent.contract_amount_original - child.item_sum IS NOT NULL)
 OR (parent.contract_amount_difference_original IS NOT NULL AND parent.contract_amount_original - child.item_sum IS NULL)
 OR
    (
        parent.dq_contract_amount_reconciled_0_01
        <> CASE WHEN ABS(parent.contract_amount_original - child.item_sum) <= CONVERT(decimal(38,14), 0.01) THEN 1 ELSE 0 END
    );

DECLARE @reconciliation_rows bigint =
(
    SELECT
        (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process)
        + (SELECT COUNT_BIG(*) FROM dw.fact_award)
        + (SELECT COUNT_BIG(*) FROM dw.fact_contract)
);
INSERT @results VALUES
('SQL-CALC-002', @reconciliation_rows, @reconciliation_issues, CONVERT(nvarchar(100), @reconciliation_issues), N'0', N'Header-item sums, differences and 0.01 flags are recalculated from child facts.');

DECLARE @classification_flag_issues bigint =
(
    SELECT COUNT_BIG(*)
    FROM
    (
        SELECT primary_category_key, standard_category_key,
               dq_classification_was_missing, dq_standard_category_missing
        FROM dw.fact_tender_item
        UNION ALL
        SELECT primary_category_key, standard_category_key,
               dq_classification_was_missing, dq_standard_category_missing
        FROM dw.fact_award_item
        UNION ALL
        SELECT primary_category_key, standard_category_key,
               dq_classification_was_missing, dq_standard_category_missing
        FROM dw.fact_contract_item
    ) AS item
    WHERE dq_classification_was_missing <> CASE WHEN primary_category_key = 0 THEN 1 ELSE 0 END
       OR dq_standard_category_missing <> CASE WHEN standard_category_key = 0 THEN 1 ELSE 0 END
);
DECLARE @classification_rows bigint =
(
    SELECT
        (SELECT COUNT_BIG(*) FROM dw.fact_tender_item)
        + (SELECT COUNT_BIG(*) FROM dw.fact_award_item)
        + (SELECT COUNT_BIG(*) FROM dw.fact_contract_item)
);
INSERT @results VALUES
('SQL-CALC-003', @classification_rows, @classification_flag_issues, CONVERT(nvarchar(100), @classification_flag_issues), N'0', N'Item classification flags match governed category key 0.');

DECLARE @zero_flag_issues bigint =
(
    SELECT COUNT_BIG(*)
    FROM dw.fact_procurement_process
    WHERE dq_tender_value_is_zero <> CASE WHEN tender_amount_original = 0 THEN 1 ELSE 0 END
);
INSERT @results VALUES
('SQL-CALC-004', (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process), @zero_flag_issues, CONVERT(nvarchar(100), @zero_flag_issues), N'0', N'Zero-value flag is recalculated from tender amount.');

DECLARE @supplier_invalid_ruc bigint =
(
    SELECT COUNT_BIG(*) FROM dw.dim_supplier
    WHERE supplier_key <> 0 AND dq_ruc_format_valid = 0
);
DECLARE @supplier_name_conflicts bigint =
(
    SELECT COUNT_BIG(*) FROM dw.dim_supplier
    WHERE supplier_key <> 0 AND dq_name_conflict = 1
);
DECLARE @category_description_conflicts bigint =
(
    SELECT COUNT_BIG(*) FROM dw.dim_category
    WHERE category_key <> 0 AND dq_description_conflict = 1
);
DECLARE @tenderer_count_differences bigint =
(
    SELECT COUNT_BIG(*) FROM dw.fact_procurement_process
    WHERE tenderer_count_declared IS NOT NULL
      AND tenderer_count_declared <> tenderer_count_observed
);
DECLARE @tender_amount_mismatches bigint =
(
    SELECT COUNT_BIG(*) FROM dw.fact_procurement_process
    WHERE dq_tender_amount_reconciled_0_01 = 0
);
DECLARE @award_amount_mismatches bigint =
(
    SELECT COUNT_BIG(*) FROM dw.fact_award
    WHERE dq_award_amount_reconciled_0_01 = 0
);
DECLARE @contract_amount_mismatches bigint =
(
    SELECT COUNT_BIG(*) FROM dw.fact_contract
    WHERE dq_contract_amount_reconciled_0_01 = 0
);
DECLARE @foreign_rows_without_rate bigint =
(
    SELECT COUNT_BIG(*)
    FROM
    (
        SELECT currency.currency_code, fact.total_amount_original AS amount_original,
               fact.dq_pen_conversion_available AS conversion_available
        FROM dw.fact_tender_item AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.award_amount_original, fact.dq_pen_conversion_available
        FROM dw.fact_award AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.total_amount_original, fact.dq_pen_conversion_available
        FROM dw.fact_award_item AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.contract_amount_original, fact.dq_pen_conversion_available
        FROM dw.fact_contract AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
        UNION ALL
        SELECT currency.currency_code, fact.total_amount_original, fact.dq_pen_conversion_available
        FROM dw.fact_contract_item AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key
    ) AS conversion
    WHERE currency_code <> N'PEN'
      AND amount_original IS NOT NULL
      AND conversion_available = 0
);
DECLARE @foreign_currency_rows bigint =
(
    SELECT
        (SELECT COUNT_BIG(*) FROM dw.fact_tender_item AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key WHERE currency.currency_code <> N'PEN' AND fact.total_amount_original IS NOT NULL)
        + (SELECT COUNT_BIG(*) FROM dw.fact_award AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key WHERE currency.currency_code <> N'PEN' AND fact.award_amount_original IS NOT NULL)
        + (SELECT COUNT_BIG(*) FROM dw.fact_award_item AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key WHERE currency.currency_code <> N'PEN' AND fact.total_amount_original IS NOT NULL)
        + (SELECT COUNT_BIG(*) FROM dw.fact_contract AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key WHERE currency.currency_code <> N'PEN' AND fact.contract_amount_original IS NOT NULL)
        + (SELECT COUNT_BIG(*) FROM dw.fact_contract_item AS fact INNER JOIN dw.dim_currency AS currency ON currency.currency_key = fact.currency_key WHERE currency.currency_code <> N'PEN' AND fact.total_amount_original IS NOT NULL)
);
DECLARE @contracts_without_final_value bigint =
(
    SELECT COUNT_BIG(*) FROM dw.fact_contract WHERE dq_final_value_available = 0
);
DECLARE @negative_amounts bigint =
(
    SELECT COUNT_BIG(*)
    FROM
    (
        SELECT tender_amount_original AS amount FROM dw.fact_procurement_process
        UNION ALL SELECT total_amount_original FROM dw.fact_tender_item
        UNION ALL SELECT award_amount_original FROM dw.fact_award
        UNION ALL SELECT total_amount_original FROM dw.fact_award_item
        UNION ALL SELECT contract_amount_original FROM dw.fact_contract
        UNION ALL SELECT total_amount_original FROM dw.fact_contract_item
    ) AS amounts
    WHERE amount < 0
);
DECLARE @zero_tender_amounts bigint =
(
    SELECT COUNT_BIG(*) FROM dw.fact_procurement_process WHERE tender_amount_original = 0
);

INSERT @results VALUES
('SQL-WARN-001', (SELECT COUNT_BIG(*) FROM dw.dim_supplier WHERE supplier_key <> 0), @supplier_invalid_ruc, CONVERT(nvarchar(100), @supplier_invalid_ruc), N'0', N'Observed invalid published supplier RUC formats; retained for traceability.'),
('SQL-WARN-002', (SELECT COUNT_BIG(*) FROM dw.dim_supplier WHERE supplier_key <> 0), @supplier_name_conflicts, CONVERT(nvarchar(100), @supplier_name_conflicts), N'0', N'Supplier natural keys with more than one observed legal name.'),
('SQL-WARN-003', (SELECT COUNT_BIG(*) FROM dw.dim_category WHERE category_key <> 0), @category_description_conflicts, CONVERT(nvarchar(100), @category_description_conflicts), N'0', N'Classification keys with conflicting published descriptions.'),
('SQL-WARN-004', (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process WHERE tenderer_count_declared IS NOT NULL), @tenderer_count_differences, CONVERT(nvarchar(100), @tenderer_count_differences), N'0', N'Declared tenderer count differs from distinct bridge observations.'),
('SQL-WARN-005', (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process), @tender_amount_mismatches, CONVERT(nvarchar(100), @tender_amount_mismatches), N'0', N'Tender header minus item sum exceeds 0.01 in absolute value.'),
('SQL-WARN-006', (SELECT COUNT_BIG(*) FROM dw.fact_award), @award_amount_mismatches, CONVERT(nvarchar(100), @award_amount_mismatches), N'0', N'Award header minus item sum exceeds 0.01 in absolute value.'),
('SQL-WARN-007', (SELECT COUNT_BIG(*) FROM dw.fact_contract), @contract_amount_mismatches, CONVERT(nvarchar(100), @contract_amount_mismatches), N'0', N'Contract header minus item sum exceeds 0.01 in absolute value.'),
('SQL-WARN-008', @foreign_currency_rows, @foreign_rows_without_rate, CONVERT(nvarchar(100), @foreign_rows_without_rate), N'0', N'Foreign-currency rows without an official published PEN conversion rate.'),
('SQL-WARN-009', (SELECT COUNT_BIG(*) FROM dw.fact_contract), @contracts_without_final_value, CONVERT(nvarchar(100), @contracts_without_final_value), N'0', N'Contracts without final implementation value; final-value KPI remains deferred.'),
('SQL-WARN-010', @conversion_rows + (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process), @negative_amounts, CONVERT(nvarchar(100), @negative_amounts), N'0', N'Negative header or item monetary amounts.'),
('SQL-WARN-011', (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process), @zero_tender_amounts, CONVERT(nvarchar(100), @zero_tender_amounts), N'0', N'Zero tender header values observed and explicitly flagged.');

SELECT rule_id, rows_evaluated, violation_count, observed_value, expected_value, details
FROM @results
ORDER BY rule_id;
