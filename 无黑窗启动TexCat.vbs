Set shell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = "C:\Users\HKJ\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
tool = scriptDir & "\src\texture_toolbox.py"
shell.Environment("PROCESS")("TCL_LIBRARY") = "C:/Users/HKJ/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/tcl/tcl8.6"
shell.Environment("PROCESS")("TK_LIBRARY") = "C:/Users/HKJ/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/tcl/tk8.6"
shell.Run "powershell -NoProfile -ExecutionPolicy Bypass -Command ""Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -like '*texture_toolbox.py*--web*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }""", 0, True
shell.Run """" & pythonw & """ """ & tool & """ --web", 0, False
