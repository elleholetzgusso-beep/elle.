@echo off
REM ============================================================
REM  CONSTRUIR O .EXE  (correr UMA vez para gerar o programa)
REM ------------------------------------------------------------
REM  Gera dist\GerarFSP.exe -- um unico ficheiro que o Roberto
REM  pode usar SEM instalar Python.
REM
REM  Precisas de Python instalado nesta maquina (so tu, quem
REM  constroi -- o Roberto nao precisa).
REM ============================================================
cd /d "%~dp0"

where py >nul 2>nul && (set "PY=py") || (set "PY=python")

echo Instalando PyInstaller (se necessario)...
%PY% -m pip install --quiet --upgrade pyinstaller openpyxl

echo.
echo Construindo GerarFSP.exe ...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "GerarFSP" ^
    --add-data "FSP_template.xlsx;." ^
    app_fsp.py

echo.
if exist "dist\GerarFSP.exe" (
    echo  ===========================================================
    echo   PRONTO! O programa esta em:  dist\GerarFSP.exe
    echo   Copia para o Roberto o ficheiro:  dist\GerarFSP.exe
    echo   ^(o template ja vai la dentro; se quiseres poder trocar o
    echo    template, poe um FSP_template.xlsx ao lado do .exe^)
    echo  ===========================================================
) else (
    echo  ERRO: a construcao falhou. Ve as mensagens acima.
)
echo.
pause
