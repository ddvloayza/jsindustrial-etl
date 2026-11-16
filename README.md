# JS Industrial → Mantra ETL

Integración de cotizaciones de `JSIndustrial` con contactos de Mantra. **No envía mensajes ni plantillas.** La arquitectura actual usa dos servidores y transferencia de archivos en una sola dirección.

## Flujo

1. El servidor de BD ejecuta `dbo.JS_usp_ExportarCotizacionesMantra` y publica un archivo JSON en una carpeta compartida. Un job de SQL Server Agent puede llamar [`run_exportar_json.ps1`](mantra_integracion/run_exportar_json.ps1). Esta etapa no usa las credenciales de Mantra.
2. El servidor de envío **solo lee** la carpeta, copia el archivo localmente y llama al API mediante [`run_enviar_archivos.ps1`](mantra_integracion/run_enviar_archivos.ps1). Aquí se guardan `MANTRA_GROUP_ID` y `MANTRA_API_KEY`.
3. Los teléfonos aceptados por Mantra se registran en un archivo SQLite local del servidor de envío para omitirlos en lotes futuros. El servidor de BD no recibe resultados y puede generar otra vez el mismo teléfono; el segundo servidor lo descarta al leerlo.

![Flujo técnico de la propuesta original](docs/flujo-mantra.png)

La imagen pertenece a la propuesta inicial; el flujo operativo vigente y sus comandos están en el [runbook de dos servidores](mantra_integracion/runbook.md). El [mapeo activo de ocho campos](mantra_integracion/mapeo_campos_mantra.csv) conserva las posiciones `custom_*` ya usadas en Mantra. El SP mantiene 23 propiedades en el JSON de origen, pero solo ocho se envían al API.

## Carpetas

- [`diagrama-mantra/`](diagrama-mantra/): esquema, diagrama de entidades, auditoría de campos y SQL del SP.
- [`mantra_integracion/`](mantra_integracion/): exportador, emisor sin conexión SQL, scripts de programación, configuración de ejemplo y pruebas.

El backup, los JSON con contactos, las claves, los logs y el registro SQLite de éxitos no se versionan. En el modo de dos servidores, `dbo.JS_MantraExportaciones` conserva solo confirmaciones anteriores al cambio de arquitectura; los éxitos nuevos se registran en SQLite. Respaldar ese archivo es necesario para evitar reenvíos si se pierde el servidor de envío.
