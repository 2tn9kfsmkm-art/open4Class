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
