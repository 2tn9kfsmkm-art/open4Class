"""悬浮窗的三层形态：

    主窗口 --最小化--> 悬浮窗（完整面板） --N 秒无操作--> 小方块（右下角）
                          ^                                  |
                          +----------- 点小方块 --------------+

设计底线：不抢焦点、不挡操作、点空白不响应。
"""

from datetime import datetime

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from core.schedule import describe, lesson_state
from ui.tokens import COLORS, FONTS

# 面板多久没被理会自动缩成小方块
COLLAPSE_MS = 20_000

_BASE_FLAGS = (
    Qt.WindowType.Tool
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
)

_PANEL_QSS = f"""

QWidget#mini_panel QLabel {{ color: {COLORS['white']}; background: transparent; }}
QLabel#mini_time {{ font-size: 30pt; font-weight: bold; }}
QLabel#mini_slot {{ font-size: 13pt; color: #F2DCDD; }}
QLabel#mini_subject {{ font-size: 20pt; font-weight: bold; padding-top: 4px; }}
QLabel#mini_next {{ font-size: 11pt; color: #F2DCDD; }}
QLabel#mini_countdown {{ font-size: 11pt; color: #F2DCDD; }}
QPushButton#mini_back {{
    background-color: rgba(255, 255, 255, 0.16);
    color: {COLORS['white']};
    border: none;
    border-radius: 8px;
    font-size: 13pt;
    font-weight: bold;
    margin: 0px;
    padding: 0px;
}}
QPushButton#mini_back:pressed {{ background-color: rgba(0, 0, 0, 0.25); }}
"""

_CHIP_QSS = f"""

QWidget#mini_chip QLabel {{ color: {COLORS['white']}; background: transparent; }}
QLabel#chip_slot {{ font-size: 11pt; color: #EDEDED; }}
QLabel#chip_subject {{ font-size: 15pt; font-weight: bold; }}
"""


def _course_at(courses, index) -> str:
    if index is None or index >= len(courses):
        return ''
    return str(courses[index] or '').strip()


def _primary_geometry():
    screen = QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else None


class MiniPanel(QWidget):
    """完整悬浮窗：时间 + 当前节次 + 科目 + 下一节 + 最近倒计时 + 返回。"""

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(_BASE_FLAGS)
        # 出现时不抢焦点：老师正在打字也不会被打断
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # 半透明背景必须开这个属性，否则 QSS 的 rgba 会被画成实色
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(260)
        self.setObjectName('mini_panel')
        self.setStyleSheet(_PANEL_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        self.time_l = QLabel('--:--')
        self.time_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_l.setObjectName('mini_time')
        self.slot_l = QLabel('')
        self.slot_l.setObjectName('mini_slot')
        self.subject_l = QLabel('')
        self.subject_l.setObjectName('mini_subject')
        self.subject_l.setWordWrap(True)
        self.next_l = QLabel('')
        self.next_l.setObjectName('mini_next')
        self.countdown_l = QLabel('')
        self.countdown_l.setObjectName('mini_countdown')

        self.back_pb = QPushButton('返回主界面')
        self.back_pb.setObjectName('mini_back')
        self.back_pb.setFixedHeight(52)
        self.back_pb.setCursor(Qt.CursorShape.PointingHandCursor)   # 触摸目标
        self.back_pb.pressed.connect(self.back_requested.emit)

        for w in (self.time_l, self.slot_l, self.subject_l,
                  self.next_l, self.countdown_l):
            layout.addWidget(w)
        layout.addSpacing(6)
        layout.addWidget(self.back_pb)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(155, 13, 20, 200))
        painter.drawRoundedRect(self.rect(), 16, 16)

    def mousePressEvent(self, event):
        # 兜底：面板没有焦点，某些环境下按钮收不到点击
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() >= self.height() - 60:
                self.back_requested.emit()
                return
        super().mousePressEvent(event)

    # ---- 内容刷新 ----
    def refresh(self, now: datetime, courses, countdowns, lesson_times=None):
        self.time_l.setText(now.strftime('%H:%M'))
        state = lesson_state(now, lesson_times)
        slot, subject = describe(state, list(courses or []))
        self.slot_l.setText(slot)
        self.subject_l.setText(subject)

        nxt = state.get('next')
        if nxt is not None and nxt < len(courses or []):
            text = str(courses[nxt] or '').strip()
            self.next_l.setText(f'下一节 {nxt + 1}：{text}' if text else '')
        elif state['status'] == 'after':
            self.next_l.setText('今天的课已结束')
        else:
            self.next_l.setText('')

        self.countdown_l.setText(_nearest_countdown(now, countdowns))
        self.layout().activate()
        self.setFixedHeight(self.sizeHint().height())

    # ---- 定位：主屏右侧垂直居中 ----
    def place(self):
        geo = _primary_geometry()
        if geo is None:
            return
        x = geo.right() - self.width() - 24
        y = geo.top() + (geo.height() - self.height()) // 2
        self.move(x, y)


class MiniChip(QWidget):
    """缩成右下角的小方块：只写当前课（课间写下一节）。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(_BASE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # 半透明背景必须开这个属性，否则 QSS 的 rgba 会被画成实色
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(112, 112)
        self.setObjectName('mini_chip')
        self.setStyleSheet(_CHIP_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(0)
        self.slot_l = QLabel('')
        self.slot_l.setObjectName('chip_slot')
        self.slot_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subject_l = QLabel('')
        self.subject_l.setObjectName('chip_subject')
        self.subject_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subject_l.setWordWrap(True)
        layout.addWidget(self.slot_l)
        layout.addWidget(self.subject_l, 1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(110, 110, 115, 190))
        painter.drawRoundedRect(self.rect(), 14, 14)

    def refresh(self, now: datetime, courses, lesson_times=None):
        state = lesson_state(now, lesson_times)
        courses = list(courses or [])
        status = state['status']
        if status == 'lesson':
            self.slot_l.setText(f'第{state["current"] + 1}节')
            subject = _course_at(courses, state['current'])
        elif status == 'break':
            self.slot_l.setText('课间')
            subject = _course_at(courses, state['next'])
        elif status == 'before':
            self.slot_l.setText('课前')
            subject = _course_at(courses, 0)
        else:
            self.slot_l.setText('放学')
            subject = ''
        # 96px 见方、10pt 字，放得下 4 个字
        self.subject_l.setText(subject[:4] if subject else '—')

    def place(self):
        geo = _primary_geometry()
        if geo is None:
            return
        self.move(geo.right() - self.width() - 24,
                  geo.bottom() - self.height() - 24)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MiniController:
    """把"主窗口最小化 → 面板 → 小方块"三种状态的切换收在一起。"""

    def __init__(self, courses_provider, countdowns_provider,
                 lesson_times_provider, on_back):
        self._courses = courses_provider
        self._countdowns = countdowns_provider
        self._lesson_times = lesson_times_provider
        self._on_back = on_back

        self.panel = MiniPanel()
        self.chip = MiniChip()
        self.chip.clicked.connect(self._show_panel)
        self.panel.back_requested.connect(self._back)

        self._collapse = _make_timer(COLLAPSE_MS, self._collapse_to_chip)

    # ---- 显示 ----
    def show_panel(self):
        self.chip.hide()
        self.refresh()
        self.panel.place()
        self.panel.show()
        # 数据是异步加载的：稍后再刷一次，避免刚最小化时短暂空白
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, self.refresh)
        self._collapse.start()

    def hide_all(self):
        self._collapse.stop()
        self.panel.hide()
        self.chip.hide()

    def is_visible(self):
        return self.panel.isVisible() or self.chip.isVisible()

    # ---- 刷新 ----
    def refresh(self):
        now = datetime.now()
        courses = self._courses()
        countdowns = self._countdowns()
        times = self._lesson_times()
        if self.panel.isVisible():
            self.panel.refresh(now, courses, countdowns, times)
        if self.chip.isVisible():
            self.chip.refresh(now, courses, times)

    # ---- 状态切换 ----
    def _collapse_to_chip(self):
        if not self.panel.isVisible():
            return
        self._collapse.stop()
        self.panel.hide()
        self.chip.refresh(datetime.now(), self._courses(), self._lesson_times())
        self.chip.place()
        self.chip.show()

    def _show_panel(self):
        self.chip.hide()
        self.show_panel()

    def _back(self):
        self.hide_all()
        if callable(self._on_back):
            self._on_back()


def _make_timer(ms, slot):
    from PySide6.QtCore import QTimer
    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(ms)
    timer.timeout.connect(slot)
    return timer


def _nearest_countdown(now: datetime, countdowns) -> str:
    """只显示最近的那个倒计时，避免面板被撑高。"""
    best = None
    best_days = None
    for item in countdowns or []:
        try:
            label = str(item.get('label', '')).strip()
            target = datetime.strptime(str(item.get('date', '')), '%Y-%m-%d')
        except (AttributeError, ValueError):
            continue
        days = (target.date() - now.date()).days
        if days < 0:
            continue
        if best_days is None or days < best_days:
            best, best_days = f'距离{label} {days} 天', days
    return best or ''
