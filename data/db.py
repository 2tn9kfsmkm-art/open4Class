"""SQLite 连接的创建与配置。

约定：
- 日期一律以 ``TEXT`` + ``YYYY-MM-DD`` 存储，转换在 Repository 层完成
- 写操作一律在 ``with conn:`` 事务里
- 主线程与后台线程共享连接，所以 ``check_same_thread=False`` + 调用方串行化
"""

import sqlite3


def connect(path: str) -> sqlite3.Connection:
    """打开（或新建）数据库，并设好 SQLite 的推荐参数。

    Args:
        path: 数据库文件路径。
    Returns:
        sqlite3.Connection，行以 ``sqlite3.Row`` 返回（可按列名取值）。
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode = WAL')
    conn.execute('PRAGMA foreign_keys = ON')
    return conn
