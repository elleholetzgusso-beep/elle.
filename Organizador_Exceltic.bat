@echo off
REM ============================================================================
REM  Organizador de carpetas y proyectos - Exceltic
REM ============================================================================
REM  Uso:
REM    1) Doble clic para abrir el menu.
REM    2) O arrastra una carpeta encima de este .bat para usarla directamente
REM       en la opcion "Organizar" / como carpeta de partida.
REM
REM  Este .bat NO necesita Python instalado en el equipo ni permisos de
REM  administrador: usa el interprete portatil (embebido) que viene en la
REM  carpeta "python-embed" al lado de este archivo. Si esa carpeta no existe,
REM  falta copiarla desde el paquete de distribucion (ver README.md del
REM  proyecto, seccion "Distribucion").
REM
REM  Ruta de red de ejemplo donde puede vivir esta carpeta completa:
REM    Y:\Herramientas\OrganizadorExceltic\
REM ============================================================================

setlocal
chcp 65001 >nul

set "AQUI=%~dp0"
set "PYTHON_EMBEBIDO=%AQUI%python-embed\python.exe"

if not exist "%PYTHON_EMBEBIDO%" (
    echo No se encuentra el interprete portatil en:
    echo   %PYTHON_EMBEBIDO%
    echo.
    echo Copia la carpeta "python-embed" junto a este archivo .bat y vuelve a intentarlo.
    echo Si el problema continua, contacta con Elle Holetzgusso.
    echo.
    pause
    exit /b 1
)

"%PYTHON_EMBEBIDO%" "%AQUI%lanzador.py" %*

endlocal
