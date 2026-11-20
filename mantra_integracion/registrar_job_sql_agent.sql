/*
  Ejecutar una vez en el SQL Server de producción mediante SSMS como administrador.
  El paso CmdExec se ejecuta bajo la cuenta de servicio de SQL Server Agent.
  Esa cuenta debe poder conectarse a JSIndustrial y escribir en outbox.
  Este job solo genera el JSON. Las claves de Mantra van en el segundo servidor.
  Se instala en modo de prueba: un contacto y horario deshabilitado.
  Editar @Launcher, @Server, @OutDir y @HoraHHMMSS si hace falta.
  El horario usa la zona horaria LOCAL del servidor SQL Server Agent.
*/
USE msdb;
GO

DECLARE @JobName sysname = N'JS Industrial - Generar JSON Mantra';
DECLARE @Launcher nvarchar(4000) = N'C:\Mantra\jsindustrial-etl\mantra_integracion\run_exportar_json.ps1';
DECLARE @Server nvarchar(4000) = N'SRV-02';
DECLARE @OutDir nvarchar(4000) = N'C:\Mantra\outbox';
DECLARE @HoraHHMMSS int = 70000; -- 07:00:00, hora local del servidor
DECLARE @Limit int = 1; -- prueba manual; activar_job_sql_agent.sql lo quita
DECLARE @Command nvarchar(max);

IF EXISTS (SELECT 1 FROM dbo.sysjobs WHERE name = @JobName)
    THROW 50011, 'El job ya existe. Edite su horario o paso desde SQL Server Agent.', 1;

SET @Command = N'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "'
             + REPLACE(@Launcher, N'"', N'""') + N'" -Server "'
             + REPLACE(@Server, N'"', N'""') + N'" -OutDir "'
             + REPLACE(@OutDir, N'"', N'""') + N'" -Limit '
             + CONVERT(nvarchar(11), @Limit);

EXEC dbo.sp_add_job
    @job_name = @JobName,
    @enabled = 1,
    @description = N'Ejecuta el SP bajo la cuenta de SQL Server Agent y genera un JSON en outbox; no llama a Mantra. Inicialmente limitado a un contacto.';

EXEC dbo.sp_add_jobstep
    @job_name = @JobName,
    @step_name = N'Generar JSON',
    @subsystem = N'CmdExec',
    @command = @Command,
    @on_success_action = 1,
    @on_fail_action = 2,
    @retry_attempts = 0;

EXEC dbo.sp_add_jobschedule
    @job_name = @JobName,
    @name = N'Mantra diario',
    @enabled = 0,
    @freq_type = 4,
    @freq_interval = 1,
    @active_start_time = @HoraHHMMSS;

EXEC dbo.sp_add_jobserver @job_name = @JobName;
GO
