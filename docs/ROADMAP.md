# 路线图

> 依据 `HANDOFF.md` 的蓝图，按当前代码的真实状态重排。**每个阶段结束打 tag，主线始终保持可运行。**

## 三条原则

1. **主线永远可运行**：任何阶段结束后出问题，`git checkout <上一个 tag>` 就能给班里用。
2. **每个阶段单独验收**：自动测试（pytest）+ 手工冒烟（`docs/SMOKE.md`），不通过不进下一阶段。
3. **先补安全网，再动大手术**：PySide6 迁移、SQLite 化都属于"改错一整片"的活。

## 已确认的决策（2026-10-31）

| 项 | 决定 |
|---|---|
| 打包 | **Nuitka**（保持 HANDOFF D8）；onefile / standalone 待定，倾向 standalone |
| `datas/` 是否进包（已废弃） | **不进包**。分发给其他班级时由首次启动向导收集，之后一律写 `%APPDATA%` |
| PySide6 | **已迁移**（v0.16）；UI 细化仍挂起 |
| 悬浮窗 | 要做（放在数据层之后） |
| Excel 导入 | 需要，只支持 `.xlsx`（需新增 `openpyxl` 依赖） |

## 阶段

| # | 阶段 | 内容 | 预计 | 状态 |
|---|---|---|---|---|
| P0 | 安全网 | pytest 脚手架、冒烟清单、75 个单测、模型层三处缺陷修复 | — | ✅ `v0.3-foundation` |
| P1 | 字号分级 | 主窗口 24pt / 对话框 11pt；随机点人保持大字 | — | ✅ `v0.4-font-scale` |
| P2 | **首次运行自举 + Excel** | 无 `datas/` 时生成空骨架（不再闪退）；接入 `openpyxl`，让课表导入真正可用 | 0.5–1 天 | ✅ `v0.5-bootstrap` / `v0.6-excel` |
| P3 | **首次启动向导（一期）** | 6 页向导：班级信息 → 名单 → 课表 → 值日 → 完成；支持设置里重置重跑；走 `bootstrap.save_all` 落盘 | 2–3 天 | ✅ `v0.7-wizard` |
| P4 | core/ 抽取 | `onduty`/`weekday`/`shape` 纯函数化，覆盖率 ≥80% | 1–1.5 天 | ✅ `v0.8-core` |
| P5 | Nuitka 通道 | 构建脚本、`.ico`、干净目录验证、产出可分发包 | 1 天 | 待做（onefile/standalone 待定） |
| P6 | SQLite 数据层 | `Repository` + `SqliteRepository` + 迁移框架 + CSV→DB 脚本 + 业务接入 + 设置里可切换 | 2 天 | ✅ `v0.11-sqlite-wired` / `v0.12-storage-switch` |
| P7 | 悬浮窗 + 托盘 | 最小化出侧边窗、托盘三菜单 | 1.5 天 | 待做 |
| P8 | 向导二期 | 值日分组文件导入、导入格式规范文档、模板下载、从设置里重跑向导 | 1 天 | 待做 |
| P9 | UI 细化 / PySide6 | 颜色 token、设置 Tab 移底部、目录重构、换 Qt 绑定 | ? | 🟡 PySide6 已迁移（v0.16）；UI 细化仍待讨论 |
| P10 | 文档 | `docs/USER_MANUAL.md` + HANDOFF 升 v1.1 | 0.5 天 | 待做 |

## 关键依赖与风险

- **P2 是 P3 和分发的前置**：现在没有 `datas/` 会在 `classlist_chain.load()` 处抛 `FileNotFoundError`，一路冲到 `Main.__init__`，双击闪退。
- **P3 与 P6 的接缝**：向导只收集表单，落盘统一走 `services/bootstrap.py`；P6 换 SQLite 时只替换该模块的实现，向导 UI 不用改。
- **P3 不要放进 `Main.__init__`**：必须先跑向导、再创建主窗口。反例见 `classlist_chain.prepare()` —— 它阻塞在 `Main.__init__` 里，导致主窗口还没显示就先弹窗，用户以为程序挂了。
- **P5 首次编译慢**：Nuitka 需要 C 编译器（MSVC 或 MinGW64），pandas + numpy + PyQt5 首次 standalone 编译通常 20–60 分钟。
- **数据隐私**：包内不带 `datas/`、不带 `messages/images/`（班级照片），两者都只存在于本机 `%APPDATA%`。

## 待定

- 向导是否支持"以后从设置里重跑"（影响 P3 的窗口形态）
- Nuitka 用 onefile 还是 standalone
- ~~PySide6 是否真的迁移~~ → **已迁移**（2026-11-01，`v0.16-pyside6`）

## 待办（Backlog）

> 按提出的先后记录。没排进阶段表的都放这里，做完打勾并注明版本。

### B1 · 触屏上拖不动页面里的滚动条（2026-10-31 提出）

- [ ] **现象**：软件装在教室触摸屏（希沃白板）上，页面内的滚动条只有 **12px** 宽，手指按不住也拖不动。
- **影响范围**：
  - 首次使用向导的每一页（`SetupWizard._Page.scroll`）
  - 设置窗口的 6 个 Tab（`SettingsDialog._wrap_scroll`）
  - 后续凡是内容比窗口高的地方
- **根因**：`stylesheet/mainpage.qss` 里 `QScrollBar:vertical { width: 12px }`，
  且项目里**没有任何触摸手势代码**（全局搜不到 `QScroller`）。
- **建议方案**（两条一起做才顺）：
  1. 给滚动区启用触摸手势：`QScroller.grabGesture(scroll.viewport(), QScroller.LeftMouseButtonGesture)` —— 手指直接拖动内容，不再依赖那条细滚动条
  2. QSS 把滚动条加宽到 **≥20px**，滑块最小高度 **44px**（触摸目标通行建议）
- **验收**：在希沃白板上用手指拖动页面能滚动；滚动条一按就能抓住；鼠标操作不受影响。
- **备注**：只能在真机验证，桌面上的鼠标测试没有意义。建议连同 P5 打包一起验。

### B2 · 其它已知待办

- [ ] `ui/` 目录的 7 个 `.ui` + 7 个 `_ui.py` 是死代码，随 P9 目录重构一并删除
- [ ] `HANDOFF.md` 更新到 v1.1：记录 P0–P3 的实际落地内容、与本文件的差异
- [ ] `.tmp/`、`pytest-cache-files-*` 等带坏 ACL 的目录，需要管理员权限才能清（不影响功能）
