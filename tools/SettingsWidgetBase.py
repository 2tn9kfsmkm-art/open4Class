from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal


class SettingsWidgetBase(QWidget):
    """设置 Tab 基类：保存成功后 emit changed，由 SettingsDialog 收集。"""
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def save(self):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError