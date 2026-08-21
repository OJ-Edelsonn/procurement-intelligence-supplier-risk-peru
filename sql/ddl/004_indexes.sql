SET XACT_ABORT ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_procurement_process') AND name = N'ix_fpp_buyer_date')
    CREATE INDEX ix_fpp_buyer_date ON dw.fact_procurement_process (buyer_key, tender_published_date_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_procurement_process') AND name = N'ix_fpp_method_currency')
    CREATE INDEX ix_fpp_method_currency ON dw.fact_procurement_process (procurement_method_key, tender_currency_key);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_tender_item') AND name = N'ix_fti_primary_date')
    CREATE INDEX ix_fti_primary_date ON dw.fact_tender_item (primary_category_key, tender_published_date_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_tender_item') AND name = N'ix_fti_standard_date')
    CREATE INDEX ix_fti_standard_date ON dw.fact_tender_item (standard_category_key, tender_published_date_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_tender_item') AND name = N'ix_fti_buyer_currency')
    CREATE INDEX ix_fti_buyer_currency ON dw.fact_tender_item (buyer_key, currency_key);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_award') AND name = N'ix_fa_supplier_date')
    CREATE INDEX ix_fa_supplier_date ON dw.fact_award (attributed_supplier_key, award_date_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_award') AND name = N'ix_fa_buyer_date')
    CREATE INDEX ix_fa_buyer_date ON dw.fact_award (buyer_key, award_date_key);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_award_item') AND name = N'ix_fai_primary_date')
    CREATE INDEX ix_fai_primary_date ON dw.fact_award_item (primary_category_key, award_date_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_award_item') AND name = N'ix_fai_supplier_date')
    CREATE INDEX ix_fai_supplier_date ON dw.fact_award_item (attributed_supplier_key, award_date_key);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_contract') AND name = N'ix_fc_supplier_date')
    CREATE INDEX ix_fc_supplier_date ON dw.fact_contract (attributed_supplier_key, contract_signed_date_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_contract') AND name = N'ix_fc_buyer_date')
    CREATE INDEX ix_fc_buyer_date ON dw.fact_contract (buyer_key, contract_signed_date_key);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_contract_item') AND name = N'ix_fci_primary_date')
    CREATE INDEX ix_fci_primary_date ON dw.fact_contract_item (primary_category_key, contract_signed_date_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.fact_contract_item') AND name = N'ix_fci_supplier_date')
    CREATE INDEX ix_fci_supplier_date ON dw.fact_contract_item (attributed_supplier_key, contract_signed_date_key);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.bridge_process_tenderer') AND name = N'ix_bpt_supplier')
    CREATE INDEX ix_bpt_supplier ON dw.bridge_process_tenderer (supplier_key, process_key);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dw.bridge_award_supplier') AND name = N'ix_bas_supplier')
    CREATE INDEX ix_bas_supplier ON dw.bridge_award_supplier (supplier_key, process_key, award_id);
GO
