"""设置窗口的写入路径：SQLite 模式下必须落到数据库，而不是 CSV。

这些用例把存储切成 sqlite，然后直接调用各 Tab 的 save()，
验证数据确实进了 Repository（而不是被悄悄写回 CSV）。
"""

import pytest
from pandas import DataFrame

from data.store import reset_shared_store, shared_store


@pytest.fixture
def sqlite_mode(tmp_dir, monkeypatch):
    monkeypatch.setenv("CLASSMANAGER_STORAGE", "sqlite")
    monkeypatch.setattr("data.sqlite_store.default_db_path",
                        lambda: str(tmp_dir / "classmanager.db"))
    reset_shared_store()
    yield
    reset_shared_store()
    monkeypatch.delenv("CLASSMANAGER_STORAGE", raising=False)


def test_roster_save_goes_to_database(sqlite_mode):
    from ui.window.settings_window import StudentListWidget

    widget = StudentListWidget()
    widget.listw.clear()
    widget.listw.addItems(["张三", "李四"])
    widget.save()

    assert shared_store().load_names()["name"].tolist() == ["张三", "李四"]


def test_course_save_goes_to_database(sqlite_mode):
    from ui.window.settings_window import CourseEditorWidget

    widget = CourseEditorWidget()
    widget.course_list.clear()
    widget.course_list.addItems(["语文", "数学"])
    widget.model = None          # 只验证课程单写入
    widget.save()

    assert shared_store().load_courses()["课程"].tolist() == ["语文", "数学"]


def test_app_save_goes_to_database(sqlite_mode):
    from ui.window.add_app_dialog import AddApp

    dialog = AddApp()
    dialog.path_le.setText("C:/Program Files/App/app.exe")
    dialog.tag_le.setText("测试应用")
    dialog._append_current()
    dialog.save()

    df = shared_store().load_apps()
    assert df.iloc[0, 0] == "测试应用"
    assert df.iloc[0, 1] == "C:/Program Files/App/app.exe"


def test_onduty_save_goes_to_database(sqlite_mode):
    from data.store import shared_store as store
    from ui.window.settings_window import OndutySpawnWidget

    store().save_names(DataFrame({"name": ["张三", "李四", "王五"]}))
    widget = OndutySpawnWidget()
    widget.daily_sb.setValue(3)
    widget.weeks_sb.setValue(1)
    widget.overwrite_cb.setChecked(True)

    # generate 里有 QMessageBox，测试里替换掉
    from ui.window import settings_window as UserSettings
    saved = {}
    class FakeBox:
        Yes = 1
        @staticmethod
        def information(*a, **k): saved['info'] = True
        @staticmethod
        def question(*a, **k): return 1
        @staticmethod
        def warning(*a, **k): saved['warn'] = True

    original = UserSettings.QMessageBox
    UserSettings.QMessageBox = FakeBox
    try:
        widget.generate()
    finally:
        UserSettings.QMessageBox = original

    assert saved.get('info') is True
    assert len(store().load_onduty()) == 5      # 1 周 × 5 天
