"""CSV → SQLite 一次性迁移。"""

import json

import pandas as pd
import pytest

from data.sqlite_repo import SqliteRepository
from tools.migrate_csv_to_sqlite import migrate, read_csv_dir

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]


@pytest.fixture
def csv_dir(tmp_dir):
    d = tmp_dir / "datas"
    d.mkdir()

    pd.DataFrame({"name": ["张三", "李四", "王五"]}).to_csv(
        d / "名单.csv", index=False, encoding="utf-8")

    pd.DataFrame({"课程": ["语文", "数学"]}).to_csv(
        d / "课程单.csv", index=False, encoding="utf-8")

    pd.DataFrame([
        ["语文", "数学", "", "", ""],
        ["英语", "", "", "", ""],
    ], columns=WEEKDAYS).to_csv(d / "课表.csv", index=False, encoding="utf-8")

    pd.DataFrame({
        "2026-11-02": ["张三 扫", "李四 擦"],
        "2026-11-03": ["王五 扫", "曾   域 擦"],
    }).to_csv(d / "未来值日.csv", index=False, encoding="utf-8")

    pd.DataFrame({
        "软件链接": ["浏览器"],
        "path": ["C:/x.exe"],
    }).to_csv(d / "应用路径.csv", index=False, encoding="utf-8")

    (d / "settings.json").write_text(
        json.dumps({"class_short_name": "高三八班"}, ensure_ascii=False),
        encoding="utf-8")
    (d / "data.json").write_text('{"last_login": "20261010"}', encoding="utf-8")
    return d


class TestReadCsvDir:
    def test_students(self, csv_dir):
        assert read_csv_dir(str(csv_dir))["students"] == ["张三", "李四", "王五"]

    def test_courses(self, csv_dir):
        assert read_csv_dir(str(csv_dir))["courses"] == ["语文", "数学"]

    def test_template_only_keeps_non_empty(self, csv_dir):
        template = read_csv_dir(str(csv_dir))["template"]
        assert (1, 1, "语文") in template
        assert (2, 1, "数学") in template
        assert all(name for _, _, name in template)
        assert len(template) == 3          # 语文/数学/英语

    def test_onduty_split_by_last_space(self, csv_dir):
        entries = read_csv_dir(str(csv_dir))["onduty"]
        assert len(entries) == 4
        inner = [e for e in entries if e.date.isoformat() == "2026-11-03"]
        assert {e.student for e in inner} == {"王五", "曾   域"}

    def test_apps(self, csv_dir):
        apps = read_csv_dir(str(csv_dir))["apps"]
        assert apps[0].name == "浏览器" and apps[0].path == "C:/x.exe"

    def test_kv(self, csv_dir):
        kv = read_csv_dir(str(csv_dir))["kv"]
        assert kv["user_settings"]["class_short_name"] == "高三八班"
        assert kv["last_login"] == "20261010"

    def test_missing_files_are_skipped(self, tmp_dir):
        empty = tmp_dir / "empty"
        empty.mkdir()
        data = read_csv_dir(str(empty))
        assert data["students"] == [] and data["apps"] == []


class TestMigrate:
    def test_writes_everything(self, csv_dir, tmp_dir):
        db = str(tmp_dir / "out.db")
        stats = migrate(str(csv_dir), db)

        assert stats == {"students": 3, "courses": 2, "template": 3,
                         "onduty": 4, "apps": 1, "kv": 2}

        repo = SqliteRepository(db)
        try:
            assert repo.list_students() == ["张三", "李四", "王五"]
            assert repo.list_courses() == ["语文", "数学"]
            assert repo.get_classlist_template()[(1, 1)] == "语文"
            assert repo.get_kv("user_settings")["class_short_name"] == "高三八班"
        finally:
            repo.close()

    def test_marker_file_written(self, csv_dir, tmp_dir):
        db = str(tmp_dir / "out.db")
        migrate(str(csv_dir), db)
        marker = db + ".migrated_at"
        payload = json.loads(open(marker, encoding="utf-8").read())
        assert payload["students"] == 3

    def test_dry_run_does_not_create_db(self, csv_dir, tmp_dir):
        db = str(tmp_dir / "dry.db")
        stats = migrate(str(csv_dir), db, dry_run=True)
        assert stats["students"] == 3
        import os
        assert not os.path.exists(db)

    def test_rerun_is_idempotent(self, csv_dir, tmp_dir):
        db = str(tmp_dir / "out.db")
        migrate(str(csv_dir), db)
        migrate(str(csv_dir), db)
        repo = SqliteRepository(db)
        try:
            assert repo.list_students() == ["张三", "李四", "王五"]
        finally:
            repo.close()
