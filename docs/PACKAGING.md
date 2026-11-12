# 打包与分发

三条命令走完全流程。**所有产物都在本地生成，不依赖网络**（第一次编译 Nuitka 需要联网下载 MinGW）。

## 0. 一次性准备

```powershell
python -m pip install nuitka ordered-set zstandard
# 首次编译会自动下载 MinGW（约 200MB），之后可离线编译
```

Inno Setup 6：https://jrsoftware.org/isdl.php （装完把 `ISCC.exe` 加进 PATH，或写全路径）

## 1. 编译程序

```powershell
build.bat            # 版本号取自最近的 git tag
build.bat 0.40.0     # 或手动指定
```

产物：`build\main.dist\` —— 整个目录复制走就能免安装运行。

要点：

- 用 `--standalone`（文件夹），**不要 `--onefile`**：启动快，杀软误报也少
- `--enable-plugin=pyside6` 必须加，否则缺 `platforms\qwindows.dll` 会闪退
- 样式表、图标、默认应用、消息模板都通过 `--include-data-dir` 打进去

## 2. 生成安装包

```powershell
iscc /DAPPVERSION=0.40.0 installer.iss
```

产物：`installer\ClassManager-Setup-0.40.0.exe`

安装行为：

| 项 | 值 |
|---|---|
| 安装位置 | `%LOCALAPPDATA%\ClassManager`（**免管理员**） |
| 快捷方式 | 开始菜单 + 可选桌面 |
| 数据位置 | `%APPDATA%\ClassManager` |
| 语言 | 简体中文向导 |
| **卸载** | 「应用和功能」里有条目；**卸载时询问是否删除班级数据，默认保留** |

## 2.1 卸载行为

Inno Setup 自动生成卸载器，安装后在两个地方可见：

1. **设置 → 应用 → 已安装的应用** 里的「班级管理系统」
2. 开始菜单 → 班级管理系统 → **卸载 班级管理系统**

卸载流程：

```
卸载程序
  → 关闭正在运行的程序（依据 AppMutex，会提示先关掉）
  → 删除 %LOCALAPPDATA%\ClassManager（程序本体）
  → 弹窗：「是否同时删除班级数据？」
        默认「否」→ 保留 %APPDATA%\ClassManager
        选「是」→ 连名单/课表/值日/消息一起删掉（不可恢复）
```

## 2.2 教室机器批量安装（静默）

```powershell
.\ClassManager-Setup-0.40.0.exe /VERYSILENT /NORESTART /MERGETASKS=desktopicon
```

- 不弹任何界面、自动建桌面图标
- 装完 `%LOCALAPPDATA%\ClassManager\ClassManager.exe`

静默卸载：

```powershell
& "$env:LOCALAPPDATA\ClassManager\unins000.exe" /VERYSILENT /NORESTART
```
（静默卸载不会弹"是否删除数据"，**保留**数据。）


## 3. 发布

打 tag 并推送（需要时手动）：

```powershell
git tag -a v1.0.0 -m "首个安装包版本"
git push origin v1.0.0
```

推送后 GitHub Actions 自动：

1. 在干净的 Windows 环境编译
2. 生成安装包 + 便携版 zip
3. 计算 SHA256
4. 创建 Release 并附上三个文件

## 4. 验收清单

在一台**没装 Python** 的电脑上：

- [ ] 安装包双击能装，不弹 UAC
- [ ] 开始菜单/桌面图标能启动，**没有黑框**
- [ ] 首次启动进入向导，完成后主界面正常
- [ ] 4K + 300% 缩放下文字不被裁
- [ ] 卸载后 `%APPDATA%\ClassManager` 里的数据还在（重装能直接接上）

---

# 杀软误报怎么降

按效果排序：

## ① 代码签名（最有效）

| 方案 | 价格 | 说明 |
|---|---|---|
| Azure Trusted Signing | ~$10/月 | 微软自家，Defender 基本不拦 |
| SignPath.io | 免费（开源项目） | 但要求仓库公开 |
| OV 证书（Certum 等） | €100–200/年 | 需身份验证 |

没有证书时，下面几条能把误报降到"偶尔"。

## ② 已经做的

- **standalone 而非 onefile**：运行时不往临时目录撒文件，不触发解压型启发式
- **不开 UPX**：压缩壳是杀软强特征
- **补全版本信息**：公司名、产品名、版本号、版权都写进 exe

## ③ 被拦了怎么办

提交误报（免费，1–3 天）：

- 微软 Defender：https://www.microsoft.com/en-us/wdsi/filesubmission
- 360：开放平台 → 误报申诉
- 火绒：论坛「误报反馈」版块
- 腾讯电脑管家：官网误报提交

提交时附上：

> 开源/校内工具；GitHub 仓库地址；功能说明（班级课表与值日管理，无网络行为、无自启、无注册表写入）

**有公开仓库地址，通过率明显更高。**

## ④ 长期

- 版本号递增、不要同名覆盖
- Release 附 `SHA256SUMS.txt`，使用者能自证文件
- 下载量积累后，云端信誉自动好转

## ⑤ 给使用者的说明（贴在 Release 里）

> 若杀毒软件提示拦截，多为「未签名的新程序」导致的误报。可对照 Release 里的 SHA256 校验值确认文件完整，再选择"仍然运行"。程序不会联网、不会开机自启、不在注册表写入任何内容。
