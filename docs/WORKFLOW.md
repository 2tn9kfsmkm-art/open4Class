# 开发与维护的分工

两条线并行，互不干扰：

| 分支 | 用途 | 谁能改 | 版本 |
|---|---|---|---|
| `main` | 线上稳定版（用户装的） | 维护端，只修 bug | `v1.0.x` |
| `dev` | v2.0 新功能 | 开发端 | `v2.0.0-dev.N` |
| `fix/*` | 单个 bug 临时分支 | 维护端 | 合回 main 后删除 |

## 两个工作目录（git worktree）

同一个仓库、两个文件夹，共享历史，不需要 push/pull 同步：

```
Desktop\widegt 3.2\    ← dev  分支（开发端，v2.0）
Desktop\widegt-fix\    ← main 分支（维护端，1.0.x）
```

查看/新增/删除：

```powershell
git worktree list
git worktree add <路径> <分支>
git worktree remove <路径>
```

> 不要直接删文件夹，否则 `.git` 里会留下无效记录。

注意：

- 同一个分支不能同时检出到两个 worktree
- 两边各自有 `build\`、`installer\`，可以同时编译
- **不要同时运行两个程序**：它们写同一个 `%APPDATA%\ClassManager`，还有单实例锁

## 修 bug（维护端）

```powershell
cd Desktop\widegt-fix
git checkout main
git pull                                  # 如果远端有更新
# ... 改代码、测试 ...
git commit -am "fix: ..."
git tag -a v1.0.1 -m "..."
git push origin main refs/tags/v1.0.1
```

然后把修复同步到开发端：

```powershell
cd Desktop\widegt 3.2
git checkout dev
git cherry-pick <修复提交>                 # 或 git merge main
```

## 开发（开发端）

```powershell
cd Desktop\widegt 3.2
git checkout dev
# ... 改代码、跑 pytest ...
git commit -am "feat: ..."
```

阶段性快照可以打 `v2.0.0-dev.1` 这类标签，并在 Release 里标为 pre-release。

## 发 v2.0.0

```powershell
cd Desktop\widegt 3.2
git checkout dev
git merge main                            # 先把维护端的修复合进来
git checkout main
git merge --no-ff dev
git tag -a v2.0.0 -m "..."
```

**`main` 只在发版时从 `dev` 合并，平时不直接改。**

## 规则

1. `main` 上只允许 bugfix，不加功能
2. 开发端只在 `dev` 提交
3. 合并前跑 `python -m pytest`
4. 打包脚本与 `installer.iss` 改动单独提交，因为两边都在用
5. push 和打 tag 由项目负责人决定
