# Integración JSIndustrial → Mantra en dos servidores

![Flujo de la propuesta original](../docs/flujo-mantra.png)

La implementación actual usa **dos servidores** y solo crea o actualiza contactos en Mantra; no envía mensajes. El [runbook](runbook.md) contiene los comandos de instalación y prueba.

```text
Servidor de BD (JSIndustrial)                  Servidor de envío
SP → JSON en carpeta compartida  ──lectura──> copia local → API Mantra
                                                   ↓
                                           registro SQLite local
```

En el servidor de BD, el Programador de tareas de Windows ejecuta [`run_exportar_json.ps1`](run_exportar_json.ps1) como `SYSTEM`. El script se conecta a SQL Server con el login `mantra`, llama a `dbo.JS_usp_ExportarCotizacionesMantra` y guarda un archivo `*.local.json` en `C:\Mantra\outbox`. La contraseña SQL se lee de un `.env` local excluido de Git y protegido con permisos de Windows. No se necesitan Python, ODBC, SQL Server Agent ni claves de Mantra en el servidor de BD. La cuenta del segundo servidor solo necesita **lectura** en la carpeta compartida. Allí, [`run_enviar_archivos.ps1`](run_enviar_archivos.ps1) copia los archivos, llama a Mantra y registra en `C:\Mantra\state\enviados.sqlite3` cada teléfono aceptado con HTTP 200/201. [`registrar_tarea.ps1`](registrar_tarea.ps1) programa esta segunda etapa.

Como no hay canal de retorno del segundo servidor a SQL, `dbo.JS_MantraExportaciones` no refleja los éxitos nuevos. El SP puede generar nuevamente un teléfono en lotes posteriores; el registro SQLite del servidor de envío lo omite. Hay que respaldar ese archivo. Un error de API no se marca como éxito y se reintenta. Mantra recibe el teléfono sin `+51` y `countryCode=51` por separado.

## Campos enviados

El JSON de origen conserva 23 propiedades para auditoría. `config.sender.json` envía solo los ocho campos de la captura:

| Destino Mantra | Propiedad del JSON | Origen SQL |
| --- | --- | --- |
| `custom_1` | `numero_cotizacion` | serie, número y revisión de `dbo.CotizacionesC` |
| `custom_2` | `fecha` | `fecemidoc` |
| `custom_3` | `cliente` | `txtrazsoc` |
| `custom_5` | `vendedor` | `codmtrven` (código) |
| `custom_7` | `referencia` | `txtrefcot` |
| `custom_13` | `genero_orden_venta` | `numpedgen`; solo sale `-` porque `1` se excluye |
| `data.name` | `nombre_contacto` | `txtnomatt`, o cliente si está vacío |
| `data.phone` | `telefono` | `txttlf001` normalizado |

El SP exige más de dos días calendario completos, descarta `numpedgen=1` y teléfonos inválidos, y elige una cotización por teléfono. Los números de `custom_*` conservan su significado anterior. El [CSV de mapeo](mapeo_campos_mantra.csv) detalla los ocho campos.

## Archivos de configuración

- Servidor de BD: `run_exportar_json.ps1` usa `SRV-02` y `JSIndustrial`. Copiar `.env.db.example` a `.env` y completar `MANTRA_SQL_USER=mantra` y `MANTRA_SQL_PASSWORD`. El `.env` contiene la contraseña SQL en texto, queda fuera de Git y solo debe ser legible por Administradores y `SYSTEM`.
- Servidor de envío: copiar `config.sender.example.json` a `config.sender.json` y `.env.example` a `.env`; completar `MANTRA_GROUP_ID` y `MANTRA_API_KEY`. No necesita acceso SQL.
- Los archivos locales de configuración, el JSON de contactos y el registro de éxitos están excluidos de Git. Dar acceso solo a las cuentas que ejecutan cada etapa.

El script antiguo [`run_mantra.ps1`](run_mantra.ps1) sigue disponible para pruebas directas con conexión SQL desde un mismo servidor, pero **no forma parte del flujo de dos servidores**. La exportación se prueba con [`registrar_tarea_bd.ps1`](registrar_tarea_bd.ps1), que crea una tarea manual limitada a un contacto. Después de revisar el archivo, [`activar_tarea_bd.ps1`](activar_tarea_bd.ps1) quita el límite y activa el horario diario.
