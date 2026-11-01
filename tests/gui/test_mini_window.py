"""三层窗口：主窗口最小化 → 悬浮窗 → 小方块 → 返回。"""

from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from core.schedule import DEFAULT_LESSON_TIMES
from ui.window.mini_window import MiniChip, MiniController, MiniPanel


@pytest.fixture
def controller():
    back_called = []
    ctrl = MiniController(
        courses_provider=lambda: ['语文', '数学', '英语'],
        countdowns_provider=lambda: [{'label': '高考', 'date': '2027-06-07'}],
        lesson_times_provider=lambda: DEFAULT_LESSON_TIMES,
        on_back=lambda: back_called.append(True),
    )
    ctrl._back_called = back_called           # noqa: SLF001 - 测试内省
    yield ctrl
    ctrl.hide_all()


class TestPanel:
    def test_shows_slot_and_subject(self, controller):
        controller.panel.refresh(
            datetime(2026, 11, 2, 7, 45), ['语文', '数学'],
            [{'label': '高考', 'date': '2027-06-07'}], DEFAULT_LESSON_TIMES)
        assert controller.panel.slot_l.text() == '第 1 节'
        assert controller.panel.subject_l.text() == '语文'
        assert '距离高考' in controller.panel.countdown_l.text()

    def test_shows_next_lesson(self, controller):
        controller.panel.refresh(datetime(2026, 11, 2, 8, 25),
                                 ['语文', '数学'], [], DEFAULT_LESSON_TIMES)
        assert controller.panel.slot_l.text() == '课间'
        assert '数学' in controller.panel.next_l.text()

    def test_back_button_is_touch_sized(self, controller):
        assert controller.panel.back_pb.minimumHeight() >= 44

    def test_panel_does_not_take_focus(self, controller):
        assert controller.panel.testAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def test_fixed_width(self, controller):
        assert controller.panel.width() == 260


class TestChip:
    def test_shows_slot_and_short_subject(self, controller):
        controller.chip.refresh(datetime(2026, 11, 2, 7, 45),
                                ['信息技术'], DEFAULT_LESSON_TIMES)
        assert controller.chip.slot_l.text() == '第1节'
        assert controller.chip.subject_l.text() == '信息技术'

    def test_badge_when_break(self, controller):
        controller.chip.refresh(datetime(2026, 11, 2, 8, 25),
                                ['语文', '数学'], DEFAULT_LESSON_TIMES)
        assert controller.chip.slot_l.text() == '课间'
        assert controller.chip.subject_l.text() == '数学'

    def test_after_school(self, controller):
        controller.chip.refresh(datetime(2026, 11, 2, 19, 0),
                                ['语文'], DEFAULT_LESSON_TIMES)
        assert controller.chip.slot_l.text() == '放学'
        assert controller.chip.subject_l.text() == '—'

    def test_click_emits(self, controller, qtbot):
        qtbot.addWidget(controller.chip)
        controller.chip.show()
        with qtbot.waitSignal(controller.chip.clicked, timeout=1000):
            QTest.mouseClick(controller.chip, Qt.MouseButton.LeftButton)


class TestFlow:
    def test_show_panel_hides_chip(self, controller):
        controller.chip.show()
        controller.show_panel()
        assert controller.panel.isVisible()
        assert not controller.chip.isVisible()

    def test_collapse_switches_to_chip(self, controller):
        controller.show_panel()
        controller._collapse_to_chip()          # noqa: SLF001
        assert not controller.panel.isVisible()
        assert controller.chip.isVisible()

    def test_chip_click_restores_panel(self, controller):
        controller.chip.show()
        controller.panel.hide()
        controller._show_panel()               # noqa: SLF001
        assert controller.panel.isVisible()

    def test_back_calls_callback_and_hides(self, controller):
        controller.show_panel()
        controller.panel.back_pb.click()
        assert controller._back_called == [True]      # noqa: SLF001
        assert not controller.is_visible()
