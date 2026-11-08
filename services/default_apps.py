"""首次分发时的默认应用链接。

随包带 `resources/default_apps.json`，其中每项可写多个候选路径；
程序启动时挑第一个真实存在的路径写进数据库，这样换机器也能用：
希沃一体机上这四个程序的安装位置基本固定，但 WPS 有时在用户目录下。
"""

import json
import os

from pandas import DataFrame

from config import RESOURCE_DIR

_DEFAULT_FILE = os.path.join(RESOURCE_DIR, 'default_apps.json')


def _load_definitions() -> list:
    try:
        with open(_DEFAULT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:                      # noqa: BLE001
        print(f'[default_apps] 读取默认应用失败: {e!r}')
        return []


def _pick_path(item: dict) -> str:
    """按 candidates 里第一个存在的路径；没有就退回首项。"""
    path = str(item.get('path', '') or '').strip()
    candidates = [path] if path else []
    candidates += [str(p) for p in item.get('fallback') or []]

    for candidate in candidates:
        if not candidate:
            continue
        candidate = os.path.expandvars(candidate)   # 支持 %LOCALAPPDATA% 这类写法
        if candidate.lower() == 'explorer':
            return candidate                   # 特殊：调用资源管理器
        if os.path.exists(candidate):
            return candidate
    return candidates[0] if candidates else ''


def default_apps_df() -> DataFrame:
    """把默认应用整理成 Store 需要的两列表。"""
    from data.store import APPS_COLUMNS

    rows = []
    for item in _load_definitions():
        name = str(item.get('name', '')).strip()
        path = _pick_path(item)
        if name and path:
            rows.append((name, path))
    return DataFrame(rows, columns=APPS_COLUMNS)


def seed_default_apps(store) -> DataFrame:
    """数据库里还没应用链接时，写入随包默认值，返回最终的表。"""
    df = store.load_apps()
    if len(df) > 0:
        return df

    defaults = default_apps_df()
    if len(defaults) > 0:
        try:
            store.save_apps(defaults)
            print(f'[default_apps] 已写入 {len(defaults)} 个默认应用')
        except Exception as e:                  # noqa: BLE001
            print(f'[default_apps] 写入失败: {e!r}')
        return defaults
    return df
