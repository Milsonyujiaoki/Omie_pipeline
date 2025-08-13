@echo off
setlocal

REM Caminho do projeto
cd /d "C:\Users\corp.robot\Documents\GitHub\Omie_pipeline"

REM Caminho do ambiente virtual
set VENV_PATH=C:\Users\corp.robot\.virtualenvs\Omie_pipeline-YyllY5GW

REM Verifica se o Python do venv existe
if not exist "%VENV_PATH%\Scripts\python.exe" (
    echo [ERRO] Python não encontrado em "%VENV_PATH%\Scripts\python.exe"
    pause
    exit /b 1
)

REM Cria diretorio de logs, se nao existir
if not exist "log" (
    mkdir log
)

REM Gera nome de log com timestamp
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do (
    set "d=%%a"
    set "m=%%b"
    set "y=%%c"
)
for /f "tokens=1-2 delims=:." %%i in ("%time%") do (
    set "hh=%%i"
    set "mm=%%j"
)
set "logname=log\Omie_%y%-%m%-%d%_%hh%%mm%.txt"

REM Ativa o ambiente virtual e executa o script Python
echo Iniciando extracao em %date% %time% > "%logname%"
call "%VENV_PATH%\Scripts\activate.bat"
"%VENV_PATH%\Scripts\python.exe" main_old.py >> "%logname%" 2>&1

echo [?] Execucao finalizada. Verifique: %logname%
timeout /t 3 >nul

endlocal