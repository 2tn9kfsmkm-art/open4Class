"""ClassManager 启动入口。

真正的窗口逻辑在 ui/window/main_window.py；这里只负责：
    1. 关闭 Qt6 的自动高 DPI 缩放（保持与 PyQt5 时代一致的尺寸）
    2. 单实例限制（第二次启动只负责把已有窗口唤到前台）
    3. 判断是否需要跑首次使用向导
    4. 打开主窗口
"""

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import bootstrap
from config import QSS_DIR, RESOURCE_DIR
from tools.qss2qt import setQss
from ui.window.main_window import Main
from ui.window.setup_wizard import SetupWizard

# 单实例锁：数据目录下的一个文本文件，内容是持有者的 PID
_LOCK_NAME = 'instance.lock'


_MUTEX_NAME = 'Global\\ClassManager-SingleInstance-v1'
_ERROR_ALREADY_EXISTS = 183


def _acquire_mutex():
    """用 Windows 命名互斥体做单实例锁。

    进程退出（包括崩溃/被强杀）时系统自动释放，不会留下需要清理的文件。
    成功返回句柄（调用方需保持引用直到退出），已被占用返回 None。
    """
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return None
        return handle
    except Exception:                           # noqa: BLE001
        return True                             # 拿不到就不阻止启动


def main():

    # Qt6 默认开启高 DPI 缩放（Qt5 默认关闭）。本机 175% 缩放下，
    # 界面整体放大 1.75 倍，行高从 57 变成 ~100 物理像素，课表装不下 12 行。
    # 关掉它即可恢复迁移前（PyQt5）的观感与尺寸。
    # 想用系统缩放的话，把这两行删掉。
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '0')
    os.environ.setdefault('QT_SCALE_FACTOR', '1')

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(RESOURCE_DIR + 'icon.png'))

    # ---- 多开限制 ----
    mutex = _acquire_mutex()
    if mutex is None:
        from PySide6.QtCore import QTimer
        box = QMessageBox(
            QMessageBox.Icon.Information, '已经在运行',
            '班级管理系统已经在运行了。\n'
            '请到任务栏、或右下角的「班级」小窗把它调出来。\n\n'
            '（这个提示 4 秒后自动关闭）', QMessageBox.StandardButton.Ok)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        QTimer.singleShot(4000, box.close)      # 无人操作也会自己消失
        box.exec()
        return

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

    def _activate():
        if mainwindow.isMinimized():
            mainwindow.showNormal()
        mainwindow.showMaximized()
        mainwindow.raise_()
        mainwindow.activateWindow()

    app.exec()


if __name__ == '__main__':
    main()
