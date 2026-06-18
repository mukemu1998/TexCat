Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
tool = scriptDir & "\src\texture_toolbox.py"

pythonCmd = FindCommand(shell, "pythonw.exe")
pythonArgs = ""

If pythonCmd = "" Then
  pythonCmd = FindCommand(shell, "pyw.exe")
  pythonArgs = "-3 "
End If

If pythonCmd = "" Then
  pythonCmd = FindCommand(shell, "python.exe")
  pythonArgs = ""
End If

If pythonCmd = "" Then
  pythonCmd = FindCommand(shell, "py.exe")
  pythonArgs = "-3 "
End If

If pythonCmd = "" Then
  MsgBox "未找到 Python。请先安装 Python 3.10+，并执行：" & vbCrLf & "py -3 -m pip install -r requirements.txt", 48, "TexCat"
  WScript.Quit 1
End If

shell.Run "powershell -NoProfile -ExecutionPolicy Bypass -Command ""Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -like '*texture_toolbox.py*--web*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }""", 0, True
shell.Run """" & pythonCmd & """ " & pythonArgs & """" & tool & """ --web", 0, False

Function FindCommand(shell, commandName)
  On Error Resume Next
  Set exec = shell.Exec("cmd /c where " & commandName)
  output = Trim(exec.StdOut.ReadAll)
  If Err.Number <> 0 Then
    Err.Clear
    FindCommand = ""
    Exit Function
  End If
  If Len(output) = 0 Then
    FindCommand = ""
  Else
    FindCommand = Split(output, vbCrLf)(0)
  End If
End Function
