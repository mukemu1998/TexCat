# ROLLBACK

TexCat 使用 Git 记录稳定版本。当前电脑上的 Git 可执行文件通常在：

```powershell
C:\Program Files\Git\cmd\git.exe
```

如果没有把 Git 加入 PATH，可以用完整路径执行命令。

## 查看当前状态

```powershell
& 'C:\Program Files\Git\cmd\git.exe' status
```

## 查看版本记录

```powershell
& 'C:\Program Files\Git\cmd\git.exe' log --oneline --decorate --graph --all
```

## 回到某个稳定版本查看

```powershell
& 'C:\Program Files\Git\cmd\git.exe' checkout v1.01
```

这会进入只读查看状态，适合临时确认旧版本。

## 从旧版本新开修复分支

```powershell
& 'C:\Program Files\Git\cmd\git.exe' checkout -b fix/from-v1.01 v1.01
```

## 回到主开发分支

```powershell
& 'C:\Program Files\Git\cmd\git.exe' checkout main
```

## 撤销未提交改动

谨慎使用，执行前先确认 `status` 输出：

```powershell
& 'C:\Program Files\Git\cmd\git.exe' restore .
```

如果已经提交，优先用新提交修复，不建议直接重写历史。

