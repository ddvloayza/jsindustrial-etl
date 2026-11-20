# Runbook: dos servidores, JSON de solo lectura

## Arquitectura

| Servidor | Responsabilidad |
| --- | --- |
| Servidor de BD | Aloja `JSIndustrial`; una tarea de Windows llama a `dbo.JS_usp_ExportarCotizacionesMantra` y deja cada lote JSON en `C:\Mantra\outbox`. No necesita claves de Mantra ni salida al API. |
| Servidor de envío | Lee los archivos por una carpeta compartida, los copia a `C:\Mantra\inbox` y llama al API de Mantra. No necesita conexión ni credenciales de SQL Server. Guarda en `C:\Mantra\state\enviados.sqlite3` los teléfonos aceptados. |

El servidor de envío solo lee la carpeta compartida; no devuelve resultados. Por eso `dbo.JS_MantraExportaciones` **no registra los éxitos nuevos** en este modo y el servidor de BD puede incluir los mismos teléfonos en lotes posteriores. El registro local del servidor de envío los omite. Hay que respaldar `enviados.sqlite3`: perderlo puede provocar nuevos envíos. Los fallos de API quedan pendientes y se reintentan al leer el archivo otra vez. El segundo servidor tampoco puede comprobar si una cotización cambió después de generar el JSON; por eso conviene enviarlo poco después de exportarlo.

## 1. Servidor de BD

Instalar el SQL de [`../diagrama-mantra/usp_ExportarCotizacionesMantra.sql`](../diagrama-mantra/usp_ExportarCotizacionesMantra.sql) en `JSIndustrial`. Ejecutar [`permisos_login_mantra.sql`](permisos_login_mantra.sql) en SSMS después de crear el login SQL `mantra`. El procedimiento devuelve el JSON como resultado de consulta; [`run_exportar_json.ps1`](run_exportar_json.ps1) lo escribe en disco. El script se conecta a `SRV-02` con ese login. La contraseña se pide una vez y se cifra con DPAPI para este servidor; no va en Git, `config.json`, `.env` ni en la tarea. La cuenta SQL recibe `CONNECT` a `JSIndustrial`, `SELECT` sobre `dbo.CotizacionesC` y `EXECUTE` sobre `dbo.JS_usp_ExportarCotizacionesMantra`. El servidor de BD no requiere Python, ODBC ni SQL Server Agent.

En PowerShell como administrador, actualizar el repositorio y guardar la contraseña SQL sin mostrarla ni escribirla en un archivo de texto:

```powershell
cd C:\Mantra\jsindustrial-etl
git pull
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mantra_integracion\guardar_credencial_sql.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mantra_integracion\run_exportar_json.ps1 -Limit 1
```

Revisar el archivo `C:\Mantra\outbox\cotizaciones_AAAAMMDD_HHMMSS_mmm.local.json` y el TXT de `C:\Mantra\logs`; no se llama a Mantra. El JSON se escribe primero como `.tmp` y luego se publica con el nombre final para que el segundo servidor no lea un archivo incompleto. El archivo cifrado `C:\Mantra\secrets\sql-mantra.bin` solo es legible por `SYSTEM` y Administradores; por usar DPAPI `LocalMachine`, otros administradores de ese equipo también pueden descifrarlo. Respaldar la contraseña por un medio seguro, porque el archivo cifrado no funciona en otro servidor.

Crear `C:\Mantra\outbox` como carpeta compartida con **permiso de solo lectura** para la cuenta del servidor de envío. Registrar la tarea sin horario y con límite de un contacto, ejecutarla manualmente como `SYSTEM` y comprobar el resultado:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mantra_integracion\registrar_tarea_bd.ps1
Start-ScheduledTask -TaskName 'JS Industrial - Generar JSON Mantra'
Get-ScheduledTaskInfo -TaskName 'JS Industrial - Generar JSON Mantra'
Get-ChildItem C:\Mantra\outbox\*.local.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

Después de validar el JSON, activar la ejecución diaria sin límite de contactos:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mantra_integracion\activar_tarea_bd.ps1 -Hora '07:00'
```

El horario es el del servidor. Mantener desactivado el job parcial de SQL Server Agent para evitar exportaciones duplicadas.

## 2. Servidor de envío

Instalar Python y las dependencias de `requirements.txt`. Copiar `config.sender.example.json` a `config.sender.json` y `.env.example` a `.env` en `C:\Mantra\jsindustrial-etl\mantra_integracion`. En `.env`, completar `MANTRA_GROUP_ID` y `MANTRA_API_KEY`. La configuración de este servidor no contiene `sql.server`, usuario ni contraseña de SQL.

La cuenta que ejecuta la tarea necesita lectura en la carpeta compartida, escritura en `C:\Mantra\inbox`, `C:\Mantra\logs` y `C:\Mantra\state`, y acceso HTTPS a Mantra. Probar manualmente con la ruta UNC real:

```powershell
powershell -File C:\Mantra\jsindustrial-etl\mantra_integracion\run_enviar_archivos.ps1 -SharePath "\\SRV-02\MantraOutbox" -PythonExe C:\Mantra\venv\Scripts\python.exe
```

**Este comando sí crea o actualiza contactos en Mantra.** Copia cada archivo a `inbox`, omite los teléfonos ya registrados en SQLite y reintenta los que tuvieron error. Un archivo con todos sus contactos resueltos recibe un marcador `.done` local. El TXT diario en `C:\Mantra\logs` registra éxito, omisión o error sin claves ni teléfonos.

Para programar el envío diario en este segundo servidor:

```powershell
powershell -File C:\Mantra\jsindustrial-etl\mantra_integracion\registrar_tarea.ps1 -Hora "08:00" -SharePath "\\SRV-02\MantraOutbox"
```

La hora del envío debe ser posterior a la generación del JSON. Verificar en el Programador de tareas que la cuenta elegida puede acceder a la ruta UNC también cuando no hay una sesión interactiva. Respaldar `C:\Mantra\state\enviados.sqlite3` y conservar los archivos de `outbox` hasta comprobar que fueron copiados; sin canal de retorno no se puede borrar automáticamente con certeza desde el servidor de BD.

## Prueba sin API

Para validar un archivo copiado sin enviarlo, en el servidor de envío ejecutar:

```powershell
& "C:\Mantra\venv\Scripts\python.exe" C:\Mantra\jsindustrial-etl\mantra_integracion\exportar_contactos.py --config C:\Mantra\jsindustrial-etl\mantra_integracion\config.sender.json --json-file C:\Mantra\inbox\NOMBRE_ARCHIVO.local.json
```

El resultado debe indicar `"modo": "DRY_RUN"` y cero errores. La exportación usa los ocho campos activos de `config.sender.json`; el JSON conserva las 23 propiedades de origen para auditoría. La selección SQL mantiene la regla de antigüedad, excluye cotizaciones con orden de venta y teléfonos registrados antes en `dbo.JS_MantraExportaciones`.
