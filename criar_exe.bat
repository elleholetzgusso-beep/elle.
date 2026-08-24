@echo off
rem Gera o arquivo dist\Extrator de Documentos.exe
cd /d "%~dp0"
echo Instalando as bibliotecas necessarias...
python -m pip install --upgrade pyinstaller openpyxl pypdf python-docx
echo.
echo Gerando o executavel (demora alguns minutos)...
python -m PyInstaller --noconfirm --onefile --windowed --name "Extrator de Documentos" app.py
echo.
echo Pronto. O programa esta em: dist\Extrator de Documentos.exe
pause
