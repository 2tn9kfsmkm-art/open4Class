"""中文主题色选择对话框。

Windows 自带的 QColorDialog 走系统语言，在中文系统上也可能显示英文，
而且原生取色器不好嵌进向导里，所以这里自己做一个：

    - 一排预设色（深红 / 藏青 / 墨绿 / 紫 / 赭石 …）
    - 可直接输入十六进制色号（#RRGGBB / RRGGBB 都认）
    - 实时预览
    - 全中文
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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


class ThemeColorDialog(QDialog):
    def __init__(self, current: str = '#9B0D14', parent=None):
        super().__init__(parent)
        self.setWindowTitle('选择主题色')
        self.setMinimumWidth(420)
        self._color = normalize_hex(current) or '#9B0D14'

        root = QVBoxLayout(self)

        root.addWidget(QLabel('预设颜色：'))
        grid = QGridLayout()
        grid.setSpacing(6)
        for idx, (name, hex_color) in enumerate(PRESETS):
            btn = QPushButton(name)
            btn.setToolTip(hex_color)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f'QPushButton {{ background: {hex_color}; color: white;'
                f' border: none; border-radius: 4px; padding: 6px 10px; }}')
            btn.clicked.connect(
                lambda _=False, c=hex_color: self._apply(c))
            grid.addWidget(btn, idx // 5, idx % 5)
        root.addLayout(grid)

        row = QHBoxLayout()
        row.addWidget(QLabel('色号：'))
        self.hex_le = QLineEdit(self._color)
        self.hex_le.setPlaceholderText('#RRGGBB')
        self.hex_le.setMaxLength(7)
        self.hex_le.textChanged.connect(self._on_text)
        row.addWidget(self.hex_le, 1)
        root.addLayout(row)

        prev_row = QHBoxLayout()
        prev_row.addWidget(QLabel('预览：'))
        self.preview = QWidget()
        self.preview.setFixedHeight(44)
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

        self._paint()

    # ----------------------------------------------------------
    def _apply(self, hex_color: str):
        self._color = hex_color
        self.hex_le.setText(hex_color)
        self._paint()

    def _on_text(self, text: str):
        value = normalize_hex(text)
        if value:
            self._color = value
            self.hint.setText('')
            self._paint()
        else:
            self.hint.setText('请输入 6 位十六进制色号，例如 #9B0D14')

    def _paint(self):
        self.preview.setStyleSheet(
            f'background: {self._color}; border: 1px solid #DDDDDD;'
            f' border-radius: 4px;')
        self.hex_le.setStyleSheet(
            'QLineEdit { padding: 4px 6px; border: 1px solid #DDDDDD;'
            ' border-radius: 4px; }')

    def color(self) -> str:
        return normalize_hex(self.hex_le.text()) or self._color
