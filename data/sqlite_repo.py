"""SQLite 实现：唯一的写入实现。

日期在库里是 ``TEXT`` + ``YYYY-MM-DD``，在这里统一与 ``datetime.date`` 互转。
"""

import json
import sqlite3
import threading
from datetime import date

from core.models import AppEntry, OndutyEntry
from data.db import connect
from data.migrations.migrate import apply_pending
from data.repository import Repository

_DATE_FMT = '%Y-%m-%d'


def _to_db(d: date) -> str:
    return d.strftime(_DATE_FMT)


def _from_db(text: str) -> date:
    return date.fromisoformat(str(text))


def _unique(names) -> list[str]:
    """去重但保留首次出现的顺序（students/courses 的 name 是 UNIQUE）。"""
    seen = set()
    result = []
    for name in names:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


class SqliteRepository(Repository):
    """SQLite 版本的数据访问实现。

    Args:
        path: 数据库文件路径。
        thread_safe: 为真时用可重入锁串行化读写（后台线程共享连接时打开）。
    """

    def __init__(self, path: str, thread_safe: bool = True):
        self.path = path
        self._conn = connect(path)
        self._lock = threading.RLock() if thread_safe else None
        apply_pending(self._conn)

    # ---------------- 内部工具 ----------------
    def _execute(self, sql: str, params=()):
        if self._lock is not None:
            with self._lock:
                return self._conn.execute(sql, params)
        return self._conn.execute(sql, params)

    def _write(self, fn):
        """在事务里执行 fn(conn)，失败回滚。"""
        conn = self._conn
        if self._lock is not None:
            with self._lock:
                with conn:
                    return fn(conn)
        with conn:
            return fn(conn)

    # ---------------- 学生 ----------------
    def list_students(self) -> list[str]:
        rows = self._execute(
            'SELECT name FROM students ORDER BY sort_order, id').fetchall()
        return [r['name'] for r in rows]

    def replace_students(self, names: list[str]) -> None:
        def _do(conn):
            conn.execute('DELETE FROM students')
            conn.executemany(
                'INSERT INTO students (name, sort_order) VALUES (?, ?)',
                [(n, i) for i, n in enumerate(_unique(names))],
            )
        self._write(_do)

    # ---------------- 课程 ----------------
    def list_courses(self) -> list[str]:
        rows = self._execute('SELECT name FROM courses ORDER BY id').fetchall()
        return [r['name'] for r in rows]

    def replace_courses(self, names: list[str]) -> None:
        def _do(conn):
            conn.execute('DELETE FROM courses')
            conn.executemany(
                'INSERT INTO courses (name) VALUES (?)',
                [(n,) for n in _unique(names)],
            )
        self._write(_do)

    # ---------------- 课表 ----------------
    def get_classlist_template(self) -> dict[tuple[int, int], str]:
        rows = self._execute(
            'SELECT weekday, lesson_index, course_name FROM classlist_template'
        ).fetchall()
        return {(r['weekday'], r['lesson_index']): (r['course_name'] or '')
                for r in rows}

    def save_classlist_template(self, rows: list[tuple[int, int, str]]) -> None:
        def _do(conn):
            conn.execute('DELETE FROM classlist_template')
            conn.executemany(
                'INSERT INTO classlist_template (weekday, lesson_index, course_name)'
                ' VALUES (?, ?, ?)',
                [(w, i, c or '') for w, i, c in rows],
            )
        self._write(_do)

    def get_classlist_for_date(self, d: date) -> list[str]:
        overrides = self._execute(
            'SELECT lesson_index, course_name FROM classlist_override'
            ' WHERE date = ? ORDER BY lesson_index', (_to_db(d),)
        ).fetchall()
        if overrides:
            return [r['course_name'] or '' for r in overrides]

        weekday = d.isoweekday()          # 1 = 周一 ... 7 = 周日
        if weekday > 5:
            return []
        rows = self._execute(
            'SELECT course_name FROM classlist_template'
            ' WHERE weekday = ? ORDER BY lesson_index', (weekday,)
        ).fetchall()
        return [r['course_name'] or '' for r in rows]

    def save_classlist_override(self, d: date, courses: list[str]) -> None:
        def _do(conn):
            conn.execute('DELETE FROM classlist_override WHERE date = ?',
                         (_to_db(d),))
            conn.executemany(
                'INSERT INTO classlist_override (date, lesson_index, course_name)'
                ' VALUES (?, ?, ?)',
                [(_to_db(d), i + 1, c or '') for i, c in enumerate(courses)],
            )
        self._write(_do)

    def delete_classlist_override(self, d: date) -> None:
        self._write(lambda conn: conn.execute(
            'DELETE FROM classlist_override WHERE date = ?', (_to_db(d),)))

    def has_classlist_override(self, d: date) -> bool:
        row = self._execute(
            'SELECT 1 FROM classlist_override WHERE date = ? LIMIT 1',
            (_to_db(d),)).fetchone()
        return row is not None

    # ---------------- 值日 ----------------
    def list_onduty(self) -> list[OndutyEntry]:
        rows = self._execute(
            'SELECT date, slot_index, student_name, job FROM onduty'
            ' ORDER BY date, slot_index').fetchall()
        return [OndutyEntry(_from_db(r['date']), r['slot_index'],
                            r['student_name'], r['job']) for r in rows]

    def replace_onduty(self, entries: list[OndutyEntry]) -> None:
        def _do(conn):
            conn.execute('DELETE FROM onduty')
            conn.executemany(
                'INSERT INTO onduty (date, slot_index, student_name, job)'
                ' VALUES (?, ?, ?, ?)',
                [(_to_db(e.date), e.slot, e.student, e.job) for e in entries],
            )
        self._write(_do)

    def get_onduty_for_date(self, d: date) -> list[OndutyEntry]:
        rows = self._execute(
            'SELECT date, slot_index, student_name, job FROM onduty'
            ' WHERE date = ? ORDER BY slot_index', (_to_db(d),)).fetchall()
        return [OndutyEntry(_from_db(r['date']), r['slot_index'],
                            r['student_name'], r['job']) for r in rows]

    def prune_onduty_before(self, d: date) -> int:
        deleted = 0

        def _do(conn):
            nonlocal deleted
            cur = conn.execute('DELETE FROM onduty WHERE date < ?', (_to_db(d),))
            deleted = cur.rowcount
        self._write(_do)
        return deleted

    # ---------------- 应用 ----------------
    def list_apps(self) -> list[AppEntry]:
        rows = self._execute(
            'SELECT name, path FROM apps ORDER BY sort_order, id').fetchall()
        return [AppEntry(r['name'], r['path']) for r in rows]

    def replace_apps(self, apps: list[AppEntry]) -> None:
        def _do(conn):
            conn.execute('DELETE FROM apps')
            conn.executemany(
                'INSERT INTO apps (name, path, sort_order) VALUES (?, ?, ?)',
                [(a.name, a.path, i) for i, a in enumerate(apps)],
            )
        self._write(_do)

    # ---------------- 键值 ----------------
    def get_kv(self, key: str, default=None):
        row = self._execute('SELECT value FROM kv WHERE key = ?', (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row['value'])
        except (ValueError, TypeError):
            return default

    def set_kv(self, key: str, value) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        self._write(lambda conn: conn.execute(
            'INSERT INTO kv (key, value) VALUES (?, ?)'
            ' ON CONFLICT(key) DO UPDATE SET value = excluded.value',
            (key, payload)))

    # ---------------- 生命周期 ----------------
    def close(self) -> None:
        if self._lock is not None:
            with self._lock:
                self._conn.close()
        else:
            self._conn.close()
