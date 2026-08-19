@echo off
REM ============================================================
REM  GERADOR DE FSP  --  atalho para abrir a aplicacao
REM ------------------------------------------------------------
REM  Da duplo-clique neste ficheiro para abrir o programa.
REM  Requer Python instalado (https://www.python.org/downloads/
REM  -> marcar "Add Python to PATH" durante a instalacao).
REM  Da primeira vez instala sozinho a dependencia (openpyxl).
REM ============================================================
cd /d "%~dp0"

REM --- encontra o Python (py launcher ou python) ---
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo.
        echo  ERRO: Python nao encontrado.
        echo  Instala em https://www.python.org/downloads/
        echo  e marca "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
)

REM --- garante a dependencia openpyxl ---
%PY% -c "import openpyxl" 2>nul
if not %errorlevel%==0 (
    echo Instalando dependencia (openpyxl)...
    %PY% -m pip install --quiet openpyxl
)

REM --- abre a aplicacao ---
%PY% "%~dp0app_fsp.py"
if not %errorlevel%==0 pause
