# JS Industrial → Mantra ETL

Piloto para seleccionar cotizaciones en SQL Server y crear o actualizar sus contactos en Mantra. Incluye el esquema extraído del backup, el procedimiento almacenado y el integrador Python. **Este alcance no envía mensajes ni plantillas.**

## Flujo técnico

![Flujo técnico de la propuesta: tarea programada, SQL Server, script Python, Mantra API y archivo TXT diario](docs/flujo-mantra.png)

Imagen original extraída de la página 2 de la propuesta. Allí figura un envío de plantilla, que quedó fuera del alcance actual; la implementación termina al crear o actualizar el contacto. La hora de las 5:00 p. m. es ilustrativa.

## Carpetas

- [`diagrama-mantra/`](diagrama-mantra/): diagrama editable de entidades, esquema JSON, auditoría de campos y `usp_ExportarCotizacionesMantra.sql`.
- [`mantra_integracion/`](mantra_integracion/): script Python, configuración de ejemplo, pruebas, lanzador y registro de tarea diaria para Windows. Lee [su instructivo](mantra_integracion/README.md) antes de desplegar.

## Estado

Una versión anterior del SP se compiló contra una restauración temporal del backup y se probó con una fila que luego se revirtió. La versión actual devuelve un arreglo JSON con veinte campos personalizados más nombre, teléfono y correo por cotización. El integrador lee ese JSON directamente del SP o desde [`contactos_prueba.json`](mantra_integracion/contactos_prueba.json) para una simulación sin SQL Server. Se creó un contacto de prueba autorizado en Mantra (HTTP 201) y una prueba posterior confirmó que el API guarda `custom_11` y `custom_20`. El SP actual aún no se ha ejecutado en el servidor del cliente.

Faltan la regla definitiva de selección, equivalencias de códigos y una prueba de extremo a extremo desde SQL Server con datos autorizados. Las 23 columnas de la muestra caben en 20 campos personalizados más nombre, teléfono y correo. Cinco campos sin origen verificado salen `null` del SP y se omiten al llamar al API. El mapeo completo está en la [tabla de campos](mantra_integracion/mapeo_campos_mantra.csv) y en el [instructivo](mantra_integracion/README.md). Las credenciales de Mantra se guardan solo en el `.env` local, que Git ignora.

Los archivos fuente con datos de clientes, backup, credenciales y logs operativos no se versionan.
