SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dw.dim_date', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_date
    (
        date_key int NOT NULL,
        full_date date NULL,
        [year] smallint NULL,
        semester tinyint NULL,
        quarter tinyint NULL,
        month_number tinyint NULL,
        month_name_es nvarchar(20) NULL,
        year_month char(7) NULL,
        day_of_month tinyint NULL,
        day_of_week_number tinyint NULL,
        day_name_es nvarchar(20) NULL,
        is_weekend bit NOT NULL,
        is_ytd_comparable_month bit NOT NULL,
        created_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_dim_date PRIMARY KEY CLUSTERED (date_key),
        CONSTRAINT uq_dw_dim_date_full_date UNIQUE (full_date),
        CONSTRAINT ck_dw_dim_date_key CHECK (date_key = 0 OR date_key BETWEEN 19000101 AND 99991231)
    );
END;
GO

IF OBJECT_ID(N'dw.dim_process', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_process
    (
        process_key int NOT NULL,
        ocid nvarchar(255) NOT NULL,
        compiled_release_id nvarchar(255) NULL,
        tender_id nvarchar(255) NULL,
        tender_title nvarchar(1000) NULL,
        tender_description nvarchar(max) NULL,
        initiation_type nvarchar(100) NULL,
        main_procurement_category nvarchar(100) NULL,
        additional_procurement_categories nvarchar(500) NULL,
        data_segmentation_id nvarchar(255) NULL,
        data_segmentation_criteria nvarchar(500) NULL,
        first_observed_period char(7) NULL,
        last_observed_period char(7) NULL,
        canonical_ingestion_run_id nvarchar(36) NULL,
        CONSTRAINT pk_dw_dim_process PRIMARY KEY CLUSTERED (process_key),
        CONSTRAINT uq_dw_dim_process_ocid UNIQUE (ocid)
    );
END;
GO

IF OBJECT_ID(N'dw.dim_buyer', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_buyer
    (
        buyer_key int NOT NULL,
        source_party_id nvarchar(255) NOT NULL,
        identifier_scheme nvarchar(50) NULL,
        identifier_id nvarchar(100) NULL,
        alternate_ruc nvarchar(20) NULL,
        display_name nvarchar(500) NULL,
        legal_name nvarchar(500) NULL,
        department_name_raw nvarchar(255) NULL,
        province_name_raw nvarchar(255) NULL,
        locality_name_raw nvarchar(255) NULL,
        country_name_raw nvarchar(255) NULL,
        name_variant_count int NOT NULL,
        dq_name_conflict bit NOT NULL,
        first_observed_period char(7) NULL,
        last_observed_period char(7) NULL,
        canonical_ingestion_run_id nvarchar(36) NULL,
        CONSTRAINT pk_dw_dim_buyer PRIMARY KEY CLUSTERED (buyer_key),
        CONSTRAINT uq_dw_dim_buyer_party UNIQUE (source_party_id)
    );
END;
GO

IF OBJECT_ID(N'dw.dim_supplier', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_supplier
    (
        supplier_key int NOT NULL,
        source_party_id nvarchar(255) NOT NULL,
        identifier_scheme nvarchar(50) NULL,
        identifier_id nvarchar(100) NULL,
        display_name nvarchar(500) NULL,
        legal_name nvarchar(500) NULL,
        country_name_raw nvarchar(255) NULL,
        dq_ruc_format_valid bit NULL,
        name_variant_count int NOT NULL,
        dq_name_conflict bit NOT NULL,
        first_observed_period char(7) NULL,
        last_observed_period char(7) NULL,
        canonical_ingestion_run_id nvarchar(36) NULL,
        CONSTRAINT pk_dw_dim_supplier PRIMARY KEY CLUSTERED (supplier_key),
        CONSTRAINT uq_dw_dim_supplier_party UNIQUE (source_party_id)
    );
END;
GO

IF OBJECT_ID(N'dw.dim_category', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_category
    (
        category_key int NOT NULL,
        classification_scheme nvarchar(50) NOT NULL,
        classification_code nvarchar(100) NOT NULL,
        classification_description nvarchar(1000) NULL,
        description_variant_count int NOT NULL,
        dq_description_conflict bit NOT NULL,
        is_unknown bit NOT NULL,
        first_observed_period char(7) NULL,
        last_observed_period char(7) NULL,
        canonical_ingestion_run_id nvarchar(36) NULL,
        CONSTRAINT pk_dw_dim_category PRIMARY KEY CLUSTERED (category_key),
        CONSTRAINT uq_dw_dim_category_natural UNIQUE (classification_scheme, classification_code)
    );
END;
GO

IF OBJECT_ID(N'dw.dim_procurement_method', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_procurement_method
    (
        procurement_method_key int NOT NULL,
        procurement_method nvarchar(100) NOT NULL,
        procurement_method_details nvarchar(500) NOT NULL,
        first_observed_period char(7) NULL,
        last_observed_period char(7) NULL,
        canonical_ingestion_run_id nvarchar(36) NULL,
        CONSTRAINT pk_dw_dim_procurement_method PRIMARY KEY CLUSTERED (procurement_method_key),
        CONSTRAINT uq_dw_dim_procurement_method_natural
            UNIQUE (procurement_method, procurement_method_details)
    );
END;
GO

IF OBJECT_ID(N'dw.dim_currency', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_currency
    (
        currency_key int NOT NULL,
        currency_code nvarchar(20) NOT NULL,
        currency_name nvarchar(100) NULL,
        first_observed_period char(7) NULL,
        last_observed_period char(7) NULL,
        canonical_ingestion_run_id nvarchar(36) NULL,
        CONSTRAINT pk_dw_dim_currency PRIMARY KEY CLUSTERED (currency_key),
        CONSTRAINT uq_dw_dim_currency_code UNIQUE (currency_code)
    );
END;
GO

IF OBJECT_ID(N'dw.dim_currency', N'U') IS NOT NULL
   AND COL_LENGTH(N'dw.dim_currency', N'currency_code') < 40
BEGIN
    ALTER TABLE dw.dim_currency
        ALTER COLUMN currency_code nvarchar(20) NOT NULL;
END;
GO

IF OBJECT_ID(N'dw.dim_unit', N'U') IS NULL
BEGIN
    CREATE TABLE dw.dim_unit
    (
        unit_key int NOT NULL,
        unit_scheme nvarchar(50) NOT NULL,
        unit_code nvarchar(100) NOT NULL,
        unit_name nvarchar(255) NULL,
        first_observed_period char(7) NULL,
        last_observed_period char(7) NULL,
        canonical_ingestion_run_id nvarchar(36) NULL,
        CONSTRAINT pk_dw_dim_unit PRIMARY KEY CLUSTERED (unit_key),
        CONSTRAINT uq_dw_dim_unit_natural UNIQUE (unit_scheme, unit_code)
    );
END;
GO
