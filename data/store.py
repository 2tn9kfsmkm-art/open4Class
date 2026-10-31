"""存储抽象层：SQLite 是唯一实现。

历史：P6 期间这里还有一个 ``CsvStore``（读 datas/*.csv），
SQLite 全面接替后已删除。需要把老机器上的 CSV 导进来时，
用 ``tools/migrate_csv_to_sqlite.py`` 手动跑一次即可，运行时不再读 CSV。

界面上上下下都是 ``DataFrame``（``PandasQItemModel`` 依赖它），
所以 Store 的接口按"读写表格"设计，而不是直接暴露 Repository 的对象。
"""

from abc import ABC, abstractmethod
from datetime import date

from pandas import DataFrame

APPS_COLUMNS = ['软件链接', 'path']


class Store(ABC):
    """五张主表 + 某天课表的读写接口。返回值一律是 DataFrame。"""

    # ---- 名单 ----
    @abstractmethod
    def load_names(self) -> DataFrame:
        """列名 ``name``，顺序即轮值顺序。"""

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

    # ---- 某天的课表（临时课表优先）----
    @abstractmethod
    def load_classlist_for_date(self, d: date) -> list[str]:
        """返回某天按节次排列的课程名；没有则返回空列表。"""

    @abstractmethod
    def save_classlist_override(self, d: date, courses: list[str]) -> None:
        """保存某天的临时课表（覆盖周模板）。"""

    @abstractmethod
    def delete_classlist_override(self, d: date) -> None:
        """删除某天的临时课表。"""

    @abstractmethod
    def has_classlist_override(self, d: date) -> bool:
        """某天是否已有临时课表。"""

    # ---- 值日 ----
    @abstractmethod
    def load_onduty(self) -> DataFrame:
        """列名为日期 ``YYYY-MM-DD``，每列最多 5 行。"""

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
        """释放资源。"""


_shared: Store | None = None


def get_store() -> Store:
    """创建当前使用的 Store 实现（目前只有 SQLite）。"""
    from data.sqlite_store import SqliteStore
    return SqliteStore()


def shared_store() -> Store:
    """进程内共享的 Store 实例（SQLite 连接需要复用）。"""
    global _shared
    if _shared is None:
        _shared = get_store()
    return _shared


def reset_shared_store() -> None:
    """丢弃共享实例：切换数据目录、重置数据后调用。"""
    global _shared
    if _shared is not None:
        try:
            _shared.close()
        except Exception:                       # noqa: BLE001
            pass
    _shared = None
