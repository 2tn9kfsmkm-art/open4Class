"""在 CSV 与 SQLite 两种存储之间切换。

切换是有破坏性的操作，所以统一流程：
    备份 → 迁移 → 记录到 settings → 提示重启

两个方向都支持：
    switch_to_sqlite()  CSV → 数据库
    switch_to_csv()     数据库 → CSV（回退用，保证不会丢数据）
"""

import os
import shutil

from data.store import CsvStore
from data.sqlite_store import SqliteStore
from tools.migrate_csv_to_sqlite import migrate

MODES = ('csv', 'sqlite')
LABELS = {'csv': 'CSV 文件', 'sqlite': 'SQLite 数据库'}


def default_db_path() -> str:
    from config import DATA_BASE
    return os.path.join(DATA_BASE, 'classmanager.db')


def _csv_has_data(csv_dir: str) -> bool:
    try:
        return len(CsvStore(csv_dir).load_names()) > 0
    except Exception:                           # noqa: BLE001
        return False


def _db_has_data(db_path: str) -> bool:
    if not os.path.exists(db_path):
        return False
    store = None
    try:
        store = SqliteStore(db_path)
        return len(store.load_names()) > 0
    except Exception:                           # noqa: BLE001
        return False
    finally:
        if store is not None:
            store.close()


def switch_to_sqlite(csv_dir: str, db_path: str | None = None,
                     backup=None) -> dict:
    """把 CSV 数据迁移进数据库。

    Args:
        csv_dir: 当前的 CSV 数据目录。
        db_path: 目标数据库，默认 %APPDATA%\\ClassManager\\classmanager.db。
        backup: 可选的无参回调，返回备份路径（通常是 bootstrap.backup_all）。
    Returns:
        摘要字典：backup / db / counts。
    """
    db_path = db_path or default_db_path()
    result = {'backup': None, 'db': db_path}

    if backup is not None:
        result['backup'] = backup()

    # 已有数据库先留一份副本，避免重复迁移把旧库覆盖掉
    if os.path.exists(db_path):
        shutil.copy2(db_path, db_path + '.bak')

    result['counts'] = migrate(csv_dir, db_path)
    return result


def switch_to_csv(csv_dir: str, db_path: str | None = None,
                  backup=None) -> dict:
    """把数据库内容导出回 CSV（回退路径，避免"切回去数据没了"）。

    Returns:
        摘要字典：backup / counts。
    """
    db_path = db_path or default_db_path()
    result = {'backup': None, 'counts': {}}

    if backup is not None:
        result['backup'] = backup()

    if not os.path.exists(db_path):
        result['counts'] = {'students': 0, 'courses': 0, 'template': 0,
                            'onduty': 0, 'apps': 0}
        return result

    src = SqliteStore(db_path)
    try:
        dst = CsvStore(csv_dir)
        names = src.load_names()
        courses = src.load_courses()
        classlist = src.load_classlist()
        onduty = src.load_onduty()
        apps = src.load_apps()

        dst.save_names(names)
        dst.save_courses(courses)
        if len(classlist.columns):
            dst.save_classlist(classlist)
        if len(onduty.columns):
            dst.save_onduty(onduty)
        dst.save_apps(apps)
    finally:
        src.close()

    result['counts'] = {
        'students': len(names),
        'courses': len(courses),
        'template': int(classlist.shape[0]),
        'onduty': int(onduty.shape[1]),
        'apps': len(apps),
    }
    return result


def ensure_storage_ready() -> str | None:
    """启动自检：用了 sqlite 但库里没数据、CSV 里有 —— 自动补一次迁移。

    Returns:
        给控制台的一行说明；无需处理时返回 None。
    """
    from config import DATA_BASE, FILE_DIR, load_user_settings

    mode = str(load_user_settings().get('storage', 'csv')).lower()
    if mode != 'sqlite':
        return None

    db_path = os.path.join(DATA_BASE, 'classmanager.db')
    if _db_has_data(db_path) or not _csv_has_data(FILE_DIR):
        return None

    result = switch_to_sqlite(FILE_DIR, db_path)
    return f"[storage] 数据库为空，已从 CSV 自动迁移：{result['counts']}"
