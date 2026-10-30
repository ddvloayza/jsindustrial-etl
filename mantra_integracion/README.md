# Integración piloto SQL Server → Mantra

![Flujo técnico de la propuesta](../docs/flujo-mantra.png)

La imagen refleja la propuesta original. **El alcance actual termina en crear o actualizar contactos; no se envían plantillas ni mensajes.**

## Flujo implementado

1. El Programador de tareas de Windows ejecuta `run_mantra.ps1` una vez al día.
2. Python llama `dbo.usp_ExportarCotizacionesMantra` con la fecha actual de Lima. El SP considera todas las cotizaciones anteriores a esa fecha menos dos días completos, excluye las que ya generaron orden de venta (`numpedgen = 1`) y los teléfonos con envío exitoso en `dbo.MantraExportaciones`. Si hay varias cotizaciones pendientes para un teléfono, toma la más reciente. Devuelve `payload_json` con los 23 datos del contacto e `ids_json` con los identificadores internos para confirmar el envío.
3. Valida nombre y teléfono. Para Perú acepta nueve dígitos que empiecen en 9, con o sin prefijo 51, y envía `countryCode="51"` separado del teléfono.
4. Envía `POST https://wbpback.mantra.chat/contacts/new` con `groupId`, `apiKey`, `data.name`, `data.phone`, `data.countryCode`, correo opcional y hasta veinte `custom_*`.
5. Después de una respuesta HTTP 200/201, Python llama `dbo.usp_ConfirmarExportacionMantra` para registrar el teléfono como enviado. Escribe un TXT diario `mantra_AAAAMMDD.txt` con hora, identificador de cotización, etapa, HTTP y resultado; no incluye credenciales ni teléfono/correo. Un fallo del API o de validación no marca el teléfono y permite reintentar en la siguiente ejecución.

`ID_Status_Oferta` es un entero y se exporta a `custom_10`; **no es el booleano de conversión a orden**. El booleano encontrado en el backup es `numpedgen`, que también alimenta `custom_13`. La regla excluye `numpedgen = 1`. La marca de exportación se guarda por teléfono peruano normalizado, no por número de cotización. Una vez enviado el contacto, nuevas cotizaciones del mismo teléfono no se vuelven a exportar automáticamente.

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

**Sin valor verificable en el backup:** Cargo, Area, Invent. Disponible, % Invent. Dispon. y fec_Estim_Cierre. El SP los incluye como `null` en el JSON y Python no envía esos `custom_*` hasta que se defina su origen. Por ahora se envían como máximo 15 campos personalizados con valor, más nombre, teléfono y correo cuando corresponda. Los valores de vendedor, condición de venta, fuente y estado siguen siendo códigos/IDs hasta contar con sus catálogos. Cada objeto representa una cotización candidata a contacto; si dos cotizaciones tienen el mismo teléfono, ambas se procesan y Mantra puede actualizar el mismo contacto.

## Probar con el JSON ficticio

Primero copia `.env.example` a `.env` si todavía no existe. Git ignora el `.env` local. Para una simulación no necesitas completar credenciales. Desde `mantra_integracion/`, ejecuta:

```bash
python exportar_contactos.py --config config.example.json --json-file contactos_prueba.json --log-dir ./logs
```

En Windows el comando es el mismo, usando `py` si así está instalado Python. Este modo no requiere SQL Server, `groupId` ni API key; valida los tres objetos de ejemplo y escribe el resultado en `./logs`. No llama a Mantra. El script rechaza `--apply` cuando se usa directamente el archivo `contactos_prueba.json` incluido en el repositorio.

Para inspeccionar pendientes en SQL Server, ejecuta `EXEC dbo.usp_ExportarCotizacionesMantra @FechaProceso='2026-02-05';`. Ese día se consideran cotizaciones anteriores al 3 de febrero. El resultado incluye `payload_json` e `ids_json`; puedes copiar `payload_json` a un archivo UTF-8 para probar la validación con `--json-file`. La ejecución real con `--apply` debe leer directamente del SP para registrar cada éxito y evitar reenvíos; no admite `--json-file`.

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
2. Ejecutar todo el SQL de `../diagrama-mantra/usp_ExportarCotizacionesMantra.sql` en la base real. Crea `dbo.MantraExportaciones`, una función de normalización de teléfono y dos SP.
3. Copiar `config.example.json` a `config.json` y definir servidor, base y carpeta de logs. `config.json` todavía no está creado en esta copia del proyecto. El usuario que ejecute la tarea necesita lectura de `dbo.CotizacionesC` y permiso `EXECUTE` sobre ambos SP y sobre `dbo.fn_NormalizarTelefonoMantra`.
4. Completar las cuatro variables de `.env` para la cuenta que ejecutará la tarea. No guardar secretos en `config.json`, el repositorio o el TXT.
5. Probar sin modificar Mantra: `python exportar_contactos.py --config config.json`. Revisar el TXT y el conteo de contactos pendientes.
6. Tras confirmar el mapeo y la regla, ejecutar una prueba autorizada con `python exportar_contactos.py --config config.json --apply`. Revisar el TXT y `dbo.MantraExportaciones` para comprobar qué teléfonos se confirmaron.
7. Registrar el horario acordado: `powershell -File .\registrar_tarea.ps1 -Hora "07:00"`. La tarea usa la fecha actual de Lima y recupera pendientes de días anteriores.

## Prueba de acceso a Mantra sin SQL Server

Completa `MANTRA_GROUP_ID` y `MANTRA_API_KEY` en `.env`. Usa un número de prueba autorizado; el script nunca imprime los secretos ni el contenido del contacto consultado.

En Windows puedes usar `powershell -File .\probar_mantra.ps1 -Phone 987654321`. El script Python lee `.env` automáticamente. Sin `-Name` hace solo la consulta de credenciales; con `-Name "Prueba JS Industrial"` crea o actualiza el contacto de prueba.

1. Solo lectura, valida las credenciales sin modificar contactos: `python probar_mantra.py --phone 987654321`. Un HTTP 200 o 404 indica que Mantra aceptó las credenciales para `/contacts/byphone`.
2. Crear o actualizar el contacto de prueba: `python probar_mantra.py --phone 987654321 --name "Prueba JS Industrial"`.

El paso 2 escribe en Mantra, pero no envía ningún WhatsApp.

## Definiciones pendientes antes de producción

- Validar con el negocio que `numpedgen = 1` corresponde a la orden aprobada indicada. El esquema lo confirma como booleano de orden generada; el backup vacío no permite observar el evento de aprobación. Las cotizaciones sin `fecemidoc` no son seleccionables.
- Las ejecuciones simultáneas y una caída después de que Mantra acepte el contacto pero antes de confirmar en SQL pueden causar un reintento. Mantra actualiza el contacto por teléfono, pero la confirmación estricta entre API y SQL no es atómica.
- Confirmar el mapeo de los veinte `custom_*` y si Mantra permite cambiar sus etiquetas visibles.
- Validar con una fila real el número de cotización calculado, la moneda y el total del documento.
- Confirmar que `txttlf001` contiene teléfonos correctos de clientes. No se exportan registros con teléfono inválido.
- Definir equivalencias de los códigos de vendedor, condición de venta, fuente y estado si Mantra necesita sus descripciones.
- Mantener y respaldar la carpeta de TXT para revisar resultados y errores de cada ejecución.

Se creó un contacto de prueba autorizado en Mantra (HTTP 201, `created`) y una consulta posterior confirmó los 13 datos enviados. El JSON de esa prueba se guardó en `contacto_envio.local.json`, ignorado por Git. La nueva regla de selección y confirmación se probó contra una restauración temporal del backup con cinco cotizaciones ficticias, pero aún no se ha probado en el servidor del cliente ni se ha instalado una tarea programada allí.
