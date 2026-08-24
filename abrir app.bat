@echo off
rem Abre o Extrator de Documentos com duplo clique.
cd /d "%~dp0"
where pythonw >NUL 2>&1
if %errorlevel%==0 (
    start "" pythonw app.py
) else (
    python app.py
    if errorlevel 1 pause
)
