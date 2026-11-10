# 云端导入（传输账号）

首次使用向导的「欢迎」页有一个 **从云端导入…** 按钮：输入老师给的
**6 位传输账号 + 12 位密码**，就能把网页端填好的名单、课表、作息、值日规则
一次性取回来，填进向导各页，不用手工重录。

## 数据和密码从哪来

1. 老师在 <https://class-manager-3ke.pages.dev/setup.html> 填好班级数据；
2. 页面生成一组 **传输账号 + 传输密码**（24 小时后失效）；
3. 把这组账号密码发给需要导入的电脑；
4. 打开 ClassManager → 向导首页 →「从云端导入…」→ 输入 → 逐页确认 → 完成。

账号在 24 小时内可以重复导入（换电脑、重装都行）；过期后返回 410，需要老师重新生成。

## 实现结构

| 文件 | 职责 |
|---|---|
| `services/class_api.py` | **vendor**：从 class-setup 仓库复制的单文件协议实现（PBKDF2 + AES-GCM + Bearer 鉴权） |
| `services/cloud_import.py` | `fetch_preview()` 拉取并转成 `ImportPreview`；`parse_payload()` 做字段校验与规整 |
| `ui/window/cloud_import_dialog.py` | 输入服务器/账号/密码的对话框；拉取在 `QThread` 里跑，失败就地红字提示 |
| `ui/window/setup_wizard.py` | 「欢迎」页的入口卡片 + `SetupWizard.apply_cloud_preview()` 把数据填进各页 |

导入**只填表单**，不直接写库：仍然点「完成」才走 `bootstrap.save_all()`，
所以覆盖前备份、校验、落盘路径都沿用原实现。

## 协议

```
GET {server}/api/class/{account}
Authorization: Bearer {authKey}
Accept: application/json

authKey = base64url(HMAC-SHA256(password, "class-setup-auth-v1"))
blob    = base64(salt[16] || iv[12] || AES-256-GCM(
              PBKDF2-HMAC-SHA256(password, salt, 600000, 32), payload))
```

响应：`encryptedBlob`、`revision`（恒为 1）、`updatedAt`、`kind`（`transfer`）、`expiresAt`。

解密后的 payload：

| 字段 | 内容 |
|---|---|
| `v` | 版本，当前 1 |
| `info` | `school_name` / `class_full_name` / `class_short_name` |
| `names` | 学生名单（顺序即值日顺序） |
| `classlist` | `{columns[5], rows[][5]}` 或纯 `rows` |
| `lesson_times` | `{"1".."5": [["07:40","08:20"], …]}` |
| `onduty` | `mode`（`sequence`/`groups`/`skip`）、`start`、`weeks`、`jobs`、`skip_weekend`、`daily`、`group_count`、`groups` |

## 安全约定

- 密码只在内存里用一次，**不写配置、不进日志**；只有服务器地址会被记住（`settings.json` 的 `cloud_server`）。
- TLS 默认校验；本地 wrangler 调试可以填 `http://127.0.0.1:8788`。
- 传输账号本身等于「24 小时内的全部班级数据」，只发给需要的电脑。

## 常见错误

| 提示 | 处理 |
|---|---|
| 账号或密码不正确（401） | 确认 6 位账号、12 位密码；`O→0`、`I/L→1` 只对账号生效 |
| 云端没有这个传输账号（404） | 过期 7 天后会被清理，让老师重新生成 |
| 传输账号已过期（410） | 超过 24 小时，重新生成 |
| 无法连接云端 | 检查网络 / 服务器地址；自建部署注意 http 与端口 |
| 云端数据里没有学生名单 / 课程表 | 服务端 payload 不完整，多半是旧版网页端 |
| 云端名单存在重名 | 先让老师在网页端改掉重名 |

## 维护注意

`services/class_api.py` 是**拷贝**，不要在这里改协议。协议要变时：

1. 先改 `class-setup/tools/class_api_tool/class_api.py` 并跑它的测试；
2. 把文件整体覆盖到 `services/class_api.py`（保留文件头的来源注释）；
3. 跑 `python -m pytest tests/unit/test_cloud_import.py tests/gui/test_setup_wizard.py -q`。
