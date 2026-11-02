"""悬浮层：顶部长条 + 右下角入口小窗，两个一起显示。"""

from datetime import datetime

import pytest
from PySide6.QtCore import Qt

from core.schedule import DEFAULT_LESSON_TIMES
from ui.window.mini_window import MiniController


@pytest.fixture
def controller():
    back = []
    ctrl = MiniController(
        courses_provider=lambda: ['语文', '数学', '英语'],
        countdowns_provider=lambda: [{'label': '春考', 'date': '2027-01-02'}],
        lesson_times_provider=lambda: DEFAULT_LESSON_TIMES,
        on_back=lambda: back.append(True),
    )
    ctrl._back_calls = back            # noqa: SLF001 - 测试内省
    yield ctrl
    ctrl.hide_all()


class TestTopBar:
    def test_lesson_shows_slot_and_subject(self, controller):
        controller.bar.refresh(datetime(2026, 11, 2, 7, 45),
                               ['语文', '数学'], [], DEFAULT_LESSON_TIMES)
        assert controller.bar.time_l.text() == '07:45'
        assert controller.bar.course_l.text() == '第 1 节 · 语文'
        assert '数学' in controller.bar.next_l.text()

    def test_break_shows_slot_only(self, controller):
        controller.bar.refresh(datetime(2026, 11, 2, 8, 25),
                               ['语文', '数学'], [], DEFAULT_LESSON_TIMES)
        assert controller.bar.course_l.text() == '课间'
        assert '数学' in controller.bar.next_l.text()

    def test_after_school(self, controller):
        controller.bar.refresh(datetime(2026, 11, 2, 19, 0),
                               ['语文'], [], DEFAULT_LESSON_TIMES)
        assert controller.bar.course_l.text() == '放学'
        assert '已结束' in controller.bar.next_l.text()

    def test_countdown_on_the_right(self, controller):
        controller.bar.refresh(datetime(2026, 11, 2, 7, 45), ['语文'],
                               [{'label': '春考', 'date': '2027-01-02'}],
                               DEFAULT_LESSON_TIMES)
        assert '距离春考' in controller.bar.info_l.text()

    def test_bar_is_a_strip(self, controller):
        assert controller.bar.height() == 96

    def test_never_steals_focus(self, controller):
        assert controller.bar.testAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating)


class TestEntryChip:
    def test_small_square(self, controller):
        assert controller.chip.width() == 112
        assert controller.chip.height() == 112

    def test_click_goes_back(self, controller):
        controller.show_all()
        controller.chip.clicked.emit()
        assert controller._back_calls == [True]      # noqa: SLF001
        assert not controller.is_visible()


class TestShowAll:
    def test_both_windows_together(self, controller):
        controller.show_all()
        assert controller.bar.isVisible()
        assert controller.chip.isVisible()

    def test_refresh_writes_real_time(self, controller):
        controller.show_all()
        controller.refresh()
        assert controller.bar.time_l.text() != '--:--'

    def test_hide_all_stops_timer(self, controller):
        controller.show_all()
        assert controller._timer.isActive()          # noqa: SLF001
        controller.hide_all()
        assert not controller._timer.isActive()      # noqa: SLF001

    def test_timer_is_one_second(self, controller):
        assert controller._timer.interval() == 1000  # noqa: SLF001
