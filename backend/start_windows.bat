@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || exit /b 1

if /I "%WEB_LOADER_ENGINE%"=="playwright" (
    if "%PLAYWRIGHT_WS_URL%"=="" (
        echo Installing Playwright browsers...
        playwright install chromium
        if errorlevel 1 exit /b 1
    )

    python -c "import nltk; nltk.download('punkt_tab')"
    if errorlevel 1 exit /b 1
)

set "KEY_FILE=.webui_secret_key"
if not "%WEBUI_SECRET_KEY_FILE%"=="" (
    set "KEY_FILE=%WEBUI_SECRET_KEY_FILE%"
)

if "%PORT%"=="" set "PORT=8080"
if "%HOST%"=="" set "HOST=0.0.0.0"
if "%FORWARDED_ALLOW_IPS%"=="" set "FORWARDED_ALLOW_IPS=127.0.0.1"
if "%UVICORN_WORKERS%"=="" set "UVICORN_WORKERS=1"

if "%WEBUI_SECRET_KEY% %WEBUI_JWT_SECRET_KEY%"==" " (
    echo Loading WEBUI_SECRET_KEY from file, not provided as an environment variable.

    if not exist "%KEY_FILE%" (
        echo Generating WEBUI_SECRET_KEY
        for /f "usebackq delims=" %%A in (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) do (
            >"%KEY_FILE%" echo %%A
        )
        if errorlevel 1 exit /b 1
    )

    echo Loading WEBUI_SECRET_KEY from %KEY_FILE%
    set /p WEBUI_SECRET_KEY=<"%KEY_FILE%"
)

if /I "%USE_OLLAMA_DOCKER%"=="true" (
    echo USE_OLLAMA_DOCKER is set to true, starting ollama serve.
    start "ollama" /B ollama serve
)

set "PYTHON_CMD="
if defined CONDA_PREFIX (
    if exist "%CONDA_PREFIX%\python.exe" (
        set "PYTHON_CMD=%CONDA_PREFIX%\python.exe"
    )
)

if "%PYTHON_CMD%"=="" (
    where python3 >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python3"
    ) else (
        where python >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_CMD=python"
        ) else (
            where py >nul 2>nul
            if not errorlevel 1 set "PYTHON_CMD=py"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo Could not find Python. Activate your Conda environment first: conda activate openwebui
    exit /b 1
)

echo Using Python: %PYTHON_CMD%

if "%~1"=="" goto run_default
goto run_custom

:run_default
"%PYTHON_CMD%" -m uvicorn open_webui.main:app --host "%HOST%" --port "%PORT%" --forwarded-allow-ips "%FORWARDED_ALLOW_IPS%" --workers "%UVICORN_WORKERS%"
goto :eof

:run_custom
"%PYTHON_CMD%" -m uvicorn open_webui.main:app --host "%HOST%" --port "%PORT%" --forwarded-allow-ips "%FORWARDED_ALLOW_IPS%" %*
