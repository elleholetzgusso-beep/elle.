@echo off
REM Abre a janela do LPA sem terminal. Clique duplo — nao precisa de escrever
REM "python -m lpa_filler gui" na linha de comandos.
REM
REM Usa pythonw.exe (a mesma instalacao do python.exe, sem consola por tras)
REM em vez de python.exe. Se ainda nao tiver instalado o pacote, instala-o
REM primeiro (rapido, so na primeira vez).
setlocal
cd /d "%~dp0"

python -c "import lpa_filler" >nul 2>&1
if errorlevel 1 (
    echo A instalar o lpa_filler pela primeira vez...
    python -m pip install --quiet -e ".[docx,pdf]"
    if errorlevel 1 (
        echo ERRO: nao consegui instalar. Confirma que o Python esta instalado
        echo e no PATH ^(python.org, com a opcao "Add to PATH" ligada^).
        pause
        exit /b 1
    )
)

start "" pythonw -m lpa_filler gui
