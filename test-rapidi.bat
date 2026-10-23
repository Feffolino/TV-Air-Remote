@echo off
rem Menu dei test rapidi di TV Air Remote.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Ambiente .venv mancante. Crealo con:
    echo   py -3.12 -m venv .venv ^&^& .venv\Scripts\python -m pip install -e ".[dev]"
    pause
    exit /b 1
)

:menu
echo.
echo ===== TV Air Remote - test rapidi =====
echo  1. Gesture in dry-run (webcam, nessun comando alla TV)
echo  2. Collegamento TV (pairing al primo avvio)
echo  3. Collegamento TV + tasto KEY_MUTE
echo  4. Accendi TV (Wake-on-LAN)
echo  5. Avvio completo (gesture + TV)
echo  6. Test automatici (pytest)
echo  7. Dry-run con webcam 1
echo  0. Esci
choice /c 12345670 /n /m "Scelta: "
set "SCELTA=%ERRORLEVEL%"

if "%SCELTA%"=="1" "%PY%" -m tv_air_remote --dry-run
if "%SCELTA%"=="2" "%PY%" scripts\tv_check.py
if "%SCELTA%"=="3" "%PY%" scripts\tv_check.py --key KEY_MUTE
if "%SCELTA%"=="4" "%PY%" scripts\tv_check.py --wol
if "%SCELTA%"=="5" "%PY%" -m tv_air_remote
if "%SCELTA%"=="6" "%PY%" -m pytest -q
if "%SCELTA%"=="7" "%PY%" -m tv_air_remote --dry-run --camera 1
rem 8 = tasto 0; 255 = errore o input chiuso
if "%SCELTA%"=="8" exit /b 0
if "%SCELTA%"=="255" exit /b 1
if "%SCELTA%"=="0" exit /b 1
goto menu
