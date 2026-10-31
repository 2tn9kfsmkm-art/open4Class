"""Store 抽象：CSV 与 SQLite 两个实现必须给出**同样形状**的 DataFrame。

这层是 P6 的接缝：上层（loading.py、设置窗口）只认 Store，
换存储时不用改业务代码。
"""

from datetime import date

import pytest
from pandas import DataFrame

from data.store import APPS_COLUMNS, CsvStore
from data.sqlite_store import SqliteStore

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]


@pytest.fixture(params=["csv", "sqlite"])
def store(request, tmp_dir):
    if request.param == "csv":
        directory = tmp_dir / "datas"
        directory.mkdir()
        s = CsvStore(str(directory))
    else:
        s = SqliteStore(str(tmp_dir / "classmanager.db"))
    yield s
    s.close()


class TestNames:
    def test_roundtrip(self, store):
        store.save_names(DataFrame({"name": ["张三", "李四"]}))
        assert store.load_names()["name"].tolist() == ["张三", "李四"]

    def test_empty_state_is_readable(self, store):
        assert len(store.load_names()) == 0


class TestCourses:
    def test_roundtrip(self, store):
        store.save_courses(DataFrame({"课程": ["语文", "数学"]}))
        assert store.load_courses()["课程"].tolist() == ["语文", "数学"]


class TestClasslist:
    def test_roundtrip(self, store):
        df = DataFrame([["语文", "数学", "", "", ""],
                        ["英语", "", "", "", ""]], columns=WEEKDAYS)
        store.save_classlist(df)
        loaded = store.load_classlist()
        assert list(loaded.columns) == WEEKDAYS
        assert loaded.iloc[0, 0] == "语文"
        assert loaded.iloc[1, 0] == "英语"

    def test_empty_cells_become_empty_string(self, store):
        df = DataFrame([["语文", "", "", "", ""]], columns=WEEKDAYS)
        store.save_classlist(df)
        assert store.load_classlist().iloc[0, 1] in ("", None) or str(
            store.load_classlist().iloc[0, 1]) == "nan"


class TestOnduty:
    def test_roundtrip(self, store):
        df = DataFrame({
            "2026-11-02": ["张三 扫", "李四 擦"],
            "2026-11-03": ["王五 扫", ""],
        })
        store.save_onduty(df)
        loaded = store.load_onduty()
        assert list(loaded.columns) == ["2026-11-02", "2026-11-03"]
        assert loaded.iloc[0, 0] == "张三 扫"
        # CSV 读回空单元格是 NaN，SQLite 是 ''；上层两者都当空处理
        empty = loaded.iloc[1, 1]
        assert empty == "" or str(empty) == "nan"

    def test_name_with_inner_spaces(self, store):
        store.save_onduty(DataFrame({"2026-11-02": ["曾   域 扫"]}))
        assert store.load_onduty().iloc[0, 0] == "曾   域 扫"

    def test_empty(self, store):
        assert len(store.load_onduty()) == 0


class TestApps:
    def test_roundtrip(self, store):
        store.save_apps(DataFrame([("浏览器", "C:/x.exe")], columns=APPS_COLUMNS))
        loaded = store.load_apps()
        assert loaded.iloc[0, 0] == "浏览器"
        assert loaded.iloc[0, 1] == "C:/x.exe"


class TestFactory:
    def test_env_switch_to_sqlite(self, tmp_dir, monkeypatch):
        monkeypatch.setenv("CLASSMANAGER_STORAGE", "sqlite")
        monkeypatch.setattr("data.sqlite_store.default_db_path",
                            lambda: str(tmp_dir / "auto.db"))
        from data.store import get_store
        s = get_store()
        assert isinstance(s, SqliteStore)
        s.close()

    def test_defaults_to_csv(self, monkeypatch):
        monkeypatch.delenv("CLASSMANAGER_STORAGE", raising=False)
        from data.store import get_store
        assert isinstance(get_store(), CsvStore)
