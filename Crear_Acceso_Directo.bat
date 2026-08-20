@echo off
REM Pos um icone "LPA Exceltic" no Ambiente de Trabalho, que abre a janela sem
REM terminal. Correr uma vez; depois abre-se pelo icone, nao por esta pasta.
setlocal
cd /d "%~dp0"

set "DESTINO=%~dp0Abrir_LPA.bat"
set "ICONE=%~dp0assets\logo.ico"
set "LNK=%USERPROFILE%\Desktop\LPA Exceltic.lnk"

if not exist "%ICONE%" set "ICONE=%DESTINO%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');" ^
  "$s.TargetPath = '%DESTINO%';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.IconLocation = '%ICONE%';" ^
  "$s.Description = 'Automatizacion de LPA';" ^
  "$s.Save()"

if errorlevel 1 (
    echo ERRO: nao consegui criar o acesso direto.
    echo Podes sempre abrir clicando duas vezes em Abrir_LPA.bat, nesta pasta.
) else (
    echo Pronto. Ve ao Ambiente de Trabalho: "LPA Exceltic".
)
pause
