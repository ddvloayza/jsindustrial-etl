# JS Industrial → Mantra ETL

Piloto para seleccionar cotizaciones en SQL Server y crear o actualizar sus contactos en Mantra. Incluye el esquema extraído del backup, el procedimiento almacenado y el integrador Python. **Este alcance no envía mensajes ni plantillas.**

## Flujo técnico

![Flujo técnico de la propuesta: tarea programada, SQL Server, script Python, Mantra API y archivo TXT diario](docs/flujo-mantra.png)

Imagen original extraída de la página 2 de la propuesta. Allí figura un envío de plantilla, que quedó fuera del alcance actual; la implementación termina al crear o actualizar el contacto. La hora de las 5:00 p. m. es ilustrativa.

## Carpetas

- [`diagrama-mantra/`](diagrama-mantra/): diagrama editable de entidades, esquema JSON, auditoría de campos y `usp_ExportarCotizacionesMantra.sql`.
- [`mantra_integracion/`](mantra_integracion/): script Python, configuración de ejemplo, pruebas, lanzador y registro de tarea diaria para Windows. Lee [su instructivo](mantra_integracion/README.md) antes de desplegar.

## Estado

Una versión anterior del SP se compiló contra una restauración temporal del backup y se probó con una fila que luego se revirtió. La versión actual devuelve un arreglo JSON con los diez campos elegidos para Mantra más nombre, teléfono y correo por cotización. El integrador lee ese JSON directamente del SP o desde [`contactos_prueba.json`](mantra_integracion/contactos_prueba.json) para una simulación sin SQL Server. Pasó pruebas locales con llamadas HTTP simuladas. No se ha ejecutado en el servidor del cliente ni se han enviado contactos reales a Mantra.

Faltan la regla definitiva de selección, equivalencias de códigos, `groupId`, `apiKey` y una prueba de extremo a extremo con datos autorizados. El API documentado solo admite diez campos personalizados por contacto; el SP selecciona esos diez en su JSON.

Los archivos fuente con datos de clientes, backup, credenciales y logs operativos no se versionan.
