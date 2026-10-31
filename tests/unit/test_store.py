"""Store 接口：SQLite 实现的行为与形状。

（CSV 实现已随"去掉 CSV 依赖"删除，这里只验 SQLite。）
"""

from datetime import date

import pytest
from pandas import DataFrame

from data.sqlite_store import SqliteStore
from data.store import APPS_COLUMNS

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"]


@pytest.fixture
def store(tmp_dir):
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

    def test_for_date_uses_template(self, store):
        store.save_classlist(DataFrame([["语文", "", "", "", ""]], columns=WEEKDAYS))
        assert store.load_classlist_for_date(date(2026, 11, 2)) == ["语文"]  # 周一

    def test_override_wins(self, store):
        store.save_classlist(DataFrame([["语文", "", "", "", ""]], columns=WEEKDAYS))
        store.save_classlist_override(date(2026, 11, 2), ["体育", "自习"])
        assert store.load_classlist_for_date(date(2026, 11, 2)) == ["体育", "自习"]

    def test_has_override(self, store):
        day = date(2026, 11, 2)
        assert store.has_classlist_override(day) is False
        store.save_classlist_override(day, ["体育"])
        assert store.has_classlist_override(day) is True
        store.delete_classlist_override(day)
        assert store.has_classlist_override(day) is False


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
