@echo off
REM ============================================================================
REM  Preparar Tkinter en python-embed  -  Organizador Exceltic
REM ============================================================================
REM  Se ejecuta UNA SOLA VEZ, en un PC que tenga Python instalado de forma
REM  normal (python.org). Copia al "python-embed" de la carpeta de red los
REM  archivos de Tkinter que el paquete embeddable no trae.
REM
REM  No requiere permisos de administrador. No modifica el Python instalado.
REM ============================================================================

setlocal enabledelayedexpansion
chcp 65001 >nul
title Preparar Tkinter - Organizador Exceltic

set "AQUI=%~dp0"
set "DESTINO=%AQUI%python-embed"

echo.
echo === Preparar Tkinter en python-embed ===
echo.

if not exist "%DESTINO%\python.exe" (
    echo [ERROR] No se encuentra "python-embed\python.exe" junto a este .bat.
    echo         Copia este archivo dentro de la carpeta del Organizador.
    echo.
    pause
    exit /b 1
)

REM --- Localizar un Python instalado normalmente -------------------------------
set "ORIGEN="
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined ORIGEN (
        for /f "delims=" %%R in ('"%%P" -c "import sys,os;print(os.path.dirname(sys.executable))" 2^>nul') do set "ORIGEN=%%R"
    )
)

if not defined ORIGEN (
    for %%V in (313 312 311 310) do (
        if not defined ORIGEN if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "ORIGEN=%LOCALAPPDATA%\Programs\Python\Python%%V"
        if not defined ORIGEN if exist "C:\Program Files\Python%%V\python.exe" set "ORIGEN=C:\Program Files\Python%%V"
    )
)

if not defined ORIGEN (
    echo [ERROR] No se ha encontrado ningun Python instalado en este equipo.
    echo         Instala Python 3.12 desde python.org ^(marcando Tcl/Tk^) y
    echo         vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)

echo Python instalado encontrado en:
echo   !ORIGEN!
echo Se copiara Tkinter a:
echo   %DESTINO%
echo.
choice /c SN /n /m "Continuar? [S/N] "
if errorlevel 2 exit /b 0
echo.

REM --- Comprobar que ese Python si trae Tkinter --------------------------------
"!ORIGEN!\python.exe" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] El Python encontrado tampoco trae Tkinter.
    echo         Reinstalalo desde python.org dejando marcada la opcion
    echo         "tcl/tk and IDLE".
    echo.
    pause
    exit /b 1
)

set "FALLOS=0"

REM --- DLLs y modulo compilado --------------------------------------------------
for %%F in (_tkinter.pyd tcl86t.dll tk86t.dll zlib1.dll) do (
    if exist "!ORIGEN!\DLLs\%%F" (
        copy /y "!ORIGEN!\DLLs\%%F" "%DESTINO%\%%F" >nul && echo   [ok] %%F
    ) else (
        echo   [--] %%F no encontrado ^(puede ser normal segun la version^)
    )
)

REM --- Paquete tkinter ----------------------------------------------------------
if exist "!ORIGEN!\Lib\tkinter" (
    xcopy /e /i /y /q "!ORIGEN!\Lib\tkinter" "%DESTINO%\tkinter\" >nul && echo   [ok] tkinter\
) else (
    echo   [ERROR] No se encuentra Lib\tkinter
    set "FALLOS=1"
)

REM --- Bibliotecas Tcl/Tk -------------------------------------------------------
if exist "!ORIGEN!\tcl" (
    xcopy /e /i /y /q "!ORIGEN!\tcl" "%DESTINO%\tcl\" >nul && echo   [ok] tcl\
) else (
    echo   [ERROR] No se encuentra la carpeta tcl
    set "FALLOS=1"
)

REM --- Anadir rutas al ._pth ----------------------------------------------------
for %%T in ("%DESTINO%\python3*._pth") do (
    findstr /x /c:"tcl" "%%~T" >nul 2>&1 || (
        echo tcl>>"%%~T"
        echo   [ok] "tcl" anadido a %%~nxT
    )
)

echo.
if "!FALLOS!"=="1" (
    echo Termino con errores. Revisa las lineas marcadas arriba.
    echo.
    pause
    exit /b 1
)

REM --- Verificacion final -------------------------------------------------------
"%DESTINO%\python.exe" -c "import tkinter; tkinter.Tk().destroy()" >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Los archivos se copiaron, pero la comprobacion final ha fallado.
    echo         Prueba a ejecutar Organizador_Exceltic_Ventana.bat: si sigue
    echo         abriendo el menu de consola, contacta con Elle Holetzgusso.
) else (
    echo Listo. python-embed ya puede abrir la ventana.
    echo Ejecuta ahora "Organizador_Exceltic_Ventana.bat".
)
echo.
pause
endlocal
