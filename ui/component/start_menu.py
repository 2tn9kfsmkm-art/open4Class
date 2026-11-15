"""侧栏「开始菜单」：点学校 logo 后整块盖住侧栏的三个选项。

不圆角、不留边，按钮贴着底部，像 Windows 开始菜单那样占满整个侧栏区域。
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ui.tokens import COLORS

_ITEMS = ('设置', '最小化', '退出程序')


class StartMenu(QWidget):
    def __init__(self, on_settings, on_minimize, on_quit, parent=None):
        super().__init__(parent)
        # Popup：点外面自动关闭；不做圆角，铺满侧栏
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(6)
        layout.addStretch(1)          # 按钮贴着底部

        self.buttons = []
        for text, slot in zip(_ITEMS, (on_settings, on_minimize, on_quit)):
            btn = QPushButton(text)
            btn.setMinimumHeight(56)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                'QPushButton {'
                '  background: transparent;'
                '  color: white;'
                '  border: none;'
                '  border-radius: 6px;'
                '  font-size: 17pt;'
                '  text-align: center;'
                '}'
                'QPushButton:hover { background-color: rgba(255, 255, 255, 0.14); }'
                'QPushButton:pressed { background-color: rgba(0, 0, 0, 0.28); }'
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
        painter.setPen(Qt.PenStyle.NoPen)
        # 跟随主题色：比侧栏主色再深一档，避免和背景糊在一起
        color = QColor(COLORS['primary-deep'])
        color.setAlpha(250)
        painter.setBrush(color)
        painter.drawRect(self.rect())

    def hideEvent(self, event):
        super().hideEvent(event)
        cb = getattr(self, 'on_closed', None)
        if callable(cb):
            cb()

    def mousePressEvent(self, event):
        # 落在按钮以外的区域（包括原来 logo 的位置）就收起
        pos = event.position().toPoint()
        if not any(btn.geometry().contains(pos) for btn in self.buttons):
            self.close()
            return
        super().mousePressEvent(event)

    def show_over(self, top_left: QPoint, width: int, height: int):
        """正好盖住给定矩形（侧栏）。"""
        self.setFixedSize(width, height)
        self.move(top_left)
        self.show()
