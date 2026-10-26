# JS Industrial → Mantra ETL

Piloto para seleccionar cotizaciones en SQL Server, crear o actualizar sus contactos en Mantra y enviar una plantilla aprobada. Incluye el esquema extraído del backup, el procedimiento almacenado y el integrador Python.

## Flujo técnico

![Flujo técnico de la propuesta: tarea programada, SQL Server, script Python, Mantra API y archivo TXT diario](docs/flujo-mantra.png)

Imagen extraída de la página 2 de la propuesta. La hora de las 5:00 p. m. que aparece en ella es ilustrativa; el horario real se define al registrar la tarea.

## Carpetas

- [`diagrama-mantra/`](diagrama-mantra/): diagrama editable de entidades, esquema JSON, auditoría de campos y `usp_ExportarCotizacionesMantra.sql`.
- [`mantra_integracion/`](mantra_integracion/): script Python, configuración de ejemplo, pruebas, lanzador y registro de tarea diaria para Windows. Lee [su instructivo](mantra_integracion/README.md) antes de desplegar.

## Estado

El SP se compiló contra una restauración temporal del backup y se probó con una fila que luego se revirtió. El integrador pasó pruebas locales con llamadas HTTP simuladas. No se ha ejecutado en el servidor del cliente ni se han enviado contactos reales a Mantra.

Faltan la regla definitiva de selección, equivalencias de códigos, `templateId`, plantilla aprobada, credenciales y una prueba de extremo a extremo con datos autorizados. El API documentado solo admite diez campos personalizados por contacto; el SP conserva las 23 columnas de la muestra y `config.example.json` prioriza diez.

Los archivos fuente con datos de clientes, backup, credenciales y logs operativos no se versionan.
