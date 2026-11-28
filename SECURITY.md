# 安全策略

> 中文 ｜ [English](#english)

## 支持范围

| 版本 | 是否接受安全报告 |
|---|---|
| `1.0.x`（最新补丁） | ✅ |
| 更早的 `0.x` / `v1.0.0` | ❌ 请先升级 |

## 怎么报告

**请不要用公开 issue 报安全问题。**

用 GitHub 的私有渠道：
[新建安全公告](https://github.com/2tn9kfsmkm-art/open4Class/security/advisories/new)
（仓库页面 → Security → Report a vulnerability）。

方便的话请包含：

- 受影响的版本（安装包文件名或 `git describe --tags`）
- 复现步骤，越具体越好
- 影响范围：能读到什么、能改什么、需不需要本机管理员权限
- 有没有 PoC（可以只描述思路，不必给完整代码）

这是课余项目，通常 **几天内** 会回，节假日可能更慢；如果一周没动静可以再 ping 一次。

## 威胁模型

先说明这个程序**是什么**，很多「漏洞」在它的形态下不成立：

- 纯本地单机应用，**不联网、没有服务器、没有账号体系**，不上传任何数据。
- 没有自动更新，安装包由人手动下载、双击安装。
- 安装在 `%LOCALAPPDATA%\ClassManager`（当前用户可写），数据在 `%APPDATA%\ClassManager`。
- 只运行在当前登录用户权限下，不请求管理员。

## 我们关心的

- **分发包被替换或篡改**：构造一个假的 `ClassManager-Setup-*.exe`。
  （程序没有代码签名，这是已知且已声明的限制，但仍欢迎报告更隐蔽的手法。）
- **导入路径处理**：Excel/CSV、分组、云端导入时是否可能写到预期目录之外，
  或读取不该读的文件。
- **消息编辑器的 HTML 处理**：粘贴/导入的 HTML、图片是否可能被执行脚本、
  触发外链请求或读到本地文件。
- **学生数据泄露**：日志、备份、导出的文件里是否可能意外包含姓名、照片，
  或把它们写到了会被同步/上传的位置。
- **崩溃或异常处理泄漏信息**：错误弹窗、`debug.log` 是否会把敏感路径或数据带给看屏幕的人。

## 一般不认为是本项目的安全问题

- 需要先拿到本机管理员权限 / 物理接触设备才能实施的攻击。
- 第三方依赖（Qt、pandas、numpy）的通用 CVE，但本程序是本地数据处理、
  不解析不可信网络输入，实际不可触发的情况（能触发的话请说明利用路径）。
- 未签名导致的 SmartScreen 提示——这是已知限制，见 [README](README.md)。
- 别人能读 `%APPDATA%` 下的数据：同一 Windows 用户本来就能读自己的文件。

## 我们会怎么处理

确认后按严重程度决定：紧急的打 `v1.0.x` 补丁并在 Release 说明里致谢（除非你要求匿名），
不紧急的排进下个版本。修复前请勿公开细节。

---

# English

> [中文](#安全策略) ｜ English

## Supported versions

| Version | Accepts security reports |
|---|---|
| `1.0.x` (latest patch) | ✅ |
| Older `0.x` / `v1.0.0` | ❌ please upgrade first |

## How to report

**Please do not report security issues in a public issue.**

Use GitHub's private channel:
[open a security advisory](https://github.com/2tn9kfsmkm-art/open4Class/security/advisories/new)
(repository page → Security → Report a vulnerability).

If possible, include:

- The affected version (installer file name or `git describe --tags`).
- Reproduction steps, as specific as you can.
- Impact: what can be read, what can be changed, and whether local administrator
  rights are required.
- A proof of concept if you have one (a description of the approach is fine).

This is a spare-time project; you can normally expect a reply **within a few
days**, slower during holidays. Ping again if a week passes with no response.

## Threat model

First, what this program **is** — many "vulnerabilities" don't apply to its shape:

- A purely local desktop app. **No network access, no server, no accounts**; no
  data is uploaded anywhere.
- No auto-update. Installers are downloaded and double-clicked by hand.
- Installed to `%LOCALAPPDATA%\ClassManager` (writable by the current user); data
  lives in `%APPDATA%\ClassManager`.
- Runs with the logged-in user's privileges and never requests administrator.

## What we care about

- **Tampered distribution packages**: a fake `ClassManager-Setup-*.exe`.
  (The app is unsigned — a known and disclosed limitation — but subtler tricks
  are still worth reporting.)
- **Import path handling**: whether Excel/CSV, group and cloud imports can write
  outside the intended directory or read unintended files.
- **HTML handling in the message editor**: whether pasted/imported HTML or images
  can execute scripts, trigger external requests, or read local files.
- **Student data leaks**: whether logs, backups or exports can accidentally
  contain names and photos, or write them somewhere that gets synced or uploaded.
- **Information leaked through crash handling**: whether error dialogs or
  `debug.log` expose sensitive paths or data to whoever can see the screen.

## Usually not considered security issues here

- Attacks that require local administrator rights or physical access first.
- Generic CVEs in third-party dependencies (Qt, pandas, numpy) that this program
  cannot actually trigger, since it processes local data and parses no untrusted
  network input (if you can trigger one, please show the path).
- SmartScreen warnings caused by the missing code signature — a known limitation,
  see [README](README.md).
- Other people reading data under `%APPDATA%`: the same Windows user can already
  read their own files.

## What happens next

Severity decides the handling: urgent fixes ship as a `v1.0.x` patch with credit
in the release notes (unless you prefer to stay anonymous); others go into the
next version. Please keep details private until a fix is out.
