"""数据访问层：SQLite + Repository 抽象。

目录约定（HANDOFF §6）：
    db.py           连接、PRAGMA、事务
    repository.py   Repository 抽象基类
    sqlite_repo.py  SqliteRepository（唯一写入实现）
    migrations/     版本化 schema 迁移

业务代码只允许通过 Repository 访问数据，禁止直接 pd.read_csv（P6 收尾时统一改）。
"""
