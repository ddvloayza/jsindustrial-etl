# Integración piloto SQL Server → Mantra

![Flujo técnico de la propuesta](../docs/flujo-mantra.png)

La imagen refleja la propuesta original. **El alcance actual termina en crear o actualizar contactos; no se envían plantillas ni mensajes.**

## Flujo implementado

1. El Programador de tareas de Windows ejecuta `run_mantra.ps1` una vez al día.
2. Python llama `dbo.usp_ExportarCotizacionesMantra` para la fecha anterior (zona horaria de Lima).
3. Valida nombre y teléfono. Para Perú acepta nueve dígitos que empiecen en 9, con o sin prefijo 51, y envía `countryCode="51"` separado del teléfono.
4. Envía `POST https://wbpback.mantra.chat/contacts/new` con `groupId`, `apiKey`, `data.name`, `data.phone`, `data.countryCode`, correo opcional y hasta diez `custom_*`.
5. Escribe un TXT diario `mantra_AAAAMMDD.txt` con registros JSON por línea: hora, identificador de cotización, etapa, HTTP y resultado. No incluye credenciales ni teléfono/correo. Si se vuelve a procesar un contacto, Mantra lo actualiza por número telefónico.

La documentación del API solo ofrece nombre, teléfono, correo y diez campos `custom_1` a `custom_10`. El SP devuelve las 23 columnas del Excel, pero la configuración prioriza diez para Mantra. Nombre, teléfono y correo se envían en sus campos propios. El mapeo de `custom_*` se puede cambiar en `config.json` sin modificar código. Los valores de vendedor, condición de venta, fuente y estado siguen siendo códigos/IDs hasta contar con sus catálogos.

## Preparación en Windows

1. Instalar Python 3.10+ y `pip install -r requirements.txt`.
2. Ejecutar el SQL de `../diagrama-mantra/usp_ExportarCotizacionesMantra.sql` en la base real.
3. Copiar `config.example.json` a `config.json` y definir servidor, base y carpeta de logs. El usuario que ejecute la tarea necesita lectura de `dbo.CotizacionesC` y permiso `EXECUTE` sobre el SP.
4. Configurar las variables de entorno **para la cuenta que ejecutará la tarea**: `MANTRA_SQL_USER`, `MANTRA_SQL_PASSWORD`, `MANTRA_GROUP_ID` y `MANTRA_API_KEY`. No guardar secretos en `config.json`, el repositorio o el TXT.
5. Probar una fecha sin modificar Mantra: `python exportar_contactos.py --config config.json --fecha 2026-02-02`. Revisar el TXT y el conteo.
6. Tras confirmar el mapeo y la regla, ejecutar una prueba autorizada con `python exportar_contactos.py --config config.json --fecha 2026-02-02 --apply`. Revisar la respuesta 200/201 del contacto en el TXT.
7. Registrar el horario acordado: `powershell -File .\registrar_tarea.ps1 -Hora "07:00"`. La tarea ejecuta la fecha anterior por defecto.

## Prueba de acceso a Mantra sin SQL Server

Configura `MANTRA_GROUP_ID` y `MANTRA_API_KEY` en el entorno de la cuenta que ejecuta Python. Usa un número de prueba autorizado; el script nunca imprime los secretos ni el contenido del contacto consultado.

En Windows puedes usar `powershell -File .\probar_mantra.ps1 -Phone 987654321`. Si faltan las variables, este lanzador solicita el group ID y la API key sin escribirlos en el comando ni guardarlos en el repositorio. Sin `-Name` hace solo la consulta de credenciales; con `-Name "Prueba JS Industrial"` crea o actualiza el contacto de prueba.

1. Solo lectura, valida las credenciales sin modificar contactos: `python probar_mantra.py --phone 987654321`. Un HTTP 200 o 404 indica que Mantra aceptó las credenciales para `/contacts/byphone`.
2. Crear o actualizar el contacto de prueba: `python probar_mantra.py --phone 987654321 --name "Prueba JS Industrial"`.

El paso 2 escribe en Mantra, pero no envía ningún WhatsApp.

## Definiciones pendientes antes de producción

- Confirmar la regla de selección diaria. La implementación actual selecciona `fecemidoc` del día anterior; la propuesta deja esta regla por acordar. Puede haber cotizaciones sin `fecemidoc` o modificaciones posteriores que la regla no capture.
- Confirmar qué representan los diez `custom_*` elegidos para el contacto.
- Validar con una fila real los campos calculados `N° Cotización`, moneda y total en moneda nacional.
- Confirmar que `txttlf001` contiene teléfonos correctos de clientes. No se exportan registros con teléfono inválido.
- Definir equivalencias de los códigos de vendedor, condición de venta, fuente y estado si Mantra necesita sus descripciones.
- Mantener y respaldar la carpeta de TXT para revisar resultados y errores de cada ejecución.

No se ha hecho una prueba real contra Mantra ni se ha instalado una tarea en el servidor del cliente; faltan credenciales, datos autorizados y acceso al servidor.
