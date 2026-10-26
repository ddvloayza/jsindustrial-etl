# Integración piloto SQL Server → Mantra

![Flujo técnico de la propuesta](../docs/flujo-mantra.png)

La imagen refleja la propuesta original. **El alcance actual termina en crear o actualizar contactos; no se envían plantillas ni mensajes.**

## Flujo implementado

1. El Programador de tareas de Windows ejecuta `run_mantra.ps1` una vez al día.
2. Python llama `dbo.usp_ExportarCotizacionesMantra` para la fecha anterior (zona horaria de Lima). El SP devuelve una fila `payload_json` con un arreglo de cotizaciones; Python lee y valida los diez campos elegidos y los tres datos de contacto de cada elemento.
3. Valida nombre y teléfono. Para Perú acepta nueve dígitos que empiecen en 9, con o sin prefijo 51, y envía `countryCode="51"` separado del teléfono.
4. Envía `POST https://wbpback.mantra.chat/contacts/new` con `groupId`, `apiKey`, `data.name`, `data.phone`, `data.countryCode`, correo opcional y hasta diez `custom_*`.
5. Escribe un TXT diario `mantra_AAAAMMDD.txt` con registros JSON por línea: hora, identificador de cotización, etapa, HTTP y resultado. No incluye credenciales ni teléfono/correo. Si se vuelve a procesar un contacto, Mantra lo actualiza por número telefónico.

La documentación del API solo ofrece nombre, teléfono, correo y diez campos `custom_1` a `custom_10`. Por eso, cada objeto del JSON contiene solo los diez campos elegidos (`numero_cotizacion`, `fecha`, `cliente`, `condicion_venta`, `vendedor`, `fuente_contacto`, `referencia`, `moneda`, `total_documento`, `estado_oferta`) más `nombre_contacto`, `telefono` y `email`. El archivo `config.json` indica a qué `custom_*` corresponde cada uno de los diez. Si cambia la selección, hay que actualizar tanto el SP como la configuración. Los valores de vendedor, condición de venta, fuente y estado siguen siendo códigos/IDs hasta contar con sus catálogos. Cada objeto del JSON representa una cotización candidata a contacto; si dos cotizaciones tienen el mismo teléfono, ambas se procesan y Mantra puede actualizar el mismo contacto.

## Probar con el JSON ficticio

Primero copia `.env.example` a `.env` si todavía no existe. Git ignora el `.env` local. Para una simulación no necesitas completar credenciales. Desde `mantra_integracion/`, ejecuta:

```bash
python exportar_contactos.py --config config.example.json --json-file contactos_prueba.json --log-dir ./logs
```

En Windows el comando es el mismo, usando `py` si así está instalado Python. Este modo no requiere SQL Server, `groupId` ni API key; valida los tres objetos de ejemplo y escribe el resultado en `./logs`. No llama a Mantra. El script rechaza `--apply` cuando se usa directamente el archivo `contactos_prueba.json` incluido en el repositorio.

Para un JSON generado desde SQL Server, el SP se puede ejecutar con `EXEC dbo.usp_ExportarCotizacionesMantra @FechaDesde='2026-02-02', @FechaHasta='2026-02-02';`. Copia el contenido de `payload_json` a un archivo UTF-8 si quieres probarlo con `--json-file`. En la ejecución diaria, Python obtiene ese mismo JSON directamente del SP, sin archivo intermedio. Un archivo con datos reales se puede enviar con `--apply` cuando estén configuradas las credenciales y se haya revisado el contenido.

## Variables de `.env`

Edita `mantra_integracion/.env` con un editor de texto. Python lo lee automáticamente al ejecutar cualquiera de los dos scripts; las variables existentes en el sistema tienen prioridad. Git ignora el archivo para que las credenciales no se publiquen.

| Variable | Cuándo se necesita | Valor |
| --- | --- | --- |
| `MANTRA_GROUP_ID` | Consulta o creación de contactos | ID del grupo en Mantra |
| `MANTRA_API_KEY` | Consulta o creación de contactos | API key de ese grupo |
| `MANTRA_SQL_USER` | Solo cuando Python lee el SP directamente | Usuario de SQL Server |
| `MANTRA_SQL_PASSWORD` | Solo cuando Python lee el SP directamente | Contraseña de ese usuario |

Con `--json-file` solo completa las dos variables de Mantra. El servidor y la base SQL se configuran aparte en `config.json` cuando uses el SP. Nunca pongas estas credenciales en el JSON de contactos.

## Preparación en Windows

1. Instalar Python 3.10+ y `pip install -r requirements.txt`.
2. Ejecutar el SQL de `../diagrama-mantra/usp_ExportarCotizacionesMantra.sql` en la base real.
3. Copiar `config.example.json` a `config.json` y definir servidor, base y carpeta de logs. El usuario que ejecute la tarea necesita lectura de `dbo.CotizacionesC` y permiso `EXECUTE` sobre el SP.
4. Completar las cuatro variables de `.env` para la cuenta que ejecutará la tarea. No guardar secretos en `config.json`, el repositorio o el TXT.
5. Probar una fecha sin modificar Mantra: `python exportar_contactos.py --config config.json --fecha 2026-02-02`. Revisar el TXT y el conteo.
6. Tras confirmar el mapeo y la regla, ejecutar una prueba autorizada con `python exportar_contactos.py --config config.json --fecha 2026-02-02 --apply`. Revisar la respuesta 200/201 del contacto en el TXT.
7. Registrar el horario acordado: `powershell -File .\registrar_tarea.ps1 -Hora "07:00"`. La tarea ejecuta la fecha anterior por defecto.

## Prueba de acceso a Mantra sin SQL Server

Completa `MANTRA_GROUP_ID` y `MANTRA_API_KEY` en `.env`. Usa un número de prueba autorizado; el script nunca imprime los secretos ni el contenido del contacto consultado.

En Windows puedes usar `powershell -File .\probar_mantra.ps1 -Phone 987654321`. El script Python lee `.env` automáticamente. Sin `-Name` hace solo la consulta de credenciales; con `-Name "Prueba JS Industrial"` crea o actualiza el contacto de prueba.

1. Solo lectura, valida las credenciales sin modificar contactos: `python probar_mantra.py --phone 987654321`. Un HTTP 200 o 404 indica que Mantra aceptó las credenciales para `/contacts/byphone`.
2. Crear o actualizar el contacto de prueba: `python probar_mantra.py --phone 987654321 --name "Prueba JS Industrial"`.

El paso 2 escribe en Mantra, pero no envía ningún WhatsApp.

## Definiciones pendientes antes de producción

- Confirmar la regla de selección diaria. La implementación actual selecciona `fecemidoc` del día anterior; la propuesta deja esta regla por acordar. Puede haber cotizaciones sin `fecemidoc` o modificaciones posteriores que la regla no capture.
- Confirmar qué representan los diez `custom_*` elegidos para el contacto.
- Validar con una fila real el número de cotización calculado, la moneda y el total del documento.
- Confirmar que `txttlf001` contiene teléfonos correctos de clientes. No se exportan registros con teléfono inválido.
- Definir equivalencias de los códigos de vendedor, condición de venta, fuente y estado si Mantra necesita sus descripciones.
- Mantener y respaldar la carpeta de TXT para revisar resultados y errores de cada ejecución.

No se ha hecho una prueba real contra Mantra ni se ha instalado una tarea en el servidor del cliente; faltan credenciales, datos autorizados y acceso al servidor.
