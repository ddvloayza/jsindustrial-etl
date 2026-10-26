# Mapeo de cotizaciones para Mantra

El procedimiento `dbo.usp_ExportarCotizacionesMantra` reproduce las 23 columnas del Excel de ejemplo. La base disponible contiene `dbo.CotizacionesC` y `dbo.CotizacionesD`; las 23 columnas corresponden a la cabecera, por lo que el SP devuelve una fila por cotización. **`numero_cotizacion` no es una columna de la BD:** es una propiedad del JSON calculada para representar `N° Cotización` del Excel.

El JSON distribuye veinte columnas entre `custom_1` y `custom_20` de Mantra. Las otras tres (`Nombre del contacto`, `Telefono`, `email`) se usan como nombre, teléfono y correo estándar. El mapeo numerado está en `../mantra_integracion/README.md`. Ninguna columna queda fuera por el límite de campos personalizados.

**Auditoría contra el backup:** las 21 columnas de `dbo.CotizacionesC` que referencia el SQL existen en el catálogo restaurado (64 columnas en esta tabla). De las 23 columnas de salida, 16 se basan en un campo existente, 2 son calculadas (`N° Cotización` y `Total M.N.`) y 5 no tienen origen verificable y salen `NULL` (`Cargo`, `Area`, `Invent. Disponible`, `% Invent. Dispon.`, `fec_Estim_Cierre`). La existencia de una columna no confirma todavía que su significado coincida con el Excel; las equivalencias por validar están indicadas abajo.

| Columna del Excel | Origen en SQL Server | Estado |
|---|---|---|
| N° Cotización (`numero_cotizacion` en JSON) | `txtserdoc` + `txtnrodoc` + `txtnrorev`; respaldo `codidtcot` | Campo calculado; formato por validar con datos reales |
| Fecha | `fecemidoc` | Directo |
| Cliente | `txtrazsoc` | Directo |
| Condicion de venta | `codfmapag` | Código; falta catálogo para descripción |
| Vendedor | `codmtrven` | Código; falta catálogo para nombre |
| Fuente de contacto | `ID_Canal_Origen` | ID; falta catálogo para descripción |
| Referencia | `txtrefcot` | Directo |
| Nombre del contacto | `txtnomatt` | Directo |
| Cargo | Sin campo equivalente | `NULL` |
| Area | Sin campo equivalente | `NULL` |
| Telefono | `txttlf001` | Directo |
| email | `txtcorele` | Directo |
| Moneda | `codtipmon` | Conversión conocida USD/DOL→US$, PEN/SOL→S/; otros códigos sin transformar |
| Total Docum. | `numtotdoc` | Directo |
| Total M.N. | `numtotdoc × numtipcam` o `numtotdoc` para soles | Cálculo por validar con datos reales |
| Invent. Disponible | Sin campo equivalente | `NULL`; también vacío en las 24 filas de ejemplo |
| % Invent. Dispon. | Sin campo equivalente | `NULL`; también vacío en las 24 filas de ejemplo |
| tasa_exito_cierre | `tasa_exito_cierre` | Directo |
| fec_Estim_Cierre | Sin campo equivalente | `NULL`; `Fec_Cierre_Exito` indica cierre exitoso y no se usó como fecha estimada |
| Status_Oferta | `ID_Status_Oferta` | ID; falta catálogo para descripción. Sin ID, `-Ninguno-` como en el ejemplo |
| Generó O/V | `numpedgen` | `1`→`SI`; otros valores→`-` |
| Comentario | `txtobsadi` | Equivalencia probable; validar |
| Usuario | `codidtusr` | ID; falta catálogo para nombre |

## Antes del envío al API

1. Revisar con el cliente el mapeo de `custom_1` a `custom_20` y si Mantra permite mostrar etiquetas personalizadas.
2. Proporcionar los catálogos de forma de pago, vendedor, canal de origen, estado de oferta y usuario para exportar descripciones en vez de códigos.
3. Verificar con una cotización real la composición de `N° Cotización`, la moneda, `Total M.N.` y `Comentario`.
4. Mantener la API key y el group ID en el integrador, fuera del procedimiento y del repositorio.

Uso: `EXEC dbo.usp_ExportarCotizacionesMantra @FechaDesde='2026-02-02', @FechaHasta='2026-02-02', @ComoJson=1;` devuelve un arreglo JSON en `payload_json`.
