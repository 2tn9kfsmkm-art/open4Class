"""窗口置前的 Windows 小工具。

Qt 的 raise_()/activateWindow() 在部分环境下不会真的把窗口顶到前面
（Windows 有前台窗口限制），这里补一层系统调用。
"""


def force_foreground(win, maximize: bool = True) -> None:
    """把窗口恢复并尽量提为前台。"""
    if win is None:
        return

    from PySide6.QtCore import Qt

    if win.isMinimized():
        win.showNormal()
    if maximize:
        win.showMaximized()

    win.raise_()
    win.activateWindow()
    win.requestActivate()

    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = int(win.winId())
        # SW_RESTORE(9) 会把最大化的窗口还原成普通大小，这里按需要选常量
        user32.ShowWindow(hwnd, 3 if maximize else 9)   # SW_MAXIMIZE / SW_RESTORE
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


def foreground_covers_screen(min_ratio: float = 0.9) -> bool:
    """前台窗口是否占满屏幕（最大化或全屏都算）。

    Args:
        min_ratio: 宽、高各自达到屏幕的比例阈值。最大化窗口因为底部有任务栏，
                   高度通常只有 ~95%，所以默认取 0.9。
    """
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

        width = max(0, rect.right - rect.left)
        height = max(0, rect.bottom - rect.top)
        return (width >= screen_w * min_ratio
                and height >= screen_h * min_ratio)
    except Exception:                           # noqa: BLE001
        return False


def foreground_is_fullscreen() -> bool:
    """真正铺满整屏（PPT 放映 / F11），不含带任务栏的最大化窗口。"""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd or foreground_class() in _SHELL_CLASSES:
            return False
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        screen_w, screen_h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        return (rect.left <= 4 and rect.top <= 4
                and rect.right >= screen_w - 4
                and rect.bottom >= screen_h - 4)
    except Exception:                           # noqa: BLE001
        return False
