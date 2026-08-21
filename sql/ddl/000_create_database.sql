:setvar DatabaseName "ProcurementIntelligence"

USE [master];
GO

IF DB_ID(N'$(DatabaseName)') IS NULL
BEGIN
    DECLARE @sql nvarchar(max) =
        N'CREATE DATABASE ' + QUOTENAME(N'$(DatabaseName)') + N';';
    EXEC sys.sp_executesql @sql;
END;
GO

-- Uso manual:
-- sqlcmd -S localhost\SQLEXPRESS -E -C -v DatabaseName="ProcurementIntelligence" -i sql\ddl\000_create_database.sql
