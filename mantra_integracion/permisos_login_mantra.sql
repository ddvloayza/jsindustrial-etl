/* Ejecutar en SSMS con una cuenta administradora, despues de crear el login SQL mantra. */
USE [JSIndustrial];
GO

IF SUSER_ID(N'mantra') IS NULL
    THROW 50020, 'Falta crear el login SQL mantra.', 1;
IF OBJECT_ID(N'dbo.CotizacionesC', N'U') IS NULL
    THROW 50021, 'Falta dbo.CotizacionesC.', 1;
IF OBJECT_ID(N'dbo.JS_usp_ExportarCotizacionesMantra', N'P') IS NULL
    THROW 50022, 'Falta el SP de exportacion.', 1;

IF USER_ID(N'mantra') IS NULL
    CREATE USER [mantra] FOR LOGIN [mantra];

GRANT CONNECT TO [mantra];
GRANT SELECT ON OBJECT::dbo.CotizacionesC TO [mantra];
GRANT EXECUTE ON OBJECT::dbo.JS_usp_ExportarCotizacionesMantra TO [mantra];
GO
