"""版本化 schema 迁移。

约定：
- 迁移文件是**纯前向 SQL**，不写 ``IF NOT EXISTS``，靠 schema_migrations 保证只跑一次
- 已发布的迁移文件禁止修改，需要变更时新增版本
- 一批迁移在同一个事务里执行，失败整体回滚
"""

import os
import sqlite3

def _sql_dirs() -> list:
    """按优先级列出可能存放 .sql 的目录。

    打包（Nuitka standalone）后模块没有真实的 __file__，SQL 需要跟着
    exe 目录一起分发，所以这里依次尝试：源码目录 → exe 目录 → RESOURCE_BASE。
    """
    dirs = []
    try:
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    try:
        import sys
        if getattr(sys, 'frozen', False) or '__compiled__' in globals():
            base = os.path.dirname(os.path.abspath(sys.executable))
            dirs.append(os.path.join(base, 'data', 'migrations'))
    except Exception:                           # noqa: BLE001
        pass
    try:
        from config import RESOURCE_BASE
        dirs.append(os.path.join(RESOURCE_BASE, 'data', 'migrations'))
    except Exception:                           # noqa: BLE001
        pass
    return dirs


def _resolve_sql_dir() -> str:
    for candidate in _sql_dirs():
        try:
            names = os.listdir(candidate)
        except OSError:
            continue
        if any(n.endswith('.sql') for n in names):
            return candidate
    return _sql_dirs()[0] if _sql_dirs() else ''


HERE = _sql_dirs()[0] if _sql_dirs() else ''
SQL_DIR = _resolve_sql_dir()

# (version, name, sql 文件名)
MIGRATIONS: list[tuple[int, str, str]] = [
    (1, 'initial_schema', 'm0001_initial.sql'),
    (2, 'lesson_times', 'm0002_lesson_times.sql'),
]


class MigrationError(Exception):
    """迁移执行失败。"""


def _ensure_bookkeeping(conn: sqlite3.Connection) -> None:
    conn.execute(
        'CREATE TABLE IF NOT EXISTS schema_migrations ('
        'version INTEGER PRIMARY KEY,'
        'name TEXT NOT NULL,'
        'applied_at TEXT NOT NULL DEFAULT (datetime(\'now\', \'localtime\'))'
        ')'
    )


def current_version(conn: sqlite3.Connection) -> int:
    """返回当前已应用的最高版本号；空库返回 0。"""
    _ensure_bookkeeping(conn)
    row = conn.execute('SELECT MAX(version) AS v FROM schema_migrations').fetchone()
    return int(row['v'] or 0)


def pending(conn: sqlite3.Connection) -> list[tuple[int, str, str]]:
    """返回尚未应用的迁移。"""
    version = current_version(conn)
    return [m for m in MIGRATIONS if m[0] > version]


def _iter_statements(script: str):
    """把 SQL 脚本拆成单条语句。

    不能用 ``executescript``：它会先隐式提交，导致迁移失败时无法整体回滚。
    用 ``sqlite3.complete_statement`` 累积判断语句是否结束，
    这样触发器里的分号也不会被拆错。
    """
    buf = ''
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            statement = buf.strip()
            if statement:
                yield statement
            buf = ''
    if buf.strip():
        yield buf.strip()


def apply_pending(conn: sqlite3.Connection) -> int:
    """按顺序应用所有未应用的迁移，返回最终版本号。

    Raises:
        MigrationError: 任一迁移执行失败（整体回滚）。
    """
    _ensure_bookkeeping(conn)
    for version, name, filename in pending(conn):
        path = os.path.join(SQL_DIR, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                script = f.read()
        except OSError as e:
            raise MigrationError(f'读不到迁移文件 {filename}: {e!r}') from e

        try:
            # 必须显式 BEGIN：Python sqlite3 的隐式事务只覆盖 DML，
            # CREATE TABLE 之类的 DDL 会被自动提交，回滚时留下半截 schema。
            conn.execute('BEGIN IMMEDIATE')
            try:
                for statement in _iter_statements(script):
                    conn.execute(statement)
                conn.execute(
                    'INSERT INTO schema_migrations (version, name) VALUES (?, ?)',
                    (version, name),
                )
                conn.execute('COMMIT')
            except Exception:
                conn.execute('ROLLBACK')
                raise
        except Exception as e:              # noqa: BLE001 - 统一包装成 MigrationError
            raise MigrationError(f'迁移 {version} ({name}) 失败: {e!r}') from e

    return current_version(conn)
