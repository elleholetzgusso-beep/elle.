@echo off
REM Constroi o executavel da janela grafica. Correr na maquina de quem desenvolve,
REM nao na do Roberto. Sai dist\LPA-Exceltic.exe, para copiar e entregar.
setlocal

cd /d "%~dp0\.."

echo.
echo === LPA Exceltic: construir o executavel ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: nao encontrei o Python. Instala de python.org e volta a tentar.
    pause
    exit /b 1
)

echo [1/4] A instalar o que e preciso...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[docx,pdf,dev]"
python -m pip install --quiet pyinstaller
if errorlevel 1 (
    echo ERRO: falhou a instalacao das dependencias.
    pause
    exit /b 1
)

echo [2/4] A correr os testes...
python -m pytest tests -q
if errorlevel 1 (
    echo.
    echo ERRO: ha testes a falhar. Nao se entrega um executavel assim.
    pause
    exit /b 1
)

echo [3/4] A empacotar...
python -m PyInstaller empacotar\LPA.spec --noconfirm --clean --workpath build
if errorlevel 1 (
    echo ERRO: falhou o empacotamento.
    pause
    exit /b 1
)

echo [4/4] Pronto.
echo.
if exist "dist\LPA-Exceltic.exe" (
    echo Executavel:  %CD%\dist\LPA-Exceltic.exe
    for %%F in ("dist\LPA-Exceltic.exe") do echo Tamanho:     %%~zF bytes
    echo.
    echo Antes de entregar, abre-o nesta maquina e corre um projeto de ponta a ponta.
) else (
    echo AVISO: nao encontrei dist\LPA-Exceltic.exe. Ve o que o PyInstaller escreveu acima.
)
echo.
pause
