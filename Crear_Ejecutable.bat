@echo off
REM ============================================================================
REM  Crear el ejecutable  -  Organizador Exceltic
REM ============================================================================
REM  Se ejecuta UNA VEZ, en TU PC (el que tiene Python instalado). Genera
REM  "dist\OrganizadorExceltic\", una carpeta con el .exe dentro que ya no
REM  necesita Python ni "python-embed" en ningun sitio.
REM
REM  Requisitos en este PC:
REM    - Python 3.12 de python.org, marcando "tcl/tk and IDLE"
REM    - Conexion a internet la primera vez (para descargar PyInstaller)
REM
REM  Roberto NO necesita nada de esto: el solo recibe la carpeta ya hecha.
REM ============================================================================

setlocal
chcp 65001 >nul
title Crear el ejecutable - Organizador Exceltic

set "AQUI=%~dp0"
cd /d "%AQUI%"

echo.
echo === Crear el ejecutable del Organizador ===
echo.

REM --- Comprobar que hay Python y que trae Tkinter ------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encuentra Python en este equipo.
    echo         Instala Python 3.12 desde python.org, dejando marcadas las
    echo         opciones "Add python.exe to PATH" y "tcl/tk and IDLE".
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%V in ('python --version 2^>^&1') do set "VERSION=%%V"
echo Python encontrado: %VERSION%

python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Ese Python no trae Tkinter, y sin Tkinter no hay ventana.
    echo         Reinstalalo desde python.org dejando marcada la opcion
    echo         "tcl/tk and IDLE".
    echo.
    pause
    exit /b 1
)
echo Tkinter: correcto
echo.

REM --- Instalar PyInstaller si hace falta ---------------------------------------
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller no esta instalado. Instalandolo ahora...
    python -m pip install --upgrade pyinstaller
    if errorlevel 1 (
        echo.
        echo [ERROR] No se ha podido instalar PyInstaller. Comprueba la
        echo         conexion a internet o el proxy de la empresa.
        echo.
        pause
        exit /b 1
    )
)
echo.

REM --- Generar ------------------------------------------------------------------
REM   --onedir    una carpeta con el .exe, en vez de un unico archivo que se
REM               autoextrae en cada arranque (los antivirus desconfian mucho
REM               menos de --onedir; ver README, seccion del .exe)
REM   --windowed  sin consola negra detras de la ventana
REM   --noupx     sin compresion UPX, otro gatilho clasico de los antivirus
REM   --clean     sin restos de una compilacion anterior
REM   --add-data  mete la carpeta assets\ (los logos) dentro del paquete
echo Generando el ejecutable. Esto tarda un par de minutos...
echo.
python -m PyInstaller ^
    --onedir ^
    --windowed ^
    --noupx ^
    --clean ^
    --noconfirm ^
    --name OrganizadorExceltic ^
    --add-data "assets;assets" ^
    interfaz.py

if errorlevel 1 (
    echo.
    echo [ERROR] La generacion ha fallado. Revisa los mensajes de arriba.
    echo.
    pause
    exit /b 1
)

echo.
if not exist "%AQUI%dist\OrganizadorExceltic\OrganizadorExceltic.exe" (
    echo [AVISO] Termino sin error, pero no encuentro el .exe en:
    echo           dist\OrganizadorExceltic\
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo  Listo. El programa esta en:
echo    %AQUI%dist\OrganizadorExceltic\
echo.
echo  QUE HACER AHORA:
echo   1) Abre esa carpeta y haz doble clic en OrganizadorExceltic.exe
echo      para comprobar que la ventana abre bien.
echo   2) Copia la CARPETA ENTERA (no solo el .exe) a la unidad de red,
echo      por ejemplo Y:\Herramientas\OrganizadorExceltic\
echo   3) Roberto abre el .exe desde ahi. No necesita Python, ni
echo      python-embed, ni permisos de administrador.
echo.
echo  Nunca lo mandes por correo ni por Teams: los antivirus de empresa
echo  bloquean los .exe que llegan como adjunto.
echo ============================================================
echo.
pause
endlocal
