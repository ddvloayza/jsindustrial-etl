/*
  Exportación de las 23 columnas de "Cotizaciones Generales Prueba.xlsx".
  Fuente disponible: dbo.CotizacionesC del backup BD_MANTRA.bak.
  Los campos sin origen verificado se devuelven NULL; los que requieren
  catálogos externos devuelven su código/ID provisional (ver mapeo.md).
  Este SP prepara datos. La llamada HTTP a Mantra debe hacerla el integrador
  una vez confirmado el contrato del API y las equivalencias de catálogos.
*/
CREATE OR ALTER PROCEDURE dbo.usp_ExportarCotizacionesMantra
    @FechaDesde date = NULL,
    @FechaHasta date = NULL,
    @Codidtcot char(10) = NULL,
    @ComoJson bit = 0
AS
BEGIN
    SET NOCOUNT ON;

    IF @FechaDesde IS NOT NULL AND @FechaHasta IS NOT NULL AND @FechaDesde > @FechaHasta
        THROW 50001, 'FechaDesde no puede ser mayor que FechaHasta.', 1;

    SELECT
        -- Campo calculado para la salida; NO existe una columna numero_cotizacion.
        -- Confirmar con una cotización real que serie-número-revisión es el formato correcto.
        CAST(COALESCE(
            CASE WHEN doc.serie IS NOT NULL AND doc.numero IS NOT NULL
                 THEN CONCAT(doc.serie, '-', doc.numero,
                     CASE WHEN doc.revision IS NULL OR doc.revision = '00' THEN ''
                          WHEN TRY_CONVERT(int, doc.revision) IS NOT NULL
                          THEN CONCAT('-', TRY_CONVERT(int, doc.revision))
                          ELSE CONCAT('-', doc.revision) END)
                 ELSE NULL END,
            LTRIM(RTRIM(c.codidtcot))
        ) AS varchar(30)) AS [N° Cotización],
        CAST(c.fecemidoc AS date) AS [Fecha],
        c.txtrazsoc AS [Cliente],
        LTRIM(RTRIM(c.codfmapag)) AS [Condicion de venta],
        LTRIM(RTRIM(c.codmtrven)) AS [Vendedor],
        CONVERT(varchar(20), c.ID_Canal_Origen) AS [Fuente de contacto],
        c.txtrefcot AS [Referencia],
        c.txtnomatt AS [Nombre del contacto],
        CAST(NULL AS varchar(100)) AS [Cargo],
        CAST(NULL AS varchar(100)) AS [Area],
        c.txttlf001 AS [Telefono],
        c.txtcorele AS [email],
        CASE LTRIM(RTRIM(c.codtipmon))
            WHEN 'USD' THEN 'US$' WHEN 'DOL' THEN 'US$'
            WHEN 'PEN' THEN 'S/'  WHEN 'SOL' THEN 'S/'
            ELSE LTRIM(RTRIM(c.codtipmon))
        END AS [Moneda],
        c.numtotdoc AS [Total Docum.],
        CAST(CASE
            WHEN LTRIM(RTRIM(c.codtipmon)) IN ('PEN', 'SOL', 'S/')
                THEN c.numtotdoc
            WHEN c.numtipcam > 0 AND c.numtotdoc IS NOT NULL
                THEN ROUND(c.numtotdoc * c.numtipcam, 2)
            ELSE NULL END AS numeric(20,2)) AS [Total M.N.],
        CAST(NULL AS numeric(20,2)) AS [Invent. Disponible],
        CAST(NULL AS numeric(7,2)) AS [% Invent. Dispon.],
        c.tasa_exito_cierre AS [tasa_exito_cierre],
        CAST(NULL AS date) AS [fec_Estim_Cierre],
        COALESCE(CONVERT(varchar(20), c.ID_Status_Oferta), '-Ninguno-') AS [Status_Oferta],
        CASE WHEN c.numpedgen = 1 THEN 'SI' ELSE '-' END AS [Generó O/V],
        c.txtobsadi AS [Comentario],
        CONVERT(varchar(20), c.codidtusr) AS [Usuario]
    INTO #CotizacionesMantra
    FROM dbo.CotizacionesC AS c
    CROSS APPLY (VALUES (
        NULLIF(LTRIM(RTRIM(c.txtserdoc)), ''),
        NULLIF(LTRIM(RTRIM(c.txtnrodoc)), ''),
        NULLIF(LTRIM(RTRIM(c.txtnrorev)), '')
    )) AS doc(serie, numero, revision)
    WHERE (@FechaDesde IS NULL OR c.fecemidoc >= @FechaDesde)
      AND (@FechaHasta IS NULL OR c.fecemidoc < DATEADD(day, 1, @FechaHasta))
      AND (@Codidtcot IS NULL OR c.codidtcot = @Codidtcot);

    IF @ComoJson = 1
        SELECT COALESCE((
            SELECT
                [N° Cotización] AS numero_cotizacion, -- nombre de propiedad JSON, no columna SQL
                [Fecha] AS fecha,
                [Cliente] AS cliente,
                [Condicion de venta] AS condicion_venta,
                [Vendedor] AS vendedor,
                [Fuente de contacto] AS fuente_contacto,
                [Referencia] AS referencia,
                [Nombre del contacto] AS nombre_contacto,
                [Cargo] AS cargo,
                [Area] AS area,
                [Telefono] AS telefono,
                [email] AS email,
                [Moneda] AS moneda,
                [Total Docum.] AS total_documento,
                [Total M.N.] AS total_moneda_nacional,
                [Invent. Disponible] AS inventario_disponible,
                [% Invent. Dispon.] AS porcentaje_inventario_disponible,
                [tasa_exito_cierre] AS tasa_exito_cierre,
                [fec_Estim_Cierre] AS fecha_estimada_cierre,
                [Status_Oferta] AS estado_oferta,
                [Generó O/V] AS genero_orden_venta,
                [Comentario] AS comentario,
                [Usuario] AS usuario
            FROM #CotizacionesMantra
            ORDER BY [Fecha], [N° Cotización]
            FOR JSON PATH, INCLUDE_NULL_VALUES
        ), N'[]') AS payload_json;
    ELSE
        SELECT * FROM #CotizacionesMantra
        ORDER BY [Fecha], [N° Cotización];
END;
GO

-- Ejemplos:
-- EXEC dbo.usp_ExportarCotizacionesMantra @FechaDesde='2026-02-02', @FechaHasta='2026-02-02';
-- EXEC dbo.usp_ExportarCotizacionesMantra @Codidtcot='COD_INTERNO', @ComoJson=1;
