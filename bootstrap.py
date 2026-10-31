"""首次使用向导的落盘层。

设计约定：**向导只收集表单，所有读写集中在这里**。
以后 P6 换 SQLite，只替换本模块的实现，向导 UI 一行不用改。

所有公开函数都接受 `root` 参数（默认为 `%APPDATA%\\ClassManager`），
测试可以传临时目录，做到完全隔离。
"""

import copy
import json
import os
import shutil
from datetime import datetime

from pandas import DataFrame, isna

from config import (
    CLASS_WEEKDAYS,
    DATA_BASE,
    DEFAULT_USER_SETTINGS,
    ENCODING,
)

STATE_FILENAME = 'setup.json'
BACKUP_DIRNAME = 'backup'


# ---------------------------------------------------------------- 路径

def _dirs(root: str | None = None) -> dict:
    """把 root 展开成各处路径，集中管理，避免散落的字符串拼接。"""
    base = root or DATA_BASE
    data_dir = os.path.join(base, 'data')
    return {
        'base': base,
        'data': data_dir,
        'messages': os.path.join(base, 'messages'),
        'state': os.path.join(base, STATE_FILENAME),
        'backup': os.path.join(base, BACKUP_DIRNAME),
        'settings': os.path.join(data_dir, 'settings.json'),
        'datajson': os.path.join(data_dir, 'data.json'),
    }


def _read_json(path: str, default=None):
    try:
        with open(path, 'r', encoding=ENCODING) as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding=ENCODING) as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 状态

def is_initialized(root: str | None = None) -> bool:
    """`setup.json` 存在且 completed 为真。"""
    payload = _read_json(_dirs(root)['state'], default={})
    return bool(isinstance(payload, dict) and payload.get('completed'))


def mark_initialized(root: str | None = None, note: str = '') -> None:
    """写入"已完成首次设置"标记。"""
    _write_json(_dirs(root)['state'], {
        'completed': True,
        'version': 1,
        'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': note,
    })


def _clean(values) -> list:
    """去掉空值与首尾空白，保持顺序。"""
    result = []
    for v in values:
        if v is None or isna(v):
            continue
        s = str(v).strip()
        if s:
            result.append(s)
    return result


def infer_legacy_state(root: str | None = None) -> bool:
    """老用户推断：数据库里已有学生和真实课表，就视为已初始化。

    典型场景：老机器把 CSV 迁移进数据库后第一次启动，此时还没有 setup.json，
    不应该被拦进向导。
    """
    from data.sqlite_store import SqliteStore

    dirs = _dirs(root)
    db_path = os.path.join(dirs['data'], 'classmanager.db')
    if not os.path.exists(db_path):
        return False

    store = None
    try:
        store = SqliteStore(db_path)
        if len(store.load_names()) == 0:
            return False
        classlist = store.load_classlist()
        if classlist.empty:
            return False
        return any(
            str(v).strip() and str(v) != 'nan'
            for v in classlist.values.flatten()
        )
    except Exception:                           # noqa: BLE001
        return False
    finally:
        if store is not None:
            store.close()



# ---------------------------------------------------------------- 写入

def _store_for(root: str | None, dirs: dict):
    """决定本次写入用哪个 Store。

    - 传了 root（单元测试 / 指定目录）→ 该目录下的独立数据库，互不干扰
    - 否则用进程共享的 Store
    Returns:
        (store, owned)：owned 为真表示用完要 close。
    """
    from data.sqlite_store import SqliteStore
    from data.store import shared_store

    if root:
        return SqliteStore(os.path.join(dirs['data'], 'classmanager.db')), True
    return shared_store(), False


def save_all(info: dict, names, classlist, onduty=None,
             root: str | None = None) -> dict:
    """把向导收集到的内容一次性落盘，并写入初始化标记。

    Args:
        info: 含 school_name / class_full_name / class_short_name，
              可选 onduty_jobs / onduty_daily_template。
        names: 学生姓名序列（顺序即轮值顺序）。
        classlist: 5 列课表 DataFrame（列顺序会被规整为 周一~周五）。
        onduty: 可选，值日表 DataFrame（列名为日期）。
        root: 数据根目录，默认 %APPDATA%\\ClassManager。
    Returns:
        写盘摘要，便于向导最后一页展示。
    Raises:
        ValueError: 名单为空；课表列数不是 5。
    """
    dirs = _dirs(root)
    os.makedirs(dirs['data'], exist_ok=True)

    clean_names = _clean(names)
    if not clean_names:
        raise ValueError('名单不能为空')

    cl = DataFrame(classlist).copy()
    if cl.shape[1] != len(CLASS_WEEKDAYS):
        raise ValueError(f'课表需要 {len(CLASS_WEEKDAYS)} 列（周一~周五），实际 {cl.shape[1]} 列')
    cl.columns = CLASS_WEEKDAYS
    cl = cl.fillna('')

    # 五张主表经 Store 写入：CSV 模式落到 datas/*.csv，SQLite 模式进数据库。
    # 传了 root（测试）就强制用该目录的 CSV，不碰全局存储。
    store, owned = _store_for(root, dirs)
    try:
        store.save_classlist(cl)
        store.save_names(DataFrame({'name': clean_names}))

        courses = sorted({
            str(v).strip()
            for v in cl.values.flatten()
            if str(v).strip()
        })
        store.save_courses(DataFrame({'课程': courses}))

        if onduty is not None and len(onduty) > 0:
            store.save_onduty(DataFrame(onduty))
    finally:
        if owned:
            store.close()

    # settings：现有值 → 默认值 → 本次向导填的值
    settings = copy.deepcopy(DEFAULT_USER_SETTINGS)
    existing = _read_json(dirs['settings'], default={})
    if isinstance(existing, dict):
        settings.update(existing)
    for key in ('school_name', 'class_full_name', 'class_short_name',
                'onduty_jobs', 'onduty_daily_template'):
        if info.get(key):
            settings[key] = info[key]
    _write_json(dirs['settings'], settings)

    # 今天已经完成设置，就当作今天已登录，避免立刻再弹"今天按星期几上课"
    _write_json(dirs['datajson'], {'last_login': datetime.now().strftime('%Y%m%d')})

    mark_initialized(root, note='向导完成')

    return {
        'students': len(clean_names),
        'courses': len(courses),
        'class_rows': int(cl.shape[0]),
        'onduty_days': 0 if onduty is None else int(onduty.shape[1]),
    }


# ---------------------------------------------------------------- 备份 / 重置

def backup_all(root: str | None = None) -> str:
    """把整个数据目录（不含 backup 自身）复制到 backup/<时间戳>/，返回路径。"""
    dirs = _dirs(root)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(dirs['backup'], stamp)
    os.makedirs(dest, exist_ok=True)

    if not os.path.isdir(dirs['base']):
        return dest

    for name in os.listdir(dirs['base']):
        if name == BACKUP_DIRNAME:
            continue
        src = os.path.join(dirs['base'], name)
        dst = os.path.join(dest, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    return dest


def _clear_dir(path: str, keep_dir: bool = True) -> None:
    if not os.path.isdir(path):
        return
    for name in os.listdir(path):
        target = os.path.join(path, name)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        else:
            try:
                os.remove(target)
            except OSError:
                pass
    if not keep_dir:
        shutil.rmtree(path, ignore_errors=True)


def _collect_apps(dirs: dict, mode: str = 'sqlite'):
    """把应用链接取出来（重置后要原样放回）。数据只在数据库里。"""
    from pandas import DataFrame

    from data.sqlite_store import SqliteStore
    from data.store import APPS_COLUMNS

    db_path = os.path.join(dirs['data'], 'classmanager.db')
    if not os.path.exists(db_path):
        return DataFrame(columns=APPS_COLUMNS)
    store = None
    try:
        store = SqliteStore(db_path)
        return store.load_apps()
    except Exception:                           # noqa: BLE001
        return DataFrame(columns=APPS_COLUMNS)
    finally:
        if store is not None:
            store.close()


def reset_all(root: str | None = None, keep_messages: bool = False,
              keep_apps: bool = True) -> str:
    """清空班级数据，回到"首次使用"状态。**会先自动备份**。

    刻意保留的两样东西：
    - **应用链接**：那是"这台电脑"的配置（本机绝对路径），换班重配很烦
    - **存储方式**：否则重置后会悄悄退回 CSV，用户以为数据丢了

    Args:
        root: 数据根目录。
        keep_messages: True 时保留 messages/（消息正文与班级照片）。
        keep_apps: True 时保留应用链接（默认）。
    Returns:
        备份目录路径（调用方应在提示里告诉用户）。
    """
    dirs = _dirs(root)
    backup = backup_all(root)

    apps = _collect_apps(dirs) if keep_apps else None

    _clear_dir(dirs['data'])
    if not keep_messages:
        _clear_dir(dirs['messages'])
    if os.path.exists(dirs['state']):
        try:
            os.remove(dirs['state'])
        except OSError:
            pass

    # SQLite 模式下真正装数据的是数据根目录里的 db 文件，一并清掉
    for db_name in ('classmanager.db', 'classmanager.db-wal',
                    'classmanager.db-shm', 'classmanager.db.migrated_at'):
        db_path = os.path.join(dirs['base'], db_name)
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass

    # 放回应用链接（写进新建的数据库）
    if keep_apps and apps is not None and len(apps) > 0:
        try:
            from data.sqlite_store import SqliteStore
            db_path = os.path.join(dirs['data'], 'classmanager.db')
            store = SqliteStore(db_path)
            try:
                store.save_apps(apps)
            finally:
                store.close()
        except Exception as e:                  # noqa: BLE001
            print(f'[reset] 恢复应用链接失败: {e!r}')

    # 其余设置交给默认值（班级名、倒计时等重新配）
    _write_json(dirs['settings'], {})

    # 丢掉共享 Store，避免继续持有已删除的数据库连接
    try:
        from data.store import reset_shared_store
        reset_shared_store()
    except Exception:                           # noqa: BLE001
        pass

    return backup
