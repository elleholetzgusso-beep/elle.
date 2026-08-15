@echo off
REM ============================================================================
REM  Organizador de carpetas y proyectos - Exceltic  (VERSION CON VENTANA)
REM ============================================================================
REM  Doble clic para abrir la ventana. Tambien puedes arrastrar una carpeta
REM  encima de este .bat: la ruta aparece ya rellenada.
REM
REM  Si el interprete portatil no trae Tkinter (ejecuta Preparar_Tkinter.bat), este
REM  .bat abre automaticamente la version de consola, para que el programa
REM  nunca deje de funcionar.
REM ============================================================================

setlocal
chcp 65001 >nul

set "AQUI=%~dp0"
set "PYTHON_EMBEBIDO=%AQUI%python-embed\pythonw.exe"
set "PYTHON_CONSOLA=%AQUI%python-embed\python.exe"

if not exist "%PYTHON_CONSOLA%" (
    echo No se encuentra el interprete portatil en:
    echo   %PYTHON_CONSOLA%
    echo.
    echo Copia la carpeta "python-embed" junto a este archivo .bat y vuelve a intentarlo.
    echo Si el problema continua, contacta con Elle Holetzgusso.
    echo.
    pause
    exit /b 1
)

REM ¿Tiene Tkinter este interprete?
"%PYTHON_CONSOLA%" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo Este equipo no puede abrir la ventana grafica ^(falta Tkinter^).
    echo Para activarla, ejecuta una vez "Preparar_Tkinter.bat".
    echo Mientras tanto, se abre la version de menu en esta consola.
    echo.
    "%PYTHON_CONSOLA%" "%AQUI%lanzador.py" %*
    endlocal
    exit /b 0
)

if exist "%PYTHON_EMBEBIDO%" (
    start "" "%PYTHON_EMBEBIDO%" "%AQUI%interfaz.py" %*
) else (
    "%PYTHON_CONSOLA%" "%AQUI%interfaz.py" %*
)

endlocal
