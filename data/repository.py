"""Repository 抽象：业务代码只依赖这个接口。

约定（HANDOFF §4.2 / §6.2）：
- 业务代码禁止直接 ``pd.read_csv`` / ``df.to_csv``，一律走 Repository
- 日期入参统一 ``datetime.date``，字符串只出现在 I/O 边界（DB 序列化）
- 星期统一 1 = 周一 ... 5 = 周五（与 ``datetime.weekday()`` 的 0 基不同，注意转换）
"""

from abc import ABC, abstractmethod
from datetime import date

from core.models import AppEntry, OndutyEntry


class Repository(ABC):
    """数据访问接口。写入只允许 SqliteRepository 实现。"""

    # ---------------- 学生 ----------------
    @abstractmethod
    def list_students(self) -> list[str]:
        """按 sort_order 返回学生姓名。"""

    @abstractmethod
    def replace_students(self, names: list[str]) -> None:
        """整体替换名单（顺序即轮值顺序）。"""

    # ---------------- 课程 ----------------
    @abstractmethod
    def list_courses(self) -> list[str]:
        """返回课程单（下拉候选）。"""

    @abstractmethod
    def replace_courses(self, names: list[str]) -> None:
        """整体替换课程单。"""

    # ---------------- 课表 ----------------
    @abstractmethod
    def get_classlist_template(self) -> dict[tuple[int, int], str]:
        """返回 {(weekday, lesson_index): course_name}，weekday 为 1..5。"""

    @abstractmethod
    def save_classlist_template(self, rows: list[tuple[int, int, str]]) -> None:
        """整体替换周模板，rows 为 [(weekday, lesson_index, course_name)]。"""

    @abstractmethod
    def get_classlist_for_date(self, d: date) -> list[str]:
        """优先取临时课表，其次周模板；按 lesson_index 排序，缺省为空串。"""

    @abstractmethod
    def save_classlist_override(self, d: date, courses: list[str]) -> None:
        """保存某一天的临时课表（lesson_index 从 1 开始）。"""

    @abstractmethod
    def delete_classlist_override(self, d: date) -> None:
        """删除某一天的临时课表。"""

    @abstractmethod
    def has_classlist_override(self, d: date) -> bool:
        """某一天是否已有临时课表。"""

    # ---------------- 作息 ----------------
    @abstractmethod
    def list_lesson_times(self) -> dict[int, list[tuple[str, str]]]:
        """{weekday: [(start, end), ...]}，weekday 1=周一。"""

    @abstractmethod
    def replace_lesson_times(self, mapping: dict[int, list[tuple[str, str]]]) -> None:
        """整体替换作息表。"""

    # ---------------- 值日 ----------------
    @abstractmethod
    def list_onduty(self) -> list[OndutyEntry]:
        """按日期、位置排序返回全部值日记录。"""

    @abstractmethod
    def replace_onduty(self, entries: list[OndutyEntry]) -> None:
        """整体替换值日表。"""

    @abstractmethod
    def get_onduty_for_date(self, d: date) -> list[OndutyEntry]:
        """返回某天的值日安排（按位置排序）。"""

    @abstractmethod
    def prune_onduty_before(self, d: date) -> int:
        """删除早于 d 的记录，返回删除条数。"""

    # ---------------- 应用 ----------------
    @abstractmethod
    def list_apps(self) -> list[AppEntry]:
        """按 sort_order 返回应用链接。"""

    @abstractmethod
    def replace_apps(self, apps: list[AppEntry]) -> None:
        """整体替换应用链接。"""

    # ---------------- 键值 ----------------
    @abstractmethod
    def get_kv(self, key: str, default=None):
        """读取任意 JSON 可序列化的值。"""

    @abstractmethod
    def set_kv(self, key: str, value) -> None:
        """写入任意 JSON 可序列化的值。"""

    # ---------------- 生命周期 ----------------
    @abstractmethod
    def close(self) -> None:
        """关闭底层连接。"""
