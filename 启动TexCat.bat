@echo off
setlocal
set "PYTHONW_EXE=C:\Users\HKJ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
set "PYTHON_EXE=C:\Users\HKJ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "TCL_LIBRARY=C:/Users/HKJ/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/tcl/tcl8.6"
set "TK_LIBRARY=C:/Users/HKJ/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/tcl/tk8.6"
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -like '*texture_toolbox.py*--web*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul
if exist "%PYTHONW_EXE%" (
    start "" "%PYTHONW_EXE%" "%~dp0src\texture_toolbox.py" --web
) else (
    start "" "%PYTHON_EXE%" "%~dp0src\texture_toolbox.py" --web
)
exit /b
