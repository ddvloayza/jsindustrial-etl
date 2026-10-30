# Integración piloto SQL Server → Mantra

![Flujo técnico de la propuesta](../docs/flujo-mantra.png)

La imagen refleja la propuesta original. **El alcance actual termina en crear o actualizar contactos; no se envían plantillas ni mensajes.**

Para instalarlo en Windows con SQL Server Agent, sigue el [runbook paso a paso](runbook.md).

## Flujo implementado

1. SQL Server Agent ejecuta un job diario con un paso `CmdExec` que llama `run_mantra.ps1` y, desde allí, a Python. El [script de registro del job](registrar_job_sql_agent.sql) queda preparado para instalarlo en el servidor Windows. El antiguo `registrar_tarea.ps1` queda como alternativa; no se deben activar ambos programadores.
2. Python llama `dbo.usp_ExportarCotizacionesMantra` con la fecha actual de Lima. El SP considera todas las cotizaciones anteriores a esa fecha menos dos días completos, excluye las que ya generaron orden de venta (`numpedgen = 1`) y los teléfonos con envío exitoso en `dbo.MantraExportaciones`. Si hay varias cotizaciones pendientes para un teléfono, toma la más reciente. Devuelve `payload_json` con los 23 datos del contacto e `ids_json` con los identificadores internos para confirmar el envío.
3. Valida nombre y teléfono. Para Perú acepta nueve dígitos que empiecen en 9, con o sin prefijo 51, y envía `countryCode="51"` separado del teléfono.
4. Envía `POST https://wbpback.mantra.chat/contacts/new` con `groupId`, `apiKey`, `data.name`, `data.phone`, `data.countryCode`, correo opcional y hasta veinte `custom_*`.
5. Después de una respuesta HTTP 200/201, Python llama `dbo.usp_ConfirmarExportacionMantra` para registrar el teléfono como enviado. Escribe un TXT diario `mantra_AAAAMMDD.txt` con hora, identificador de cotización, etapa, HTTP y resultado; no incluye credenciales ni teléfono/correo. Un fallo del API o de validación no marca el teléfono y permite reintentar en la siguiente ejecución.

`genero_orden_venta` proviene del booleano `numpedgen`: `true` (`1`) significa que la cotización se completó y generó orden de venta, por lo que **no se envía a Mantra**. Solo se consideran cotizaciones con `false` (`0`); en `custom_13` ese valor aparece como `-`, siguiendo el formato del Excel. `ID_Status_Oferta` es otro campo, de tipo entero, y se exporta a `custom_10`. La marca de exportación se guarda por teléfono peruano normalizado, no por número de cotización. Una vez enviado el contacto, nuevas cotizaciones del mismo teléfono no se vuelven a exportar automáticamente.

El PDF entregado documenta `custom_1` a `custom_10`. La interfaz muestra 20 campos, y una prueba real confirmó que el API guarda `custom_11` y `custom_20`. El JSON incluye los veinte campos personalizados de la tabla siguiente, más `nombre_contacto`, `telefono` y `email`. Estos últimos se envían como `data.name`, `data.phone` y `data.email`; por tanto, las 23 columnas del Excel tienen una posición asignada en el JSON y en el mapeo del API. `countryCode` se añade desde la configuración. La [tabla CSV de mapeo](mapeo_campos_mantra.csv) agrega el origen SQL y el estado de cada campo y se puede abrir en Excel.

| Posición Mantra | Propiedad JSON | Columna del Excel |
| --- | --- | --- |
| `custom_1` | `numero_cotizacion` | N° Cotización |
| `custom_2` | `fecha` | Fecha |
| `custom_3` | `cliente` | Cliente |
| `custom_4` | `condicion_venta` | Condicion de venta |
| `custom_5` | `vendedor` | Vendedor |
| `custom_6` | `fuente_contacto` | Fuente de contacto |
| `custom_7` | `referencia` | Referencia |
| `custom_8` | `moneda` | Moneda |
| `custom_9` | `total_documento` | Total Docum. |
| `custom_10` | `estado_oferta` | Status_Oferta |
| `custom_11` | `total_moneda_nacional` | Total M.N. |
| `custom_12` | `tasa_exito_cierre` | tasa_exito_cierre |
| `custom_13` | `genero_orden_venta` | Generó O/V |
| `custom_14` | `comentario` | Comentario |
| `custom_15` | `usuario` | Usuario |
| `custom_16` | `cargo` | Cargo |
| `custom_17` | `area` | Area |
| `custom_18` | `inventario_disponible` | Invent. Disponible |
| `custom_19` | `porcentaje_inventario_disponible` | % Invent. Dispon. |
| `custom_20` | `fecha_estimada_cierre` | fec_Estim_Cierre |

**Sin valor verificable en el backup:** Cargo, Area, Invent. Disponible, % Invent. Dispon. y fec_Estim_Cierre. El SP los incluye como `null` en el JSON y Python no envía esos `custom_*` hasta que se defina su origen. Por ahora se envían como máximo 15 campos personalizados con valor, más nombre, teléfono y correo cuando corresponda. Los valores de vendedor, condición de venta, fuente y estado siguen siendo códigos/IDs hasta contar con sus catálogos. Si hay varias cotizaciones elegibles para el mismo teléfono, el SP entrega solo la más reciente.

## Probar con el JSON ficticio

Primero copia `.env.example` a `.env` si todavía no existe. Git ignora el `.env` local. Para una simulación no necesitas completar credenciales. Desde `mantra_integracion/`, ejecuta:

```bash
python exportar_contactos.py --config config.example.json --json-file contactos_prueba.json --log-dir ./logs
```

En Windows el comando es el mismo, usando `py` si así está instalado Python. Este modo no requiere SQL Server, `groupId` ni API key; valida los tres objetos de ejemplo y escribe el resultado en `./logs`. No llama a Mantra. El script rechaza `--apply` con cualquier `--json-file`, porque un envío real debe confirmar el resultado en SQL Server.

Para inspeccionar pendientes en SQL Server, ejecuta `EXEC dbo.usp_ExportarCotizacionesMantra @FechaProceso='2026-02-05';`. Ese día se consideran cotizaciones anteriores al 3 de febrero. El resultado incluye `payload_json` e `ids_json`; puedes copiar `payload_json` a un archivo UTF-8 para probar la validación con `--json-file`. La ejecución real con `--apply` debe leer directamente del SP para registrar cada éxito y evitar reenvíos; no admite `--json-file`.

## Variables de `.env`

Edita `mantra_integracion/.env` con un editor de texto. Python lo lee automáticamente al ejecutar cualquiera de los dos scripts; las variables existentes en el sistema tienen prioridad. Git ignora el archivo para que las credenciales no se publiquen.

| Variable | Cuándo se necesita | Valor |
| --- | --- | --- |
| `MANTRA_GROUP_ID` | Consulta o creación de contactos | ID del grupo en Mantra |
| `MANTRA_API_KEY` | Consulta o creación de contactos | API key de ese grupo |

En el flujo con SQL Server Agent, `config.json` usa `sql.authentication = "windows"`. Python se conecta con la identidad de Windows del proxy del job mediante ODBC; **no necesita usuario ni contraseña de SQL en `.env`**. El servidor y la base se configuran en `config.json`. La cuenta proxy necesita permisos `EXECUTE` sobre ambos SP, lectura del `.env` y escritura en la carpeta de logs. La API key de Mantra sí sigue en `.env`.

Para pruebas fuera de ese servidor, se conserva el modo opcional `sql.authentication = "sql"`, que usa `MANTRA_SQL_USER` y `MANTRA_SQL_PASSWORD` como variables de entorno. No se requieren en el job con autenticación de Windows.

## Preparación en Windows

1. En el servidor Windows que ejecuta SQL Server Agent, instalar Python 3.10+, las dependencias de `requirements.txt` y Microsoft ODBC Driver 18 for SQL Server. La conexión integrada exige que la cuenta del job tenga acceso al servidor SQL y que su certificado TLS sea confiable para ODBC.
2. Ejecutar todo el SQL de `../diagrama-mantra/usp_ExportarCotizacionesMantra.sql` en la base real. Crea `dbo.MantraExportaciones`, una función de normalización de teléfono y dos SP.
3. Copiar `config.example.json` a `config.json` y definir servidor, base y carpeta de logs. Mantener `"authentication": "windows"`. `config.json` todavía no está creado en esta copia del proyecto.
4. Completar solo `MANTRA_GROUP_ID` y `MANTRA_API_KEY` en `.env`. Dar acceso de lectura a ese archivo únicamente a la cuenta que ejecutará el job. No guardar secretos en `config.json`, el repositorio o el TXT.
5. Probar sin modificar Mantra: `powershell -File .\run_mantra.ps1 -PythonExe "C:\Mantra\venv\Scripts\python.exe" -DryRun`. Revisar el TXT y el conteo de contactos pendientes. También se puede llamar Python directamente sin `--apply`.
6. Tras confirmar el mapeo y la regla, ejecutar una prueba autorizada con `python exportar_contactos.py --config config.json --apply`. Revisar el TXT y `dbo.MantraExportaciones` para comprobar qué teléfonos se confirmaron.
7. El administrador de SQL Server debe crear un proxy de Agent habilitado para `CmdExec` con una cuenta de Windows de permisos limitados. Editar `@ProxyName`, `@Launcher`, `@PythonExe` y `@HoraHHMMSS` en `registrar_job_sql_agent.sql` y ejecutar el script en SSMS. La hora se interpreta en la zona horaria del **servidor**, mientras Python calcula la fecha de selección en Lima. El job recupera pendientes de días anteriores. No crear además la tarea con `registrar_tarea.ps1`.

El job de SQL Server Agent es un objeto de `msdb` administrado por el servicio SQL Server Agent; el SP de la base sigue generando el JSON. Agent dispara Python, y Python llama al SP usando la identidad de Windows del proxy. SQL Server Express no permite utilizar SQL Server Agent para esta programación; en esa edición se puede usar el Programador de tareas de Windows con la misma autenticación integrada.

## Prueba de acceso a Mantra sin SQL Server

Completa `MANTRA_GROUP_ID` y `MANTRA_API_KEY` en `.env`. Usa un número de prueba autorizado; el script nunca imprime los secretos ni el contenido del contacto consultado.

En Windows puedes usar `powershell -File .\probar_mantra.ps1 -Phone 987654321`. El script Python lee `.env` automáticamente. Sin `-Name` hace solo la consulta de credenciales; con `-Name "Prueba JS Industrial"` crea o actualiza el contacto de prueba.

1. Solo lectura, valida las credenciales sin modificar contactos: `python probar_mantra.py --phone 987654321`. Un HTTP 200 o 404 indica que Mantra aceptó las credenciales para `/contacts/byphone`.
2. Crear o actualizar el contacto de prueba: `python probar_mantra.py --phone 987654321 --name "Prueba JS Industrial"`.

El paso 2 escribe en Mantra, pero no envía ningún WhatsApp.

## Definiciones pendientes antes de producción

- Las cotizaciones sin `fecemidoc` no son seleccionables.
- Las ejecuciones simultáneas y una caída después de que Mantra acepte el contacto pero antes de confirmar en SQL pueden causar un reintento. Mantra actualiza el contacto por teléfono, pero la confirmación estricta entre API y SQL no es atómica.
- Confirmar el mapeo de los veinte `custom_*` y si Mantra permite cambiar sus etiquetas visibles.
- Validar con una fila real el número de cotización calculado, la moneda y el total del documento.
- Confirmar que `txttlf001` contiene teléfonos correctos de clientes. No se exportan registros con teléfono inválido.
- Definir equivalencias de los códigos de vendedor, condición de venta, fuente y estado si Mantra necesita sus descripciones.
- Mantener y respaldar la carpeta de TXT para revisar resultados y errores de cada ejecución.

Se creó un contacto de prueba autorizado en Mantra (HTTP 201, `created`) y una consulta posterior confirmó los 13 datos enviados. El JSON de esa prueba se guardó en `contacto_envio.local.json`, ignorado por Git. La regla de selección y confirmación se probó contra una restauración temporal del backup con cinco cotizaciones ficticias. El job de Agent y la conexión integrada aún no se han probado en el servidor del cliente.
