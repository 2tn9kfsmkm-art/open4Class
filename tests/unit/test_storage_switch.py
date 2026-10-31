"""CSV ↔ SQLite 切换。

切换必须做到"数据不丢"：两个方向各验一遍，外加设置窗口里的那按钮。
"""

import pytest
from pandas import DataFrame

import UserSettings
from data.sqlite_store import SqliteStore
from data.store import CsvStore
from config import DEFAULT_USER_SETTINGS
from tools.storage_switch import switch_to_csv, switch_to_sqlite

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]


def seed_csv(csv_dir):
    store = CsvStore(str(csv_dir))
    store.save_names(DataFrame({"name": ["张三", "李四", "王五"]}))
    store.save_courses(DataFrame({"课程": ["语文", "数学"]}))
    store.save_classlist(DataFrame([["语文", "数学", "", "", ""]], columns=WEEKDAYS))
    store.save_onduty(DataFrame({"2026-11-02": ["张三 扫", "李四 擦"]}))
    store.save_apps(DataFrame([("浏览器", "C:/x.exe")],
                              columns=["软件链接", "path"]))


@pytest.fixture
def dirs(tmp_dir):
    csv_dir = tmp_dir / "datas"
    csv_dir.mkdir()
    seed_csv(csv_dir)
    return str(csv_dir), str(tmp_dir / "classmanager.db")


class TestSwitchToSqlite:
    def test_migrates_everything(self, dirs):
        csv_dir, db = dirs
        switch_to_sqlite(csv_dir, db)

        store = SqliteStore(db)
        try:
            assert store.load_names()["name"].tolist() == ["张三", "李四", "王五"]
            assert store.load_courses()["课程"].tolist() == ["语文", "数学"]
            assert store.load_classlist().iloc[0, 0] == "语文"
            assert store.load_onduty().iloc[0, 0] == "张三 扫"
            assert store.load_apps().iloc[0, 0] == "浏览器"
        finally:
            store.close()

    def test_calls_backup(self, dirs):
        csv_dir, db = dirs
        called = []
        switch_to_sqlite(csv_dir, db, backup=lambda: called.append(1) or "C:/bak")
        assert called == [1]


class TestSwitchToCsv:
    def test_roundtrip_keeps_data(self, dirs, tmp_dir):
        csv_dir, db = dirs
        switch_to_sqlite(csv_dir, db)

        # 清空 CSV 再从数据库导回
        import shutil
        shutil.rmtree(csv_dir)
        import os
        os.makedirs(csv_dir)

        switch_to_csv(csv_dir, db)
        store = CsvStore(csv_dir)
        assert store.load_names()["name"].tolist() == ["张三", "李四", "王五"]
        assert store.load_courses()["课程"].tolist() == ["语文", "数学"]
        assert store.load_onduty().iloc[0, 0] == "张三 扫"

    def test_missing_db_is_harmless(self, dirs):
        csv_dir, db = dirs
        result = switch_to_csv(csv_dir, db)
        assert result["counts"]["students"] == 0


class TestSettingsButton:
    @pytest.fixture
    def env(self, tmp_dir, monkeypatch):
        """把设置窗口里的路径和配置读写都指向临时对象。"""
        csv_dir = tmp_dir / "datas"
        csv_dir.mkdir()
        seed_csv(csv_dir)
        db = str(tmp_dir / "classmanager.db")

        cfg = dict(DEFAULT_USER_SETTINGS)
        cfg["storage"] = "csv"
        monkeypatch.setattr(UserSettings, "FILE_DIR", str(csv_dir) + os.sep)
        monkeypatch.setattr(UserSettings, "default_db_path", lambda: db)
        monkeypatch.setattr(UserSettings, "load_user_settings", lambda: dict(cfg))
        monkeypatch.setattr(
            UserSettings, "save_user_settings", lambda d: cfg.update(d))
        return cfg, db

    def test_switch_to_sqlite_updates_settings(self, env, monkeypatch):
        cfg, db = env
        widget = UserSettings.GeneralWidget()
        widget._refresh_storage_ui()
        widget.storage_cb.setCurrentIndex(1)          # SQLite

        class Box:
            Yes = 1
            No = 0
            def question(self, *a, **k):
                return 1
            def information(self, *a, **k):
                pass
            def warning(self, *a, **k):
                pass
            def critical(self, *a, **k):
                pass

        class App:
            def quit(self):
                pass

        monkeypatch.setattr(UserSettings, "QMessageBox", Box())
        monkeypatch.setattr(UserSettings, "QApplication",
                            type("A", (), {"instance": staticmethod(lambda: App())}))
        monkeypatch.setattr(UserSettings.bootstrap, "backup_all", lambda: "C:/bak")

        widget._on_switch_storage()

        assert cfg["storage"] == "sqlite"
        import os.path
        assert os.path.exists(db)


import os  # noqa: E402  （测试里用到 os.sep / os.path）
