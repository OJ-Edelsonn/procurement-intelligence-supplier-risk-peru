SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @latest_batch_id bigint =
(
    SELECT MAX(load_batch_id)
    FROM audit.load_batch
    WHERE status = 'SUCCEEDED'
);

DECLARE @source_id nvarchar(100);
DECLARE @source_period char(7);
DECLARE @snapshot_date date;
DECLARE @ingestion_run_id nvarchar(36);

SELECT
    @source_id = source_id,
    @source_period = source_period,
    @snapshot_date = snapshot_date,
    @ingestion_run_id = ingestion_run_id
FROM audit.load_batch
WHERE load_batch_id = @latest_batch_id;

DECLARE @results TABLE
(
    rule_id varchar(40) NOT NULL,
    rows_evaluated bigint NOT NULL,
    violation_count bigint NOT NULL,
    observed_value nvarchar(100) NULL,
    expected_value nvarchar(100) NULL,
    details nvarchar(1000) NOT NULL
);

INSERT @results
SELECT
    'SQL-BATCH-001',
    COUNT_BIG(*),
    CASE WHEN @latest_batch_id IS NULL THEN 1 ELSE 0 END,
    COALESCE(CONVERT(nvarchar(100), @latest_batch_id), N'NULL'),
    N'non-null',
    N'Latest successful SQL Server load batch.'
FROM audit.load_batch;

DECLARE @staging_table_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'stg'
);
DECLARE @warehouse_table_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dw'
);
DECLARE @primary_key_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.key_constraints AS kc
    INNER JOIN sys.tables AS t ON t.object_id = kc.parent_object_id
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dw' AND kc.type = 'PK'
);
DECLARE @unique_constraint_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.key_constraints AS kc
    INNER JOIN sys.tables AS t ON t.object_id = kc.parent_object_id
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dw' AND kc.type = 'UQ'
);
DECLARE @check_constraint_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.check_constraints AS cc
    WHERE OBJECT_SCHEMA_NAME(cc.parent_object_id) = N'dw'
);
DECLARE @foreign_key_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.foreign_keys AS fk
    WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = N'dw'
);
DECLARE @foreign_key_issues bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.foreign_keys AS fk
    WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = N'dw'
      AND (fk.is_disabled = 1 OR fk.is_not_trusted = 1)
);
DECLARE @heap_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dw'
      AND NOT EXISTS
      (
          SELECT 1
          FROM sys.indexes AS i
          WHERE i.object_id = t.object_id AND i.index_id = 1
      )
);

INSERT @results VALUES
('SQL-STRUCT-001', @staging_table_count, CASE WHEN @staging_table_count = 22 THEN 0 ELSE 1 END, CONVERT(nvarchar(100), @staging_table_count), N'22', N'Staging table count.'),
('SQL-STRUCT-002', @warehouse_table_count, CASE WHEN @warehouse_table_count = 16 THEN 0 ELSE 1 END, CONVERT(nvarchar(100), @warehouse_table_count), N'16', N'Warehouse table count.'),
('SQL-STRUCT-003', @warehouse_table_count, CASE WHEN @primary_key_count = 16 THEN 0 ELSE 1 END, CONVERT(nvarchar(100), @primary_key_count), N'16', N'Warehouse primary-key constraint count.'),
('SQL-STRUCT-004', @warehouse_table_count, CASE WHEN @unique_constraint_count = 16 THEN 0 ELSE 1 END, CONVERT(nvarchar(100), @unique_constraint_count), N'16', N'Warehouse unique constraint count.'),
('SQL-STRUCT-005', @warehouse_table_count, CASE WHEN @check_constraint_count = 9 THEN 0 ELSE 1 END, CONVERT(nvarchar(100), @check_constraint_count), N'9', N'Warehouse check constraint count.'),
('SQL-STRUCT-006', @foreign_key_count, CASE WHEN @foreign_key_count = 55 THEN @foreign_key_issues ELSE @foreign_key_issues + 1 END, CONCAT(N'count=', @foreign_key_count, N'; issues=', @foreign_key_issues), N'count=55; issues=0', N'Foreign-key count and trust state.'),
('SQL-STRUCT-007', @warehouse_table_count, @heap_count, CONVERT(nvarchar(100), @heap_count), N'0', N'Warehouse heap count.');

DECLARE @audit_issue_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM audit.load_table
    WHERE load_batch_id = @latest_batch_id
      AND
      (
          status <> 'SUCCEEDED'
          OR loaded_rows IS NULL
          OR expected_rows <> loaded_rows
      )
);
DECLARE @audit_table_count bigint =
(
    SELECT COUNT_BIG(*)
    FROM audit.load_table
    WHERE load_batch_id = @latest_batch_id
);

INSERT @results VALUES
(
    'SQL-AUDIT-001',
    @audit_table_count,
    CASE WHEN @audit_table_count = 38 THEN @audit_issue_count ELSE @audit_issue_count + 1 END,
    CONCAT(N'tables=', @audit_table_count, N'; issues=', @audit_issue_count),
    N'tables=38; issues=0',
    N'Latest batch table-level audit completeness.'
);

CREATE TABLE #actual_table_rows
(
    schema_name sysname NOT NULL,
    table_name sysname NOT NULL,
    row_count bigint NOT NULL
);

DECLARE @row_count_sql nvarchar(max);
SELECT @row_count_sql = STRING_AGG
(
    CAST
    (
        N'SELECT N''' + REPLACE(schema_name, '''', '''''') + N''', N'''
        + REPLACE(table_name, '''', '''''') + N''', COUNT_BIG(*) FROM '
        + QUOTENAME(schema_name) + N'.' + QUOTENAME(table_name)
        AS nvarchar(max)
    ),
    N' UNION ALL '
)
FROM audit.load_table
WHERE load_batch_id = @latest_batch_id;

IF @row_count_sql IS NOT NULL
    INSERT #actual_table_rows EXEC sys.sp_executesql @row_count_sql;

DECLARE @physical_row_issues bigint =
(
    SELECT COUNT_BIG(*)
    FROM audit.load_table AS expected
    FULL OUTER JOIN #actual_table_rows AS actual
      ON actual.schema_name = expected.schema_name
     AND actual.table_name = expected.table_name
    WHERE expected.load_batch_id = @latest_batch_id
      AND
      (
          actual.row_count IS NULL
          OR expected.loaded_rows IS NULL
          OR actual.row_count <> expected.loaded_rows
      )
);

INSERT @results VALUES
(
    'SQL-AUDIT-002',
    (SELECT COUNT_BIG(*) FROM #actual_table_rows),
    COALESCE(@physical_row_issues, 1),
    CONVERT(nvarchar(100), COALESCE(@physical_row_issues, 1)),
    N'0',
    N'Exact COUNT_BIG results compared with latest audit.load_table values.'
);

DECLARE @unknown_member_issues bigint =
(
    SELECT SUM(ABS(unknown_rows - 1))
    FROM
    (
        SELECT COUNT_BIG(CASE WHEN date_key = 0 THEN 1 END) AS unknown_rows FROM dw.dim_date
        UNION ALL SELECT COUNT_BIG(CASE WHEN process_key = 0 THEN 1 END) FROM dw.dim_process
        UNION ALL SELECT COUNT_BIG(CASE WHEN buyer_key = 0 THEN 1 END) FROM dw.dim_buyer
        UNION ALL SELECT COUNT_BIG(CASE WHEN supplier_key = 0 THEN 1 END) FROM dw.dim_supplier
        UNION ALL SELECT COUNT_BIG(CASE WHEN category_key = 0 THEN 1 END) FROM dw.dim_category
        UNION ALL SELECT COUNT_BIG(CASE WHEN procurement_method_key = 0 THEN 1 END) FROM dw.dim_procurement_method
        UNION ALL SELECT COUNT_BIG(CASE WHEN currency_key = 0 THEN 1 END) FROM dw.dim_currency
        UNION ALL SELECT COUNT_BIG(CASE WHEN unit_key = 0 THEN 1 END) FROM dw.dim_unit
    ) AS dimensions
);

INSERT @results VALUES
('SQL-DIM-001', 8, @unknown_member_issues, CONVERT(nvarchar(100), @unknown_member_issues), N'0', N'Exactly one surrogate key 0 in every dimension.');

DECLARE @date_attribute_issues bigint =
(
    SELECT COUNT_BIG(*)
    FROM dw.dim_date
    WHERE date_key <> 0
      AND
      (
          full_date IS NULL
          OR date_key <> CONVERT(int, CONVERT(char(8), full_date, 112))
          OR [year] <> DATEPART(year, full_date)
          OR quarter <> DATEPART(quarter, full_date)
          OR month_number <> DATEPART(month, full_date)
          OR day_of_month <> DATEPART(day, full_date)
          OR year_month <> CONVERT(char(7), full_date, 126)
      )
);
DECLARE @calendar_rows bigint = (SELECT COUNT_BIG(*) FROM dw.dim_date WHERE date_key <> 0);
DECLARE @calendar_expected_rows bigint =
(
    SELECT DATEDIFF(day, MIN(full_date), MAX(full_date)) + 1
    FROM dw.dim_date
    WHERE date_key <> 0
);

INSERT @results VALUES
(
    'SQL-DIM-002',
    @calendar_rows,
    @date_attribute_issues + CASE WHEN @calendar_rows = @calendar_expected_rows THEN 0 ELSE 1 END,
    CONCAT(N'rows=', @calendar_rows, N'; attribute_issues=', @date_attribute_issues),
    CONCAT(N'rows=', @calendar_expected_rows, N'; attribute_issues=0'),
    N'Calendar continuity and deterministic date attributes.'
);

INSERT @results
SELECT 'SQL-GRAIN-001', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key FROM dw.fact_procurement_process GROUP BY process_key HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One row per process.'
FROM dw.fact_procurement_process;
INSERT @results
SELECT 'SQL-GRAIN-002', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key, tender_item_id FROM dw.fact_tender_item GROUP BY process_key, tender_item_id HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One tender item per process and item ID.'
FROM dw.fact_tender_item;
INSERT @results
SELECT 'SQL-GRAIN-003', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key, award_id FROM dw.fact_award GROUP BY process_key, award_id HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One award per process and award ID.'
FROM dw.fact_award;
INSERT @results
SELECT 'SQL-GRAIN-004', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key, award_id, award_item_id FROM dw.fact_award_item GROUP BY process_key, award_id, award_item_id HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One award item per process, award and item ID.'
FROM dw.fact_award_item;
INSERT @results
SELECT 'SQL-GRAIN-005', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key, contract_id FROM dw.fact_contract GROUP BY process_key, contract_id HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One contract per process and contract ID.'
FROM dw.fact_contract;
INSERT @results
SELECT 'SQL-GRAIN-006', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key, contract_id, contract_item_id FROM dw.fact_contract_item GROUP BY process_key, contract_id, contract_item_id HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One contract item per process, contract and item ID.'
FROM dw.fact_contract_item;
INSERT @results
SELECT 'SQL-GRAIN-007', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key, supplier_key FROM dw.bridge_process_tenderer GROUP BY process_key, supplier_key HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One tenderer participation per process and supplier.'
FROM dw.bridge_process_tenderer;
INSERT @results
SELECT 'SQL-GRAIN-008', COUNT_BIG(*),
       (SELECT COUNT_BIG(*) FROM (SELECT process_key, award_id, supplier_key FROM dw.bridge_award_supplier GROUP BY process_key, award_id, supplier_key HAVING COUNT_BIG(*) > 1) AS duplicates),
       NULL, N'0 duplicate groups', N'One supplier participation per process, award and supplier.'
FROM dw.bridge_award_supplier;

DECLARE @contract_award_orphans bigint =
(
    SELECT COUNT_BIG(*)
    FROM dw.fact_contract AS contract
    WHERE contract.award_id IS NOT NULL
      AND NOT EXISTS
      (
          SELECT 1
          FROM dw.fact_award AS award
          WHERE award.process_key = contract.process_key
            AND award.award_id = contract.award_id
      )
);
INSERT @results VALUES
('SQL-REF-002', (SELECT COUNT_BIG(*) FROM dw.fact_contract WHERE award_id IS NOT NULL), @contract_award_orphans, CONVERT(nvarchar(100), @contract_award_orphans), N'0', N'Non-null contract award IDs resolve inside the same process.');

DECLARE @lineage_issues bigint =
(
    SELECT COUNT_BIG(*)
    FROM
    (
        SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.fact_procurement_process
        UNION ALL SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.fact_tender_item
        UNION ALL SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.fact_award
        UNION ALL SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.fact_award_item
        UNION ALL SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.fact_contract
        UNION ALL SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.fact_contract_item
        UNION ALL SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.bridge_process_tenderer
        UNION ALL SELECT source_id, source_period, snapshot_date, ingestion_run_id FROM dw.bridge_award_supplier
    ) AS lineage
    WHERE source_id <> @source_id
       OR source_period <> @source_period
       OR snapshot_date <> @snapshot_date
       OR ingestion_run_id <> @ingestion_run_id
);
DECLARE @lineage_rows bigint =
(
    SELECT fact_rows + bridge_rows
    FROM audit.load_batch
    WHERE load_batch_id = @latest_batch_id
);
INSERT @results VALUES
('SQL-LINEAGE-001', COALESCE(@lineage_rows, 0), @lineage_issues, CONVERT(nvarchar(100), @lineage_issues), N'0', N'Lineage columns equal the active load-batch identity.');

DECLARE @bridge_monetary_columns bigint =
(
    SELECT COUNT_BIG(*)
    FROM sys.columns AS c
    INNER JOIN sys.tables AS t ON t.object_id = c.object_id
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = N'dw'
      AND t.name IN (N'bridge_process_tenderer', N'bridge_award_supplier')
      AND
      (
          c.name LIKE N'%amount%'
          OR c.name LIKE N'%value%'
          OR c.name LIKE N'%price%'
          OR c.name LIKE N'%rate%'
      )
);
INSERT @results VALUES
('SQL-BRIDGE-001', (SELECT COUNT_BIG(*) FROM sys.columns WHERE object_id IN (OBJECT_ID(N'dw.bridge_process_tenderer'), OBJECT_ID(N'dw.bridge_award_supplier'))), @bridge_monetary_columns, CONVERT(nvarchar(100), @bridge_monetary_columns), N'0', N'Factless bridges must never duplicate monetary measures.');

SELECT rule_id, rows_evaluated, violation_count, observed_value, expected_value, details
FROM @results
ORDER BY rule_id;

DROP TABLE #actual_table_rows;
