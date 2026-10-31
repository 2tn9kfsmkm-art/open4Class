"""data/ 层：迁移与 Repository 行为。

全部在临时目录里建库，不碰真实数据。
"""

from datetime import date

import pytest

import data.migrations.migrate as migrate
from core.models import AppEntry, OndutyEntry
from data.db import connect
from data.migrations.migrate import MigrationError, apply_pending, current_version
from data.sqlite_repo import SqliteRepository


@pytest.fixture
def db_path(tmp_dir):
    return str(tmp_dir / "classmanager.db")


@pytest.fixture
def repo(db_path):
    r = SqliteRepository(db_path)
    yield r
    r.close()


# ------------------------------------------------------------------ 迁移

class TestMigrations:
    def test_fresh_db_is_version_zero(self, db_path):
        conn = connect(db_path)
        try:
            assert current_version(conn) == 0
        finally:
            conn.close()

    def test_apply_brings_to_latest(self, db_path):
        conn = connect(db_path)
        try:
            assert apply_pending(conn) == migrate.MIGRATIONS[-1][0]
        finally:
            conn.close()

    def test_apply_is_idempotent(self, db_path):
        conn = connect(db_path)
        try:
            first = apply_pending(conn)
            second = apply_pending(conn)
            assert first == second
            rows = conn.execute('SELECT COUNT(*) AS n FROM schema_migrations').fetchone()
            assert rows['n'] == len(migrate.MIGRATIONS)
        finally:
            conn.close()

    def test_missing_file_raises(self, db_path, monkeypatch):
        monkeypatch.setattr(
            migrate, 'MIGRATIONS', [(99, 'broken', 'm9999_missing.sql')])
        conn = connect(db_path)
        try:
            with pytest.raises(MigrationError):
                apply_pending(conn)
        finally:
            conn.close()

    def test_bad_sql_rolls_back(self, db_path, tmp_dir, monkeypatch):
        bad = tmp_dir / 'm9999_bad.sql'
        bad.write_text(
            'CREATE TABLE good_one (a INTEGER);\nTHIS IS NOT SQL;\n',
            encoding='utf-8')
        monkeypatch.setattr(
            migrate, 'MIGRATIONS', [(99, 'bad', bad.name)])
        monkeypatch.setattr(migrate, 'HERE', str(tmp_dir))

        conn = connect(db_path)
        try:
            with pytest.raises(MigrationError):
                apply_pending(conn)
            # 事务回滚：坏脚本里的建表不应留下
            tables = {r['name'] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            assert 'good_one' not in tables
        finally:
            conn.close()


# ------------------------------------------------------------------ 学生/课程

class TestStudentsAndCourses:
    def test_students_keep_order(self, repo):
        repo.replace_students(["丙", "甲", "乙"])
        assert repo.list_students() == ["丙", "甲", "乙"]

    def test_replace_students_is_full_replacement(self, repo):
        repo.replace_students(["甲", "乙"])
        repo.replace_students(["丙"])
        assert repo.list_students() == ["丙"]

    def test_courses_roundtrip(self, repo):
        repo.replace_courses(["语文", "数学", "语文"])
        assert repo.list_courses() == ["语文", "数学"]


# ------------------------------------------------------------------ 课表

class TestClasslist:
    def test_template_roundtrip(self, repo):
        repo.save_classlist_template([(1, 1, "语文"), (5, 8, "班会")])
        assert repo.get_classlist_template() == {(1, 1): "语文", (5, 8): "班会"}

    def test_date_falls_back_to_template(self, repo):
        repo.save_classlist_template([(1, 1, "语文"), (1, 2, "数学")])
        # 2026-11-02 是周一
        assert repo.get_classlist_for_date(date(2026, 11, 2)) == ["语文", "数学"]

    def test_override_wins_over_template(self, repo):
        repo.save_classlist_template([(1, 1, "语文"), (1, 2, "数学")])
        repo.save_classlist_override(date(2026, 11, 2), ["体育", "自习"])
        assert repo.get_classlist_for_date(date(2026, 11, 2)) == ["体育", "自习"]

    def test_delete_override_restores_template(self, repo):
        repo.save_classlist_template([(1, 1, "语文")])
        repo.save_classlist_override(date(2026, 11, 2), ["体育"])
        repo.delete_classlist_override(date(2026, 11, 2))
        assert repo.get_classlist_for_date(date(2026, 11, 2)) == ["语文"]

    def test_weekend_has_no_template(self, repo):
        repo.save_classlist_template([(1, 1, "语文")])
        assert repo.get_classlist_for_date(date(2026, 11, 7)) == []   # 周六

    def test_empty_cells_survive(self, repo):
        repo.save_classlist_template([(1, 1, ""), (1, 2, "数学")])
        assert repo.get_classlist_for_date(date(2026, 11, 2)) == ["", "数学"]


# ------------------------------------------------------------------ 值日

class TestOnduty:
    def test_entries_roundtrip_in_order(self, repo):
        entries = [
            OndutyEntry(date(2026, 11, 3), 1, "李四", "擦"),
            OndutyEntry(date(2026, 11, 2), 0, "张三", "扫"),
        ]
        repo.replace_onduty(entries)
        assert [e.student for e in repo.list_onduty()] == ["张三", "李四"]

    def test_for_date_filters(self, repo):
        repo.replace_onduty([
            OndutyEntry(date(2026, 11, 2), 0, "张三", "扫"),
            OndutyEntry(date(2026, 11, 3), 0, "李四", "扫"),
        ])
        assert [e.student for e in repo.get_onduty_for_date(date(2026, 11, 2))] == ["张三"]

    def test_prune_returns_deleted_count(self, repo):
        repo.replace_onduty([
            OndutyEntry(date(2026, 11, 1), 0, "甲", "扫"),
            OndutyEntry(date(2026, 11, 2), 0, "乙", "扫"),
            OndutyEntry(date(2026, 11, 3), 0, "丙", "扫"),
        ])
        assert repo.prune_onduty_before(date(2026, 11, 3)) == 2
        assert len(repo.list_onduty()) == 1

    def test_students_with_inner_spaces_are_stored_verbatim(self, repo):
        repo.replace_onduty([OndutyEntry(date(2026, 11, 2), 0, "曾   域", "扫")])
        assert repo.get_onduty_for_date(date(2026, 11, 2))[0].student == "曾   域"


# ------------------------------------------------------------------ 应用 / kv

class TestAppsAndKv:
    def test_apps_order(self, repo):
        repo.replace_apps([AppEntry("浏览器", "C:/a.exe"), AppEntry("WPS", "C:/b.exe")])
        assert [a.name for a in repo.list_apps()] == ["浏览器", "WPS"]

    def test_kv_roundtrip_keeps_types(self, repo):
        repo.set_kv("user_settings", {"a": 1, "b": ["x"]})
        assert repo.get_kv("user_settings") == {"a": 1, "b": ["x"]}

    def test_kv_missing_returns_default(self, repo):
        assert repo.get_kv("nope", default="?") == "?"

    def test_kv_overwrite(self, repo):
        repo.set_kv("k", 1)
        repo.set_kv("k", 2)
        assert repo.get_kv("k") == 2
