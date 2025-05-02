@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Starting Script...

:: --- Python Check ---
set "PYTHON_EXE="
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PYTHON_EXE=%%i"
    goto :found_python
)
echo ERROR: Python not found in PATH.
goto :end

:found_python
echo Found Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version

:: --- Check requests ---
echo Checking requests module...
"%PYTHON_EXE%" -m pip show requests > nul 2>&1
if %errorlevel% neq 0 (
    echo Installing requests...
    "%PYTHON_EXE%" -m pip install requests
    :: --- IMPROVED CHECK: Verify installation using pip show again ---
    echo Verifying requests installation...
    "%PYTHON_EXE%" -m pip show requests > nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install or verify requests. Check pip output and network.
        goto :end
    ) else (
        echo OK: requests installed and verified.
    )
) else (
    echo OK: requests is already installed.
)
echo.

:: --- Check speedtest module (using import name) ---
echo Checking speedtest module (via import)...
"%PYTHON_EXE%" -c "import speedtest" > nul 2>&1
if %errorlevel% neq 0 (
    echo Installing speedtest-cli package...
    "%PYTHON_EXE%" -m pip install speedtest-cli
    :: --- IMPROVED CHECK: Verify installation using import ---
    echo Verifying speedtest module import...
    "%PYTHON_EXE%" -c "import speedtest" > nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install speedtest-cli or verify 'import speedtest'. Check pip output.
        goto :end
    ) else (
        echo OK: speedtest module can be imported.
    )
) else (
    echo OK: speedtest module can already be imported.
)
echo.

:: --- Execute Python Script ---
set "PYTHON_SCRIPT=clash_speedtest_debug.py"
echo Checking for Python script: %PYTHON_SCRIPT%
if not exist "%PYTHON_SCRIPT%" (
    echo ERROR: Cannot find Python script: %PYTHON_SCRIPT%
    echo Make sure it is in the same directory as the batch file.
    goto :end
)

echo Executing Python script: %PYTHON_SCRIPT% ...
echo Command: "%PYTHON_EXE%" "%PYTHON_SCRIPT%"
"%PYTHON_EXE%" "%PYTHON_SCRIPT%"
echo Python script finished.

:end
echo.
echo Script finished. Press any key to exit.
pause > nul
exit /b