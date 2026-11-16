/*
  Ejecutar una vez en el SQL Server de producción mediante SSMS como administrador.
  Antes: crear un proxy de SQL Server Agent para CmdExec con una cuenta de Windows
  que pueda ejecutar Python, escribir en outbox y conectarse a JSIndustrial.
  Este job solo genera el JSON. Las claves de Mantra van en el segundo servidor.
  Editar @ProxyName, @Launcher, @PythonExe, @OutDir y @HoraHHMMSS.
  El horario usa la zona horaria LOCAL del servidor SQL Server Agent.
*/
USE msdb;
GO

DECLARE @JobName sysname = N'JS Industrial - Generar JSON Mantra';
DECLARE @ProxyName sysname = N'MantraCmdExecProxy';
DECLARE @Launcher nvarchar(4000) = N'C:\Mantra\jsindustrial-etl\mantra_integracion\run_exportar_json.ps1';
DECLARE @PythonExe nvarchar(4000) = N'C:\Mantra\venv\Scripts\python.exe';
DECLARE @OutDir nvarchar(4000) = N'C:\Mantra\outbox';
DECLARE @HoraHHMMSS int = 70000; -- 07:00:00, hora local del servidor
DECLARE @Command nvarchar(max);

IF NOT EXISTS (SELECT 1 FROM dbo.sysproxies WHERE name = @ProxyName AND enabled = 1)
    THROW 50010, 'Falta crear y habilitar el proxy CmdExec indicado.', 1;
IF EXISTS (SELECT 1 FROM dbo.sysjobs WHERE name = @JobName)
    THROW 50011, 'El job ya existe. Edite su horario o paso desde SQL Server Agent.', 1;

SET @Command = N'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "'
             + REPLACE(@Launcher, N'"', N'""') + N'" -PythonExe "'
             + REPLACE(@PythonExe, N'"', N'""') + N'" -OutDir "'
             + REPLACE(@OutDir, N'"', N'""') + N'"';

EXEC dbo.sp_add_job
    @job_name = @JobName,
    @enabled = 1,
    @description = N'Consulta el SP y genera un JSON en outbox; no llama a Mantra.';

EXEC dbo.sp_add_jobstep
    @job_name = @JobName,
    @step_name = N'Generar JSON',
    @subsystem = N'CmdExec',
    @command = @Command,
    @proxy_name = @ProxyName,
    @on_success_action = 1,
    @on_fail_action = 2,
    @retry_attempts = 0;

EXEC dbo.sp_add_jobschedule
    @job_name = @JobName,
    @name = N'Mantra diario',
    @enabled = 1,
    @freq_type = 4,
    @freq_interval = 1,
    @active_start_time = @HoraHHMMSS;

EXEC dbo.sp_add_jobserver @job_name = @JobName;
GO
