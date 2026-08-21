:setvar DatabaseName "ProcurementIntelligence"

USE [$(DatabaseName)];
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

DECLARE @latest_batch_id bigint =
(
    SELECT MAX(load_batch_id)
    FROM audit.load_batch
    WHERE status = 'SUCCEEDED'
);

IF @latest_batch_id IS NULL
    THROW 51000, 'No successful SQL Server load batch exists.', 1;

IF (SELECT COUNT(*) FROM sys.tables AS t INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id WHERE s.name = N'stg') <> 22
    THROW 51001, 'Expected 22 staging tables.', 1;

IF (SELECT COUNT(*) FROM sys.tables AS t INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id WHERE s.name = N'dw') <> 16
    THROW 51002, 'Expected 16 dimensional tables.', 1;

;WITH table_rows AS
(
    SELECT
        s.name AS schema_name,
        t.name AS table_name,
        SUM(p.rows) AS row_count
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    INNER JOIN sys.partitions AS p ON p.object_id = t.object_id
    WHERE p.index_id IN (0, 1)
      AND s.name IN (N'stg', N'dw')
    GROUP BY s.name, t.name
)
SELECT schema_name, table_name, row_count
FROM table_rows
ORDER BY schema_name, table_name;

DECLARE @staging_rows bigint =
(
    SELECT SUM(p.rows)
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    INNER JOIN sys.partitions AS p ON p.object_id = t.object_id
    WHERE p.index_id IN (0, 1) AND s.name = N'stg'
);
DECLARE @dimension_rows bigint =
(
    SELECT SUM(p.rows)
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    INNER JOIN sys.partitions AS p ON p.object_id = t.object_id
    WHERE p.index_id IN (0, 1) AND s.name = N'dw' AND t.name LIKE N'dim[_]%'
);
DECLARE @fact_rows bigint =
(
    SELECT SUM(p.rows)
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    INNER JOIN sys.partitions AS p ON p.object_id = t.object_id
    WHERE p.index_id IN (0, 1) AND s.name = N'dw' AND t.name LIKE N'fact[_]%'
);
DECLARE @bridge_rows bigint =
(
    SELECT SUM(p.rows)
    FROM sys.tables AS t
    INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    INNER JOIN sys.partitions AS p ON p.object_id = t.object_id
    WHERE p.index_id IN (0, 1) AND s.name = N'dw' AND t.name LIKE N'bridge[_]%'
);

IF @staging_rows <> 231113 THROW 51003, 'Staging row count does not match Silver.', 1;
IF @dimension_rows <> 26592 THROW 51004, 'Dimension row count does not match the approved build.', 1;
IF @fact_rows <> 23056 THROW 51005, 'Fact row count does not match Phase 6.', 1;
IF @bridge_rows <> 37511 THROW 51006, 'Bridge row count does not match Phase 6.', 1;

SELECT
    @latest_batch_id AS load_batch_id,
    @staging_rows AS staging_rows,
    @dimension_rows AS dimension_rows,
    @fact_rows AS fact_rows,
    @bridge_rows AS bridge_rows,
    @dimension_rows + @fact_rows + @bridge_rows AS total_dw_rows;

SELECT *
FROM audit.load_batch
WHERE load_batch_id = @latest_batch_id;

SELECT layer, COUNT(*) AS tables_loaded, SUM(loaded_rows) AS rows_loaded
FROM audit.load_table
WHERE load_batch_id = @latest_batch_id
GROUP BY layer;

SELECT
    fk.name AS foreign_key_name,
    OBJECT_SCHEMA_NAME(fk.parent_object_id) AS schema_name,
    OBJECT_NAME(fk.parent_object_id) AS table_name,
    fk.is_disabled,
    fk.is_not_trusted
FROM sys.foreign_keys AS fk
WHERE fk.is_disabled = 1 OR fk.is_not_trusted = 1;

DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS;
GO
