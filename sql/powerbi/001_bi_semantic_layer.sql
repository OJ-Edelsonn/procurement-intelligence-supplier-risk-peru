SET NOCOUNT ON;
SET XACT_ABORT ON;

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'bi')
    EXEC(N'CREATE SCHEMA bi AUTHORIZATION dbo;');
GO

IF OBJECT_ID(N'bi.market_opportunity_score', N'U') IS NULL
BEGIN
    CREATE TABLE bi.market_opportunity_score
    (
        category_key int NOT NULL PRIMARY KEY,
        classification_code nvarchar(100) NOT NULL,
        classification_description nvarchar(1000) NULL,
        award_item_count bigint NOT NULL,
        buyer_count bigint NOT NULL,
        supplier_count bigint NOT NULL,
        total_category_amount_pen float NOT NULL,
        attributable_amount_pen float NOT NULL,
        attributable_amount_coverage_pct float NOT NULL,
        top1_share_pct float NOT NULL,
        top3_share_pct float NOT NULL,
        top5_share_pct float NOT NULL,
        top10_share_pct float NOT NULL,
        hhi float NOT NULL,
        effective_supplier_count float NOT NULL,
        is_analysis_eligible bit NOT NULL,
        average_ticket float NOT NULL,
        component_market_size float NOT NULL,
        component_frequency float NOT NULL,
        component_buyer_breadth float NOT NULL,
        component_average_ticket float NOT NULL,
        component_market_openness float NOT NULL,
        score_baseline float NOT NULL,
        rank_baseline int NOT NULL,
        score_demand_heavy float NOT NULL,
        rank_demand_heavy int NOT NULL,
        score_accessibility_heavy float NOT NULL,
        rank_accessibility_heavy int NOT NULL,
        score_balanced_equal float NOT NULL,
        rank_balanced_equal int NOT NULL,
        opportunity_band nvarchar(40) NOT NULL,
        scenario_score_range float NOT NULL,
        maximum_absolute_rank_shift int NOT NULL,
        CONSTRAINT ck_bi_market_score CHECK (score_baseline BETWEEN 0 AND 100)
    );
END;
GO

IF OBJECT_ID(N'bi.supplier_exposure_score', N'U') IS NULL
BEGIN
    CREATE TABLE bi.supplier_exposure_score
    (
        supplier_key int NOT NULL PRIMARY KEY,
        supplier_name nvarchar(500) NOT NULL,
        award_count bigint NOT NULL,
        buyer_count bigint NOT NULL,
        award_amount_pen float NOT NULL,
        average_award_ticket_pen float NOT NULL,
        known_buyer_amount_pen float NOT NULL,
        top_buyer_share_pct float NOT NULL,
        award_hhi float NOT NULL,
        award_item_count bigint NOT NULL,
        award_item_amount_pen float NOT NULL,
        known_category_item_amount_pen float NOT NULL,
        category_count bigint NOT NULL,
        top_category_share_pct float NOT NULL,
        contract_count bigint NOT NULL,
        contract_amount_pen float NOT NULL,
        known_buyer_amount_coverage_pct float NOT NULL,
        known_category_item_amount_coverage_pct float NOT NULL,
        effective_award_count float NOT NULL,
        is_score_eligible bit NOT NULL,
        component_award_amount_materiality float NOT NULL,
        component_buyer_dependency float NOT NULL,
        component_category_dependency float NOT NULL,
        component_award_concentration float NOT NULL,
        component_limited_buyer_breadth float NOT NULL,
        score_baseline float NOT NULL,
        rank_baseline int NOT NULL,
        score_dependency_heavy float NOT NULL,
        rank_dependency_heavy int NOT NULL,
        score_materiality_heavy float NOT NULL,
        rank_materiality_heavy int NOT NULL,
        score_balanced_equal float NOT NULL,
        rank_balanced_equal int NOT NULL,
        exposure_band nvarchar(40) NOT NULL,
        maximum_absolute_rank_shift int NOT NULL,
        scenario_score_range float NOT NULL,
        CONSTRAINT ck_bi_supplier_score CHECK (score_baseline BETWEEN 0 AND 100)
    );
END;
GO

IF OBJECT_ID(N'bi.semantic_load_audit', N'U') IS NULL
BEGIN
    CREATE TABLE bi.semantic_load_audit
    (
        artifact_name nvarchar(100) NOT NULL PRIMARY KEY,
        source_relative_path nvarchar(500) NOT NULL,
        source_sha256 char(64) NOT NULL,
        source_rows bigint NOT NULL,
        loaded_at_utc datetime2(6) NOT NULL
    );
END;
GO

CREATE OR ALTER VIEW bi.vw_executive_overview
AS
SELECT
    (SELECT MAX(source_period) FROM dw.fact_procurement_process) AS source_period,
    (SELECT COUNT_BIG(*) FROM dw.fact_procurement_process) AS process_count,
    (SELECT SUM(tender_amount_pen_published) FROM dw.fact_procurement_process) AS tender_amount_pen,
    (SELECT COUNT_BIG(DISTINCT buyer_key) FROM dw.fact_procurement_process WHERE buyer_key <> 0) AS active_buyers,
    (SELECT COUNT_BIG(*) FROM dw.fact_award) AS award_count,
    (SELECT SUM(award_amount_pen_calculated) FROM dw.fact_award) AS award_amount_pen,
    (SELECT COUNT_BIG(DISTINCT attributed_supplier_key) FROM dw.fact_award WHERE attributed_supplier_key <> 0) AS awarded_suppliers,
    (SELECT COUNT_BIG(*) FROM dw.fact_contract) AS contract_count,
    (SELECT SUM(contract_amount_pen_calculated) FROM dw.fact_contract) AS contract_amount_pen,
    (SELECT COUNT_BIG(*) FROM bi.market_opportunity_score) AS eligible_markets,
    (SELECT COUNT_BIG(*) FROM bi.supplier_exposure_score) AS scored_suppliers;
GO

CREATE OR ALTER VIEW bi.vw_monthly_activity
AS
WITH process_month AS
(
    SELECT d.year_month,
           COUNT_BIG(*) AS process_count,
           SUM(f.tender_amount_pen_published) AS tender_amount_pen
    FROM dw.fact_procurement_process AS f
    INNER JOIN dw.dim_date AS d ON d.date_key = f.tender_published_date_key
    WHERE d.date_key <> 0
    GROUP BY d.year_month
),
award_month AS
(
    SELECT d.year_month,
           COUNT_BIG(*) AS award_count,
           SUM(f.award_amount_pen_calculated) AS award_amount_pen
    FROM dw.fact_award AS f
    INNER JOIN dw.dim_date AS d ON d.date_key = f.award_date_key
    WHERE d.date_key <> 0
    GROUP BY d.year_month
),
contract_month AS
(
    SELECT d.year_month,
           COUNT_BIG(*) AS contract_count,
           SUM(f.contract_amount_pen_calculated) AS contract_amount_pen
    FROM dw.fact_contract AS f
    INNER JOIN dw.dim_date AS d ON d.date_key = f.contract_signed_date_key
    WHERE d.date_key <> 0
    GROUP BY d.year_month
),
months AS
(
    SELECT year_month FROM process_month
    UNION SELECT year_month FROM award_month
    UNION SELECT year_month FROM contract_month
)
SELECT m.year_month,
       COALESCE(p.process_count, 0) AS process_count,
       p.tender_amount_pen,
       COALESCE(a.award_count, 0) AS award_count,
       a.award_amount_pen,
       COALESCE(c.contract_count, 0) AS contract_count,
       c.contract_amount_pen
FROM months AS m
LEFT JOIN process_month AS p ON p.year_month = m.year_month
LEFT JOIN award_month AS a ON a.year_month = m.year_month
LEFT JOIN contract_month AS c ON c.year_month = m.year_month;
GO

CREATE OR ALTER VIEW bi.vw_buyer_summary
AS
WITH process_summary AS
(
    SELECT buyer_key,
           COUNT_BIG(*) AS process_count,
           SUM(tender_amount_pen_published) AS tender_amount_pen
    FROM dw.fact_procurement_process
    WHERE buyer_key <> 0
    GROUP BY buyer_key
),
award_summary AS
(
    SELECT buyer_key,
           COUNT_BIG(*) AS award_count,
           SUM(award_amount_pen_calculated) AS award_amount_pen
    FROM dw.fact_award
    WHERE buyer_key <> 0
    GROUP BY buyer_key
),
contract_summary AS
(
    SELECT buyer_key,
           COUNT_BIG(*) AS contract_count,
           SUM(contract_amount_pen_calculated) AS contract_amount_pen
    FROM dw.fact_contract
    WHERE buyer_key <> 0
    GROUP BY buyer_key
)
SELECT b.buyer_key,
       b.display_name AS buyer_name,
       b.department_name_raw AS department_name,
       p.process_count,
       p.tender_amount_pen,
       COALESCE(a.award_count, 0) AS award_count,
       a.award_amount_pen,
       COALESCE(c.contract_count, 0) AS contract_count,
       c.contract_amount_pen
FROM process_summary AS p
INNER JOIN dw.dim_buyer AS b ON b.buyer_key = p.buyer_key
LEFT JOIN award_summary AS a ON a.buyer_key = p.buyer_key
LEFT JOIN contract_summary AS c ON c.buyer_key = p.buyer_key;
GO

CREATE OR ALTER VIEW bi.vw_supplier_summary
AS
WITH award_summary AS
(
    SELECT attributed_supplier_key AS supplier_key,
           COUNT_BIG(*) AS award_count,
           COUNT_BIG(DISTINCT buyer_key) AS buyer_count,
           SUM(award_amount_pen_calculated) AS award_amount_pen
    FROM dw.fact_award
    WHERE attributed_supplier_key <> 0
    GROUP BY attributed_supplier_key
),
contract_summary AS
(
    SELECT attributed_supplier_key AS supplier_key,
           COUNT_BIG(*) AS contract_count,
           SUM(contract_amount_pen_calculated) AS contract_amount_pen
    FROM dw.fact_contract
    WHERE attributed_supplier_key <> 0
    GROUP BY attributed_supplier_key
)
SELECT s.supplier_key,
       s.display_name AS supplier_name,
       a.award_count,
       a.buyer_count,
       a.award_amount_pen,
       COALESCE(c.contract_count, 0) AS contract_count,
       c.contract_amount_pen
FROM award_summary AS a
INNER JOIN dw.dim_supplier AS s ON s.supplier_key = a.supplier_key
LEFT JOIN contract_summary AS c ON c.supplier_key = a.supplier_key;
GO

CREATE OR ALTER VIEW bi.vw_category_summary
AS
SELECT c.category_key,
       c.classification_code,
       c.classification_description,
       COUNT_BIG(*) AS award_item_count,
       COUNT_BIG(DISTINCT NULLIF(f.buyer_key, 0)) AS buyer_count,
       COUNT_BIG(DISTINCT NULLIF(f.attributed_supplier_key, 0)) AS supplier_count,
       SUM(f.total_amount_pen_calculated) AS award_item_amount_pen
FROM dw.fact_award_item AS f
INNER JOIN dw.dim_category AS c ON c.category_key = f.standard_category_key
WHERE f.standard_category_key <> 0
  AND f.attributed_supplier_key <> 0
  AND f.total_amount_pen_calculated > 0
GROUP BY c.category_key, c.classification_code, c.classification_description;
GO

CREATE OR ALTER VIEW bi.vw_top_market_opportunity
AS
SELECT TOP (10)
       classification_code,
       classification_description,
       total_category_amount_pen,
       buyer_count,
       supplier_count,
       hhi,
       score_baseline,
       rank_baseline
FROM bi.market_opportunity_score
ORDER BY rank_baseline, classification_code;
GO

CREATE OR ALTER VIEW bi.vw_top_supplier_exposure
AS
SELECT TOP (10)
       supplier_key,
       supplier_name,
       award_count,
       buyer_count,
       award_amount_pen,
       top_buyer_share_pct,
       top_category_share_pct,
       score_baseline,
       rank_baseline
FROM bi.supplier_exposure_score
ORDER BY rank_baseline, supplier_key;
GO

CREATE OR ALTER VIEW bi.vw_top_suppliers
AS
SELECT TOP (10) *
FROM bi.vw_supplier_summary
ORDER BY award_amount_pen DESC, supplier_key;
GO

CREATE OR ALTER VIEW bi.vw_top_buyers
AS
SELECT TOP (10) *
FROM bi.vw_buyer_summary
ORDER BY tender_amount_pen DESC, buyer_key;
GO

CREATE OR ALTER VIEW bi.vw_top_categories
AS
SELECT TOP (10) *
FROM bi.vw_category_summary
ORDER BY award_item_amount_pen DESC, category_key;
GO
