@echo off
rem TV Air Remote - quick test menu.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo The .venv environment is missing. Create it with:
    echo   py -3.12 -m venv .venv ^&^& .venv\Scripts\python -m pip install -e ".[dev]"
    pause
    exit /b 1
)

:menu
echo.
echo ===== TV Air Remote - quick tests =====
echo  1. Gestures in dry run (webcam, no commands sent to the TV)
echo  2. TV connection check (pairing on first run)
echo  3. TV connection check + KEY_MUTE
echo  4. Turn the TV on (Wake-on-LAN)
echo  5. Full run (gestures + TV)
echo  6. Automated tests (pytest)
echo  7. Dry run with webcam 1
echo  8. Dry run with the Italian interface
echo  0. Exit
choice /c 123456780 /n /m "Choice: "
set "CHOICE=%ERRORLEVEL%"

if "%CHOICE%"=="1" "%PY%" -m tv_air_remote --dry-run
if "%CHOICE%"=="2" "%PY%" scripts\tv_check.py
if "%CHOICE%"=="3" "%PY%" scripts\tv_check.py --key KEY_MUTE
if "%CHOICE%"=="4" "%PY%" scripts\tv_check.py --wol
if "%CHOICE%"=="5" "%PY%" -m tv_air_remote
if "%CHOICE%"=="6" "%PY%" -m pytest -q
if "%CHOICE%"=="7" "%PY%" -m tv_air_remote --dry-run --camera 1
if "%CHOICE%"=="8" "%PY%" -m tv_air_remote --dry-run --lang it
rem 9 = key 0; 255 = error or closed input
if "%CHOICE%"=="9" exit /b 0
if "%CHOICE%"=="255" exit /b 1
if "%CHOICE%"=="0" exit /b 1
goto menu
