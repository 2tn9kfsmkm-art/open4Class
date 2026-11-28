
# open4Class

### This is an opensource class-manager for Chinese high/middle/primary schools.
---

这是一套给班级日常使用的桌面程序，包括：**课表、值日、消息、倒计时、随机点名、应用快捷入口**
装在一体机上，目前能提供基础的信息，减轻每天重复无意义的动作（比如写课表）
网站[class-manager-3ke.pages.dev](https://class-manager-3ke.pages.dev/)

## Installation

下载 [ReleasePage](https://github.com/2tn9kfsmkm-art/open4Class/releases) 里的 `ClassManager-Setup-x.y.z.exe`，双击安装：

- 开始菜单和桌面（可选）会有快捷方式
- 班级数据存在 `%APPDATA%\ClassManager`，**卸载时默认保留**（可勾选删除）

> 若 Windows 提示「已保护你的电脑」，这是对未签名程序的默认拦截，点「更多信息 → 仍要运行」即可。杀软（360 / 电脑管家）若拦截写入，请把安装目录加入信任区。

## Set up

**v1.0.1已支持线上拉取，网址[class-manager-3ke.pages.dev](https://class-manager-3ke.pages.dev/)**
可将以下的内容在线上填写后，将其一并传输至seewo上(向导第一页`从云端导入`)，只需填写每次生成的账号和密码即可传输

由于目前的软件仍处于本地运行模式，在第一次打开前需要准备好一下几个文件（Excel/CSV）:
- 名单，一列姓名即可，表头用`name`，例如：

| name |
|---|
| 张三 |
| 李四 |
| 王五 |

- 课程表，表头为星期，例如：

| 周一 | 周二 | 周三 | 周四 | 周五 |
|---|---|---|---|---|
| 语文 | 数学 | 英语 | 物理 | 化学 |
| 地理 | 生物 | 历史 | 思政 | 信息 |

-作息时间：尽管可以使用向导导入，但是UI现在还需一定的改进，建议使用导入功能：

格式一：
| 周一 | 周二 | 周三 | 周四 | 周五 |
|---|---|---|---|---|
| 7:30-8:10 | 7:30-8:10 | 7:30-8:10 | 7:30-8:10 | 7:30-8:10 |
| 8:20-9:00 | 8:20-9:00 | 8:20-9:00 | 8:20-9:00 | 8:20-9:00 |

格式二：
| 开始 | 结束 |
|---|---|
| 7:30 | 8:10 |
| 8:20 | 9:00 |
> 采用格式二默认5天作息一致

## Features

| 模块 | 说明 |
|---|---|
| 今日课表 | 按星期显示当天各节课；双击可临时调整 |
| 值日生 | 每天数个职务，可*按顺序轮值*或*按分组轮值*；双击可临时调整 |
| 消息 | 富文本 + 图片，双击编辑 |
| 倒计时 | 最多 3 个（高考、期末考等），显示在左栏，自动倒数 |
| 随机点名 | 选取名单内的一位同学 |
| 应用链接 | 一键启动常用程序（内置 U盘（explorer） / WPS / 希沃白板 / 浏览器 在Seewo一体机上的默认目录） |
| 悬浮窗 | 最小化后顶部显示时间与当前课（进度条显示本段剩余），右下角小窗可拖拽、用于点击返回主界面 |
| 首次向导 | 6 步完成配置 |
| 作息时间 | 用于进度条的绘制，周一至周五可各自不同 |

更多信息请参见[user-manual.pdf](user-manual.pdf)

## Future developement plan

>由于开发者在读高三，不能保证后续开发的连续性，也不能保证后续功能能够在短期内实现。开发者可能会优先开发部分功能

- 自动更新
- 支持更改学校名称、标志、主题色
- 支持远程管理班级内容，支持搭建服务器（适合全校使用）
- 远程消息传输、历史消息存储
- 一体机使用管理
- UI优化
- 性能优化

## Structure

```
class-manager
---main.py                 启动入口（单实例、DPI、向导判断）
---ui/window/              主窗口、设置、向导、各类编辑器
---ui/component/           通用组件（对话框、表格代理、悬浮层、托盘）
---services/               数据加载编排、导入、云端拉取、诊断日志
---core/                   纯逻辑（节次判断、轮值、形状处理）
---data/                   Store / Repository / SQLite 迁移
---tools/                  模型、样式加载、杂项
---docs/                   ROADMAP / SMOKE / PACKAGING / 导入格式
---tests/                  pytest（单元 + GUI）
```

## Development

欢迎issue，但是问题不一定能够及时解决，望见谅

## Privacy

open4Class目前阶段所有数据**只存在本机** `%APPDATA%\ClassManager`，不上传

## License

本项目以 [GNU General Public License v3.0](LICENSE) 发布。

