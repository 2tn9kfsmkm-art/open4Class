"""首次使用向导：页面校验与完整走查。

不调用 exec_()，直接驱动 _on_next()，避免模态对话框阻塞测试。
校验失败的分支只测 page.validate()，不触发 QMessageBox。
"""

from pathlib import Path

import pytest

from pandas import read_csv
from PySide6.QtWidgets import QDialog, QTableWidgetItem

import bootstrap
from ui.window.setup_wizard import SetupWizard


def build_wizard(root):
    return SetupWizard(root=str(root))


def test_full_walk_writes_all_data(tmp_dir):
    wizard = build_wizard(tmp_dir)

    # ① 欢迎 → ② 班级信息
    wizard._on_next()
    assert wizard.current == 1

    info = wizard.pages[1]
    info.school_le.setText("测试中学")
    info.full_le.setText("高三（1）班")
    info.short_le.setText("高三一班")
    wizard._on_next()

    # ③ 名单
    assert wizard.current == 2
    roster = wizard.pages[2]
    roster.text_edit.setPlainText("张三\n李四\n王五")
    wizard._on_next()

    # ④ 课表
    assert wizard.current == 3
    classlist = wizard.pages[3]
    classlist.table.setItem(0, 0, QTableWidgetItem("语文"))
    classlist.table.setItem(0, 1, QTableWidgetItem("数学"))
    wizard._on_next()

    # ⑤ 值日
    assert wizard.current == 4
    onduty = wizard.pages[4]
    onduty.daily_sb.setValue(3)
    wizard._on_next()

    # ⑥ 完成
    assert wizard.current == 5
    wizard._on_next()

    assert wizard.result() == QDialog.Accepted

    from data.sqlite_store import SqliteStore
    store = SqliteStore(str(tmp_dir / "data" / "classmanager.db"))
    try:
        assert store.load_names()["name"].tolist() == ["张三", "李四", "王五"]
        assert store.load_classlist().iloc[0, 0] == "语文"
        assert len(store.load_onduty()) > 0
    finally:
        store.close()
    assert bootstrap.is_initialized(str(tmp_dir)) is True


def test_roster_rejects_empty(tmp_dir):
    wizard = build_wizard(tmp_dir)
    roster = wizard.pages[2]
    roster.text_edit.setPlainText("   \n\n")
    assert roster.validate() is not None


def test_roster_rejects_duplicates(tmp_dir):
    wizard = build_wizard(tmp_dir)
    roster = wizard.pages[2]
    roster.text_edit.setPlainText("张三\n李四\n张三")
    message = roster.validate()
    assert message is not None and "重名" in message


def test_classlist_rejects_empty(tmp_dir):
    wizard = build_wizard(tmp_dir)
    page = wizard.pages[3]
    assert page.validate() is not None


def test_classlist_accepts_one_cell(tmp_dir):
    wizard = build_wizard(tmp_dir)
    page = wizard.pages[3]
    page.table.setItem(2, 4, QTableWidgetItem("体育"))
    assert page.validate() is None
    df = page.dataframe()
    assert df.iloc[2, 4] == "体育"


def test_class_info_requires_fields(tmp_dir):
    wizard = build_wizard(tmp_dir)
    page = wizard.pages[1]
    page.school_le.setText("")
    assert page.validate() is not None
    page.school_le.setText("某中学")
    page.short_le.setText("这是一个超过十个字的班级短名")
    assert page.validate() is not None


def test_onduty_daily_cannot_exceed_roster(tmp_dir):
    wizard = build_wizard(tmp_dir)
    wizard.data["names"] = ["张三", "李四"]
    page = wizard.pages[4]
    page.daily_sb.setValue(5)
    df, err = page.build()
    assert df is None and err is not None


def test_onduty_can_be_skipped(tmp_dir):
    wizard = build_wizard(tmp_dir)
    wizard.data["names"] = ["张三", "李四"]
    page = wizard.pages[4]
    page.mode_cb.setCurrentIndex(2)
    df, err = page.build()
    assert df is None and err is None
    assert page.validate() is None


def test_onduty_group_mode_auto_split(tmp_dir):
    wizard = build_wizard(tmp_dir)
    wizard.data["names"] = ["A", "B", "C", "D", "E"]
    page = wizard.pages[4]
    page.mode_cb.setCurrentIndex(1)
    page.group_count_sb.setValue(2)

    groups = page.groups()
    assert list(groups) == ["第1组", "第2组"]
    assert groups["第1组"] == ["A", "C", "E"]

    df, err = page.build()
    assert err is None
    assert df.shape[0] == 3          # 行数 = 最大组人数


def test_onduty_group_mode_uses_imported_table(tmp_dir):
    wizard = build_wizard(tmp_dir)
    wizard.data["names"] = ["A", "B", "C"]
    page = wizard.pages[4]
    page._imported_groups = {"甲组": ["A", "B"], "乙组": ["C"]}
    page.mode_cb.setCurrentIndex(1)

    assert page.groups() == {"甲组": ["A", "B"], "乙组": ["C"]}
    df, err = page.build()
    assert err is None
    assert df.shape[0] == 2          # 按最大组补齐


def test_group_rows_hidden_outside_group_mode(tmp_dir, qapp):
    wizard = build_wizard(tmp_dir)
    page = wizard.pages[4]

    page.mode_cb.setCurrentIndex(0)
    qapp.processEvents()
    assert page.group_count_sb.isVisibleTo(page) is False

    page.mode_cb.setCurrentIndex(1)
    qapp.processEvents()
    assert page.group_count_sb.isVisibleTo(page) is True


def test_back_navigation_keeps_data(tmp_dir):
    wizard = build_wizard(tmp_dir)
    wizard._on_next()                      # ① → ②（班级信息，已有预填值）
    wizard._on_next()                      # ② 校验通过 → ③
    assert wizard.current == 2

    wizard.pages[2].text_edit.setPlainText("张三\n李四")
    wizard._on_next()                      # ③ 收集名单 → ④
    assert wizard.current == 3
    assert wizard.data["names"] == ["张三", "李四"]

    wizard._on_back()
    assert wizard.current == 2
    wizard._on_back()
    assert wizard.current == 1
    assert wizard.pages[2].names() == ["张三", "李四"]


class TestLayoutStability:
    """窗口由用户拖动缩放；切换模式不得改变窗口尺寸，也不得留下残影。"""

    def test_window_size_is_stable_across_modes(self, tmp_dir):
        wizard = SetupWizard(root=str(tmp_dir))
        wizard._goto(4)
        page = wizard.pages[4]

        page.mode_cb.setCurrentIndex(0)
        size_seq = (wizard.width(), wizard.height())
        page.mode_cb.setCurrentIndex(1)
        assert (wizard.width(), wizard.height()) == size_seq
        page.mode_cb.setCurrentIndex(2)
        assert (wizard.width(), wizard.height()) == size_seq

    def test_window_size_is_stable_across_pages(self, tmp_dir):
        wizard = SetupWizard(root=str(tmp_dir))
        wizard._goto(0)
        size = (wizard.width(), wizard.height())
        for index in range(6):
            wizard._goto(index)
            assert (wizard.width(), wizard.height()) == size

    def test_group_box_toggles_with_mode(self, tmp_dir):
        wizard = SetupWizard(root=str(tmp_dir))
        page = wizard.pages[4]
        page.mode_cb.setCurrentIndex(0)
        assert page.group_box.isVisibleTo(page) is False
        page.mode_cb.setCurrentIndex(1)
        assert page.group_box.isVisibleTo(page) is True

    def test_content_lives_in_scroll_area(self, tmp_dir):
        wizard = SetupWizard(root=str(tmp_dir))
        page = wizard.pages[4]
        assert page.scroll.widget() is page.content
        # 内容不会把页面撑破：滚动区自身可以被压到很小
        assert page.minimumSizeHint().height() < 400

    def test_resizable_by_user(self, tmp_dir):
        wizard = SetupWizard(root=str(tmp_dir))
        wizard.resize(1000, 760)
        assert (wizard.width(), wizard.height()) == (1000, 760)
        # 最小尺寸仍然生效，避免拖成一条线
        wizard.resize(200, 200)
        assert wizard.width() >= 760 and wizard.height() >= 520