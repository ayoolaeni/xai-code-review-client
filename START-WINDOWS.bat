@echo off
rem Starts the application at http://localhost:8000. Close this window to stop it. See HOW_TO_RUN.txt.
setlocal
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo The application is not installed yet. Run SETUP-WINDOWS.bat first.
    pause
    exit /b 1
)
if not exist "..\.env" (
    echo The settings file .env is missing. Run SETUP-WINDOWS.bat first.
    pause
    exit /b 1
)
echo.
echo ===== Explainable AI Code Review Assistant =====
echo Starting... the website opens in your browser at http://localhost:8000
echo Keep this window open while you use the application. Close it to stop the application.
echo.
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://localhost:8000"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
echo.
echo The application has stopped.
pause
