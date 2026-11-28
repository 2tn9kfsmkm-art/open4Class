# 参与开发

> 中文 ｜ [English](#english)

感谢愿意帮忙。这个项目由几名高中生在课余维护，节奏不快，但发出去的每个版本
都有班级在用，所以对「别把别人的数据弄坏」看得比「功能多」更重。

先读一遍 [README.md](README.md)；使用者请看 [user-manual.pdf](user-manual.pdf)（10 页手册）。

## 报告问题之前

1. 翻一下 [user-manual.pdf](user-manual.pdf) 第 8 章的常见问题。
2. 看一眼 `%APPDATA%\ClassManager\debug.log` 的最后几十行。
3. 确认不是「已经有实例在跑」——程序是单实例的，第二次双击只会把窗口叫到前台。

提 issue 时可以用模板，**把真实学生姓名打码或替换成假名**。

## 分支与发版

| 分支 | 用途 | 允许什么 |
|---|---|---|
| `main` | 线上稳定版，用户装的就是它 | **修复 bug，以及影响小、经过测试的改进**（小功能、文案、交互微调） |
| `dev` | 下一个大版本（v2.0） | 结构性改动：本地转云端、目录重构、界面大改 |
| `fix/*` | 单个 bug 的临时分支 | 从 `main` 切出，修完合回 `main` 后删除 |

判断一次改动该进哪个分支：

| 情况 | 去处 |
|---|---|
| 修 bug、改错字、调间距、加一个不改变数据结构的按钮 | `main`，打 `v1.0.x` |
| 新功能但只改局部、不动数据库结构、能完整测一遍 | `main` 也可以，打 `v1.0.x` 或 `v1.x.0` |
| 改数据库表结构、重建目录、换 UI 框架、动首次向导流程（需要和开发者沟通） | `dev`，进 `v2.0` |

> v2.0 与 v1.0 预期会有较大差别，所以凡是「不好回退、影响面铺开」的改动，
> 一律放 `dev`，不要在 `main` 上试。

- 发版时由维护端打 tag（`v1.0.x` / `v2.0.0`），**PR 里不要自己打 tag**。
- 打包（Nuitka）和做安装包（Inno Setup）由维护端统一执行，
  **不要把 `build/`、`installer/` 的产物提交进仓库**。

> 更细的分工说明和日常命令见 `dev` 分支上的 `docs/WORKFLOW.md`。

## 提交前

```powershell
python -m pytest -q          # 必须全过
```

- 改了界面：照 `docs/SMOKE.md` 里相关条目手工走一遍，并在 PR 里写清走了哪几条。
- 改了数据层 / 迁移：说明老库能不能平滑升级，以及回退办法。
- 改了打包脚本或 `installer.iss`：单独提交，并说明影响（两边都在用）。
- 提交信息用 `type(scope): 中文摘要`，例如 `fix(启动): 修复 _QTimer 未定义`。
  类型常用 `feat` / `fix` / `docs` / `build` / `chore` / `refactor` / `test`。

## 代码约定

- Python 3.13 + PySide6 6.12 + pandas 3。不要引入需要编译的新依赖，除非必要。
- 纯逻辑放 `core/`，**不允许 import Qt**；界面放 `ui/`，数据访问放 `data/`。
- 线程边界：`Chain.load/input/process` 在后台线程，禁止碰任何 `QWidget`；
  要更新界面必须走 `Signal`。
- 中文界面文案保持现有风格：短句、动词开头、不堆术语。

## 许可

提交即表示同意你的贡献以 [GPL-3.0](LICENSE) 发布。

---

# English

> [中文](#参与开发) ｜ English

Thanks for helping. This project is maintained by a few high-school students in
their spare time. The pace is slow, but every release is used by real classes,
so "don't break other people's data" matters more than "more features".

Read [README.md](README.md) first; for end users see
[user-manual.pdf](user-manual.pdf) (a 10-page manual, in Chinese).

## Before reporting a problem

1. Check the FAQ in chapter 8 of [user-manual.pdf](user-manual.pdf).
2. Look at the last few dozen lines of `%APPDATA%\ClassManager\debug.log`.
3. Make sure there isn't already an instance running — the app is
   single-instance; a second launch only brings the existing window forward.

Please use the issue template, and **redact or replace real student names**.

## Branches and releases

| Branch | Purpose | Allowed |
|---|---|---|
| `main` | The stable release users install | **Bug fixes, plus small, well-tested improvements** (small features, wording, minor UI tweaks) |
| `dev` | The next major version (v2.0) | Cloud stroages: data format, directory layout, large UI reworks |
| `fix/*` | Temporary branch for a single fix | Branch off `main`, merge back, then delete |

Where a change belongs:

| Situation | Where |
|---|---|
| Fix a bug, fix a typo, adjust spacing, add a button that doesn't change the data model | `main`, release as `v1.0.x` |
| A new feature that is local, doesn't touch the database schema, and can be tested end to end | `main` is fine, release as `v1.0.x` |
| Change the database schema, restructure directories, rework the UI framework or the first-run wizard ( You need to tell the owner before requesting a merge or push ) | `dev`, goes into `v2.0` |

> v2.0 is expected to differ substantially from v1.0, so anything hard to roll
> back or wide-reaching goes to `dev` — don't experiment on `main`.

- Maintainers create tags (`v1.0.x` / `v2.0.0`); **do not create tags in a PR**.
- Packaging (Nuitka) and building the installer (Inno Setup) are done by the
  maintainer, not by contributors. **Never commit `build/` or `installer/`
  artifacts.**

## Before committing

```powershell
python -m pytest -q          # must pass
```

- UI changes: walk the relevant items in `docs/SMOKE.md` and list which ones in the PR.
- Data layer / migration changes: state whether older databases upgrade
  cleanly and how to roll back.
- Changes to the build script or `installer.iss`: commit separately and explain
  the impact (both sides use them).
- Commit messages: `type(scope): summary`, e.g. `fix(启动): 修复 _QTimer 未定义`.
  Common types: `feat` / `fix` / `docs` / `build` / `chore` / `refactor` / `test`.

## Code conventions

- Python 3.13 + PySide6 6.12 + pandas 3. Avoid new dependencies that need
  compilation unless necessary.
- Pure logic goes in `core/` and **must not import Qt**; UI in `ui/`, data access
  in `data/`.
- Threading: `Chain.load/input/process` run on worker threads and must never
  touch a `QWidget`; UI updates go through `Signal`.
- Chinese UI copy keeps the existing style: short sentences, verb-first, no jargon.

## License

By submitting a contribution you agree it is released under
[GPL-3.0](LICENSE).
