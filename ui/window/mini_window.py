"""悬浮层：顶部长条 + 右下角入口小窗。

设计（2026-11 重做）：
    顶部长条：  22:58   第 5 节 · 物理   下一节 自习   距离春考 61 天

    右下角入口：[班级]  ← 点它回主界面

两个窗口同时显示、没有先后顺序；不存在"自动收缩"那一套。
"""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtCore import QRectF
from PySide6.QtGui import (
    QColor, QGuiApplication, QMouseEvent, QPainter, QPainterPath,
)
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from core.schedule import describe, lesson_state
from ui.tokens import COLORS

_FLAGS = (
    Qt.WindowType.Tool
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
)

_BAR_HEIGHT = 96
_CHIP_SIZE = 112


def _course_at(courses, index) -> str:
    if index is None or index >= len(courses):
        return ''
    return str(courses[index] or '').strip()


def _primary_geometry():
    screen = QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else None


def _segment_progress(now: datetime, state: dict) -> float:
    """当前时段（一节课或一个课间）已经过去的比例。"""
    start, end = state.get('starts_at'), state.get('ends_at')
    if start is None or end is None or start >= end:
        return 0.0
    def _secs(t):
        return t.hour * 3600 + t.minute * 60 + t.second

    total = _secs(end) - _secs(start)
    if total <= 0:
        return 0.0
    passed = _secs(now.time()) - _secs(start)
    return max(0.0, min(1.0, passed / total))


def _nearest_countdown(now: datetime, countdowns) -> str:
    best, best_days = '', None
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
    return best


class TopBar(QWidget):
    """顶部长条：左时间、中课表、右其他信息。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedHeight(_BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(24)

        self._progress = 0.0        # 当前时段已过比例 0~1
        self.time_l = QLabel('--:--')
        self.time_l.setStyleSheet(
            f'color: {COLORS["white"]}; font-size: 26pt; font-weight: bold;'
            'background: transparent; border: none;')
        self.course_l = QLabel('')
        self.course_l.setStyleSheet(
            f'color: {COLORS["white"]}; font-size: 18pt; font-weight: bold;'
            'background: transparent; border: none;')
        self.next_l = QLabel('')
        self.next_l.setStyleSheet('color: #F2DCDD; font-size: 12pt; background: transparent; border: none;')
        self.info_l = QLabel('')
        self.info_l.setStyleSheet('color: #F2DCDD; font-size: 12pt; background: transparent; border: none;')

        self.time_l.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.time_l)
        layout.addSpacing(28)
        layout.addWidget(self.course_l)
        layout.addSpacing(12)
        layout.addWidget(self.next_l)
        layout.addStretch(1)
        for _lbl in (self.time_l, self.course_l, self.next_l, self.info_l):
            _lbl.setAutoFillBackground(False)
        layout.addWidget(self.info_l)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(155, 13, 20, 175))
        painter.drawRoundedRect(self.rect(), 16, 16)

        # 顶部进度条：当前这节课/这个课间还剩多少（红色不透明、无边框）
        if self._progress > 0:
            bar_w = int(self.width() * min(1.0, self._progress))
            # 按顶条圆角裁剪，避免进度条自己的圆角在左上角露出来
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(self.rect()), 16, 16)
            painter.save()
            painter.setClipPath(clip)
            # 底槽：整条浅灰，表示"这一整段"
            painter.setBrush(QColor(255, 255, 255, 70))
            painter.drawRect(0, 0, self.width(), 5)
            # 已过部分：红色
            painter.setBrush(QColor(230, 40, 45, 255))
            painter.drawRect(0, 0, bar_w, 5)
            # 分界处一条浅色竖线
            painter.setBrush(QColor(255, 255, 255, 220))
            painter.drawRect(max(0, bar_w - 2), 0, 2, 5)
            painter.restore()

    def refresh(self, now, courses, countdowns, lesson_times=None):
        self.time_l.setText(now.strftime('%H:%M'))
        state = lesson_state(now, lesson_times)
        slot, subject = describe(state, list(courses or []))
        if state['status'] == 'lesson':
            self.course_l.setText(subject)      # 只写科目，不带「第 N 节」
        else:
            self.course_l.setText(slot)

        nxt = state.get('next')
        text = _course_at(courses, nxt) if nxt is not None else ''
        if state['status'] == 'after':
            self.next_l.setText('今天的课已结束')
        elif text:
            self.next_l.setText(f'下一节 {text}')
        else:
            self.next_l.setText('')

        self.info_l.setText(_nearest_countdown(now, countdowns))
        new_progress = _segment_progress(now, state)
        if abs(new_progress - self._progress) > 0.001:
            self._progress = new_progress
            self.update()          # 进度条是自绘的，必须主动请求重绘

    def place(self):
        geo = _primary_geometry()
        if geo is None:
            return
        width = min(1700, int(geo.width() * 0.88))
        self.setFixedWidth(width)
        self.move(geo.left() + (geo.width() - width) // 2, geo.top() + 12)


class EntryChip(QWidget):
    """右下角入口小窗：只有两个字，点一下回主界面。"""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(_CHIP_SIZE, _CHIP_SIZE)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._drag_offset = None
        self._dragged = False
        self._user_moved = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel('班级')
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(
            f'color: {COLORS["white"]}; font-size: 20pt; font-weight: bold;'
            'background: transparent; border: none;')
        layout.addWidget(self.label)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(155, 13, 20, 190))
        painter.drawRoundedRect(self.rect(), 16, 16)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (event.globalPosition().toPoint()
                                 - self.frameGeometry().topLeft())
            self._dragged = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_offset is not None and (
                event.buttons() & Qt.MouseButton.LeftButton):
            target = event.globalPosition().toPoint() - self._drag_offset
            if (target - self.pos()).manhattanLength() > 3:
                self._dragged = True
                self._user_moved = True
            self.move(target)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        # 拖过就不算点击，避免移动完又跳回主界面
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._dragged:
                self.clicked.emit()
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def place(self):
        if self._user_moved:
            return                      # 用户拖过位置，就尊重他的选择
        geo = _primary_geometry()
        if geo is None:
            return
        self.move(geo.right() - self.width() - 28,
                  geo.bottom() - self.height() - 28)


class MiniController:
    """管两个窗口：一起显示、一起隐藏，每秒刷新一次。"""

    def __init__(self, courses_provider, countdowns_provider,
                 lesson_times_provider, on_back):
        self._courses = courses_provider
        self._countdowns = countdowns_provider
        self._lesson_times = lesson_times_provider
        self._on_back = on_back

        self.bar = TopBar()
        self.chip = EntryChip()
        self.chip.clicked.connect(self._back)

        self._timer = QTimer(self.bar)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.refresh)

    # ---- 显示 / 隐藏 ----
    def show_all(self):
        self.refresh()
        self.bar.place()
        self.chip.place()
        self.bar.show()
        self.chip.show()
        self.bar.raise_()
        self.chip.raise_()
        self._timer.start()

    def hide_all(self):
        self._timer.stop()
        self.bar.hide()
        self.chip.hide()

    def is_visible(self):
        return self.bar.isVisible() or self.chip.isVisible()

    # ---- 刷新 ----
    def refresh(self):
        now = datetime.now()
        self.bar.time_l.setText(now.strftime('%H:%M'))   # 时间最要紧，先写
        try:
            courses = self._courses()
        except Exception:                       # noqa: BLE001
            courses = []
        try:
            countdowns = self._countdowns()
        except Exception:                       # noqa: BLE001
            countdowns = []
        try:
            times = self._lesson_times()
        except Exception:                       # noqa: BLE001
            times = None
        self.bar.refresh(now, courses, countdowns, times)

    def _back(self):
        self.hide_all()
        if callable(self._on_back):
            self._on_back()
