@echo off
set ARCHIPEL_PORT=7777

echo ==========================================
echo    ARCHIPEL PREMIUM WEB DASHBOARD
echo ==========================================

REM Try to activate venv if it exists
if exist venv\Scripts\activate (
    echo Activating virtual environment...
    call venv\Scripts\activate
)

REM Set the python command to use
set PY_CMD=python
if exist venv\Scripts\python.exe (
    set PY_CMD=venv\Scripts\python.exe
)

echo.
echo [1/2] Starting API Server on http://127.0.0.1:8000...
echo [Note] If port 7777 is used by the TUI, the web node will use 7778.
echo.

start http://127.0.0.1:8000

%PY_CMD% -m src.api.server

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Le serveur a echoue. Verifiez que 'fastapi', 'uvicorn' et 'python-multipart' sont installes.
    echo Tapez: pip install fastapi uvicorn python-multipart
)

pause
