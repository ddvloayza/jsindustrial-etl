# Runbook: exportación y envío en SRV-02

La tarea de Windows ejecuta el flujo completo cada día a las **05:00, hora local de SRV-02**. Genera `C:\Mantra\outbox\cotizaciones_*.local.json`, envía los contactos a Mantra y confirma solo las respuestas HTTP 200/201 en `dbo.JS_MantraExportaciones`. Los errores se reintentan en la siguiente ejecución. No se usa SQL Server Agent ni una carpeta compartida.

## 1. Base de datos

El SP de [`../diagrama-mantra/usp_ExportarCotizacionesMantra.sql`](../diagrama-mantra/usp_ExportarCotizacionesMantra.sql) debe estar instalado en `JSIndustrial`. Volver a ejecutar ese archivo en SSMS al actualizar el repositorio para activar la actualización por cotización nueva y el corte fijo desde el **1 de octubre de 2026**; conserva la tabla y sus registros existentes. Ejecutar [`permisos_login_mantra.sql`](permisos_login_mantra.sql) con una cuenta administradora: concede al login SQL `mantra` lectura de `dbo.CotizacionesC` y ejecución de los SP de exportación y confirmación. La confirmación escribe en `dbo.JS_MantraExportaciones` mediante el SP; no se concede escritura directa sobre esa tabla.

## 2. Preparar SRV-02

En PowerShell como administrador, actualizar el repositorio y preparar Python 3.11. Las dos primeras líneas evitan que ZKBioTime mezcle sus archivos de Python 3.7 con el entorno virtual:

```powershell
cd C:\Mantra\jsindustrial-etl
git pull
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
py -3.11 -m venv C:\Mantra\venv
& C:\Mantra\venv\Scripts\python.exe -m pip install -r .\mantra_integracion\requirements.txt
if (-not (Test-Path .\mantra_integracion\config.local.json)) { Copy-Item .\mantra_integracion\config.local.example.json .\mantra_integracion\config.local.json }
if (-not (Test-Path .\mantra_integracion\.env)) { Copy-Item .\mantra_integracion\.env.db.example .\mantra_integracion\.env }
notepad .\mantra_integracion\.env
```

Conservar los valores SQL que ya funcionan y añadir `MANTRA_GROUP_ID` y `MANTRA_API_KEY` al mismo `.env`, sin comillas ni espacios alrededor de `=`. `config.local.json` usa `SRV-02`, `JSIndustrial`, puerto `1433` y autenticación SQL; ajustar el puerto solo si la instancia escucha en otro. El `.env` contiene secretos en texto y está excluido de Git. Limitar su lectura a `SYSTEM` y Administradores:

```powershell
icacls.exe .\mantra_integracion\.env /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F'
```

## 3. Probar antes de programar

Primero generar un JSON de un contacto y validar el mapeo **sin llamar al API**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mantra_integracion\run_mantra_local.ps1 -Limit 1 -DryRun
```

El resultado de Python debe indicar `"modo":"DRY_RUN"` y `"errores":0`. Comprobar también la conexión SQL desde Python, que usa un controlador distinto al exportador PowerShell:

```powershell
& C:\Mantra\venv\Scripts\python.exe .\mantra_integracion\exportar_contactos.py --config .\mantra_integracion\config.local.json --limit 1
```

Esta consulta también debe terminar con `"modo":"DRY_RUN"` y `"errores":0`. Después, crear o actualizar **un contacto real** y confirmar el envío en SQL:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mantra_integracion\run_mantra_local.ps1 -Limit 1
```

El resultado debe indicar `"contactos_ok":1` y `"errores":0`. Comprobarlo también en SSMS:

```sql
USE [JSIndustrial];
SELECT TOP (10) telefono, codidtcot, fecha_envio, http_status
FROM dbo.JS_MantraExportaciones
ORDER BY fecha_envio DESC;
```

Cada ejecución crea su propio JSON; los archivos anteriores quedan en `outbox` como evidencia y este flujo solo envía el archivo recién generado. Los TXT de `C:\Mantra\logs` registran la exportación y el resultado del API. El teléfono se envía sin `+51`; `countryCode=51` se envía por separado. Si `referencia` está vacía, se envía `-`. Python usa `vendedores.json` para sustituir el código de vendedor por su nombre al llamar al API; si falta el código en el catálogo, conserva el código. El SP y los dos clientes de SQL fijan la fecha de inicio en el 1 de octubre de 2026. Una cotización nueva del mismo teléfono vuelve a ser elegible al cumplir el plazo y actualiza el contacto; la tabla guarda la última cotización enviada por teléfono.

## 4. Activar ejecución diaria a las 05:00

Verificar que la hora local de SRV-02 corresponda a Lima y registrar la tarea:

```powershell
Get-TimeZone
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\mantra_integracion\registrar_tarea_local.ps1 -Hora '05:00'
Get-ScheduledTask -TaskName 'JS Industrial - Exportar y enviar Mantra'
```

La tarea corre como `SYSTEM` y no requiere una sesión iniciada. Deshabilita la antigua tarea que solo generaba JSON, si existe. Si se creó un job parcial de SQL Server Agent en intentos anteriores, mantenerlo deshabilitado. Revisar el historial de la tarea y `C:\Mantra\logs` después de la primera ejecución programada.
