-- Run after Django migrations against SQL Server 2019+.
-- Execute with SSMS/sqlcmd: GO separates batches. No operational records are modified.
CREATE OR ALTER VIEW dbo.dim_product AS
SELECT id AS product_key,name,molecule,category,unit_price,unit_cost FROM dbo.core_sku;
GO
CREATE OR ALTER VIEW dbo.dim_depot AS
SELECT id AS depot_key,name FROM dbo.core_depot;
GO
CREATE OR ALTER VIEW dbo.dim_date AS
SELECT DISTINCT [date] AS date_key,YEAR([date]) AS [year],MONTH([date]) AS [month],DAY([date]) AS [day],DATENAME(weekday,[date]) AS weekday_name FROM dbo.core_demandobservation;
GO
CREATE OR ALTER VIEW dbo.fact_demand AS
SELECT id,sku_id AS product_key,depot_id AS depot_key,[date] AS date_key,units,rx_index,disease_index,holiday,regulatory_index,competitor_price FROM dbo.core_demandobservation;
GO
CREATE OR ALTER VIEW dbo.fact_stock AS
SELECT id,sku_id AS product_key,depot_id AS depot_key,batch_code,expiry_date,quantity FROM dbo.core_stocklot;
GO
CREATE OR ALTER VIEW dbo.bi_monthly_demand AS
WITH totals AS (
 SELECT sku_id,depot_id,DATEFROMPARTS(YEAR([date]),MONTH([date]),1) AS month_start,SUM(CAST(units AS bigint)) AS units
 FROM dbo.core_demandobservation GROUP BY sku_id,depot_id,YEAR([date]),MONTH([date])
), periods AS (
 SELECT *,LAG(units,1) OVER(PARTITION BY sku_id,depot_id ORDER BY month_start) AS previous_month_units,LAG(units,12) OVER(PARTITION BY sku_id,depot_id ORDER BY month_start) AS sply_units FROM totals
)
SELECT *,100.0*(units-previous_month_units)/NULLIF(previous_month_units,0) AS mom_pct,100.0*(units-sply_units)/NULLIF(sply_units,0) AS sply_pct FROM periods;
GO
-- LAG assumes continuous periods. Seeded data is daily/continuous. For incomplete
-- operational history, join an enterprise calendar spine and zero-fill first.
CREATE OR ALTER VIEW dbo.bi_weekly_demand AS
WITH totals AS (
 SELECT sku_id,depot_id,DATEADD(day,-(DATEDIFF(day,'19000101',[date])%7),[date]) AS week_start,SUM(CAST(units AS bigint)) AS units
 FROM dbo.core_demandobservation GROUP BY sku_id,depot_id,DATEADD(day,-(DATEDIFF(day,'19000101',[date])%7),[date])
), periods AS (
 SELECT *,LAG(units) OVER(PARTITION BY sku_id,depot_id ORDER BY week_start) AS previous_week_units FROM totals
)
SELECT *,100.0*(units-previous_week_units)/NULLIF(previous_week_units,0) AS wow_pct FROM periods;
GO
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE name='ix_demand_cover' AND object_id=OBJECT_ID('dbo.core_demandobservation'))
CREATE INDEX ix_demand_cover ON dbo.core_demandobservation(sku_id,depot_id,[date]) INCLUDE(units,rx_index,disease_index,holiday,regulatory_index,competitor_price);
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE name='ix_stock_fefo_cover' AND object_id=OBJECT_ID('dbo.core_stocklot'))
CREATE INDEX ix_stock_fefo_cover ON dbo.core_stocklot(sku_id,depot_id,expiry_date) INCLUDE(quantity,batch_code);
GO
-- Use a restricted runtime SQL principal: SELECT/INSERT on AuditTrail only;
-- no UPDATE, DELETE, ALTER, CONTROL or db_owner. Migration account is separate.
-- Migration 0002 installs an INSTEAD OF UPDATE,DELETE audit protection trigger.
