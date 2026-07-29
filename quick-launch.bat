@echo off
setlocal EnableExtensions

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if errorlevel 1 (
        echo Python 3 was not found on PATH.
        exit /b 1
    )
    set "PYTHON=py -3"
) else (
    set "PYTHON=python"
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo npm was not found on PATH.
    exit /b 1
)

%PYTHON% -c "import cryptography, fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Installing Python dependencies...
    %PYTHON% -m pip install -e ".[dev]"
    if errorlevel 1 (
        echo Python dependency installation failed.
        exit /b 1
    )
)

if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    pushd frontend
    call npm.cmd install
    if errorlevel 1 (
        popd
        echo Frontend dependency installation failed.
        exit /b 1
    )
    popd
)

if not defined LLE_SECRET_ENCRYPTION_KEY (
    if not exist "data" mkdir "data"
    if not exist "data\.lle-secret-key" (
        %PYTHON% -c "from pathlib import Path; from cryptography.fernet import Fernet; Path(r'data/.lle-secret-key').write_bytes(Fernet.generate_key())"
        if errorlevel 1 (
            echo Could not create the local encryption key.
            exit /b 1
        )
    )
    for /f "usebackq delims=" %%K in ("data\.lle-secret-key") do set "LLE_SECRET_ENCRYPTION_KEY=%%K"
)

if not defined LLE_ADMIN_TOKEN (
    if not defined LLE_ALLOW_INSECURE_LOCAL_AUTH set "LLE_ALLOW_INSECURE_LOCAL_AUTH=true"
)

if not defined LLE_SECRET_ENCRYPTION_KEY (
    echo LLE_SECRET_ENCRYPTION_KEY is empty.
    exit /b 1
)

if /i "%~1"=="--check" (
    echo Quick launch checks passed.
    exit /b 0
)

echo Starting the API at http://127.0.0.1:8000
start "LLM Evaluation API" /D "%~dp0" cmd /k %PYTHON% -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

echo Starting the web app at http://127.0.0.1:5173
start "LLM Evaluation Web" /D "%~dp0frontend" cmd /k npm.cmd run dev -- --host 127.0.0.1

echo Both services are running in separate windows. Close those windows to stop them.
echo Open http://127.0.0.1:5173 in your browser.
exit /b 0
