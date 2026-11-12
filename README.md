# 班级管理系统（ClassManager）

一套给高中班级日常使用的桌面程序：**课表、值日、消息、倒计时、随机点名、应用快捷入口**，
装在一体机（如希沃）上给全班看，老师在电脑上维护数据。

- 界面：PySide6（Qt 6）
- 数据：SQLite（`%APPDATA%\ClassManager\data\classmanager.db`）
- 打包：Nuitka（standalone）+ Inno Setup
- 许可：[GPL-3.0](LICENSE)

## 功能

| 模块 | 说明 |
|---|---|
| 今日课表 | 按星期显示当天各节课；双击可临时调整 |
| 值日生 | 每天 5 个职务，可按顺序轮值或按分组轮值 |
| 消息 | 富文本 + 图片，双击编辑 |
| 倒计时 | 最多 3 个（高考、春考等），显示在左栏 |
| 随机点名 | 大字号显示，投屏用 |
| 应用链接 | 一键启动常用程序（U盘 / WPS / 希沃白板 / 浏览器等） |
| 悬浮层 | 最小化后顶部显示时间与当前课（进度条显示本段剩余），右下角小窗可拖拽、点击回主界面 |
| 首次向导 | 6 步完成配置；支持从云端一次性导入、Excel/CSV 导入 |
| 作息时间 | 周一至周五可各自不同，精确到 1 分钟 |

## 安装

下载 Release 里的 `ClassManager-Setup-x.y.z.exe`，双击安装：

- 装到 `%LOCALAPPDATA%\ClassManager`，**不需要管理员权限**
- 开始菜单和桌面（可选）会有快捷方式
- 班级数据存在 `%APPDATA%\ClassManager`，**卸载时默认保留**（可勾选删除）

> 若 Windows 提示「已保护你的电脑」，这是对未签名程序的默认拦截，点
> 「更多信息 → 仍要运行」即可。杀软（360 / 电脑管家）若拦截写入，请把
> 安装目录加入信任区。

## 从源码运行

```powershell
python -m pip install -r requirements.txt
python main.py          # 带控制台，方便看日志
# 或双击 ClassManager.pyw（无控制台）
```

Python 3.13 + PySide6 6.12。

## 打包

```powershell
python -m pip install nuitka ordered-set zstandard
.\build.bat 0.40.0                                    # 编译到 build\main.dist
iscc /DAPPVERSION=0.40.0 installer.iss                # 生成安装包
```

细节见 [docs/PACKAGING.md](docs/PACKAGING.md)。

## 目录结构

```
main.py                 启动入口（单实例、DPI、向导判断）
ui/window/              主窗口、设置、向导、各类编辑器
ui/component/           通用组件（对话框、表格代理、悬浮层、托盘）
services/               数据加载编排、导入、云端拉取、诊断日志
core/                   纯逻辑（节次判断、轮值、形状处理）
data/                   Store / Repository / SQLite 迁移
tools/                  模型、样式加载、杂项
docs/                   ROADMAP / SMOKE / PACKAGING / 导入格式
tests/                  pytest（单元 + GUI）
```

## 数据与隐私

- 所有数据只存在本机 `%APPDATA%\ClassManager`，不上传
- 仓库里**不含**任何学生姓名、照片（`messages/images/` 与 `*.csv` 均被忽略）
- 云端导入功能只在你主动输入账号密码时访问指定服务器

## 开发

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

改动后请按 [docs/SMOKE.md](docs/SMOKE.md) 走一遍界面冒烟。

## 许可

本项目以 [GNU General Public License v3.0](LICENSE) 发布。
