SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dw.fact_procurement_process', N'U') IS NULL
BEGIN
    CREATE TABLE dw.fact_procurement_process
    (
        procurement_process_fact_key bigint NOT NULL,
        process_key int NOT NULL,
        buyer_key int NOT NULL,
        procurement_method_key int NOT NULL,
        tender_currency_key int NOT NULL,
        budget_currency_key int NOT NULL,
        tender_published_date_key int NOT NULL,
        record_date_key int NOT NULL,
        published_date_key int NOT NULL,
        tender_period_start_date_key int NOT NULL,
        tender_period_end_date_key int NOT NULL,
        enquiry_period_start_date_key int NOT NULL,
        enquiry_period_end_date_key int NOT NULL,
        process_count tinyint NOT NULL,
        planning_budget_amount_original decimal(38,14) NULL,
        tender_amount_original decimal(38,14) NULL,
        tender_amount_pen_published decimal(38,14) NULL,
        tenderer_count_declared bigint NULL,
        tenderer_count_observed bigint NOT NULL,
        tender_item_amount_sum_original decimal(38,14) NULL,
        tender_amount_difference_original decimal(38,14) NULL,
        dq_tender_value_is_zero bit NOT NULL,
        dq_tenderer_count_matches_observed bit NOT NULL,
        dq_tender_amount_reconciled_0_01 bit NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_fact_procurement_process PRIMARY KEY CLUSTERED (procurement_process_fact_key),
        CONSTRAINT uq_dw_fact_procurement_process_grain UNIQUE (process_key),
        CONSTRAINT ck_dw_fact_procurement_process_count CHECK (process_count = 1),
        CONSTRAINT fk_fpp_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_fpp_buyer FOREIGN KEY (buyer_key) REFERENCES dw.dim_buyer(buyer_key),
        CONSTRAINT fk_fpp_method FOREIGN KEY (procurement_method_key) REFERENCES dw.dim_procurement_method(procurement_method_key),
        CONSTRAINT fk_fpp_tender_currency FOREIGN KEY (tender_currency_key) REFERENCES dw.dim_currency(currency_key),
        CONSTRAINT fk_fpp_budget_currency FOREIGN KEY (budget_currency_key) REFERENCES dw.dim_currency(currency_key),
        CONSTRAINT fk_fpp_tender_published_date FOREIGN KEY (tender_published_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fpp_record_date FOREIGN KEY (record_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fpp_published_date FOREIGN KEY (published_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fpp_tender_start_date FOREIGN KEY (tender_period_start_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fpp_tender_end_date FOREIGN KEY (tender_period_end_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fpp_enquiry_start_date FOREIGN KEY (enquiry_period_start_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fpp_enquiry_end_date FOREIGN KEY (enquiry_period_end_date_key) REFERENCES dw.dim_date(date_key)
    );
END;
GO

IF OBJECT_ID(N'dw.fact_tender_item', N'U') IS NULL
BEGIN
    CREATE TABLE dw.fact_tender_item
    (
        tender_item_fact_key bigint NOT NULL,
        process_key int NOT NULL,
        buyer_key int NOT NULL,
        procurement_method_key int NOT NULL,
        primary_category_key int NOT NULL,
        standard_category_key int NOT NULL,
        unit_key int NOT NULL,
        currency_key int NOT NULL,
        tender_published_date_key int NOT NULL,
        tender_item_id nvarchar(255) NOT NULL,
        item_position bigint NULL,
        item_description nvarchar(max) NULL,
        item_status nvarchar(100) NULL,
        item_status_details nvarchar(500) NULL,
        tender_item_count tinyint NOT NULL,
        quantity decimal(38,14) NULL,
        total_amount_original decimal(38,14) NULL,
        conversion_rate_to_pen decimal(38,14) NULL,
        total_amount_pen_calculated decimal(38,14) NULL,
        dq_classification_was_missing bit NOT NULL,
        dq_standard_category_missing bit NOT NULL,
        dq_pen_conversion_available bit NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_fact_tender_item PRIMARY KEY CLUSTERED (tender_item_fact_key),
        CONSTRAINT uq_dw_fact_tender_item_grain UNIQUE (process_key, tender_item_id),
        CONSTRAINT ck_dw_fact_tender_item_count CHECK (tender_item_count = 1),
        CONSTRAINT fk_fti_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_fti_buyer FOREIGN KEY (buyer_key) REFERENCES dw.dim_buyer(buyer_key),
        CONSTRAINT fk_fti_method FOREIGN KEY (procurement_method_key) REFERENCES dw.dim_procurement_method(procurement_method_key),
        CONSTRAINT fk_fti_primary_category FOREIGN KEY (primary_category_key) REFERENCES dw.dim_category(category_key),
        CONSTRAINT fk_fti_standard_category FOREIGN KEY (standard_category_key) REFERENCES dw.dim_category(category_key),
        CONSTRAINT fk_fti_unit FOREIGN KEY (unit_key) REFERENCES dw.dim_unit(unit_key),
        CONSTRAINT fk_fti_currency FOREIGN KEY (currency_key) REFERENCES dw.dim_currency(currency_key),
        CONSTRAINT fk_fti_date FOREIGN KEY (tender_published_date_key) REFERENCES dw.dim_date(date_key)
    );
END;
GO

IF OBJECT_ID(N'dw.fact_award', N'U') IS NULL
BEGIN
    CREATE TABLE dw.fact_award
    (
        award_fact_key bigint NOT NULL,
        process_key int NOT NULL,
        buyer_key int NOT NULL,
        procurement_method_key int NOT NULL,
        attributed_supplier_key int NOT NULL,
        currency_key int NOT NULL,
        award_date_key int NOT NULL,
        award_id nvarchar(255) NOT NULL,
        award_count tinyint NOT NULL,
        award_amount_original decimal(38,14) NULL,
        conversion_rate_to_pen decimal(38,14) NULL,
        award_amount_pen_calculated decimal(38,14) NULL,
        supplier_count bigint NOT NULL,
        award_item_amount_sum_original decimal(38,14) NULL,
        award_amount_difference_original decimal(38,14) NULL,
        dq_supplier_amount_attributable bit NOT NULL,
        dq_pen_conversion_available bit NOT NULL,
        dq_award_amount_reconciled_0_01 bit NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_fact_award PRIMARY KEY CLUSTERED (award_fact_key),
        CONSTRAINT uq_dw_fact_award_grain UNIQUE (process_key, award_id),
        CONSTRAINT ck_dw_fact_award_count CHECK (award_count = 1),
        CONSTRAINT fk_fa_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_fa_buyer FOREIGN KEY (buyer_key) REFERENCES dw.dim_buyer(buyer_key),
        CONSTRAINT fk_fa_method FOREIGN KEY (procurement_method_key) REFERENCES dw.dim_procurement_method(procurement_method_key),
        CONSTRAINT fk_fa_supplier FOREIGN KEY (attributed_supplier_key) REFERENCES dw.dim_supplier(supplier_key),
        CONSTRAINT fk_fa_currency FOREIGN KEY (currency_key) REFERENCES dw.dim_currency(currency_key),
        CONSTRAINT fk_fa_date FOREIGN KEY (award_date_key) REFERENCES dw.dim_date(date_key)
    );
END;
GO

IF OBJECT_ID(N'dw.fact_award_item', N'U') IS NULL
BEGIN
    CREATE TABLE dw.fact_award_item
    (
        award_item_fact_key bigint NOT NULL,
        process_key int NOT NULL,
        buyer_key int NOT NULL,
        attributed_supplier_key int NOT NULL,
        primary_category_key int NOT NULL,
        standard_category_key int NOT NULL,
        unit_key int NOT NULL,
        currency_key int NOT NULL,
        award_date_key int NOT NULL,
        award_id nvarchar(255) NOT NULL,
        award_item_id nvarchar(255) NOT NULL,
        item_position bigint NULL,
        item_description nvarchar(max) NULL,
        item_status nvarchar(100) NULL,
        item_status_details nvarchar(500) NULL,
        award_item_count tinyint NOT NULL,
        quantity decimal(38,14) NULL,
        total_amount_original decimal(38,14) NULL,
        conversion_rate_to_pen decimal(38,14) NULL,
        total_amount_pen_calculated decimal(38,14) NULL,
        dq_classification_was_missing bit NOT NULL,
        dq_standard_category_missing bit NOT NULL,
        dq_supplier_amount_attributable bit NOT NULL,
        dq_pen_conversion_available bit NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_fact_award_item PRIMARY KEY CLUSTERED (award_item_fact_key),
        CONSTRAINT uq_dw_fact_award_item_grain UNIQUE (process_key, award_id, award_item_id),
        CONSTRAINT ck_dw_fact_award_item_count CHECK (award_item_count = 1),
        CONSTRAINT fk_fai_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_fai_buyer FOREIGN KEY (buyer_key) REFERENCES dw.dim_buyer(buyer_key),
        CONSTRAINT fk_fai_supplier FOREIGN KEY (attributed_supplier_key) REFERENCES dw.dim_supplier(supplier_key),
        CONSTRAINT fk_fai_primary_category FOREIGN KEY (primary_category_key) REFERENCES dw.dim_category(category_key),
        CONSTRAINT fk_fai_standard_category FOREIGN KEY (standard_category_key) REFERENCES dw.dim_category(category_key),
        CONSTRAINT fk_fai_unit FOREIGN KEY (unit_key) REFERENCES dw.dim_unit(unit_key),
        CONSTRAINT fk_fai_currency FOREIGN KEY (currency_key) REFERENCES dw.dim_currency(currency_key),
        CONSTRAINT fk_fai_date FOREIGN KEY (award_date_key) REFERENCES dw.dim_date(date_key)
    );
END;
GO

IF OBJECT_ID(N'dw.fact_contract', N'U') IS NULL
BEGIN
    CREATE TABLE dw.fact_contract
    (
        contract_fact_key bigint NOT NULL,
        process_key int NOT NULL,
        buyer_key int NOT NULL,
        procurement_method_key int NOT NULL,
        attributed_supplier_key int NOT NULL,
        currency_key int NOT NULL,
        contract_signed_date_key int NOT NULL,
        contract_period_start_date_key int NOT NULL,
        contract_period_end_date_key int NOT NULL,
        implementation_end_date_key int NOT NULL,
        contract_id nvarchar(255) NOT NULL,
        award_id nvarchar(255) NULL,
        contract_title nvarchar(1000) NULL,
        contract_description nvarchar(max) NULL,
        contract_count tinyint NOT NULL,
        contract_amount_original decimal(38,14) NULL,
        conversion_rate_to_pen decimal(38,14) NULL,
        contract_amount_pen_calculated decimal(38,14) NULL,
        contract_duration_days bigint NULL,
        final_value_original decimal(38,14) NULL,
        contract_item_amount_sum_original decimal(38,14) NULL,
        contract_amount_difference_original decimal(38,14) NULL,
        dq_final_value_available bit NOT NULL,
        dq_supplier_amount_attributable bit NOT NULL,
        dq_pen_conversion_available bit NOT NULL,
        dq_contract_amount_reconciled_0_01 bit NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_fact_contract PRIMARY KEY CLUSTERED (contract_fact_key),
        CONSTRAINT uq_dw_fact_contract_grain UNIQUE (process_key, contract_id),
        CONSTRAINT ck_dw_fact_contract_count CHECK (contract_count = 1),
        CONSTRAINT fk_fc_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_fc_buyer FOREIGN KEY (buyer_key) REFERENCES dw.dim_buyer(buyer_key),
        CONSTRAINT fk_fc_method FOREIGN KEY (procurement_method_key) REFERENCES dw.dim_procurement_method(procurement_method_key),
        CONSTRAINT fk_fc_supplier FOREIGN KEY (attributed_supplier_key) REFERENCES dw.dim_supplier(supplier_key),
        CONSTRAINT fk_fc_currency FOREIGN KEY (currency_key) REFERENCES dw.dim_currency(currency_key),
        CONSTRAINT fk_fc_signed_date FOREIGN KEY (contract_signed_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fc_start_date FOREIGN KEY (contract_period_start_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fc_end_date FOREIGN KEY (contract_period_end_date_key) REFERENCES dw.dim_date(date_key),
        CONSTRAINT fk_fc_implementation_date FOREIGN KEY (implementation_end_date_key) REFERENCES dw.dim_date(date_key)
    );
END;
GO

IF OBJECT_ID(N'dw.fact_contract_item', N'U') IS NULL
BEGIN
    CREATE TABLE dw.fact_contract_item
    (
        contract_item_fact_key bigint NOT NULL,
        process_key int NOT NULL,
        buyer_key int NOT NULL,
        attributed_supplier_key int NOT NULL,
        primary_category_key int NOT NULL,
        standard_category_key int NOT NULL,
        unit_key int NOT NULL,
        currency_key int NOT NULL,
        contract_signed_date_key int NOT NULL,
        contract_id nvarchar(255) NOT NULL,
        contract_item_id nvarchar(255) NOT NULL,
        item_position bigint NULL,
        item_description nvarchar(max) NULL,
        item_status nvarchar(100) NULL,
        item_status_details nvarchar(500) NULL,
        contract_item_count tinyint NOT NULL,
        quantity decimal(38,14) NULL,
        total_amount_original decimal(38,14) NULL,
        conversion_rate_to_pen decimal(38,14) NULL,
        total_amount_pen_calculated decimal(38,14) NULL,
        dq_classification_was_missing bit NOT NULL,
        dq_standard_category_missing bit NOT NULL,
        dq_supplier_amount_attributable bit NOT NULL,
        dq_pen_conversion_available bit NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_fact_contract_item PRIMARY KEY CLUSTERED (contract_item_fact_key),
        CONSTRAINT uq_dw_fact_contract_item_grain UNIQUE (process_key, contract_id, contract_item_id),
        CONSTRAINT ck_dw_fact_contract_item_count CHECK (contract_item_count = 1),
        CONSTRAINT fk_fci_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_fci_buyer FOREIGN KEY (buyer_key) REFERENCES dw.dim_buyer(buyer_key),
        CONSTRAINT fk_fci_supplier FOREIGN KEY (attributed_supplier_key) REFERENCES dw.dim_supplier(supplier_key),
        CONSTRAINT fk_fci_primary_category FOREIGN KEY (primary_category_key) REFERENCES dw.dim_category(category_key),
        CONSTRAINT fk_fci_standard_category FOREIGN KEY (standard_category_key) REFERENCES dw.dim_category(category_key),
        CONSTRAINT fk_fci_unit FOREIGN KEY (unit_key) REFERENCES dw.dim_unit(unit_key),
        CONSTRAINT fk_fci_currency FOREIGN KEY (currency_key) REFERENCES dw.dim_currency(currency_key),
        CONSTRAINT fk_fci_date FOREIGN KEY (contract_signed_date_key) REFERENCES dw.dim_date(date_key)
    );
END;
GO

IF OBJECT_ID(N'dw.bridge_process_tenderer', N'U') IS NULL
BEGIN
    CREATE TABLE dw.bridge_process_tenderer
    (
        process_tenderer_bridge_key bigint NOT NULL,
        process_key int NOT NULL,
        supplier_key int NOT NULL,
        participation_count tinyint NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_bridge_process_tenderer PRIMARY KEY CLUSTERED (process_tenderer_bridge_key),
        CONSTRAINT uq_dw_bridge_process_tenderer_grain UNIQUE (process_key, supplier_key),
        CONSTRAINT ck_dw_bridge_process_tenderer_count CHECK (participation_count = 1),
        CONSTRAINT fk_bpt_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_bpt_supplier FOREIGN KEY (supplier_key) REFERENCES dw.dim_supplier(supplier_key)
    );
END;
GO

IF OBJECT_ID(N'dw.bridge_award_supplier', N'U') IS NULL
BEGIN
    CREATE TABLE dw.bridge_award_supplier
    (
        award_supplier_bridge_key bigint NOT NULL,
        process_key int NOT NULL,
        supplier_key int NOT NULL,
        award_id nvarchar(255) NOT NULL,
        participation_count tinyint NOT NULL,
        source_id nvarchar(100) NOT NULL,
        source_period char(7) NOT NULL,
        snapshot_date date NOT NULL,
        ingestion_run_id nvarchar(36) NOT NULL,
        source_file_name nvarchar(255) NOT NULL,
        source_file_sha256 char(64) NOT NULL,
        source_table_name nvarchar(255) NOT NULL,
        source_row_number bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL,
        CONSTRAINT pk_dw_bridge_award_supplier PRIMARY KEY CLUSTERED (award_supplier_bridge_key),
        CONSTRAINT uq_dw_bridge_award_supplier_grain UNIQUE (process_key, award_id, supplier_key),
        CONSTRAINT ck_dw_bridge_award_supplier_count CHECK (participation_count = 1),
        CONSTRAINT fk_bas_process FOREIGN KEY (process_key) REFERENCES dw.dim_process(process_key),
        CONSTRAINT fk_bas_supplier FOREIGN KEY (supplier_key) REFERENCES dw.dim_supplier(supplier_key)
    );
END;
GO
