# Runbook de instalación: SQL Server → Mantra

Este procedimiento instala el envío diario de contactos mediante **SQL Server Agent en Windows**. El job ejecuta PowerShell y Python; Python lee el JSON generado por el SP, crea los contactos en Mantra y confirma en SQL los envíos aceptados. No envía mensajes de WhatsApp.

La ruta `C:\Mantra\jsindustrial-etl` y la hora 07:00 son ejemplos. Cambiarlas si el servidor usa otras rutas u horario. El job usa la **hora local del servidor**; Python calcula la fecha de selección en `America/Lima`.

## 1. Verificar el servidor

- Confirmar que la base de destino es Microsoft SQL Server en un servidor **Windows**, que SQL Server Agent está disponible y que su servicio está iniciado.
- Confirmar que SQL Server Agent puede salir a `https://wbpback.mantra.chat` y acceder al servidor SQL.
- En SQL Server Express, Agent no está disponible para esta programación. En ese caso, usar el Programador de tareas de Windows y [`registrar_tarea.ps1`](registrar_tarea.ps1), sin crear también el job de Agent.
- Si SQL Server Agent corre dentro de un contenedor Linux, el job de este repositorio requiere adaptación porque llama a `powershell.exe`.

## 2. Instalar los componentes en el servidor Windows

Instalar Python 3.11, Git si se clonará el repositorio y [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server). Después, en PowerShell:

```powershell
New-Item -ItemType Directory -Force C:\Mantra\logs
git clone git@github.com:ddvloayza/jsindustrial-etl.git C:\Mantra\jsindustrial-etl
py -3.11 -m venv C:\Mantra\venv
& "C:\Mantra\venv\Scripts\python.exe" -m pip install -r "C:\Mantra\jsindustrial-etl\mantra_integracion\requirements.txt"
& "C:\Mantra\venv\Scripts\python.exe" -c "from zoneinfo import ZoneInfo; print(ZoneInfo('America/Lima'))"
```

Si el servidor no tiene acceso SSH a GitHub, copiar allí el repositorio por un medio aprobado y conservar la misma estructura de carpetas. `requirements.txt` incluye `tzdata`, necesario para resolver `America/Lima` en Windows.

## 3. Instalar el SQL de la integración

En SQL Server Management Studio (SSMS), seleccionar la base real **`BD_MANTRA`** y ejecutar completo [`../diagrama-mantra/usp_ExportarCotizacionesMantra.sql`](../diagrama-mantra/usp_ExportarCotizacionesMantra.sql). No ejecutarlo en `master` ni en `msdb`.

El archivo crea `dbo.MantraExportaciones`, `dbo.fn_NormalizarTelefonoMantra`, `dbo.usp_ExportarCotizacionesMantra` y `dbo.usp_ConfirmarExportacionMantra`. El primer SP devuelve los contactos pendientes; el segundo registra un teléfono solo después de que Mantra responda HTTP 200 o 201.

## 4. Crear los archivos locales de configuración

En PowerShell:

```powershell
Set-Location C:\Mantra\jsindustrial-etl\mantra_integracion
Copy-Item .\config.example.json .\config.json
Copy-Item .\.env.example .\.env
notepad .\config.json
notepad .\.env
```

En `config.json`, cambiar `sql.server` por el servidor real y verificar `sql.database`, `sql.port` y `log_dir`. Mantener `"authentication": "windows"`. Si se usa una instancia con nombre en `sql.server`, quitar `sql.port` cuando no corresponda un puerto fijo.

En `.env`, completar solamente:

```dotenv
MANTRA_GROUP_ID=ID_DEL_GRUPO
MANTRA_API_KEY=CLAVE_DEL_GRUPO
```

`config.json` y `.env` son locales y están excluidos de Git. La cuenta que ejecutará el job debe poder leerlos. El controlador ODBC 18 valida el certificado TLS del servidor SQL; si la conexión falla por el certificado, el administrador debe configurar uno confiable.

## 5. Preparar la cuenta del job y el proxy

El administrador debe crear o elegir una cuenta de Windows con permisos para:

1. Ejecutar `C:\Mantra\venv\Scripts\python.exe` y leer el proyecto, incluido `.env`.
2. Escribir en `C:\Mantra\logs`.
3. Conectarse a `BD_MANTRA` con autenticación de Windows y ejecutar ambos SP.
4. Acceder al endpoint de Mantra por HTTPS.

En SSMS, crear una **Credential** para esa cuenta y un proxy de SQL Server Agent llamado `MantraCmdExecProxy`, habilitado para el subsistema **Operating System (CmdExec)**. El proxy no concede automáticamente permisos dentro de `BD_MANTRA`: el administrador debe crear o asignar el login/usuario de Windows y otorgarle `EXECUTE` sobre los dos SP. [Procedimiento de Microsoft para crear un proxy](https://learn.microsoft.com/en-us/sql/ssms/agent/create-a-sql-server-agent-proxy).

## 6. Probar sin enviar contactos

Desde `C:\Mantra\jsindustrial-etl\mantra_integracion`, ejecutar:

```powershell
powershell -File .\run_mantra.ps1 -PythonExe "C:\Mantra\venv\Scripts\python.exe" -DryRun
```

La salida debe indicar `"modo": "DRY_RUN"`, el número de contactos seleccionados y los errores. Revisar además el TXT en `C:\Mantra\logs`. Este comando consulta el SP y valida los contactos, **sin llamar al API de Mantra ni registrar envíos**. Si se prueba desde una cuenta distinta de la cuenta proxy, el administrador debe verificar también los permisos de esta última.

La selección considera cotizaciones de más de dos días completos, excluye `genero_orden_venta = true` y los teléfonos ya registrados en `dbo.MantraExportaciones`. Antes del primer envío real, revisar el número de pendientes y el mapeo de campos en [`mapeo_campos_mantra.csv`](mapeo_campos_mantra.csv).

## 7. Registrar el job diario

Editar [`registrar_job_sql_agent.sql`](registrar_job_sql_agent.sql):

| Variable | Valor que debe quedar |
| --- | --- |
| `@ProxyName` | Nombre del proxy creado en el paso 5. |
| `@Launcher` | Ruta real de `run_mantra.ps1`. |
| `@PythonExe` | `C:\Mantra\venv\Scripts\python.exe`, si se siguieron las rutas anteriores. |
| `@HoraHHMMSS` | Hora diaria **del servidor**; `70000` significa 07:00:00. |

Con los valores revisados, ejecutar el archivo en SSMS. El script usa `msdb`, crea el job `JS Industrial - Exportar contactos a Mantra` y lo deja **habilitado**. Su primera ejecución programada enviará todos los contactos pendientes que cumplan la regla. No registrar simultáneamente [`registrar_tarea.ps1`](registrar_tarea.ps1).

## 8. Revisar la primera ejecución

En SSMS, abrir **SQL Server Agent → Jobs → JS Industrial - Exportar contactos a Mantra → View History**. Revisar el TXT diario en `C:\Mantra\logs` y, en `BD_MANTRA`, consultar los envíos confirmados:

```sql
SELECT TOP (20) telefono, codidtcot, fecha_envio, http_status
FROM dbo.MantraExportaciones
ORDER BY fecha_envio DESC;
```

Un error de validación o del API no marca el teléfono como enviado; podrá reintentarse en la siguiente ejecución. Una caída después de que Mantra acepte el contacto y antes de confirmar en SQL puede causar un nuevo intento; Mantra actualiza el contacto por teléfono.

El job y la autenticación integrada están preparados en el repositorio, pero **aún no se han instalado ni probado en el servidor del cliente**.
