/* Ejecutar en SSMS solo despues de validar el JSON de prueba.
   Quita el limite de un contacto y habilita la ejecucion diaria. */
USE msdb;
GO

DECLARE @Command nvarchar(max) =
    N'powershell.exe -NoProfile -ExecutionPolicy Bypass -File '
    + N'"C:\Mantra\jsindustrial-etl\mantra_integracion\run_exportar_json.ps1" '
    + N'-Server "SRV-02" -OutDir "C:\Mantra\outbox"';

EXEC dbo.sp_update_jobstep
    @job_name = N'JS Industrial - Generar JSON Mantra',
    @step_id = 1,
    @command = @Command;

EXEC dbo.sp_update_schedule
    @name = N'Mantra diario',
    @enabled = 1;
GO
