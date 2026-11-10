# ============================================================================
# vendor: 本文件从 class-setup 仓库原样复制，请勿在这里改协议实现。
#   repo   : https://github.com/2tn9kfsmkm-art/class-setup
#   file   : tools/class_api_tool/class_api.py
#   commit : 1d8920d（含 2026-11-10 的传输账号收缩改动）
# 协议要变，先在 class-setup 改并跑它的测试，再整体同步覆盖本文件；
# 同步后跑 python -m pytest tests/unit/test_cloud_import.py 验证。
# ============================================================================
"""班级云端只读 API 工具（单文件，无 GUI）。

给 open4Class / 其他 Python 客户端直接 import，也可以命令行运行。

协议（与服务端、网页端一致）::

    authKey = base64url(HMAC-SHA256(password, "class-setup-auth-v1"))
    blob    = base64(salt[16] || iv[12] || AES-256-GCM(
                  PBKDF2-HMAC-SHA256(password, salt, 600000, 32), payload))

    GET /api/class/<account>
        Authorization: Bearer <authKey>

用法::

    # 命令行：打印 {meta, payload}
    python class_api.py --server https://class-manager-3ke.pages.dev \
        --account ABC-DEF --password XXXX-XXXX-XXXX

    # 只输出 payload
    python class_api.py --account ABC-DEF --password ... --raw

    # 写入文件
    python class_api.py --account ABC-DEF --password ... --out class.json

    # 只检查服务端
    python class_api.py --health

    # 代码里
    from class_api import fetch_class
    data = fetch_class("https://...", "ABC-DEF", "XXXX-XXXX-XXXX")
    print(data.meta.kind, data.payload["names"])

安全说明：

- 密码不会上传；服务端只看到 authKey 的 SHA-256 和密文。
- 本文件不写任何日志到磁盘；命令行请在交互提示下输入密码，
  避免 `--password` 留在 shell 历史/进程列表。
- 生产环境保持 TLS 校验；`--no-verify-tls` 只用于本地自签证书调试。
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SERVER = "https://class-manager-3ke.pages.dev"
AUTH_MESSAGE = b"class-setup-auth-v1"
PBKDF2_ITERATIONS = 600_000
MAX_BLOB = 700 * 1024
USER_AGENT = "ClassApiTool/1.0 (+class-setup)"

__all__ = [
    "DEFAULT_SERVER", "MAX_BLOB", "ApiToolError", "NetworkError", "HttpError",
    "DecryptError", "ResponseFormatError", "ResponseMeta", "ClassData",
    "normalize_account", "normalize_password", "format_account",
    "format_password", "normalize_server_url", "derive_auth_key",
    "decrypt_blob", "encrypt_blob", "parse_iso_datetime",
    "format_local_datetime", "remaining_text", "fetch_class", "check_health",
    "main",
]


# ---------------------------------------------------------------- 异常
class ApiToolError(Exception):
    """所有可展示错误的基类。"""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str = "",
        detail: str = "",
        elapsed_ms: int | None = None,
        raw: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.detail = detail
        self.elapsed_ms = elapsed_ms
        self.raw = raw or {}


class NetworkError(ApiToolError):
    """DNS / 连接 / 超时 / TLS 失败。"""


class HttpError(ApiToolError):
    """服务端返回了 4xx/5xx。"""


class DecryptError(ApiToolError):
    """密文解不开（密码错误或数据损坏）。"""


class ResponseFormatError(ApiToolError):
    """返回的不是预期 JSON / 缺字段 / payload 不是对象。"""


# ---------------------------------------------------------------- 归一化
def normalize_account(value: Any) -> str:
    """6 位账号：转大写、去分隔符、O→0、I/L→1。"""
    text = str(value or "").upper()
    text = "".join(ch for ch in text if ch.isascii() and ch.isalnum())
    return text.replace("O", "0").replace("I", "1").replace("L", "1")


def normalize_password(value: Any) -> str:
    """密码只去分隔符 + 转大写，不做 O/I/L 映射（否则解密失败）。"""
    text = str(value or "").upper()
    return "".join(ch for ch in text if ch.isascii() and ch.isalnum())


def format_account(value: Any) -> str:
    text = normalize_account(value)
    return f"{text[:3]}-{text[3:]}" if len(text) > 3 else text


def format_password(value: Any) -> str:
    text = normalize_password(value)
    return "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def normalize_server_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        text = DEFAULT_SERVER
    if "://" not in text:
        text = "https://" + text
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ApiToolError("服务器地址必须是 http:// 或 https:// 开头的完整地址")
    return text.rstrip("/")


# ---------------------------------------------------------------- 加密 / 鉴权
def derive_auth_key(password: str) -> str:
    """由密码派生 Bearer token（base64url，无 padding）。"""
    digest = hmac.new(
        normalize_password(password).encode("utf-8"),
        AUTH_MESSAGE,
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _derive_key(password: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    ).derive(normalize_password(password).encode("utf-8"))


def decrypt_blob(blob_b64: str, password: str) -> dict:
    """解密网页端/传输账号的 blob，返回 payload dict。"""
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        raw = base64.b64decode(str(blob_b64), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ResponseFormatError("云端 encryptedBlob 不是有效的 Base64") from exc
    if len(raw) < 16 + 12 + 16:
        raise ResponseFormatError("云端 encryptedBlob 长度不足，可能已损坏")

    salt, iv, ciphertext = raw[:16], raw[16:28], raw[28:]
    try:
        key = _derive_key(password, salt)
        plain = AESGCM(key).decrypt(iv, ciphertext, None)
    except InvalidTag as exc:
        raise DecryptError(
            "密码错误，无法解密云端数据；请确认输入的是这个账号对应的密码"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise DecryptError(f"解密失败：{exc}") from exc

    try:
        payload = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResponseFormatError("解密后的内容不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise ResponseFormatError("解密后的 payload 不是 JSON 对象")
    return payload


def encrypt_blob(payload: dict | str, password: str) -> str:
    """加密 payload（测试/生成 fixture 用；正常客户端不上传）。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plain = payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"))
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = _derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(iv, plain.encode("utf-8"), None)
    return base64.b64encode(salt + iv + ciphertext).decode("ascii")


# ---------------------------------------------------------------- 结果模型
@dataclass(frozen=True)
class ResponseMeta:
    status: int
    elapsed_ms: int
    bytes: int
    revision: int
    updated_at: str
    kind: str
    account: str
    expires_at: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def kind_label(self) -> str:
        if self.kind == "transfer":
            return "传输账号（24 小时有效）"
        return "未知类型（服务端可能是旧版本）"


@dataclass(frozen=True)
class ClassData:
    meta: ResponseMeta
    payload: dict


# ---------------------------------------------------------------- 时间
def parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_local_datetime(value: str) -> str:
    moment = parse_iso_datetime(value)
    if not moment:
        return str(value or "")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def remaining_text(expires_at: str) -> tuple[str, bool]:
    """返回 (剩余时间文案, 是否已过期)。空值返回 ("", False)。"""
    moment = parse_iso_datetime(expires_at)
    if not moment:
        return "", False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    seconds = int((moment - datetime.now(timezone.utc)).total_seconds())
    if seconds <= 0:
        return "已过期", True
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} 小时 {minutes} 分", False
    if minutes:
        return f"{minutes} 分 {secs} 秒", False
    return f"{secs} 秒", False


# ---------------------------------------------------------------- HTTP
def _tls_context(verify_tls: bool) -> ssl.SSLContext:
    if verify_tls:
        return ssl.create_default_context()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _build_opener(*, verify_tls: bool, proxy: str) -> urllib.request.OpenerDirector:
    handlers: list[Any] = [urllib.request.HTTPSHandler(context=_tls_context(verify_tls))]
    proxy = str(proxy or "").strip()
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def _network_error(exc: BaseException, timeout: float) -> NetworkError:
    reason = getattr(exc, "reason", exc)
    text = str(reason)
    if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in text.upper():
        return NetworkError(
            "TLS 证书校验失败。如果服务器使用自签证书，可关闭 TLS 校验，"
            f"但仅限本地调试。\n{text}"
        )
    if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in text.lower():
        return NetworkError(f"连接超时（{timeout:g} 秒），请检查网络或稍后重试")
    if isinstance(reason, socket.gaierror):
        return NetworkError(f"无法解析服务器地址：{text}")
    if isinstance(reason, ConnectionRefusedError) or "refused" in text.lower():
        return NetworkError(f"连接被拒绝：{text}")
    return NetworkError(f"无法连接服务器：{text}")


def _open(
    url: str,
    headers: dict[str, str],
    *,
    timeout: float,
    verify_tls: bool,
    proxy: str,
    retries: int,
) -> tuple[int, bytes, int]:
    """返回 (status, body, elapsed_ms)；4xx/5xx 也按正常结果返回，由调用方解释。"""
    opener = _build_opener(verify_tls=verify_tls, proxy=proxy)
    attempts = max(0, int(retries)) + 1
    last_error: BaseException | None = None

    for attempt in range(attempts):
        request = urllib.request.Request(url, headers=headers, method="GET")
        started = time.monotonic()
        try:
            with opener.open(request, timeout=timeout) as response:
                body = response.read()
                elapsed = int((time.monotonic() - started) * 1000)
                return int(response.status), body, elapsed
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001
                body = b""
            elapsed = int((time.monotonic() - started) * 1000)
            if 500 <= int(exc.code) < 600 and attempt < attempts - 1:
                last_error = exc
                time.sleep(0.5 * (attempt + 1))
                continue
            return int(exc.code), body, elapsed
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise _network_error(exc, timeout) from exc

    raise _network_error(last_error or RuntimeError("unknown network error"), timeout)


def _decode_json(body: bytes, *, status: int, elapsed_ms: int) -> dict:
    text = body.decode("utf-8", "replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        snippet = " ".join(text.strip().split())[:160]
        raise ResponseFormatError(
            f"服务器返回的不是 JSON（HTTP {status}）。Functions 可能没有部署成功。"
            + (f"\n返回片段：{snippet}" if snippet else ""),
            status=status,
            elapsed_ms=elapsed_ms,
        ) from exc
    if not isinstance(data, dict):
        raise ResponseFormatError(
            f"服务器返回的 JSON 不是对象（HTTP {status}）",
            status=status,
            elapsed_ms=elapsed_ms,
        )
    return data


def _http_error_message(status: int, data: dict) -> str:
    code = str(data.get("error") or "")
    message = str(data.get("message") or "").strip()
    detail = str(data.get("detail") or "").strip()

    if status == 401:
        return "账号或密码错误（401）。请确认账号是 6 位、密码是这个账号对应的密码。"
    if status == 403:
        return "没有权限（403）" + (f"：{message}" if message else "")
    if status == 404:
        return "云端没有这个传输账号（404），可能已过期并被清理。"
    if status == 409:
        return "云端状态冲突（409），请稍后重试"
    if status == 410:
        return "传输账号已过期（410），请在网页重新生成"
    if status == 413:
        return "云端数据太大（413）"
    if status == 429:
        return "请求过于频繁，请稍后再试（429）"
    if status >= 500:
        if code == "db_binding_missing":
            return "云端没有绑定 D1 数据库（db_binding_missing）"
        if code == "db_not_ready":
            return "云端数据库还没初始化或查询失败（db_not_ready）"
        if code:
            return f"云端服务器错误（{status}）：{code}" + (
                f"；{detail}" if detail else "")
        return f"云端服务器错误（{status}），请稍后再试"
    suffix = f"：{message}" if message else ""
    return f"云端请求失败（{status}）{suffix}"


def _request_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    verify_tls: bool,
    proxy: str,
    retries: int,
) -> tuple[dict, int, int, int]:
    """返回 (data, status, elapsed_ms, bytes)。4xx/5xx 抛 HttpError。"""
    status, body, elapsed = _open(
        url,
        headers,
        timeout=timeout,
        verify_tls=verify_tls,
        proxy=proxy,
        retries=retries,
    )
    data = _decode_json(body, status=status, elapsed_ms=elapsed)
    if status >= 400:
        raise HttpError(
            _http_error_message(status, data),
            status=status,
            code=str(data.get("error") or ""),
            detail=str(data.get("detail") or ""),
            elapsed_ms=elapsed,
            raw=data,
        )
    return data, status, elapsed, len(body)


def _sanitize_response(data: dict) -> dict:
    """去掉大字段，保留可展示的响应元数据。"""
    clean = {key: value for key, value in data.items() if key != "encryptedBlob"}
    blob = data.get("encryptedBlob")
    if isinstance(blob, str):
        clean["encryptedBlobLength"] = len(blob)
    return clean


def fetch_class(
    server_url: str,
    account: str,
    password: str,
    *,
    timeout: float = 25.0,
    verify_tls: bool = True,
    proxy: str = "",
    retries: int = 0,
) -> ClassData:
    """拉取并解密一个账号；网络/鉴权/解密/格式错误都抛 ApiToolError 子类。"""
    account = normalize_account(account)
    password = normalize_password(password)
    if len(account) != 6:
        raise ApiToolError("班级账号应为 6 位（例如 ABC-DEF）")
    if not password:
        raise ApiToolError("请填写班级密码")

    base = normalize_server_url(server_url)
    auth_key = derive_auth_key(password)
    url = f"{base}/api/class/{account}"

    data, status, elapsed, size = _request_json(
        url,
        headers={
            "Authorization": f"Bearer {auth_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-store",
        },
        timeout=timeout,
        verify_tls=verify_tls,
        proxy=proxy,
        retries=retries,
    )

    blob = data.get("encryptedBlob")
    if not isinstance(blob, str) or not blob:
        raise ResponseFormatError(
            "云端没有返回 encryptedBlob",
            status=status,
            elapsed_ms=elapsed,
            raw=_sanitize_response(data),
        )
    if len(blob) > MAX_BLOB:
        raise ResponseFormatError(
            f"云端 encryptedBlob 超过上限（{len(blob)} > {MAX_BLOB}）",
            status=status,
            elapsed_ms=elapsed,
            raw=_sanitize_response(data),
        )

    payload = decrypt_blob(blob, password)

    kind = str(data.get("kind") or "").strip() or "transfer"

    meta = ResponseMeta(
        status=status,
        elapsed_ms=elapsed,
        bytes=size,
        revision=int(data.get("revision") or 1),
        updated_at=str(data.get("updatedAt") or ""),
        kind=kind,
        account=str(data.get("account") or account),
        expires_at=str(data.get("expiresAt") or ""),
        raw=_sanitize_response(data),
    )
    return ClassData(meta=meta, payload=payload)


def check_health(
    server_url: str,
    *,
    timeout: float = 15.0,
    verify_tls: bool = True,
    proxy: str = "",
    retries: int = 0,
) -> dict:
    """GET /api/health；返回原始 dict（含 ok/tables/missing/...）。"""
    base = normalize_server_url(server_url)
    data, _, _, _ = _request_json(
        f"{base}/api/health",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-store",
        },
        timeout=timeout,
        verify_tls=verify_tls,
        proxy=proxy,
        retries=retries,
    )
    return data


# ---------------------------------------------------------------- 命令行
def _json_text(value: Any, compact: bool = False) -> str:
    if compact:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(value, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="班级云端只读 API 工具（无 GUI）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python class_api.py --health\n"
            "  python class_api.py --account ABC-DEF\n"
            "  python class_api.py --account ABC-DEF --password XXXX-XXXX-XXXX --raw\n"
        ),
    )
    parser.add_argument("--server", default=DEFAULT_SERVER, help="服务器地址")
    parser.add_argument("--account", help="6 位班级账号（或 24h 传输账号）")
    parser.add_argument("--password", help="12 位密码；不传则交互输入")
    parser.add_argument("--health", action="store_true", help="只检查 /api/health")
    parser.add_argument("--timeout", type=float, default=25.0, help="超时秒数，默认 25")
    parser.add_argument("--retries", type=int, default=0, help="网络/5xx 重试次数，默认 0")
    parser.add_argument("--proxy", default="", help="HTTP 代理，如 http://127.0.0.1:7890")
    parser.add_argument("--no-verify-tls", action="store_true",
                        help="关闭 TLS 校验（仅本地自签证书调试）")
    parser.add_argument("--out", help="把 {meta, payload} 写入 JSON 文件")
    parser.add_argument("--raw", action="store_true", help="只输出 payload，不输出 meta")
    parser.add_argument("--compact", action="store_true", help="JSON 不缩进")
    args = parser.parse_args(argv)

    common = {
        "timeout": args.timeout,
        "verify_tls": not args.no_verify_tls,
        "proxy": args.proxy,
        "retries": args.retries,
    }

    try:
        if args.health:
            data = check_health(args.server, **common)
            print(_json_text(data, args.compact))
            return 0 if data.get("ok") else 2

        if not args.account:
            parser.error("除非使用 --health，否则必须提供 --account")
        password = args.password
        if not password:
            import getpass
            password = getpass.getpass("班级密码: ")
        if not password:
            parser.error("密码不能为空")

        data = fetch_class(args.server, args.account, password, **common)
        meta = asdict(data.meta)

        print(
            f"HTTP {data.meta.status} · {data.meta.elapsed_ms} ms · "
            f"revision {data.meta.revision} · {data.meta.kind_label}",
            file=sys.stderr,
        )
        if data.meta.expires_at:
            print(
                f"有效期至 {format_local_datetime(data.meta.expires_at)}"
                f"（{remaining_text(data.meta.expires_at)[0]}）",
                file=sys.stderr,
            )
            print("提示：云端只保留这一份，建议用 --out 落盘备份", file=sys.stderr)

        if args.out:
            target = Path(args.out)
            try:
                target.write_text(
                    _json_text({"meta": meta, "payload": data.payload}, args.compact),
                    encoding="utf-8",
                )
            except OSError as exc:
                print(f"写入失败：{exc}", file=sys.stderr)
                return 1
            print(f"已写入 {target}", file=sys.stderr)
        else:
            value = data.payload if args.raw else {"meta": meta, "payload": data.payload}
            print(_json_text(value, args.compact))
        return 0
    except ApiToolError as exc:
        print(f"错误：{exc.message}", file=sys.stderr)
        if exc.detail:
            print(f"详情：{exc.detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
