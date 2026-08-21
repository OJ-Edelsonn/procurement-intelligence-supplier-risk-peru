SET XACT_ABORT ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'audit')
    EXEC(N'CREATE SCHEMA [audit] AUTHORIZATION [dbo];');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'stg')
    EXEC(N'CREATE SCHEMA [stg] AUTHORIZATION [dbo];');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'dw')
    EXEC(N'CREATE SCHEMA [dw] AUTHORIZATION [dbo];');
GO

IF OBJECT_ID(N'audit.load_batch', N'U') IS NULL
BEGIN
    CREATE TABLE audit.load_batch
    (
        load_batch_id bigint IDENTITY(1,1) NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        archive_sha256 char(64) NOT NULL,
        etl_summary_sha256 char(64) NOT NULL,
        model_config_sha256 char(64) NOT NULL,
        physical_config_sha256 char(64) NOT NULL,
        ddl_bundle_sha256 char(64) NOT NULL,
        load_mode varchar(30) NOT NULL,
        database_name sysname NOT NULL,
        started_at_utc datetime2(6) NOT NULL,
        completed_at_utc datetime2(6) NULL,
        status varchar(20) NOT NULL,
        staging_rows bigint NULL,
        dimension_rows bigint NULL,
        fact_rows bigint NULL,
        bridge_rows bigint NULL,
        duration_seconds decimal(18,4) NULL,
        error_message nvarchar(4000) NULL,
        CONSTRAINT pk_audit_load_batch PRIMARY KEY CLUSTERED (load_batch_id),
        CONSTRAINT ck_audit_load_batch_status
            CHECK (status IN ('STARTED', 'SUCCEEDED', 'FAILED', 'SKIPPED')),
        CONSTRAINT ck_audit_load_batch_mode
            CHECK (load_mode IN ('initial_snapshot', 'replace_snapshot', 'skip_existing'))
    );
END;
GO

IF OBJECT_ID(N'audit.load_batch', N'U') IS NOT NULL
   AND COL_LENGTH(N'audit.load_batch', N'ddl_bundle_sha256') IS NULL
BEGIN
    ALTER TABLE audit.load_batch
        ADD ddl_bundle_sha256 char(64) NULL;
END;
GO

IF OBJECT_ID(N'audit.load_table', N'U') IS NULL
BEGIN
    CREATE TABLE audit.load_table
    (
        load_table_id bigint IDENTITY(1,1) NOT NULL,
        load_batch_id bigint NOT NULL,
        layer varchar(10) NOT NULL,
        schema_name sysname NOT NULL,
        table_name sysname NOT NULL,
        expected_rows bigint NOT NULL,
        loaded_rows bigint NULL,
        started_at_utc datetime2(6) NOT NULL,
        completed_at_utc datetime2(6) NULL,
        duration_seconds decimal(18,4) NULL,
        status varchar(20) NOT NULL,
        error_message nvarchar(4000) NULL,
        CONSTRAINT pk_audit_load_table PRIMARY KEY CLUSTERED (load_table_id),
        CONSTRAINT fk_audit_load_table_batch FOREIGN KEY (load_batch_id)
            REFERENCES audit.load_batch(load_batch_id),
        CONSTRAINT uq_audit_load_table UNIQUE (load_batch_id, schema_name, table_name),
        CONSTRAINT ck_audit_load_table_layer CHECK (layer IN ('STG', 'DW')),
        CONSTRAINT ck_audit_load_table_status
            CHECK (status IN ('STARTED', 'SUCCEEDED', 'FAILED', 'SKIPPED'))
    );
END;
GO

IF NOT EXISTS
(
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'audit.load_batch')
      AND name = N'ix_audit_load_batch_idempotency'
)
BEGIN
    CREATE INDEX ix_audit_load_batch_idempotency
        ON audit.load_batch
        (source_id, source_period, snapshot_date, ingestion_run_id, model_config_sha256, status);
END;
GO
