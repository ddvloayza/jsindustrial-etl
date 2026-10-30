/*
  Exportación de contactos basada en "Cotizaciones Generales Prueba.xlsx".
  Fuente disponible: dbo.CotizacionesC del backup BD_MANTRA.bak.
  Los campos que requieren catálogos externos devuelven su código/ID
  provisional (ver mapeo_cotizaciones_mantra.md).
  Selecciona contactos con una cotización de más de dos días completos,
  sin orden de venta generada y sin envío exitoso registrado para el teléfono.
  El integrador confirma cada éxito mediante usp_ConfirmarExportacionMantra.
*/
IF OBJECT_ID(N'dbo.MantraExportaciones', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.MantraExportaciones (
        telefono char(9) NOT NULL PRIMARY KEY,
        codidtcot char(10) NOT NULL,
        fecha_envio datetime2(0) NOT NULL
            CONSTRAINT DF_MantraExportaciones_fecha_envio DEFAULT SYSDATETIME(),
        http_status smallint NOT NULL
    );
END;
GO

CREATE OR ALTER FUNCTION dbo.fn_NormalizarTelefonoMantra(@Texto varchar(20))
RETURNS varchar(9)
AS
BEGIN
    DECLARE @Digitos varchar(20) = ISNULL(@Texto, '');
    WHILE PATINDEX('%[^0-9]%', @Digitos) > 0
        SET @Digitos = STUFF(@Digitos, PATINDEX('%[^0-9]%', @Digitos), 1, '');
    IF LEN(@Digitos) = 11 AND LEFT(@Digitos, 2) = '51'
        SET @Digitos = RIGHT(@Digitos, 9);
    IF LEN(@Digitos) = 9 AND LEFT(@Digitos, 1) = '9'
        RETURN @Digitos;
    RETURN NULL;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_ExportarCotizacionesMantra
    @FechaDesde date = NULL,
    @FechaHasta date = NULL,
    @Codidtcot char(10) = NULL,
    @ComoJson bit = 1,
    @FechaProceso date = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SET @FechaProceso = COALESCE(@FechaProceso, CONVERT(date, SYSDATETIME()));

    IF @FechaDesde IS NOT NULL AND @FechaHasta IS NOT NULL AND @FechaDesde > @FechaHasta
        THROW 50001, 'FechaDesde no puede ser mayor que FechaHasta.', 1;

    SELECT
        c.codidtcot AS id_interno,
        tel.normalizado AS telefono_normalizado,
        ROW_NUMBER() OVER (
            PARTITION BY tel.normalizado
            ORDER BY c.fecemidoc DESC, c.codidtcot DESC
        ) AS fila_telefono,
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
    CROSS APPLY (VALUES (dbo.fn_NormalizarTelefonoMantra(c.txttlf001))) AS tel(normalizado)
    WHERE (@FechaDesde IS NULL OR c.fecemidoc >= @FechaDesde)
      AND (@FechaHasta IS NULL OR c.fecemidoc < DATEADD(day, 1, @FechaHasta))
      AND (@Codidtcot IS NULL OR c.codidtcot = @Codidtcot)
      -- Más de dos días completos: el día D procesa fechas anteriores a D-2.
      AND c.fecemidoc < DATEADD(day, -2, @FechaProceso)
      -- numpedgen es bit: 1 indica que ya se generó la orden de venta.
      AND c.numpedgen = 0
      AND tel.normalizado IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM dbo.MantraExportaciones AS e
          WHERE e.telefono = tel.normalizado
      );

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
                [Moneda] AS moneda,
                [Total Docum.] AS total_documento,
                [Status_Oferta] AS estado_oferta,
                [Total M.N.] AS total_moneda_nacional,
                [tasa_exito_cierre] AS tasa_exito_cierre,
                [Generó O/V] AS genero_orden_venta,
                [Comentario] AS comentario,
                [Usuario] AS usuario,
                [Cargo] AS cargo,
                [Area] AS area,
                [Invent. Disponible] AS inventario_disponible,
                [% Invent. Dispon.] AS porcentaje_inventario_disponible,
                [fec_Estim_Cierre] AS fecha_estimada_cierre,
                [Nombre del contacto] AS nombre_contacto,
                [Telefono] AS telefono,
                [email] AS email
            FROM #CotizacionesMantra
            WHERE fila_telefono = 1
            ORDER BY [Fecha], [N° Cotización], id_interno
            FOR JSON PATH, INCLUDE_NULL_VALUES
        ), N'[]') AS payload_json,
        -- IDs internos en el mismo orden para confirmar cada envío exitoso.
        -- No forman parte de los 23 campos del contacto ni se envían al API.
        COALESCE((
            SELECT id_interno AS codidtcot, telefono_normalizado AS telefono
            FROM #CotizacionesMantra
            WHERE fila_telefono = 1
            ORDER BY [Fecha], [N° Cotización], id_interno
            FOR JSON PATH
        ), N'[]') AS ids_json;
    ELSE
        SELECT * FROM #CotizacionesMantra
        WHERE fila_telefono = 1
        ORDER BY [Fecha], [N° Cotización];
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_ConfirmarExportacionMantra
    @Codidtcot char(10),
    @Telefono char(9),
    @HttpStatus smallint
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @HttpStatus NOT IN (200, 201)
        THROW 50002, 'Solo se confirma un envio aceptado por Mantra.', 1;
    IF LEN(@Telefono) <> 9 OR LEFT(@Telefono, 1) <> '9' OR @Telefono LIKE '%[^0-9]%'
        THROW 50003, 'Telefono invalido para confirmar exportacion.', 1;

    BEGIN TRANSACTION;
    IF NOT EXISTS (
        SELECT 1 FROM dbo.MantraExportaciones WITH (UPDLOCK, HOLDLOCK)
        WHERE telefono = @Telefono
    )
        INSERT dbo.MantraExportaciones (telefono, codidtcot, http_status)
        VALUES (@Telefono, @Codidtcot, @HttpStatus);
    COMMIT TRANSACTION;
END;
GO

-- Ejemplos:
-- EXEC dbo.usp_ExportarCotizacionesMantra @FechaProceso='2026-10-30';
-- EXEC dbo.usp_ExportarCotizacionesMantra @Codidtcot='COD_INTERNO';
-- Para ver los mismos campos como tabla: EXEC dbo.usp_ExportarCotizacionesMantra @ComoJson=0;
