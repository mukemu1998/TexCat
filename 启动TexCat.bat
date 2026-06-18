@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
set "PYTHON_ARGS="

where pythonw.exe >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=pythonw.exe"
) else (
    where pyw.exe >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=pyw.exe"
        set "PYTHON_ARGS=-3"
    ) else (
        where python.exe >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_CMD=python.exe"
        ) else (
            where py.exe >nul 2>nul
            if not errorlevel 1 (
                set "PYTHON_CMD=py.exe"
                set "PYTHON_ARGS=-3"
            )
        )
    )
)

if not defined PYTHON_CMD (
    echo 未找到 Python。请先安装 Python 3.10+，并执行：
    echo py -3 -m pip install -r requirements.txt
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -like '*texture_toolbox.py*--web*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul

if defined PYTHON_ARGS (
    start "" "%PYTHON_CMD%" %PYTHON_ARGS% "%~dp0src\texture_toolbox.py" --web
) else (
    start "" "%PYTHON_CMD%" "%~dp0src\texture_toolbox.py" --web
)
exit /b
