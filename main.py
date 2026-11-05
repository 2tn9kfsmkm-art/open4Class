"""ClassManager 启动入口。

真正的窗口逻辑在 ui/window/main_window.py；这里只负责：
    1. 关闭 Qt6 的自动高 DPI 缩放（保持与 PyQt5 时代一致的尺寸）
    2. 单实例限制（第二次启动只负责把已有窗口唤到前台）
    3. 判断是否需要跑首次使用向导
    4. 打开主窗口
"""

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import bootstrap
from config import QSS_DIR, RESOURCE_DIR
from tools.qss2qt import setQss
from ui.component.winutil import force_foreground
from ui.window.main_window import Main
from ui.window.setup_wizard import SetupWizard

# 单实例锁：数据目录下的一个文本文件，内容是持有者的 PID
_LOCK_NAME = 'instance.lock'


_MUTEX_NAME = 'Global\\ClassManager-SingleInstance-v1'
# 第二个实例通过这个文件请求"把窗口叫出来"，运行中的实例轮询后删除
_SHOW_REQUEST = 'show.request'
_PID_FILE = 'instance.pid'
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
        # 已有实例：留个"请显示窗口"的请求，然后自己退出
        from config import DATA_BASE
        # 关键：第二个进程此刻是前台，由它授权第一个进程抢前台
        try:
            import ctypes
            pid_file = os.path.join(DATA_BASE, _PID_FILE)
            with open(pid_file, 'r', encoding='utf-8') as f:
                other = int(f.read().strip() or 0)
            if other > 0:
                ctypes.windll.user32.AllowSetForegroundWindow(other)
        except Exception:                       # noqa: BLE001
            pass
        try:
            with open(os.path.join(DATA_BASE, _SHOW_REQUEST), 'w',
                      encoding='utf-8') as f:
                f.write(str(os.getpid()))
        except OSError as e:                    # noqa: BLE001
            print(f'[single-instance] 无法写入请求文件: {e!r}')
        print('已经有一个班级管理系统在运行，已请它把窗口调出来。')
        return

    # 只有超过 250% 才降字号：250%（教室常用）实测刚好，不需要缩。
    # 300% 时降约 15%，避免容器装不下放大的字。
    from ui.tokens import set_font_scale
    screen = app.primaryScreen()
    dpi_scale = (screen.logicalDotsPerInch() / 96.0) if screen else 1.0
    set_font_scale(1.0 - max(0.0, dpi_scale - 2.5) * 0.3)

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

    # 监听"叫窗口"请求（放在建窗口之前：即使主窗口还卡在询问框里也能响应）
    from config import DATA_BASE
    request_path = os.path.join(DATA_BASE, _SHOW_REQUEST)
    holder = {'win': None}

    def _activate():
        force_foreground(holder['win'])

    def _check_request():
        if os.path.exists(request_path):
            try:
                os.remove(request_path)
            except OSError:
                pass
            _activate()

    watcher = QTimer()
    watcher.setInterval(500)
    watcher.timeout.connect(_check_request)
    watcher.start()
    _check_request()                            # 启动瞬间清掉上次残留

    from config import DATA_BASE as _DB
    try:
        with open(os.path.join(_DB, _PID_FILE), 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
    except OSError:
        pass

    mainwindow = Main()
    holder['win'] = mainwindow
    mainwindow.showMaximized()
    _check_request()

    app.exec()


if __name__ == '__main__':
    main()
