下面是交接文档初稿。在 3 天 + AI 开发的约束下，我把它写成"可执行 spec + 路线图"，把必须做和可砍项显式分开。**请重点看第 3、4 节（接口契约）和第 11 节（路线图）**，那是最容易在后续开发中跑偏的地方。

---

# ClassManager 项目交接文档

| 项 | 值 |
|---|---|
| 文档版本 | v1.0-draft |
| 项目代号 | ClassManager |
| 交接对象 | 后续 AI 驱动开发团队 |
| 计划工期 | 3 个自然日 |
| 关键约束 | 后续开发以 AI 为主，人工仅评审与验收 |
| 决策基线 | 见 §2 决策摘要 |

---

## 目录

1. [交接目标](#1-交接目标)
2. [决策摘要](#2-决策摘要)
3. [项目现状](#3-项目现状)
4. [接口契约（硬约束）](#4-接口契约硬约束)
5. [目标架构](#5-目标架构)
6. [数据层设计（SQLite + Repository + Migrate）](#6-数据层设计)
7. [改造项清单（含验收标准 DoD）](#7-改造项清单)
8. [测试计划](#8-测试计划)
9. [打包（Nuitka）](#9-打包)
10. [用户使用说明书要求](#10-用户使用说明书要求)
11. [3 天交付路线图](#11-3-天交付路线图)
12. [风险与开放问题](#12-风险与开放问题)
13. [附录](#13-附录)

---

## 1. 交接目标

一句话：**在不破坏班级日常使用的前提下，把当前 CSV + PyQt5 的"能跑"状态，重构为 PySide6 + SQLite + 可测试 + 可打包 + 界面分级清晰的 v1，并补齐文档与用户手册。**

具体交付物：

- [ ] PySide6 版本可运行、可打包
- [ ] SQLite 数据层 + 一次性 CSV→DB 迁移脚本 + schema 版本迁移框架
- [ ] Repository 抽象层，业务代码不再直接 `pd.read_csv`
- [ ] 主窗口最小化 → 右侧悬浮窗（课程表 / 时间 / 倒计时 / 返回按钮）
- [ ] 系统托盘（显示主窗口 / 显示悬浮窗 / 退出）
- [ ] 主题色板 + 字号规范（QSS token 化）
- [ ] TableEditor / Message 编辑器 / UserSettings 字号收敛，Settings Tab 移到底部
- [ ] 纯逻辑单元测试 + TableEditor GUI 测试
- [ ] Nuitka 打包脚本
- [ ] `docs/USER_MANUAL.md` 用户手册
- [ ] 本文件更新至 v1.1（记录实际落地内容）

---

## 2. 决策摘要

| 编号 | 决策点 | 结论 |
|---|---|---|
| D1 | 最小化形态 | **最小化至任务栏**（不是隐藏到托盘），同时弹出**右侧悬浮窗**；托盘为额外快捷入口 |
| D2 | 悬浮窗规格 | 宽 = `screen.width()/5`，高 = `screen.height()*2/3`，圆角，**不可拖动**，右侧垂直居中，不出现在任务栏（`Qt.Tool`） |
| D3 | 悬浮窗内容 | 时间 + 倒计时 + 今日课程表 + 返回主界面按钮 |
| D4 | 数据库 | SQLite（单文件，放在 `DATA_BASE`） |
| D5 | 迁移 | 需要 schema migration 框架 + CSV→DB 一次性迁移脚本；保留 CSV 导出作为备份 |
| D6 | 测试范围 | 纯逻辑单元测试（pytest）+ TableEditor GUI 测试（pytest-qt） |
| D7 | Qt 版本 | **升级到 PySide6** |
| D8 | 打包 | **Nuitka** |
| D9 | 主题色 | **保留深红 `#9B0D14` 作主色**；必须配套中性灰阶 + 琥珀金辅助强调 + 语义色；不做多套主题 |
| D10 | 字号收敛范围 | `TableEditor` + `Message`（**仅操作 UI，不含消息正文**）+ `UserSettings`（**同时 Tab 移到下方**） |
| D11 | 目录重构 | 引入 `ui/component/` 与 `ui/window/` 二级目录区分复用组件与完整窗口 |
| D12 | 代码冗余 | 全部做（清单见 §7.7） |
| D13 | 用户手册 | 需要，简版 Markdown 先行 |
| D14 | 交付顺序 | 测试基线 → 硬伤修复 → 目录/接口规范 → DB 落地 → 悬浮窗 → UI 优化 → 文档/打包 |

### 关于"深红色是不是陷阱"

**结论：深红本身不是陷阱，"只有深红"才是陷阱。**

现状问题定位：
- 全局 QSS 里几乎所有强调元素都用 `#9B0D14`，导致"选中态 / 主按钮 / 侧边栏 / 标题"没有层级差异
- 缺少中性色阶，所有分隔和层次靠留白
- 缺少语义色，"保存成功"与"删除应用"视觉上完全一样

处方（不是换色，是**建立颜色体系**）：

| Token | 色值 | 用途 |
|---|---|---|
| `--color-primary` | `#9B0D14` | 主按钮、当前 Tab、侧边栏、主标题下划线 |
| `--color-primary-hover` | `#7A0A10` | 主按钮悬停 |
| `--color-primary-pressed` | `#5C070C` | 主按钮按下 |
| `--color-primary-soft` | `#F5E8E9` | 选中行背景、悬停背景 |
| `--color-accent` | `#C9A227` | **次强调**：悬浮窗倒计时数字、图标高亮、图标徽标 |
| `--color-neutral-50` | `#FAFAFA` | 页面背景 |
| `--color-neutral-100` | `#F2F2F2` | 卡片背景 |
| `--color-neutral-200` | `#E0E0E0` | 分割线、边框 |
| `--color-neutral-500` | `#9E9E9E` | 次要文本、占位符 |
| `--color-neutral-800` | `#333333` | 主文本 |
| `--color-neutral-900` | `#1A1A1A` | 标题文本 |
| `--color-success` | `#2E7D32` | 保存成功提示 |
| `--color-warning` | `#ED6C02` | 警告提示 |
| `--color-danger` | `#C62828` | 删除、危险操作（与主色区分，主色更深更沉） |
| `--color-info` | `#0288D1` | 信息提示 |

使用原则：**深红 = 品牌/主操作；琥珀金 = 次强调；灰阶 = 90% 的内容；语义色 = 状态提示**。这样"深红"就不会因为"到处用"而失去强调能力。

---

## 3. 项目现状

### 3.1 模块职责（现状）

| 文件 | 职责 | 备注 |
|---|---|---|
| `Main.py` | 主窗口、数据加载编排、各编辑窗口入口 | 已统一信号连接，`_render_countdowns` 动态渲染 |
| `loading.py` | `Chain` 链式数据加载 + `ChainPool` | `load/input/process/play` 四段式 |
| `config.py` | 路径、默认设置、settings 读写 | **存在重复定义（见 §7.7）** |
| `Addapp.py` | 应用链接添加对话框 + `LoadApp` 线程 | `urls` 队列式 `pop(0)` 逻辑待抽象 |
| `Dialogs.py` | 通用输入/选择/随机点人 | 稳定 |
| `Message.py` | 消息 HTML 编辑器 | 字号 24pt 过大 |
| `TableEditor.py` | 通用表格编辑对话框 | 字号大，`save()` 行/列同步逻辑复杂 |
| `UserSettings.py` | 设置窗口（多个 Tab） | Tab 在顶部，字号大，某些 Tab 逻辑与 `ondutySpawn` 重复 |
| `ondutySpawn.py` | 值日表生成（名单/分组模式 + 统计） | 纯函数化程度较好，**最适合先补测试** |
| `tools/PandasQModel.py` | DataFrame ↔ Qt Model 桥 | 大量 `_bind_df` / indexer 打补丁，测试重点 |
| `tools/shape.py` | 索引解包工具 | 纯函数，易测 |
| `tools/num2word.py` | 星期转化 | 纯函数，易测 |
| `windows/dropableTableView.py` | 可拖拽 QTableView + 各类 Delegate | **GUI 测试重点** |

### 3.2 已识别的硬伤（后续必改）

1. `config.py` 中 `DEFAULT_USER_SETTINGS` / `load_user_settings` **重复定义两次**（第二次会覆盖第一次，`countdowns` 只在第二次存在）
2. `jsonSpawn.ensure_data_json` 与 `Main.ensure_data_json` **重复**
3. `loading.py` 里 `classlist_chain._set_tmp_classlist` 的"取消/接受"分支语义与 `TableEditor.on_finish/on_cancel` 耦合，回归风险高
4. `Addapp.py` 里 `self.urls.pop(0)` 在异常时队列状态不清晰
5. `windows/dropableTableView.py` 拼写 `dropable`（应为 `droppable`），因会引发大范围重命名，**本期不改，仅在文档标注**
6. `TableEditor.save()` 行列同步逻辑存在行数差补齐，无测试覆盖

---

## 4. 接口契约（硬约束）

> 本节是"规范问题没问题"的落地形式。所有 PR 评审以本节为准。

### 4.1 线程与 UI 边界

- `Chain.load/input/process` **只允许在后台线程**执行；**禁止触碰任何 `QWidget`**
- `Chain.play` **只在主线程执行**（由 `ChainPool._on_done` 保证）
- 任何跨线程信号必须用 `Signal`/`Slot`，**禁止**在工作线程里 `widget.setText(...)`
- 新增交互（按钮、菜单）必须在主线程创建

### 4.2 数据访问

- 业务代码（`Main.py`、`UserSettings.py` 等）**禁止**直接 `pd.read_csv(...)` / `df.to_csv(...)`
- 所有数据读写走 `data/Repository`（见 §6.2）
- 允许的例外：`data/migrations/*.py` 与 `tools/migrate_csv_to_sqlite.py`

### 4.3 时间与日期

- **入参统一 `datetime` 或 `date`**，禁止传裸字符串；字符串只在 I/O 边界（DB 序列化、展示）出现
- DB 中日期列统一 `TEXT` + `YYYY-MM-DD`（SQLite 惯例），**在 Repository 层转换**
- 星期（1–7 / 1–5）统一"1 = 周一"，禁止混用 Python `weekday()` 语义外泄

### 4.4 值日单元格格式

- **契约：`"{学生姓名} {职务}"`**，姓名内允许含空格，**按最后一个空格切分**
- 该规则已在 `OndutyContentDelegate.setEditorData` 实现，**必须作为测试用例固化**
- 空单元格 = `""`（不是 `None`，不是 `NaN`）

### 4.5 公开函数签名

- 所有 `data/`、`core/`、`services/` 目录下的公开函数：
  - 有 **type hints**
  - 有**中文 docstring**（一行摘要 + 参数 + 返回 + 可能抛出的异常）
  - 私有函数以 `_` 前缀
- 示例：

```python
def build_onduty_df(
    start: date,
    weeks: int,
    daily: int,
    names: list[str],
    jobs: list[str],
    *,
    skip_weekend: bool = True,
    offset: int = 0,
    stride: int = 1,
    skip_names: set[str] | None = None,
    shuffle: bool = False,
    seed: int | None = None,
) -> pd.DataFrame:
    """按名单顺序或分组轮值生成值日表。

    Args:
        start: 起始日期（含当日）。
        weeks: 生成的周数。
        ...
    Returns:
        列名为 `YYYY-MM-DD`，每列为 `daily` 行，单元格格式见 §4.4。
    Raises:
        ValueError: 名单为空 / 职务为空 / daily≤0 / weeks≤0。
    """
```

### 4.6 弹窗文案

- 保存成功：`"已保存到 {path}"` 或 `"已保存"`（不拼图标字符）
- 保存失败：`"保存失败：{reason}"`（冒号后接 reason，不接 traceback）
- 危险确认：`"确定要 {动作} 吗？此操作不可撤销。"` + `QMessageBox.Yes | No`，默认 `No`
- 禁止在文案中拼接原始 `repr(exception)`（应在日志中打）

### 4.7 命名与兼容

- 新代码遵守 PEP 8；现有名称（如 `dropableQTableView`）**本期不重命名**，避免回归
- 需要暴露旧名称时通过 `alias` 保留一个发布周期

---

## 5. 目标架构

### 5.1 目录树（目标态）

```
ClassManager/
├── main.py                    # 入口（替代 Main.py 的 __main__）
├── config/                    # 配置与路径
│   ├── __init__.py
│   ├── paths.py               # RESOURCE_BASE / DATA_BASE / FILE_DIR ...
│   └── defaults.py            # DEFAULT_USER_SETTINGS（唯一）
├── core/                      # 纯领域逻辑（无 Qt 依赖）
│   ├── onduty.py              # build_onduty_df / build_onduty_df_from_groups / compute_stats
│   ├── weekday.py             # weekday2word / 星期语义
│   ├── shape.py               # 索引解包
│   └── models.py              # dataclass: Student / Course / OndutyEntry / AppEntry / Countdown
├── data/                      # 数据访问层（Qt 无依赖，除 Repository 的 signal 用 PySide6.QtCore.Signal）
│   ├── repository.py          # 抽象基类 Repository
│   ├── sqlite_repo.py         # SqliteRepository
│   ├── csv_repo.py            # CsvRepository（迁移期只读）
│   ├── db.py                  # 连接池 / 事务 / PRAGMA
│   ├── schema.sql             # 当前 schema 汇总（供只读展示与调试）
│   └── migrations/
│       ├── __init__.py        # MIGRATIONS 列表
│       ├── m0001_initial.sql
│       └── migrate.py         # apply_pending / current_version
├── services/                  # 编排层
│   ├── load_pool.py           # Chain / ChainPool（原 loading.py）
│   ├── add_app_service.py     # 从 Addapp.py 抽出队列逻辑
│   └── classlist_service.py   # 周模板 + 临时课表的解析逻辑
├── ui/
│   ├── tokens/
│   │   ├── colors.py          # 颜色常量
│   │   ├── fonts.py           # 字号常量
│   │   └── qss/               # qss 源文件（保留可读变量注释）
│   ├── component/             # 复用组件（含 .ui 与 _ui.py）
│   │   ├── input_dialog.py / .ui
│   │   ├── line_edit_dialog.py / .ui
│   │   ├── show_dialog.py / .ui
│   │   ├── droppable_table_view.py    # 保留类名 dropableQTableView
│   │   └── ratio_pixmap_label.py
│   └── window/                # 完整窗口
│       ├── main_window.py + main.ui
│       ├── settings_window.py + settings.ui
│       ├── message_editor.py + message.ui
│       ├── table_editor.py + onduty.ui
│       ├── add_app_dialog.py + add_app.ui
│       ├── mini_window.py             # 悬浮窗（新增）
│       └── tray.py                    # 托盘（新增）
├── tools/
│   ├── pandas_qmodel.py
│   ├── qss2qt.py
│   └── migrate_csv_to_sqlite.py       # 一次性迁移脚本（新增）
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_onduty.py
│   │   ├── test_weekday.py
│   │   ├── test_shape.py
│   │   ├── test_models.py
│   │   ├── test_repository_sqlite.py
│   │   ├── test_migrations.py
│   │   └── test_pandas_qmodel.py
│   └── gui/
│       ├── test_table_editor.py
│       └── test_mini_window.py
├── docs/
│   ├── PROJECT_HANDOFF.md     # 本文件
│   └── USER_MANUAL.md         # 用户手册
├── resources/ stylesheet/ datas/ ...（原有资源）
└── pyproject.toml             # 依赖 + pytest + nuitka 命令
```

### 5.2 分层依赖规则

```
ui  →  services  →  data  →  core
ui  ─────────────────────────→  core（只允许依赖 dataclass 与纯函数）
data ↔ core（依赖 dataclass）
tools ← ui / data（单向，tools 不得反向 import ui）
```

- `core/` **禁止 import Qt**
- `data/` **禁止 import ui**
- 违反者视为架构回归，评审打回

---

## 6. 数据层设计

### 6.1 Schema（v1）

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 学生名单（顺序即轮值顺序）
CREATE TABLE students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    sort_order   INTEGER NOT NULL DEFAULT 0
);

-- 课程单
CREATE TABLE courses (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL UNIQUE
);

-- 周模板课表（周一~周五 × 节次）
CREATE TABLE classlist_template (
    weekday       INTEGER NOT NULL CHECK (weekday BETWEEN 1 AND 5),
    lesson_index  INTEGER NOT NULL CHECK (lesson_index >= 1),
    course_name   TEXT,
    PRIMARY KEY (weekday, lesson_index)
);

-- 特定日期覆盖（"临时课表"）
CREATE TABLE classlist_override (
    date          TEXT NOT NULL,              -- YYYY-MM-DD
    lesson_index  INTEGER NOT NULL CHECK (lesson_index >= 1),
    course_name   TEXT,
    PRIMARY KEY (date, lesson_index)
);

-- 值日表
CREATE TABLE onduty (
    date          TEXT NOT NULL,              -- YYYY-MM-DD
    slot_index    INTEGER NOT NULL CHECK (slot_index BETWEEN 0 AND 4),
    student_name  TEXT NOT NULL,
    job           TEXT NOT NULL,
    PRIMARY KEY (date, slot_index)
);

-- 应用链接
CREATE TABLE apps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    path        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- 通用键值（settings、data.json 内容、倒计时等）
CREATE TABLE kv (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL                       -- JSON 序列化
);

CREATE TABLE schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL
);
```

**刻意不放进 DB 的**：
- `message.html` 与其图片 → 继续存 `MESSAGE_DIR`（HTML 富文本 + 图片引用路径，DB 化收益低）
- `data.json` 的 `last_login` → 进 `kv` 表，`key = 'last_login'`
- `settings.json` → 整体入 `kv` 表，`key = 'user_settings'`（**JSON 整体存，不做列拆**，避免 settings 结构变更引发 schema 变更）

### 6.2 Repository 接口

```python
# data/repository.py
from abc import ABC, abstractmethod
from datetime import date

class Repository(ABC):
    # --- 学生 ---
    @abstractmethod
    def list_students(self) -> list[Student]: ...
    @abstractmethod
    def replace_students(self, names: list[str]) -> None: ...

    # --- 课程 ---
    @abstractmethod
    def list_courses(self) -> list[Course]: ...
    @abstractmethod
    def replace_courses(self, names: list[str]) -> None: ...

    # --- 周模板 / 临时课表 ---
    @abstractmethod
    def get_classlist_template(self) -> dict[tuple[int, int], str]:
        """返回 {(weekday, lesson_index): course_name}。"""
    @abstractmethod
    def save_classlist_template(self, rows: list[tuple[int, int, str]]) -> None: ...
    @abstractmethod
    def get_classlist_for_date(self, d: date) -> list[str]:
        """优先 override，其次 template；返回按 lesson_index 排序的课程名列表（缺省 ''）。"""
    @abstractmethod
    def save_classlist_override(self, d: date, courses: list[str]) -> None: ...
    @abstractmethod
    def delete_classlist_override(self, d: date) -> None: ...

    # --- 值日 ---
    @abstractmethod
    def list_onduty(self) -> list[OndutyEntry]: ...
    @abstractmethod
    def replace_onduty(self, entries: list[OndutyEntry]) -> None: ...
    @abstractmethod
    def get_onduty_for_date(self, d: date) -> list[OndutyEntry]: ...
    @abstractmethod
    def prune_onduty_before(self, d: date) -> int:
        """删除 date < d 的记录，返回删除条数。"""

    # --- 应用 ---
    @abstractmethod
    def list_apps(self) -> list[AppEntry]: ...
    @abstractmethod
    def replace_apps(self, apps: list[AppEntry]) -> None: ...

    # --- 键值 ---
    @abstractmethod
    def get_kv(self, key: str, default=None): ...
    @abstractmethod
    def set_kv(self, key: str, value) -> None: ...

    # --- 事务 / 生命周期 ---
    @abstractmethod
    def close(self) -> None: ...
```

- `SqliteRepository` 是唯一写入实现
- `CsvRepository` 只实现读方法（供迁移脚本用），写方法 `raise NotImplementedError`
- 用户手册中不暴露 Repository

### 6.3 Schema Migration 框架

`data/migrations/migrate.py`：

```python
MIGRATIONS: list[tuple[int, str, str]] = [
    # (version, name, sql_file_relative_path)
    (1, "initial_schema", "m0001_initial.sql"),
    # 未来追加：(2, "add_xxx", "m0002_xxx.sql")
]

def current_version(conn) -> int: ...
def apply_pending(conn) -> int:
    """应用所有未应用的迁移，返回最终版本。在事务内逐条执行。"""
```

**约定**：
- 每个迁移文件是**幂等性外的纯前向 SQL**（不写 `IF NOT EXISTS`，靠版本号保证只跑一次）
- 迁移执行失败 → 整体回滚 → 抛 `MigrationError`
- 应用启动时 `main.py` 自动 `apply_pending`，失败弹出错误窗口并退出
- **禁止**修改已发布的迁移文件；需要变更时新增版本

### 6.4 CSV → SQLite 一次性迁移

`tools/migrate_csv_to_sqlite.py`：

- CLI：`python -m tools.migrate_csv_to_sqlite --csv-dir <FILE_DIR> --db <path> [--dry-run]`
- 读取顺序（缺失文件跳过，打印警告）：
  - `名单.csv` → `students`
  - `课程单.csv` → `courses`
  - `课表.csv`（列 = 周一~周五）→ `classlist_template`
  - `未来值日.csv`（列 = 日期，每列 5 行）→ `onduty`
  - `应用路径.csv`（`软件链接`, `path`）→ `apps`
  - `settings.json` → `kv['user_settings']`
  - `data.json` → `kv['last_login']`
- `--dry-run` 打印迁移统计但不写库
- 迁移完成后写入 `<db>.migrated_at` 标记文件（内含时间戳与行数）
- **迁移不删除 CSV**：保留供回滚与人工核对

### 6.5 数据路径

- DB 文件：`DATA_BASE + "classmanager.db"`
- 连接参数：`PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;`
- 事务：写操作一律 `with conn:` 包裹
- **并发**：主线程与 `LoadApp` 线程共享一个连接对象；读写操作加 `threading.Lock`（SQLite 默认串行，简单可靠）

---

## 7. 改造项清单

> 每项含 **DoD（Definition of Done）**，未达标不计完成。

### 7.1 PySide6 迁移（D7）

**内容**：
- 依赖改为 `PySide6>=6.6`
- 全量 `from PyQt5 ...` → `from PySide6 ...`
- API 差异处理：
  - `pyqtSignal` → `Signal`，`pyqtSlot` → `Slot`
  - `exec_()` → `exec()`
  - `QAction` 从 `QtWidgets` 移到 `QtGui`
  - `QRegExp`（如出现）→ `QRegularExpression`
  - `Qt.AlignCenter` 等旧枚举 → `Qt.AlignmentFlag.AlignCenter`
  - `QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)` 在 Qt6 默认已开，删除
- `.ui` 文件用 `pyuic6` 重新生成 `_ui.py`
- `windows/mainpage_rc.py` 用 `pyside6-rcc` 重新编译
- `QDate.fromString` 等签名在 Qt6 里兼容，无需改

**DoD**：
- [ ] `grep -r "PyQt5" --include="*.py"` 返回 0 行（除 `pyproject.toml` 历史注释）
- [ ] 启动、主界面、设置、值日编辑、消息编辑、添加应用全流程人工跑通
- [ ] `pytest tests/` 全绿
- [ ] Nuitka 打包通过

**风险点**：`webengine` 无关；`QTextEdit.toHtml()` 输出格式在 Qt6 与 Qt5 略有差异，需人工比对 `message.html` 是否被无意义改写（迁移前备份 `message.html`）。

### 7.2 目录重构（D11）

**内容**：
- 按 §5.1 目录树迁移
- `dialogs/` → `ui/component/`
- `windows/` → `ui/window/`
- 顶层 `.py`（`Main.py`、`loading.py`、`Addapp.py`、`TableEditor.py`、`Message.py`、`UserSettings.py`、`Dialogs.py`）拆入对应层
- `ui/component/` 与 `ui/window/` 下**各自**保留 `_ui.py` 与 `.ui` 源文件

**DoD**：
- [ ] `tree -L 2 -I "__pycache__"` 与 §5.1 一致（允许细微差异，需在 PR 说明）
- [ ] 循环 import 检查通过（`python -X importtime -c "import main"` 无错误）
- [ ] 所有旧路径引用已更新，`grep -r "from windows\.\|from dialogs\."` 返回 0

### 7.3 config 去重（D12 子项）

**内容**：
- `config/defaults.py` 只保留**一份** `DEFAULT_USER_SETTINGS`（含 `countdowns`）
- `config/paths.py` 承载路径计算
- `config/__init__.py` 重导出对外的 API，**不重复定义**
- `jsonSpawn.ensure_data_json` 合并到 `services/` 或 `main.py`，唯一入口

**DoD**：
- [ ] `grep -r "DEFAULT_USER_SETTINGS ="` 返回 1 处
- [ ] `grep -r "def load_user_settings"` 返回 1 处
- [ ] 单测 `test_config_defaults.py`：默认值含 `countdowns`，写读往返一致

### 7.4 SQLite + Repository + Migrate（D4/D5）

**内容**：见 §6 全部

**DoD**：
- [ ] `data/sqlite_repo.py` 完整实现接口，单测覆盖所有方法
- [ ] `migrations/migrate.py` 有版本化测试：从 v0 应用到最新；重复调用幂等
- [ ] `tools/migrate_csv_to_sqlite.py` 在真实 `datas/` 上跑通，行数与 CSV 一致
- [ ] `loading.py` 等业务代码**不再 `pd.read_csv`**（`grep` 验证）
- [ ] CSV 导出备份功能保留（`Repository.export_csv(dir)` 可选，落地或标为 TODO）

### 7.5 悬浮窗 + 托盘（D1/D2/D3）

**悬浮窗规格（落实）**：
- 类：`ui/window/mini_window.py: MiniWindow(QWidget)`
- 窗口标志：`Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- 位置：
  ```python
  screen = QApplication.primaryScreen().availableGeometry()
  w = screen.width() // 5
  h = screen.height() * 2 // 3
  x = screen.right() - w - margin
  y = screen.top() + (screen.height() - h) // 2
  ```
- 外形：`QFrame` 圆角 + `QGraphicsDropShadowEffect` 阴影 + 半透明白底
- 布局（自上而下）：
  1. **时间区**：大号时间（`HH:mm:ss`）+ 日期 + 星期
  2. **倒计时区**：按 `settings['countdowns']` 渲染，数字用 `--color-accent` 琥珀金
  3. **课程表区**：`QTableView` 或纵向 `QListWidget`，显示今日课程，**高亮当前节**（根据当前时间推断）
  4. **底部**：`返回主界面` 按钮（主色）
- **不可拖动**（不加拖动事件、`setWindowFlags` 不放开移动）
- 刷新：`QTimer` 每秒更新时间与高亮；课程/倒计时变更时通过信号刷新

**托盘**：
- `ui/window/tray.py: Tray(QSystemTrayIcon)`
- 菜单：`显示主窗口` / `显示悬浮窗` / `退出`
- 双击图标 → 显示主窗口
- 退出前询问是否有未保存内容（当前无 dirty 态，直接退出即可）

**主窗口集成**：
- `Main.changeEvent` 拦截 `WindowStateChange`
  - `isMinimized() == True` → `mini_window.show()`（**主窗口保留在任务栏，不改 flags**）
  - 恢复 → `mini_window.hide()`
- 悬浮窗"返回主界面"→ `main.showNormal(); main.raise_(); main.activateWindow()`

**DoD**：
- [ ] 最小化 → 悬浮窗出现；恢复 → 悬浮窗消失
- [ ] 悬浮窗不占任务栏（`Qt.Tool` 生效）
- [ ] 悬浮窗位置随屏幕分辨率正确计算（多屏时用主屏）
- [ ] 倒计时/课程变更后 ≤1s 内刷新
- [ ] GUI 测试 `test_mini_window.py` 覆盖：位置计算、倒计时渲染、返回按钮信号

### 7.6 主题色 + 字号收敛（D9/D10）

**内容**：
- `ui/tokens/colors.py` 定义 §2 颜色 token
- `ui/tokens/fonts.py` 定义字号 token
- `stylesheet/*.qss` 全部重写为**引用 token 的语义化样式**（QSS 不支持变量，实际做法：在 `ui/tokens/qss.py` 里用 Python 字符串模板 + `.format(**colors)` 生成，或直接硬编码但**只在 `qss.py` 一处硬编码**）
- **字号 token**：

| Token | 值 | 用途 |
|---|---|---|
| `FONT_DISPLAY` | 40pt | 主标题（`title_l`） |
| `FONT_H1` | 28pt | 主界面数据区（课表、值日表） |
| `FONT_H2` | 22pt | 分组标题、悬浮窗时间 |
| `FONT_BODY` | 11pt | 一般按钮、标签、输入 |
| `FONT_SMALL` | 10pt | **TableEditor 工具栏、Message 操作栏、UserSettings 各面板** |
| `FONT_CAPTION` | 9pt | 辅助说明 |

- 应用范围（仅三处，**不全局改**）：
  - `TableEditor`：工具栏按钮、`show_size` 标签、`save/cancel` 按钮 → `FONT_SMALL`
  - `Message`：字号滑块、粗体/插入图片/导入/保存/关闭 → `FONT_SMALL`；**消息正文保持 24pt 默认，不受影响**
  - `UserSettings`：所有 Tab 内的标签、按钮、输入 → `FONT_SMALL`；**Tab 位置从顶部改到底部**（`QTabWidget.setTabPosition(QTabWidget.South)`）

**DoD**：
- [ ] `grep -rn "24pt" stylesheet/` 只在 `mainpage.qss` 的 `FONT_H2` 相关出现，其余收敛
- [ ] `TableEditor` / `Message` / `UserSettings` 三处截图与改造前对比，字号明显变小
- [ ] 设置窗口 Tab 在底部
- [ ] 颜色 token 覆盖率：`grep -rn "#9b0d14" --include="*.qss"` 只出现在 `ui/tokens/qss.py`（QSS 引用它生成的文件）

### 7.7 代码冗余清理（D12）

**清单**（逐项打勾）：
- [ ] `config.py` 重复定义合并（§7.3）
- [ ] `ensure_data_json` 唯一化
- [ ] `loading.py: _set_tmp_classlist` 的重入逻辑抽出 `services/classlist_service.py`，并有单测
- [ ] `Addapp.py: urls` 队列逻辑抽出 `services/add_app_service.py`，暴露 `AddAppQueue`（有单测）
- [ ] `TableEditor.save()` 行/列同步逻辑抽出 `ui/window/table_editor.py: _sync_rows_and_columns(model_df, data_df)`，纯函数，有单测
- [ ] `ondutySpawn` / `UserSettings.OndutySpawnWidget` 中值日生成逻辑合并到 `core/onduty.py`，Widget 只负责收集参数
- [ ] `Main._on_settings_changed` 的 `dict` 分发改为 `Literal` 常量 + 显式 `match`（Py3.10+）
- [ ] 删除未使用的 import（`flake8 --select=F401`）
- [ ] `dialogs/__init__.py` 中 `__all__` 与实际导出一致

**DoD**：
- [ ] `flake8 --select=F401,F811,F841 .` 返回 0
- [ ] 新增 `tests/unit/test_add_app_service.py`、`test_classlist_service.py`、`test_table_editor_sync.py`

### 7.8 用户手册（D13）

见 §10。

---

## 8. 测试计划

### 8.1 工具

- `pytest>=8`
- `pytest-qt>=4.4`（GUI 测试）
- `pytest-cov`
- `pytest-mock`

### 8.2 目录与命名

- `tests/unit/`：无 Qt 依赖（除 `Signal` 定义可容忍）
- `tests/gui/`：`pytest-qt` 的 `qtbot`
- 文件名 `test_<module>.py`，测试函数 `test_<behavior>_<condition>()`

### 8.3 必测范围

**纯逻辑（覆盖率目标 ≥ 80%）**：

| 模块 | 关键用例 |
|---|---|
| `core/onduty.py` | 空名单/空职务/负数参数抛 `ValueError`；`offset`/`stride` 边界；`shuffle` + `seed` 可复现；`skip_names` 过滤；分组模式空组过滤；`compute_stats` 对空单元格、含空格姓名、带职务切分正确 |
| `core/shape.py` | `reshapeRow` 边界（row=1、row>len、空 list）；`unpack_index` 各类 indexer |
| `core/weekday.py` | `1..7` 全映射；字符串输入；越界抛 `TypeError` |
| `data/sqlite_repo.py` | 增删改查；`get_classlist_for_date` 的 override 优先；`prune_onduty_before` 返回删除数 |
| `data/migrations/migrate.py` | v0 → 最新；重复 `apply_pending` 幂等；SQL 错误回滚 |
| `tools/pandas_qmodel.py` | `PandasQItemModel` 的 `to_data`（`header=True/False`、`extraHeader=True/False` 四象限）；`setData` 写入 DF 后 `dataChanged` 触发；`divideModel.update` 回写源 |
| `services/add_app_service.py` | 队列 `pop(0)` 语义；空队列 `finish` 行为 |
| `services/classlist_service.py` | override 存在 → 用 override；否则用 template；`weekday ≥ 6` 分支 |

**TableEditor GUI 测试（冒烟 + 核心交互，目标 8–12 个用例）**：

| 用例 | 断言 |
|---|---|
| 构造后行/列数正确 | `model.rowCount/columnCount` |
| 编辑单元格 → `is_saved=False` | `windowTitle` 含 `*` |
| 点"完成"→ `accept()` 且 `savepath` 写入 | 文件 mtime 更新；新 DF 内容正确 |
| 点"取消"→ `reject()` 且不写盘 | 文件 mtime 不变 |
| `_add_row` 追加一行 | 行数 +1，UI 固定尺寸更新 |
| `_delete_last_row` 至少保留 1 行 | 行数 1 时再删仍为 1 |
| `row_ops=True` 时按钮可见；`False` 时隐藏 | `isVisibleTo` |
| `OndutyContentDelegate.setEditorData` 按最后一个空格切分 | 含空格姓名正确回显 |
| 单元格编辑后 `setModelData` 写回 `"{name} {job}"` 格式 | DF 值正确 |

**不做**：
- `Main` 主窗口整体 GUI 测试（成本高，靠手工验收）
- 悬浮窗整体交互（只测位置计算 + 倒计时字符串生成两个纯函数）

### 8.4 CI 脚本（`pyproject.toml`）

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --cov=. --cov-report=term-missing --cov-omit='ui/**/.*_ui.py,ui/tokens/qss.py'"
qt_api = "pyside6"
```

---

## 9. 打包（Nuitka）

### 9.1 命令

```bash
python -m nuitka \
  --standalone \
  --enable-plugin=pyside6 \
  --include-data-dir=resources=resources \
  --include-data-dir=stylesheet=stylesheet \
  --include-data-dir=messages=messages \
  --include-data-dir=datas=datas \
  --windows-console-mode=disable \
  --windows-icon-from-ico=resources/icon.png \
  --output-dir=bin \
  main.py
```

### 9.2 路径核对

- `config/paths.py` 已区分 `RESOURCE_BASE`（打包后为 exe 目录）与 `DATA_BASE`（`%APPDATA%\ClassManager`）
- **只读资源**（`resources/stylesheet/messages/datas`）与 `--include-data-dir` 一致
- **可写数据**（`classmanager.db`、`message.html` 编辑后）写入 `DATA_BASE`

### 9.3 DoD

- [ ] 打包产物在干净机器（或新用户目录）能启动、能迁移、能读写数据
- [ ] 首次启动自动 `apply_pending` 建库
- [ ] 若检测到 `datas/` 下有 CSV 且 DB 不存在，**弹窗询问**是否迁移（默认 Yes）
- [ ] `bin/` 下产物总大小记录在文档（用于回归）

---

## 10. 用户使用说明书要求

**位置**：`docs/USER_MANUAL.md`

**目标读者**：班主任 / 班级管理员 / 值日班长（非技术用户）

**必含章节**：

1. 安装与首次启动
2. 界面总览（主窗口 / 悬浮窗 / 托盘）
3. 班级信息设置（短名、全名、学校名）
4. 学生名单管理（新增 / 导入 / 删除）
5. 课程与课表（周模板、临时课表、导入 Excel）
6. 值日生生成（名单模式 / 分组模式 / 预览 / 生成 / 直接编辑）
7. 应用链接管理（添加 / 删除 / 拖入文件）
8. 消息编辑（插入图片 / 导入 HTML / 字号）
9. 倒计时设置
10. 悬浮窗使用说明
11. 常见问题（数据存在哪、如何备份、如何恢复 CSV、迁移后旧 CSV 在哪）
12. 快捷键与手势（如有）

**形式**：纯 Markdown，先文字版；截图在 v1.1 补。所有涉及"去哪里点"的步骤必须给出**按钮文案原文**。

**DoD**：
- [ ] 一个从未用过本软件的人按文档能完成"从零到生成第一份值日表"
- [ ] 所有报错文案（§4.6）在 FAQ 里能被检索到

---

## 11. 3 天交付路线图

> 假设 AI 可并行执行，人工评审为瓶颈。**每日结束必须有可演示状态。**

### Day 1 — 迁移与基线

| 时段 | 任务 | 产出 | DoD |
|---|---|---|---|
| 上午 | PySide6 迁移 + `.ui` 重新生成 + `mainpage_rc.py` 重编译 | 可运行 PySide6 版本 | §7.1 DoD 全部 |
| 下午上半 | `config/` 拆分 + 去重；`jsonSpawn` 合并 | `config/defaults.py` 唯一 | §7.3 DoD |
| 下午下半 | 目录重构（§5.1）+ import 全量更新 | 新目录树可运行 | §7.2 DoD |
| 晚间 | pytest + pytest-qt 脚手架；补 `core/onduty.py` / `shape.py` / `weekday.py` 单测 | `tests/unit/` 初版 | 覆盖率 ≥ 80%（仅这三个模块） |

### Day 2 — 数据层与悬浮窗

| 时段 | 任务 | 产出 | DoD |
|---|---|---|---|
| 上午 | SQLite schema + migration 框架 + `SqliteRepository` | `data/` 可用 | §7.4 DoD（除业务接入） |
| 下午上半 | `tools/migrate_csv_to_sqlite.py` + 在 `datas/` 上跑通 | 迁移脚本 + 测试 | 行数一致 |
| 下午下半 | 业务接入 Repository（`loading.py`、`Addapp.py`、`UserSettings.py`） | 业务代码不再 `pd.read_csv` | `grep` 验证 |
| 晚间 | 悬浮窗 + 托盘 + `Main.changeEvent` 集成 | 最小化出悬浮窗 | §7.5 DoD（GUI 测试除外） |

### Day 3 — UI 优化、GUI 测试、文档、打包

| 时段 | 任务 | 产出 | DoD |
|---|---|---|---|
| 上午 | 颜色/字号 token + QSS 重写；`TableEditor`/`Message`/`UserSettings` 字号收敛；Tab 底部 | 视觉优化 | §7.6 DoD |
| 下午上半 | TableEditor GUI 测试（8–12 用例）+ 悬浮窗单测 | `tests/gui/` | §8.3 GUI 部分 DoD |
| 下午下半 | 代码冗余清理（§7.7 全部打勾） | — | §7.7 DoD |
| 晚间 | Nuitka 打包 + 用户手册 + 本文件更新 v1.1 | `bin/` + `docs/` | §9/§10 DoD |

### 若进度不足，按此顺序砍（保命优先级从高到低）

1. **保**：PySide6 可运行、SQLite 可用、主流程不回归
2. **保**：悬浮窗（用户明确要的功能）
3. 砍：TableEditor GUI 测试降至 3–5 个冒烟用例
4. 砍：用户手册写"简版"（只覆盖前 6 章）
5. 砍：`CsvRepository` 只保留迁移所需读方法
6. 砍：QSS token 生成器改为直接硬编码色值（注释标注来源）——**最后手段**
7. **绝不砍**：Repository 抽象（否则 Day 3 收尾时无法隔离数据访问回归）

---

## 12. 风险与开放问题

### 已知风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| Qt6 迁移期 `QTextEdit.toHtml()` 输出变化可能污染 `message.html` | 消息页显示错乱 | 迁移前备份；迁移后人工 diff |
| SQLite 在 `LoadApp` 后台线程并发写 | `database is locked` | 全局 `Lock` + WAL；写操作串行 |
| `TableEditor.save()` 行数差补齐逻辑无测试 | 编辑后数据丢失 | 抽出纯函数 + 单测（§7.7） |
| 悬浮窗在高 DPI 屏幕位置计算偏移 | 显示位置错 | 用 `availableGeometry()` 而非 `geometry()`；测试覆盖 |
| Nuitka 打包后 `_MEIPASS` 与 `DATA_BASE` 混淆 | 数据写不进或写错位置 | `config/paths.py` 已有区分；打包后人工核对 |
| 3 天工期 | 部分 DoD 未达成 | 按 §11 砍单顺序执行 |

### 需要在开工前 24h 内确认（如无异议按默认）

- [ ] **迁移后旧 CSV 是否保留在 `datas/`**（默认：保留，并在 `DATA_BASE/backup_csv/` 存档一份带时间戳副本）
- [ ] **悬浮窗是否需要"置顶"**（默认：是，`WindowStaysOnTopHint`）
- [ ] **多显示器场景**（默认：悬浮窗出现在主屏；若用户希望出现在"鼠标所在屏"，需在 v1.1 加设置）
- [ ] **`classlist_override` 是否支持"整周一次性覆盖"**（默认：v1 只支持单日覆盖，够用）
- [ ] **`kv` 表是否拆出 `settings` 与 `countdowns` 两行**（默认：整体存 `user_settings` 一行 JSON）

---

## 13. 附录

### 13.1 字号 token 完整表

见 §7.6 表格。

### 13.2 颜色 token 完整表

见 §2 "关于深红色" 表格。

### 13.3 QSS 生成示例（推荐）

```python
# ui/tokens/qss.py
COLORS = {...}
def build_stylesheet() -> str:
    return f"""
    QPushButton {{
        background-color: {COLORS['primary']};
        color: white;
    }}
    ...
    """
```

- 启动时 `app.setStyleSheet(build_stylesheet())`
- 各组件仍可通过 `setQss()` 局部覆盖，但**禁止**在局部 QSS 里硬编码色值

### 13.4 迁移脚本输出样例


[1/6] 名单.csv → students: 42 行
[2/6] 课程单.csv → courses: 12 行
[3/6] 课表.csv → classlist_template: 8×5 单元格
[4/6] 未来值日.csv → onduty: 110 天 × 5 行 = 550 行
[5/6] 应用路径.csv → apps: 6 行
[6/6] settings.json + data.json → kv: 2 行
Done in 0.42s. DB size: 148 KB
Backup CSV → C:\Users\<user>\AppData\Roaming\ClassManager\backup_csv\20261030_143022\


### 13.5 术语表

| 词 | 含义 |
|---|---|
| 周模板 | `classlist_template`，周一到周五的固定课表 |
| 临时课表 | `classlist_override`，某一天的覆盖 |
| 值日 slot | 每日值日的第 0–4 位（对应 5 个职务） |
| `kv` | 通用键值表，存 settings / last_login |

---

## 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1.0-draft | 2026-10-30 | 初稿，基于决策 D1–D14 |
| v1.1 | TBD | 记录实际落地情况与偏差 |
