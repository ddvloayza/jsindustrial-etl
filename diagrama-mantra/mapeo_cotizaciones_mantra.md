# Mapeo de cotizaciones para Mantra

El procedimiento `dbo.JS_usp_ExportarCotizacionesMantra` reproduce las 23 columnas del Excel de ejemplo. La base disponible contiene `dbo.CotizacionesC` y `dbo.CotizacionesD`; las 23 columnas corresponden a la cabecera, por lo que el SP devuelve una fila por cotización. **`numero_cotizacion` no es una columna de la BD:** es una propiedad del JSON calculada para representar `N° Cotización` del Excel.

El SP sigue devolviendo las 23 propiedades de origen en JSON. La configuración activa envía a Mantra solo los ocho campos de la captura: seis campos personalizados (`custom_1`, `custom_2`, `custom_3`, `custom_5`, `custom_7`, `custom_13`) y nombre y teléfono estándar. El correo y las demás propiedades no se envían al API. El mapeo activo está en `../mantra_integracion/README.md`.

**Auditoría contra el backup:** las 21 columnas de `dbo.CotizacionesC` que referencia el SQL existen en el catálogo restaurado (64 columnas en esta tabla). De las 23 columnas de salida, 16 se basan en un campo existente, 2 son calculadas (`N° Cotización` y `Total M.N.`) y 5 no tienen origen verificable y salen `NULL` (`Cargo`, `Area`, `Invent. Disponible`, `% Invent. Dispon.`, `fec_Estim_Cierre`). La existencia de una columna no confirma todavía que su significado coincida con el Excel; las equivalencias por validar están indicadas abajo.

| Columna del Excel | Origen en SQL Server | Estado |
|---|---|---|
| N° Cotización (`numero_cotizacion` en JSON) | `txtserdoc` + `txtnrodoc` + `txtnrorev`; respaldo `codidtcot` | Campo calculado; formato por validar con datos reales |
| Fecha | `fecemidoc` | Directo |
| Cliente | `txtrazsoc` | Directo |
| Condicion de venta | `codfmapag` | Código; falta catálogo para descripción |
| Vendedor | `codmtrven` | El SP devuelve código; el emisor lo convierte a nombre mediante `mantra_integracion/vendedores.json` |
| Fuente de contacto | `ID_Canal_Origen` | ID; falta catálogo para descripción |
| Referencia | `txtrefcot` | Directo |
| Nombre del contacto | `txtnomatt` | Directo |
| Cargo | Sin campo equivalente | `NULL` |
| Area | Sin campo equivalente | `NULL` |
| Telefono | `txttlf001` mediante `dbo.fn_NormalizarTelefonoMantra` | Nueve dígitos peruanos; quita `+51` y separadores; teléfonos inválidos quedan fuera |
| email | `txtcorele` | Directo |
| Moneda | `codtipmon` | Conversión conocida USD/DOL→US$, PEN/SOL→S/; otros códigos sin transformar |
| Total Docum. | `numtotdoc` | Directo |
| Total M.N. | `numtotdoc × numtipcam` o `numtotdoc` para soles | Cálculo por validar con datos reales |
| Invent. Disponible | Sin campo equivalente | `NULL`; también vacío en las 24 filas de ejemplo |
| % Invent. Dispon. | Sin campo equivalente | `NULL`; también vacío en las 24 filas de ejemplo |
| tasa_exito_cierre | `tasa_exito_cierre` | Directo |
| fec_Estim_Cierre | Sin campo equivalente | `NULL`; `Fec_Cierre_Exito` indica cierre exitoso y no se usó como fecha estimada |
| Status_Oferta | `ID_Status_Oferta` | ID; falta catálogo para descripción. Sin ID, `-Ninguno-` como en el ejemplo |
| Generó O/V (`genero_orden_venta`) | `numpedgen` (`bit`) | `1`: cotización completada, se excluye de Mantra; `0`: puede exportarse y aparece como `-` en `custom_13` |
| Comentario | `txtobsadi` | Equivalencia probable; validar |
| Usuario | `codidtusr` | ID; falta catálogo para nombre |

## Antes del envío al API

1. Revisar con el cliente las etiquetas de los seis `custom_*` activos y si Mantra permite cambiarlas.
2. Proporcionar los catálogos de forma de pago, canal de origen, estado de oferta y usuario para exportar descripciones en vez de códigos. El catálogo de vendedores ya está en `mantra_integracion/vendedores.json`.
3. Verificar con una cotización real la composición de `N° Cotización`, la moneda, `Total M.N.` y `Comentario`.
4. Mantener la API key y el group ID en el integrador, fuera del procedimiento y del repositorio.

Uso: `EXEC dbo.JS_usp_ExportarCotizacionesMantra @ComoJson=1;` devuelve los contactos pendientes en `payload_json` y sus identificadores en `ids_json`. La cotización más reciente de cada teléfono debe ser posterior o igual al 1 de octubre de 2026, tener más de dos días completos y no haber generado orden de venta (`numpedgen = 0`). Si su ID ya coincide con el último registrado en `dbo.JS_MantraExportaciones`, no se reenvía. El servidor `SRV-02` genera el JSON, envía contactos al API y confirma los HTTP 200/201 mediante `dbo.JS_usp_ConfirmarExportacionMantra`.
