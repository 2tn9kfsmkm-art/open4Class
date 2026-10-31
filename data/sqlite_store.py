"""Store 的 SQLite 实现：把 Repository 的对象模型转回界面需要的 DataFrame。

转换规则与 CSV 完全对齐，这样切换存储时上层代码零改动：
- 课表：列 = 周一~周五，行 = 节次
- 值日：列 = 日期，行 = 位置 0~4，单元格 = "{姓名} {职务}"
- 应用：列 = 软件链接 / path
"""

import os
from datetime import date

from pandas import DataFrame

from config import CLASS_WEEKDAYS, DB_PATH
from core.models import AppEntry, OndutyEntry
from data.sqlite_repo import SqliteRepository
from data.store import APPS_COLUMNS, Store

DB_FILENAME = 'classmanager.db'


def default_db_path() -> str:
    return DB_PATH


class SqliteStore(Store):
    """基于 SqliteRepository 的实现。"""

    def __init__(self, path: str | None = None, repo: SqliteRepository | None = None):
        if repo is not None:
            self._repo = repo
            self.path = repo.path
        else:
            self.path = path or default_db_path()
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._repo = SqliteRepository(self.path)

    # ---------------- 名单 ----------------
    def load_names(self) -> DataFrame:
        return DataFrame({'name': self._repo.list_students()})

    def save_names(self, df: DataFrame) -> None:
        column = 'name' if 'name' in df.columns else df.columns[0]
        names = [str(v).strip() for v in df[column].tolist() if str(v).strip()]
        self._repo.replace_students(names)

    # ---------------- 课程单 ----------------
    def load_courses(self) -> DataFrame:
        return DataFrame({'课程': self._repo.list_courses()})

    def save_courses(self, df: DataFrame) -> None:
        names = [str(v).strip() for v in df.iloc[:, 0].tolist() if str(v).strip()]
        self._repo.replace_courses(names)

    # ---------------- 课表 ----------------
    def load_classlist(self) -> DataFrame:
        template = self._repo.get_classlist_template()
        if not template:
            return DataFrame(columns=CLASS_WEEKDAYS)
        lessons = max(lesson for _, lesson in template)
        rows = []
        for lesson in range(1, lessons + 1):
            rows.append([template.get((weekday, lesson), '')
                         for weekday in range(1, 6)])
        return DataFrame(rows, columns=CLASS_WEEKDAYS)

    def save_classlist(self, df: DataFrame) -> None:
        rows = []
        for weekday in range(1, 6):
            if weekday - 1 >= df.shape[1]:
                continue
            for lesson, value in enumerate(df.iloc[:, weekday - 1].tolist(), start=1):
                text = '' if value is None or str(value) == 'nan' else str(value).strip()
                if text:
                    rows.append((weekday, lesson, text))
        self._repo.save_classlist_template(rows)

    def load_classlist_for_date(self, d: date) -> list[str]:
        return self._repo.get_classlist_for_date(d)

    def save_classlist_override(self, d: date, courses: list[str]) -> None:
        self._repo.save_classlist_override(
            d, ['' if c is None else str(c) for c in courses])

    def delete_classlist_override(self, d: date) -> None:
        self._repo.delete_classlist_override(d)

    def has_classlist_override(self, d: date) -> bool:
        return self._repo.has_classlist_override(d)

    # ---------------- 值日 ----------------
    def load_onduty(self) -> DataFrame:
        entries = self._repo.list_onduty()
        if not entries:
            return DataFrame()
        days = sorted({e.date for e in entries})
        by_day = {}
        for entry in entries:
            by_day.setdefault(entry.date, {})[entry.slot] = entry
        columns = {}
        for day in days:
            column = []
            for slot in range(5):
                entry = by_day[day].get(slot)
                column.append(f'{entry.student} {entry.job}'.strip() if entry else '')
            columns[day.isoformat()] = column
        return DataFrame(columns)

    def save_onduty(self, df: DataFrame) -> None:
        entries = []
        for column in df.columns:
            try:
                day = date.fromisoformat(str(column).strip())
            except ValueError:
                continue
            for slot, cell in enumerate(df[column].tolist()):
                if slot >= 5:
                    break
                text = '' if cell is None or str(cell) == 'nan' else str(cell).strip()
                if not text:
                    continue
                parts = text.rsplit(None, 1)
                student = parts[0]
                job = parts[1] if len(parts) == 2 else ''
                entries.append(OndutyEntry(day, slot, student, job))
        self._repo.replace_onduty(entries)

    # ---------------- 应用链接 ----------------
    def load_apps(self) -> DataFrame:
        apps = self._repo.list_apps()
        return DataFrame([(a.name, a.path) for a in apps], columns=APPS_COLUMNS)

    def save_apps(self, df: DataFrame) -> None:
        apps = []
        for _, row in df.iterrows():
            name = str(row[APPS_COLUMNS[0]]).strip()
            path = str(row[APPS_COLUMNS[1]]).strip()
            if name and path and path != 'nan':
                apps.append(AppEntry(name, path))
        self._repo.replace_apps(apps)

    # ---------------- 生命周期 ----------------
    def close(self) -> None:
        self._repo.close()
