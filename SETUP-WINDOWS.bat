@echo off
rem One-time installation on Windows. See HOW_TO_RUN.txt.
setlocal
cd /d "%~dp0"
echo.
echo ===== Explainable AI Code Review Assistant - setup =====
echo.

rem ---- 1. Find Python 3.12 or 3.13 ----
set "PY="
py -3.13 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3.13"
if not defined PY (
    py -3.12 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY=py -3.12"
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    echo [ERROR] Python 3.12 or 3.13 was not found.
    echo         Install it from https://www.python.org/downloads/ and tick
    echo         "Add python.exe to PATH" during installation. Then run this file again.
    goto :fail
)
echo [1/4] Using Python:
%PY% --version

rem ---- 2. Python environment and packages ----
echo.
echo [2/4] Installing the application's Python packages (this can take several minutes)...
if not exist "backend\.venv\Scripts\python.exe" (
    %PY% -m venv backend\.venv || goto :fail
)
backend\.venv\Scripts\python -m pip install --upgrade pip || goto :fail
backend\.venv\Scripts\python -m pip install -e backend || goto :fail

rem ---- 3. ESLint (optional, for JavaScript analysis) ----
echo.
echo [3/4] Installing the JavaScript checker (ESLint)...
where npm >nul 2>nul
if errorlevel 1 (
    echo [NOTE] Node.js was not found, so ESLint is skipped. The application still works;
    echo        JavaScript code is then explained by the AI without the ESLint check.
    echo        To add it later: install Node.js 20 LTS or newer from https://nodejs.org and run this file again.
) else (
    pushd backend\app\static_analysis\eslint
    call npm install --omit=dev
    popd
)

rem ---- 4. Settings (.env) ----
echo.
echo [4/4] Settings
backend\.venv\Scripts\python scripts\setup_env.py || goto :fail

echo.
echo ===== Setup finished. Double-click START-WINDOWS.bat to run the application. =====
echo.
pause
exit /b 0

:fail
echo.
echo ===== Setup did NOT finish. Read the message above, fix it, and run SETUP-WINDOWS.bat again. =====
echo.
pause
exit /b 1
