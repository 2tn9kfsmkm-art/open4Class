"""系统托盘：主窗口/悬浮窗的备用入口。

希沃一体机上托盘可能被外壳隐藏，所以托盘只是"额外入口"，
主窗口最小化与悬浮窗不依赖它。
"""

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon(QSystemTrayIcon):
    def __init__(self, icon_path: str, on_show_main, on_show_mini, on_quit,
                 parent=None):
        super().__init__(QIcon(icon_path), parent)
        self._on_show_main = on_show_main
        self.setToolTip('班级管理系统')

        menu = QMenu()
        act_main = QAction('显示主界面', menu)
        act_main.triggered.connect(on_show_main)
        act_mini = QAction('显示悬浮窗', menu)
        act_mini.triggered.connect(on_show_mini)
        act_quit = QAction('退出', menu)
        act_quit.triggered.connect(on_quit)

        menu.addAction(act_main)
        menu.addAction(act_mini)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        # 双击托盘图标 → 回主界面（触摸屏上一般用右键菜单）
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_show_main()

    @staticmethod
    def available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()
