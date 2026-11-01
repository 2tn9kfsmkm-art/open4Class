"""ClassManager 启动入口。

真正的窗口逻辑在 ui/window/main_window.py；这里只负责：
    1. 关闭 Qt6 的自动高 DPI 缩放（保持与 PyQt5 时代一致的尺寸）
    2. 判断是否需要跑首次使用向导
    3. 打开主窗口
"""

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

import bootstrap
from config import QSS_DIR, RESOURCE_DIR
from tools.qss2qt import setQss
from ui.window.main_window import Main
from ui.window.setup_wizard import SetupWizard


if __name__ == '__main__':
    # Qt6 默认开启高 DPI 缩放（Qt5 默认关闭）。在本机 175% 缩放下，
    # 界面整体放大 1.75 倍，行高从 57 变成 ~100 物理像素，课表装不下 12 行。
    # 关掉它即可恢复迁移前（PyQt5）的观感与尺寸。
    # 想用系统缩放的话，把这两行删掉。
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '0')
    os.environ.setdefault('QT_SCALE_FACTOR', '1')

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(RESOURCE_DIR + 'icon.png'))
    setQss(QSS_DIR + 'mainpage.qss', app)

    # 首次使用：先确认数据是否就绪，再创建主窗口。
    # 顺序很重要 —— 不能让向导卡在 Main.__init__ 里面（那样主窗口还没出来
    # 就先弹窗，用户会以为程序挂了）。
    if not bootstrap.is_initialized():
        if bootstrap.infer_legacy_state():
            # 老用户：已有名单和真实课表，静默补标记，不打扰
            bootstrap.mark_initialized(note='老用户推断')
        else:
            if not SetupWizard.run():
                sys.exit(0)

    mainwindow = Main()
    mainwindow.showMaximized()
    app.exec()