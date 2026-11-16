# Runbook: dos servidores, JSON de solo lectura

## Arquitectura

| Servidor | Responsabilidad |
| --- | --- |
| Servidor de BD | Aloja `JSIndustrial`, ejecuta `dbo.JS_usp_ExportarCotizacionesMantra` y deja cada lote JSON en `C:\Mantra\outbox`. No necesita claves de Mantra ni salida al API. |
| Servidor de envío | Lee los archivos por una carpeta compartida, los copia a `C:\Mantra\inbox` y llama al API de Mantra. No necesita conexión ni credenciales de SQL Server. Guarda en `C:\Mantra\state\enviados.sqlite3` los teléfonos aceptados. |

El servidor de envío solo lee la carpeta compartida; no devuelve resultados. Por eso `dbo.JS_MantraExportaciones` **no registra los éxitos nuevos** en este modo y el servidor de BD puede incluir los mismos teléfonos en lotes posteriores. El registro local del servidor de envío los omite. Hay que respaldar `enviados.sqlite3`: perderlo puede provocar nuevos envíos. Los fallos de API quedan pendientes y se reintentan al leer el archivo otra vez. El segundo servidor tampoco puede comprobar si una cotización cambió después de generar el JSON; por eso conviene enviarlo poco después de exportarlo.

## 1. Servidor de BD

Instalar el SQL de [`../diagrama-mantra/usp_ExportarCotizacionesMantra.sql`](../diagrama-mantra/usp_ExportarCotizacionesMantra.sql) en `JSIndustrial`. En este servidor, instalar Python, las dependencias de `requirements.txt` y Microsoft ODBC Driver 18. Crear `config.json` desde `config.example.json`, con `sql.server` apuntando a SQL Server, `sql.database = "JSIndustrial"` y autenticación de Windows si la cuenta de la tarea tiene permiso `EXECUTE` sobre el SP. No se necesita `.env` con claves de Mantra.

Crear `C:\Mantra\outbox` y compartirlo con **permiso de solo lectura** para la cuenta del servidor de envío. Dar escritura solo a la cuenta que genera archivos en el servidor de BD. Generar manualmente un lote de prueba:

```powershell
powershell -File C:\Mantra\jsindustrial-etl\mantra_integracion\run_exportar_json.ps1 -PythonExe C:\Mantra\venv\Scripts\python.exe -OutDir C:\Mantra\outbox -Limit 1
```

El comando devuelve la ruta del archivo `cotizaciones_AAAAMMDD_HHMMSS_mmm.local.json`; no llama a Mantra. El JSON se escribe primero como `.tmp` y luego se publica con el nombre final para que el segundo servidor no lea un archivo incompleto. Revisar el archivo y el número de contactos antes de programar la tarea.

Para ejecutarlo diariamente con SQL Server Agent, editar `@ProxyName`, `@Launcher`, `@PythonExe`, `@OutDir` y `@HoraHHMMSS` en [`registrar_job_sql_agent.sql`](registrar_job_sql_agent.sql), y ejecutarlo en SSMS. El job **solo genera JSON**. También se puede programar `run_exportar_json.ps1` con el Programador de tareas de Windows; activar un solo programador.

## 2. Servidor de envío

Instalar Python y las dependencias de `requirements.txt`. Copiar `config.sender.example.json` a `config.sender.json` y `.env.example` a `.env` en `C:\Mantra\jsindustrial-etl\mantra_integracion`. En `.env`, completar `MANTRA_GROUP_ID` y `MANTRA_API_KEY`. La configuración de este servidor no contiene `sql.server`, usuario ni contraseña de SQL.

La cuenta que ejecuta la tarea necesita lectura en la carpeta compartida, escritura en `C:\Mantra\inbox`, `C:\Mantra\logs` y `C:\Mantra\state`, y acceso HTTPS a Mantra. Probar manualmente con la ruta UNC real:

```powershell
powershell -File C:\Mantra\jsindustrial-etl\mantra_integracion\run_enviar_archivos.ps1 -SharePath "\\SERVIDOR_BD\MantraOutbox" -PythonExe C:\Mantra\venv\Scripts\python.exe
```

**Este comando sí crea o actualiza contactos en Mantra.** Copia cada archivo a `inbox`, omite los teléfonos ya registrados en SQLite y reintenta los que tuvieron error. Un archivo con todos sus contactos resueltos recibe un marcador `.done` local. El TXT diario en `C:\Mantra\logs` registra éxito, omisión o error sin claves ni teléfonos.

Para programar el envío diario en este segundo servidor:

```powershell
powershell -File C:\Mantra\jsindustrial-etl\mantra_integracion\registrar_tarea.ps1 -Hora "08:00" -SharePath "\\SERVIDOR_BD\MantraOutbox"
```

La hora del envío debe ser posterior a la generación del JSON. Verificar en el Programador de tareas que la cuenta elegida puede acceder a la ruta UNC también cuando no hay una sesión interactiva. Respaldar `C:\Mantra\state\enviados.sqlite3` y conservar los archivos de `outbox` hasta comprobar que fueron copiados; sin canal de retorno no se puede borrar automáticamente con certeza desde el servidor de BD.

## Prueba sin API

Para validar un archivo copiado sin enviarlo, en el servidor de envío ejecutar:

```powershell
& "C:\Mantra\venv\Scripts\python.exe" C:\Mantra\jsindustrial-etl\mantra_integracion\exportar_contactos.py --config C:\Mantra\jsindustrial-etl\mantra_integracion\config.sender.json --json-file C:\Mantra\inbox\NOMBRE_ARCHIVO.local.json
```

El resultado debe indicar `"modo": "DRY_RUN"` y cero errores. La exportación usa los ocho campos activos de `config.sender.json`; el JSON conserva las 23 propiedades de origen para auditoría. La selección SQL mantiene la regla de antigüedad, excluye cotizaciones con orden de venta y teléfonos registrados antes en `dbo.JS_MantraExportaciones`.
