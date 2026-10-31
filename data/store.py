"""存储抽象层：业务代码只跟这里打交道，不直接碰 CSV 或 SQLite。

设计取舍：界面上上下下都是 ``DataFrame``（``PandasQItemModel`` 依赖它），
所以 Store 的接口就按"读写表格"来设计，而不是直接暴露 Repository 的对象。
两种实现：

    CsvStore      当前行为（datas/*.csv），默认
    SqliteStore   走 data/ 层的 Repository，settings 里 storage=sqlite 时启用

这样切换存储时，业务代码一行不用改。
"""

import os
from abc import ABC, abstractmethod

from pandas import DataFrame, read_csv

from config import CLASS_WEEKDAYS, ENCODING, FILE_DIR

NAMES_FILE = '名单.csv'
COURSES_FILE = '课程单.csv'
CLASSLIST_FILE = '课表.csv'
ONDUTY_FILE = '未来值日.csv'
APPS_FILE = '应用路径.csv'

APPS_COLUMNS = ['软件链接', 'path']


def _path(filename: str) -> str:
    return os.path.join(FILE_DIR, filename)


class Store(ABC):
    """五张主表的读写接口。返回值一律是 DataFrame，列名与 CSV 表头一致。"""

    # ---- 名单 ----
    @abstractmethod
    def load_names(self) -> DataFrame:
        """列名 ``name``；文件不存在时返回空表（并落一个空文件）。"""

    @abstractmethod
    def save_names(self, df: DataFrame) -> None:
        """整体替换名单。"""

    # ---- 课程单 ----
    @abstractmethod
    def load_courses(self) -> DataFrame:
        """列名 ``课程``。"""

    @abstractmethod
    def save_courses(self, df: DataFrame) -> None:
        """整体替换课程单。"""

    # ---- 周模板课表 ----
    @abstractmethod
    def load_classlist(self) -> DataFrame:
        """列名 周一~周五，每行一节。"""

    @abstractmethod
    def save_classlist(self, df: DataFrame) -> None:
        """整体替换周模板。"""

    # ---- 值日 ----
    @abstractmethod
    def load_onduty(self) -> DataFrame:
        """列名为日期 ``YYYY-MM-DD``，每列 5 行。"""

    @abstractmethod
    def save_onduty(self, df: DataFrame) -> None:
        """整体替换值日表。"""

    # ---- 应用链接 ----
    @abstractmethod
    def load_apps(self) -> DataFrame:
        """列名 ``软件链接`` / ``path``。"""

    @abstractmethod
    def save_apps(self, df: DataFrame) -> None:
        """整体替换应用链接。"""

    # ---- 生命周期 ----
    def close(self) -> None:
        """释放资源（CSV 实现无需做任何事）。"""


class CsvStore(Store):
    """基于 datas/*.csv 的实现，行为与改造前完全一致。"""

    def __init__(self, directory: str | None = None):
        self.directory = directory or FILE_DIR

    def _path(self, filename: str) -> str:
        return os.path.join(self.directory, filename)

    def _read(self, filename: str, columns: list[str] | None = None) -> DataFrame:
        path = self._path(filename)
        if not os.path.exists(path):
            df = DataFrame(columns=columns or [])
            df.to_csv(path, index=False, encoding=ENCODING)
            return df
        return read_csv(path, encoding=ENCODING, index_col=False)

    # ---- 名单 ----
    def load_names(self) -> DataFrame:
        return self._read(NAMES_FILE, columns=['name'])

    def save_names(self, df: DataFrame) -> None:
        DataFrame(df).to_csv(self._path(NAMES_FILE), index=False, encoding=ENCODING)

    # ---- 课程单 ----
    def load_courses(self) -> DataFrame:
        return self._read(COURSES_FILE, columns=['课程'])

    def save_courses(self, df: DataFrame) -> None:
        DataFrame(df).to_csv(self._path(COURSES_FILE), index=False, encoding=ENCODING)

    # ---- 课表 ----
    def load_classlist(self) -> DataFrame:
        return self._read(CLASSLIST_FILE, columns=CLASS_WEEKDAYS)

    def save_classlist(self, df: DataFrame) -> None:
        DataFrame(df).to_csv(self._path(CLASSLIST_FILE), index=False, encoding=ENCODING)

    # ---- 值日 ----
    def load_onduty(self) -> DataFrame:
        return self._read(ONDUTY_FILE)

    def save_onduty(self, df: DataFrame) -> None:
        DataFrame(df).to_csv(self._path(ONDUTY_FILE), index=False, encoding=ENCODING)

    # ---- 应用链接 ----
    def load_apps(self) -> DataFrame:
        return self._read(APPS_FILE, columns=APPS_COLUMNS)

    def save_apps(self, df: DataFrame) -> None:
        DataFrame(df).to_csv(self._path(APPS_FILE), index=False, encoding=ENCODING)


_shared: Store | None = None


def shared_store() -> Store:
    """进程内共享的 Store 实例。

    SQLite 实现会长期持有连接，必须复用；CSV 实现复用也无副作用。
    """
    global _shared
    if _shared is None:
        _shared = get_store()
    return _shared


def reset_shared_store() -> None:
    """测试用：丢弃共享实例（切换存储或换数据目录后调用）。"""
    global _shared
    if _shared is not None:
        try:
            _shared.close()
        except Exception:                       # noqa: BLE001
            pass
    _shared = None


def get_store() -> Store:
    """按设置返回存储实现。

    读取 ``settings.json`` 的 ``storage`` 字段（默认 ``csv``）；
    也支持 ``CLASSMANAGER_STORAGE`` 环境变量覆盖，便于测试。
    """
    mode = os.environ.get('CLASSMANAGER_STORAGE', '').strip().lower()
    if not mode:
        try:
            from config import load_user_settings
            mode = str(load_user_settings().get('storage', 'csv')).lower()
        except Exception:                       # noqa: BLE001 - 设置读不到就退回默认
            mode = 'csv'

    if mode == 'sqlite':
        from data.sqlite_store import SqliteStore
        return SqliteStore()
    return CsvStore()
