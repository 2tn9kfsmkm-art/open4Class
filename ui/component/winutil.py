"""窗口置前的 Windows 小工具。

Qt 的 raise_()/activateWindow() 在部分环境下不会真的把窗口顶到前面
（Windows 有前台窗口限制），这里补一层系统调用。
"""


def force_foreground(win) -> None:
    """把窗口恢复并尽量提为前台。"""
    if win is None:
        return

    from PySide6.QtCore import Qt

    if win.isMinimized():
        win.showNormal()
    if not win.isMaximized():
        win.showMaximized()

    win.raise_()
    win.activateWindow()
    win.requestActivate()

    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = int(win.winId())
        user32.ShowWindow(hwnd, 9)              # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        if user32.GetForegroundWindow() == hwnd:
            return

        # 前台锁：把自己的线程输入挂到当前前台窗口的线程上再抢一次
        kernel32 = ctypes.windll.kernel32
        fg = user32.GetForegroundWindow()
        if fg:
            fg_thread = user32.GetWindowThreadProcessId(fg, None)
            my_thread = kernel32.GetCurrentThreadId()
            attached = user32.AttachThreadInput(my_thread, fg_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            if attached:
                user32.AttachThreadInput(my_thread, fg_thread, False)
            if user32.GetForegroundWindow() == hwnd:
                return
    except Exception:                           # noqa: BLE001
        pass

    # 兜底：短暂置顶再取消，强制系统重新排一次 Z 序
    try:
        win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        win.show()
        win.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        win.show()
        win.raise_()
        win.activateWindow()
    except Exception:                           # noqa: BLE001
        pass


# 这些窗口类属于系统外壳（开始菜单、桌面、任务栏），它们抢到前台时
# 不应该被当成"用户切换到了别的软件"
_SHELL_CLASSES = {
    'Windows.UI.Core.CoreWindow',
    'XamlExplorerHostIslandWindow',
    'Shell_TrayWnd',
    'Shell_SecondaryTrayWnd',
    'Progman',
    'WorkerW',
    'Button',
}


def foreground_class() -> str:
    """当前前台窗口的类名；拿不到返回空串。"""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ''
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        return buf.value
    except Exception:                           # noqa: BLE001
        return ''


def is_shell_foreground() -> bool:
    """前台是不是开始菜单/桌面这类系统外壳。"""
    return foreground_class() in _SHELL_CLASSES


def foreground_is_fullscreen() -> bool:
    """当前前台窗口是不是全屏（PPT 放映、视频、全屏浏览器等）。"""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        if foreground_class() in _SHELL_CLASSES:
            return False

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        if screen_w <= 0 or screen_h <= 0:
            return False

        # 前后留 4px 容差，避免无边框全屏差一两个像素被判成窗口
        covers = (rect.left <= 4 and rect.top <= 4
                  and rect.right >= screen_w - 4
                  and rect.bottom >= screen_h - 4)
        return covers
    except Exception:                           # noqa: BLE001
        return False
