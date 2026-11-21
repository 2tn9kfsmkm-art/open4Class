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
from PySide6.QtGui import QGuiApplication
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


def _install_qt_chinese(app):
    """让 Qt 自带的对话框（取色器、消息框按钮等）显示中文。"""
    try:
        import os
        from PySide6.QtCore import QLibraryInfo, QTranslator

        candidates = [
            QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)]
        # 打包后翻译文件被放在 exe 旁的 translations/ 里
        try:
            from config import RESOURCE_BASE
            candidates.append(os.path.join(RESOURCE_BASE, 'translations'))
        except Exception:                          # noqa: BLE001
            pass
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'translations'))

        for folder in candidates:
            translator = QTranslator(app)
            if translator.load('qtbase_zh_CN', folder):
                app.installTranslator(translator)
                app._qt_zh_translator = translator     # 防止被 GC
                return True
    except Exception:                              # noqa: BLE001
        pass
    return False


def main():

    # Qt6 默认开启高 DPI 缩放（Qt5 默认关闭）。本机 175% 缩放下，
    # 界面整体放大 1.75 倍，行高从 57 变成 ~100 物理像素，课表装不下 12 行。
    # 关掉它即可恢复迁移前（PyQt5）的观感与尺寸。
    # 想用系统缩放的话，把这两行删掉。
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '0')
    os.environ.setdefault('QT_SCALE_FACTOR', '1')

    app = QApplication(sys.argv)
    _install_qt_chinese(app)
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
    set_font_scale(1.0 - max(0.0, dpi_scale - 2.5) * 0.4)

    # 数据目录写入自检：写不进去时后面的备份/保存都会失败，
    # 提前记一笔日志，用户反馈问题时一眼能看到
    try:
        from config import DATA_BASE
        from services.diag import log
        probe = os.path.join(DATA_BASE, 'data', '.write-probe')
        os.makedirs(os.path.dirname(probe), exist_ok=True)
        with open(probe, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(probe)
        log('probe', '数据目录可写')
    except Exception as e:                      # noqa: BLE001
        try:
            from services.diag import log
            log('probe', f'数据目录不可写: {e!r}')
        except Exception:                       # noqa: BLE001
            pass

    from config import load_user_settings
    from ui.tokens import set_primary
    set_primary(load_user_settings().get('theme_color', '#9B0D14'))
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

    # 再补一次：某些高 DPI 组合下首次 showMaximized 会被布局的最小尺寸顶掉，
    # 等事件循环跑起来后再强制最大化一次，并把实际状态写进日志。
    def _force_maximize():
        # 与「从悬浮层恢复」走同一条路径：Qt 的 showMaximized 在启动早期
        # 偶尔会被 Windows 的初始放置覆盖（状态是最大化但尺寸没铺满），
        # 这里补一次 Win32 ShowWindow(SW_MAXIMIZE) 才真正生效。
        mainwindow.showMaximized()
        try:
            from ui.component.winutil import force_foreground
            force_foreground(mainwindow, maximize=True)
        except Exception as e:                  # noqa: BLE001
            log('startup', f'force_foreground 失败: {e!r}')
        screen = mainwindow.screen()
        avail = screen.availableGeometry()
        geo = screen.geometry()
        log('startup',
            f'maximized={mainwindow.isMaximized()} '
            f'win={mainwindow.width()}x{mainwindow.height()} '
            f'frame={mainwindow.frameGeometry().width()}x{mainwindow.frameGeometry().height()} '
            f'avail={avail.width()}x{avail.height()} screen={geo.width()}x{geo.height()} '
            f'dpr={screen.devicePixelRatio()} dpi={screen.logicalDotsPerInch():.0f} '
            f'min={mainwindow.minimumSizeHint().width()}x{mainwindow.minimumSizeHint().height()} '
            f'screens={len(QGuiApplication.screens())}')

        # 兜底：明明最大化了却明显小于可用区域时，直接贴到可用区域
        gap_w = avail.width() - mainwindow.frameGeometry().width()
        gap_h = avail.height() - mainwindow.frameGeometry().height()
        if gap_w > 4 or gap_h > 4:
            log('startup', f'尺寸不匹配(w差{gap_w},h差{gap_h})，强制铺满可用区域')
            mainwindow.setGeometry(avail)

    QTimer.singleShot(0, _force_maximize)
    _check_request()

    app.exec()


def _run_guarded():
    """兜底：把未捕获异常写进 debug.log 再抛出。

    打包后没有控制台，崩溃时用户只看到"双击没反应"，
    有了这条日志才能事后定位。
    """
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        try:
            from services.diag import log
            log('crash', traceback.format_exc())
        except Exception:                       # noqa: BLE001
            pass
        raise


if __name__ == '__main__':
    _run_guarded()
