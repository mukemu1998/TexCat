# ROLLBACK

TexCat 使用 Git 记录稳定版本。以下命令默认你的系统已经可以直接运行 `git`；如果没有，请先安装 Git 并把它加入 PATH。

## 查看当前状态

```powershell
git status
```

## 查看版本记录

```powershell
git log --oneline --decorate --graph --all
```

## 回到某个稳定版本查看

```powershell
git checkout v1.01
```

这会进入只读查看状态，适合临时确认旧版本。

## 从旧版本新开修复分支

```powershell
git checkout -b fix/from-v1.01 v1.01
```

## 回到主开发分支

```powershell
git checkout main
```

## 撤销未提交改动

谨慎使用，执行前先确认 `status` 输出：

```powershell
git restore .
```

如果已经提交，优先用新提交修复，不建议直接重写历史。
