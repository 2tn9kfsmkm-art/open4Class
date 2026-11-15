"""中文主题色选择对话框。

功能：
    - 调色板：色相条 + 饱和度/明度方块，可拖动取色
    - 预设色块（深红 / 藏青 / 墨绿 …）
    - 色号输入（#RRGGBB，认三位简写）与实时预览
    - 「从屏幕取色」：全屏截图后点哪取哪
    - 全中文

不用系统 QColorDialog 的原因：它的界面语言跟随系统、且不好嵌进向导。
"""

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

PRESETS = [
    ('深红', '#9B0D14'),
    ('藏青', '#1F3A93'),
    ('湖蓝', '#1F6FEB'),
    ('墨绿', '#1E6B45'),
    ('紫罗兰', '#6A3D9A'),
    ('赭石', '#A0522D'),
    ('青灰', '#2F4F4F'),
    ('玫红', '#C2185B'),
    ('橄榄', '#6B7A22'),
    ('石墨', '#37474F'),
]


def normalize_hex(text: str) -> str | None:
    """把用户输入规整成 #RRGGBB；不合法返回 None。"""
    t = (text or '').strip().lstrip('#')
    if len(t) == 3:
        t = ''.join(c * 2 for c in t)
    if len(t) != 6:
        return None
    try:
        int(t, 16)
    except ValueError:
        return None
    return '#' + t.upper()


# ---------------------------------------------------------------- 调色板
class _HueBar(QWidget):
    """横向色相条。"""

    changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue = 355

    def set_hue(self, hue: int):
        self._hue = max(0, min(359, int(hue)))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        for x in range(w):
            color = QColor.fromHsv(int(x * 359 / max(1, w - 1)), 255, 255)
            p.setPen(color)
            p.drawLine(x, 0, x, h)
        p.setPen(QPen(Qt.GlobalColor.white, 2))
        x = int(self._hue * (w - 1) / 359)
        p.drawRect(QRect(x - 3, 0, 6, h - 1))

    def _pick(self, pos: QPoint):
        hue = int(max(0, min(359, pos.x() * 359 / max(1, self.width() - 1))))
        self._hue = hue
        self.update()
        self.changed.emit(hue)

    def mousePressEvent(self, e):
        self._pick(e.position().toPoint())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._pick(e.position().toPoint())


class _SVPad(QWidget):
    """饱和度(x) × 明度(y) 方块。"""

    changed = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 130)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._hue = 355
        self._s = 1.0
        self._v = 1.0

    def set_hue(self, hue: int):
        self._hue = hue
        self.update()

    def set_color(self, color: QColor):
        h, s, v, _ = color.getHsv()
        if h >= 0:
            self._hue = h
        self._s, self._v = s / 255, v / 255
        self.update()

    def color(self) -> QColor:
        return QColor.fromHsv(self._hue, int(self._s * 255), int(self._v * 255))

    def paintEvent(self, event):
        img = QImage(self.width(), self.height(), QImage.Format.Format_RGB32)
        for x in range(img.width()):
            s = int(x * 255 / max(1, img.width() - 1))
            for y in range(img.height()):
                v = int((1 - y / max(1, img.height() - 1)) * 255)
                img.setPixelColor(x, y, QColor.fromHsv(self._hue, s, v))
        QPainter(self).drawImage(0, 0, img)
        p = QPainter(self)
        x = int(self._s * (self.width() - 1))
        y = int((1 - self._v) * (self.height() - 1))
        p.setPen(QPen(Qt.GlobalColor.white, 2))
        p.drawEllipse(QPoint(x, y), 6, 6)
        p.setPen(QPen(Qt.GlobalColor.black, 1))
        p.drawEllipse(QPoint(x, y), 8, 8)

    def _pick(self, pos: QPoint):
        self._s = max(0.0, min(1.0, pos.x() / max(1, self.width() - 1)))
        self._v = max(0.0, min(1.0, 1 - pos.y() / max(1, self.height() - 1)))
        self.update()
        self.changed.emit(self.color())

    def mousePressEvent(self, e):
        self._pick(e.position().toPoint())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._pick(e.position().toPoint())


# ---------------------------------------------------------------- 屏幕取色
class ScreenPicker(QWidget):
    """全屏截图 + 点击取色。Esc 取消。"""

    picked = Signal(QColor)

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self._pixmap = QPixmap()
        self._hover = QPoint(-100, -100)
        self._load()

    def _load(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._screen = screen
        geo = screen.geometry()
        self.setGeometry(geo)
        self._pixmap = screen.grabWindow(0)
        self._offset = geo.topLeft()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)
        p.fillRect(self.rect(), QColor(0, 0, 0, 60))
        if self._pixmap.isNull():
            return
        pos = self._hover
        if not self.rect().contains(pos):
            return
        color = self._pixmap.toImage().pixelColor(pos)
        # 放大镜
        size = 90
        src = QRect(pos.x() - 6, pos.y() - 6, 12, 12)
        p.drawPixmap(QRect(pos.x() + 18, pos.y() + 18, size, size),
                     self._pixmap, src)
        p.setPen(QPen(Qt.GlobalColor.white, 1))
        p.drawRect(QRect(pos.x() + 18, pos.y() + 18, size, size))
        # 色值提示
        text = f'{color.name().upper()}  单击取色 · Esc 取消'
        box = QRect(pos.x() + 18, pos.y() + 18 + size + 6, 230, 26)
        p.fillRect(box, QColor(0, 0, 0, 180))
        p.setPen(QColor(255, 255, 255))
        p.drawText(box.adjusted(8, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, text)

    def mouseMoveEvent(self, e):
        self._hover = e.position().toPoint()
        self.update()

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        if not self._pixmap.isNull() and self.rect().contains(pos):
            self.picked.emit(self._pixmap.toImage().pixelColor(pos))
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()


# ---------------------------------------------------------------- 对话框
class ThemeColorDialog(QDialog):
    def __init__(self, current: str = '#9B0D14', parent=None):
        super().__init__(parent)
        self.setWindowTitle('选择主题色')
        self.setMinimumWidth(460)
        self._color = normalize_hex(current) or '#9B0D14'

        root = QVBoxLayout(self)

        # 调色板
        self.hue_bar = _HueBar(self)
        self.sv_pad = _SVPad(self)
        self.hue_bar.changed.connect(self._on_hue)
        self.sv_pad.changed.connect(self._on_pad)
        root.addWidget(self.sv_pad)
        root.addWidget(self.hue_bar)

        # 预设
        root.addWidget(QLabel('常用颜色：'))
        grid = QGridLayout()
        grid.setSpacing(6)
        for idx, (name, hex_color) in enumerate(PRESETS):
            btn = QPushButton(name)
            btn.setToolTip(hex_color)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f'QPushButton {{ background: {hex_color}; color: white;'
                f' border: none; border-radius: 4px; padding: 5px 8px; }}')
            btn.clicked.connect(lambda _=False, c=hex_color: self._apply(c))
            grid.addWidget(btn, idx // 5, idx % 5)
        root.addLayout(grid)

        # 色号 + 屏幕取色
        row = QHBoxLayout()
        row.addWidget(QLabel('色号：'))
        self.hex_le = QLineEdit(self._color)
        self.hex_le.setPlaceholderText('#RRGGBB')
        self.hex_le.setMaxLength(7)
        self.hex_le.textChanged.connect(self._on_text)
        row.addWidget(self.hex_le, 1)
        self.pick_btn = QPushButton('从屏幕取色')
        self.pick_btn.clicked.connect(self._pick_screen)
        row.addWidget(self.pick_btn)
        root.addLayout(row)

        # 预览
        prev_row = QHBoxLayout()
        prev_row.addWidget(QLabel('预览：'))
        self.preview = QWidget()
        self.preview.setFixedHeight(40)
        prev_row.addWidget(self.preview, 1)
        root.addLayout(prev_row)

        self.hint = QLabel('')
        self.hint.setStyleSheet('color: #C62828; font-size: 9pt;')
        root.addWidget(self.hint)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        box.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)

        self._sync_from_color(self._color)

    # ----------------------------------------------------------
    def _sync_from_color(self, hex_color: str):
        color = QColor(hex_color)
        self.sv_pad.set_color(color)
        self.hue_bar.set_hue(max(0, color.hue()) if color.hue() >= 0 else 0)
        self._paint(hex_color)

    def _on_hue(self, hue: int):
        self.sv_pad.set_hue(hue)
        self._apply(self.sv_pad.color().name())

    def _on_pad(self, color: QColor):
        self._apply(color.name())

    def _apply(self, hex_color: str):
        value = normalize_hex(hex_color) or self._color
        self._color = value
        if self.hex_le.text().upper() != value:
            self.hex_le.blockSignals(True)
            self.hex_le.setText(value)
            self.hex_le.blockSignals(False)
        color = QColor(value)
        if color.hue() >= 0:
            self.hue_bar.blockSignals(True)
            self.hue_bar.set_hue(color.hue())
            self.hue_bar.blockSignals(False)
        self.sv_pad.set_color(color)
        self._paint(value)

    def _on_text(self, text: str):
        value = normalize_hex(text)
        if value:
            self.hint.setText('')
            self._apply(value)
        else:
            self.hint.setText('请输入 6 位十六进制色号，例如 #9B0D14')

    def _pick_screen(self):
        self.hide()
        picker = ScreenPicker()
        result = {}

        def on_picked(color: QColor):
            result['color'] = color.name().upper()

        picker.picked.connect(on_picked)
        picker.showFullScreen()
        picker.activateWindow()
        picker.raise_()
        # 模态等待取色结束
        while picker.isVisible():
            QGuiApplication.processEvents()
        self.show()
        self.raise_()
        if result.get('color'):
            self._apply(result['color'])

    def _paint(self, hex_color: str):
        self.preview.setStyleSheet(
            f'background: {hex_color}; border: 1px solid #DDDDDD;'
            f' border-radius: 4px;')
        self.hex_le.setStyleSheet(
            'QLineEdit { padding: 4px 6px; border: 1px solid #DDDDDD;'
            ' border-radius: 4px; }')

    def color(self) -> str:
        return normalize_hex(self.hex_le.text()) or self._color
