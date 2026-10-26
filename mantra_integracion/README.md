# Integración piloto SQL Server → Mantra

![Flujo técnico de la propuesta](../docs/flujo-mantra.png)

## Flujo implementado

1. El Programador de tareas de Windows ejecuta `run_mantra.ps1` una vez al día.
2. Python llama `dbo.usp_ExportarCotizacionesMantra` para la fecha anterior (zona horaria de Lima).
3. Valida nombre y teléfono. Para Perú acepta nueve dígitos que empiecen en 9, con o sin prefijo 51, y envía `countryCode="51"` separado del teléfono.
4. Envía `POST https://wbpback.mantra.chat/contacts/new` con `groupId`, `apiKey`, `data.name`, `data.phone`, `data.countryCode`, correo opcional y hasta diez `custom_*`.
5. Si Mantra responde 200 o 201, envía `POST https://wbpback.mantra.chat/contacts/send` con `templateId`, teléfono y código de país. Se puede omitir este paso con `--contacts-only`.
6. Escribe un TXT diario `mantra_AAAAMMDD.txt` con registros JSON por línea: hora, identificador de cotización, etapa, HTTP y resultado. No incluye credenciales ni teléfono/correo.
7. Antes de enviar una plantilla revisa los TXT previos para evitar repetir un envío confirmado o incierto. Una respuesta perdida o un HTTP 5xx en `/contacts/send` queda marcada `INCIERTO` para revisión manual: no hay reintento automático que pueda duplicar el mensaje.

La documentación del API solo ofrece nombre, teléfono, correo y diez campos `custom_1` a `custom_10`. El SP devuelve las 23 columnas del Excel, pero la configuración prioriza diez para Mantra. Nombre, teléfono y correo se envían en sus campos propios. El mapeo de `custom_*` se puede cambiar en `config.json` sin modificar código. Los valores de vendedor, condición de venta, fuente y estado siguen siendo códigos/IDs hasta contar con sus catálogos.

## Preparación en Windows

1. Instalar Python 3.10+ y `pip install -r requirements.txt`.
2. Ejecutar el SQL de `../diagrama-mantra/usp_ExportarCotizacionesMantra.sql` en la base real.
3. Copiar `config.example.json` a `config.json` y definir servidor, base y carpeta de logs. El usuario que ejecute la tarea necesita lectura de `dbo.CotizacionesC` y permiso `EXECUTE` sobre el SP.
4. Configurar las variables de entorno **para la cuenta que ejecutará la tarea**: `MANTRA_SQL_USER`, `MANTRA_SQL_PASSWORD`, `MANTRA_GROUP_ID`, `MANTRA_API_KEY` y `MANTRA_TEMPLATE_ID`. No guardar secretos en `config.json`, el repositorio o el TXT.
5. Probar una fecha sin enviar: `python exportar_contactos.py --config config.json --fecha 2026-02-02`. Revisar el TXT y el conteo. Para enviar contactos solamente: `python exportar_contactos.py --config config.json --fecha 2026-02-02 --send --contacts-only`.
6. Tras confirmar el mapeo, regla y plantilla, ejecutar una prueba autorizada con `--send` y una fecha que seleccione un lead de prueba. Revisar respuesta 200/201 de contacto y 201 de plantilla en el TXT.
7. Registrar el horario acordado: `powershell -File .\registrar_tarea.ps1 -Hora "07:00"`. La tarea ejecuta la fecha anterior por defecto.

## Definiciones pendientes antes de producción

- Confirmar la regla de selección diaria. La implementación actual selecciona `fecemidoc` del día anterior; la propuesta deja esta regla por acordar. Puede haber cotizaciones sin `fecemidoc` o modificaciones posteriores que la regla no capture.
- Confirmar el `templateId`, la plantilla aprobada y qué representan sus variables frente a los diez `custom_*` elegidos.
- Validar con una fila real los campos calculados `N° Cotización`, moneda y total en moneda nacional.
- Confirmar que `txttlf001` contiene números WhatsApp de clientes y que se cuenta con autorización para la comunicación. No se envían registros con teléfono inválido.
- Definir equivalencias de los códigos de vendedor, condición de venta, fuente y estado si Mantra necesita sus descripciones.
- Mantener y respaldar la carpeta de TXT: el control de duplicados depende de su conservación. Una respuesta `INCIERTO` requiere verificación en Mantra antes de reejecutar.

No se ha hecho una prueba real contra Mantra ni se ha instalado una tarea en el servidor del cliente; faltan credenciales, plantilla aprobada, datos autorizados y acceso al servidor.
