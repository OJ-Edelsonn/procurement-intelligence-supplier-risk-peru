SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @latest_batch_id bigint =
(
    SELECT MAX(load_batch_id)
    FROM audit.load_batch
    WHERE status = 'SUCCEEDED'
);

IF @latest_batch_id IS NULL
    THROW 52001, 'No successful load batch is available for reconciliation.', 1;

CREATE TABLE #phase8_actual_table_rows
(
    schema_name sysname NOT NULL,
    table_name sysname NOT NULL,
    actual_rows bigint NOT NULL
);

DECLARE @sql nvarchar(max);
SELECT @sql = STRING_AGG
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

INSERT #phase8_actual_table_rows EXEC sys.sp_executesql @sql;

SELECT
    @latest_batch_id AS load_batch_id,
    audit.layer,
    audit.schema_name,
    audit.table_name,
    actual.actual_rows,
    audit.expected_rows AS audit_expected_rows,
    audit.loaded_rows AS audit_loaded_rows,
    audit.status AS audit_status
FROM audit.load_table AS audit
INNER JOIN #phase8_actual_table_rows AS actual
  ON actual.schema_name = audit.schema_name
 AND actual.table_name = audit.table_name
WHERE audit.load_batch_id = @latest_batch_id
ORDER BY audit.layer, audit.schema_name, audit.table_name;

DROP TABLE #phase8_actual_table_rows;
