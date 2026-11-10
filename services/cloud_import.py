"""把云端传输账号里的数据，规整成首次向导能直接填进去的结构。

分工：
- 网络与解密交给 ``services.class_api``（从 class-setup vendor 来的单文件实现）；
- 这里只做「payload → 向导数据结构」的校验与规整，不联网、不碰 UI。

云端 payload 的字段（class-setup 的 ``public/app.js`` 生成）::

    {v, info, names, classlist, lesson_times, onduty}

其中 ``classlist`` 可能是 ``{columns, rows}`` 也可能是纯 ``rows``；
``lesson_times`` 的星期键可能是字符串；``onduty`` 允许只有 ``mode``（skip 模式）。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime

from pandas import DataFrame

from config import CLASS_WEEKDAYS
from services.class_api import (
    DEFAULT_SERVER,
    ApiToolError,
    DecryptError,
    HttpError,
    NetworkError,
    ResponseFormatError,
    fetch_class,
    normalize_account,
    normalize_password,
)

__all__ = [
    'DEFAULT_SERVER',
    'CloudImportError',
    'ImportPreview',
    'ONDUTY_MODES',
    'fetch_preview',
    'format_expiry',
    'parse_payload',
    'summary_text',
]

WEEKDAY_COUNT = len(CLASS_WEEKDAYS)
ONDUTY_MODES = {'sequence': 0, 'groups': 1, 'skip': 2}


class CloudImportError(Exception):
    """导入失败；``str(exc)`` 可以直接显示给用户。"""


@dataclass(frozen=True)
class ImportPreview:
    """一份可以直接填进向导的云端数据。"""

    info: dict = field(default_factory=dict)
    names: list[str] = field(default_factory=list)
    classlist: DataFrame | None = None
    lesson_times: dict[int, list[tuple[str, str]]] = field(default_factory=dict)
    onduty: dict = field(default_factory=dict)
    account: str = ''
    expires_at: str = ''

    @property
    def rows(self) -> int:
        return 0 if self.classlist is None else int(self.classlist.shape[0])

    @property
    def lesson_days(self) -> int:
        return len(self.lesson_times)


# ---------------------------------------------------------------- 网络
def fetch_preview(
    server: str,
    account: str,
    password: str,
    *,
    timeout: float = 20.0,
    retries: int = 1,
) -> ImportPreview:
    """拉取 + 解密 + 规整；所有失败都转成 ``CloudImportError``。"""
    server = (server or '').strip() or DEFAULT_SERVER
    account = normalize_account(account)
    password = normalize_password(password)
    if len(account) != 6:
        raise CloudImportError('传输账号应为 6 位（例如 ABC-DEF）')
    if not password:
        raise CloudImportError('请填写传输密码')

    try:
        data = fetch_class(
            server, account, password, timeout=timeout, retries=retries)
    except HttpError as exc:
        raise CloudImportError(_http_message(exc)) from exc
    except NetworkError as exc:
        raise CloudImportError(f'无法连接云端：{exc.message}') from exc
    except DecryptError as exc:
        raise CloudImportError('密码不正确，无法解密云端数据') from exc
    except ResponseFormatError as exc:
        raise CloudImportError(exc.message) from exc
    except ApiToolError as exc:
        raise CloudImportError(exc.message) from exc

    preview = parse_payload(data.payload)
    return replace(
        preview,
        account=data.meta.account or account,
        expires_at=data.meta.expires_at,
    )


def _http_message(exc: HttpError) -> str:
    status = exc.status
    if status == 401:
        return '账号或密码不正确（401）'
    if status == 403:
        return '云端拒绝了这次请求（403）'
    if status == 404:
        return '云端没有这个传输账号，可能已过期并被清理（404）'
    if status == 410:
        return '传输账号已过期（410），请让老师重新生成'
    if status == 413:
        return '云端数据太大（413）'
    if status == 429:
        return '请求过于频繁，请稍后再试（429）'
    if status and status >= 500:
        return f'云端服务器错误（{status}），请稍后再试'
    return exc.message or f'云端请求失败（{status}）'


# ---------------------------------------------------------------- 解析
def parse_payload(payload: object) -> ImportPreview:
    """把解密后的 payload 规整成 ``ImportPreview``；不合法时抛 ``CloudImportError``。"""
    if not isinstance(payload, dict):
        raise CloudImportError('云端数据不是 JSON 对象，无法导入')

    version = payload.get('v')
    if version is not None and (not isinstance(version, int) or version < 1):
        raise CloudImportError(f'云端数据版本不受支持：{version!r}')

    names = _parse_names(payload.get('names'))
    classlist = _parse_classlist(payload.get('classlist'))
    lesson_times = _parse_lesson_times(payload.get('lesson_times'))
    onduty = _parse_onduty(payload.get('onduty'), names)
    info = _parse_info(payload.get('info'))

    return ImportPreview(
        info=info,
        names=names,
        classlist=classlist,
        lesson_times=lesson_times,
        onduty=onduty,
    )


def _parse_info(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key in ('school_name', 'class_full_name', 'class_short_name'):
        text = str(raw.get(key) or '').strip()
        if text:
            result[key] = text
    return result


def _parse_names(raw) -> list[str]:
    if not isinstance(raw, list):
        raise CloudImportError('云端数据里没有学生名单（names）')

    names = [str(item).strip() for item in raw if str(item or '').strip()]
    if not names:
        raise CloudImportError('云端名单是空的，无法导入')

    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        shown = '、'.join(duplicates[:6]) + ('…' if len(duplicates) > 6 else '')
        raise CloudImportError(f'云端名单存在重名，无法导入：{shown}')
    return names


def _parse_classlist(raw) -> DataFrame:
    rows = raw.get('rows') if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise CloudImportError('云端数据里没有课程表（classlist）')

    cleaned: list[list[str]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            continue
        values = []
        for cell in row:
            if cell is None:
                values.append('')
            else:
                text = str(cell).strip()
                values.append('' if text.lower() == 'nan' else text)
        values = (values + [''] * WEEKDAY_COUNT)[:WEEKDAY_COUNT]
        cleaned.append(values)

    while cleaned and not any(cleaned[-1]):
        cleaned.pop()
    if not cleaned or not any(any(row) for row in cleaned):
        raise CloudImportError('云端课程表是空的，无法导入')

    return DataFrame(cleaned, columns=list(CLASS_WEEKDAYS))


def _norm_time(value) -> str | None:
    text = str(value or '').strip()
    parts = text.split(':')
    if len(parts) != 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except (TypeError, ValueError):
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return f'{hour:02d}:{minute:02d}'


def _parse_lesson_times(raw) -> dict[int, list[tuple[str, str]]]:
    """非法时段直接丢掉，不阻断导入（作息可以在向导里手工补）。"""
    if not isinstance(raw, dict):
        return {}

    result: dict[int, list[tuple[str, str]]] = {}
    for key, slots in raw.items():
        try:
            weekday = int(key)
        except (TypeError, ValueError):
            continue
        if not 1 <= weekday <= 5 or not isinstance(slots, list):
            continue
        cleaned: list[tuple[str, str]] = []
        for slot in slots:
            if not isinstance(slot, (list, tuple)) or len(slot) != 2:
                continue
            start, end = _norm_time(slot[0]), _norm_time(slot[1])
            if start and end and start < end:
                cleaned.append((start, end))
        if cleaned:
            result[weekday] = cleaned
    return result


def _parse_onduty(raw, names: list[str]) -> dict:
    if not isinstance(raw, dict):
        return {}
    mode = str(raw.get('mode') or '').strip()
    if mode not in ONDUTY_MODES:
        return {}

    result: dict = {'mode': mode}
    if mode == 'skip':
        return result

    start = str(raw.get('start') or '').strip()
    try:
        datetime.strptime(start, '%Y-%m-%d')
        result['start'] = start
    except ValueError:
        result['start'] = date.today().isoformat()

    weeks = _positive_int(raw.get('weeks'))
    if weeks:
        result['weeks'] = weeks

    jobs = [str(item).strip() for item in (raw.get('jobs') or []) if str(item or '').strip()]
    if jobs:
        result['jobs'] = jobs

    if isinstance(raw.get('skip_weekend'), bool):
        result['skip_weekend'] = raw['skip_weekend']

    if mode == 'sequence':
        daily = _positive_int(raw.get('daily'))
        if daily:
            result['daily'] = min(daily, max(1, len(names)))
        return result

    group_count = _positive_int(raw.get('group_count'))
    if group_count:
        result['group_count'] = group_count
    groups = raw.get('groups')
    if isinstance(groups, dict):
        cleaned = {
            str(key): [str(name).strip() for name in value if str(name or '').strip()]
            for key, value in groups.items() if isinstance(value, list)
        }
        cleaned = {key: value for key, value in cleaned.items() if value}
        if cleaned:
            result['groups'] = cleaned
    return result


def _positive_int(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


# ---------------------------------------------------------------- 展示
def format_expiry(value: str) -> str:
    """把 ISO8601（UTC）转成本地时间；解析不了就原样返回。"""
    text = str(value or '').strip()
    if not text:
        return ''
    try:
        moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return text
    return moment.astimezone().strftime('%Y-%m-%d %H:%M')


def summary_text(preview: ImportPreview) -> str:
    """一行中文摘要，给对话框和提示框用。"""
    bits = [
        f'{len(preview.names)} 人',
        f'{preview.rows} 节课表',
        f'{preview.lesson_days} 天作息',
    ]
    mode = preview.onduty.get('mode')
    if mode == 'skip':
        bits.append('值日稍后设置')
    elif mode:
        bits.append('值日含规则')
    return ' · '.join(bits)
