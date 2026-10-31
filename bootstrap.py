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
    datas = os.path.join(base, 'datas')
    return {
        'base': base,
        'datas': datas,
        'messages': os.path.join(base, 'messages'),
        'loadings': os.path.join(datas, 'loadings'),
        'state': os.path.join(base, STATE_FILENAME),
        'backup': os.path.join(base, BACKUP_DIRNAME),
        'settings': os.path.join(datas, 'settings.json'),
        'data': os.path.join(datas, 'data.json'),
        'names': os.path.join(datas, '名单.csv'),
        'classlist': os.path.join(datas, '课表.csv'),
        'courses': os.path.join(datas, '课程单.csv'),
        'onduty': os.path.join(datas, '未来值日.csv'),
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


def _read_csv(path: str):
    from pandas import read_csv
    if not os.path.exists(path):
        return None
    try:
        return read_csv(path, encoding=ENCODING)
    except Exception:
        return None


def infer_legacy_state(root: str | None = None) -> bool:
    """老用户推断：名单里有学生、且课表里有真实课程，即视为已初始化。

    班里那台机器升级到带向导的版本时，不能因为缺少 setup.json 就被拦在向导里。
    """
    dirs = _dirs(root)

    names = _read_csv(dirs['names'])
    if names is None or len(names) == 0:
        return False
    if 'name' not in [str(c) for c in names.columns]:
        return False
    if not _clean(names['name'].tolist()):
        return False

    classlist = _read_csv(dirs['classlist'])
    if classlist is None or classlist.empty:
        return False
    # 课表骨架是 8 行全空，必须区分"有内容"和"只有表头"。
    # 不能先 fillna('')：全空列是 float64，pandas 4 会直接报错。
    def _cell(v):
        return '' if v is None or isna(v) else str(v).strip()

    filled = classlist.apply(lambda col: col.map(_cell))
    if (filled == '').all().all():
        return False
    return True
    return True


# ---------------------------------------------------------------- 写入

def _store_for(root: str | None, dirs: dict):
    """决定本次写入用哪个 Store。

    - 传了 root（单元测试 / 指定目录）→ 该目录下的 CsvStore，互不干扰
    - 否则用进程共享的 Store（跟随 settings.storage / 环境变量）
    Returns:
        (store, owned)：owned 为真表示用完要 close。
    """
    from data.store import CsvStore, shared_store

    if root:
        return CsvStore(dirs['datas']), True
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
    os.makedirs(dirs['datas'], exist_ok=True)

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
    _write_json(dirs['data'], {'last_login': datetime.now().strftime('%Y%m%d')})

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


def reset_all(root: str | None = None, keep_messages: bool = False) -> str:
    """清空全部班级数据，回到"首次使用"状态。**会先自动备份**。

    Args:
        root: 数据根目录。
        keep_messages: True 时保留 messages/（消息正文与班级照片）。
    Returns:
        备份目录路径（调用方应在提示里告诉用户）。
    """
    dirs = _dirs(root)
    backup = backup_all(root)

    _clear_dir(dirs['datas'])
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

    # 丢掉共享 Store，避免继续持有已删除的数据库连接
    try:
        from data.store import reset_shared_store
        reset_shared_store()
    except Exception:                           # noqa: BLE001
        pass

    return backup
