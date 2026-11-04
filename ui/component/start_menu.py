"""侧栏底部的「开始菜单」：点学校 logo 向上弹出的三个选项。

用普通无边框面板而不是 QMenu —— QMenu 的内边距、对齐和圆角都很难调，
这里自己摆按钮，视觉效果与侧栏一致。
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ui.tokens import COLORS

_ITEMS = ('设置', '最小化', '退出程序')


class StartMenu(QWidget):
    def __init__(self, on_settings, on_minimize, on_quit, width=280, parent=None):
        super().__init__(parent)
        # Popup：点面板外面自动关闭
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.buttons = []
        for text, slot in zip(_ITEMS, (on_settings, on_minimize, on_quit)):
            btn = QPushButton(text)
            btn.setMinimumHeight(52)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                'QPushButton {'
                '  background: transparent;'
                '  color: white;'
                '  border: none;'
                '  border-radius: 8px;'
                '  font-size: 17pt;'
                '  text-align: center;'
                '}'
                'QPushButton:hover { background-color: rgba(0, 0, 0, 0.22); }'
                'QPushButton:pressed { background-color: rgba(0, 0, 0, 0.34); }'
            )
            btn.clicked.connect(self._make_handler(slot))
            layout.addWidget(btn)
            self.buttons.append(btn)

    def _make_handler(self, slot):
        def _run():
            self.close()
            slot()
        return _run

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 比侧栏更深一档，并用浅金细边和侧栏拉开层次
        painter.setBrush(QColor(88, 8, 12, 250))
        painter.setPen(QPen(QColor(201, 162, 39, 150), 1))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        painter.drawPath(path)

    def show_above(self, anchor_x: int, anchor_top: int):
        """在给定点的上方弹出。"""
        self.adjustSize()
        x = anchor_x
        y = anchor_top - self.height() - 6
        self.move(QPoint(x, max(0, y)))
        self.show()
