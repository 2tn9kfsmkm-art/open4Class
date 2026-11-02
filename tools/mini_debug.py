"""悬浮窗刷新诊断：运行 12 秒，每秒打印一次内部状态。

用法：
    python tools/mini_debug.py

期间请在屏幕上点一下右下角小方块，让大悬浮窗重新出现，
然后把控制台输出整段发我。
"""

import sys
import time
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, '.')

import config                       # noqa: E402
from tools.qss2qt import setQss     # noqa: E402
from ui.window.main_window import Main  # noqa: E402


def main():
    app = QApplication(sys.argv)
    setQss(config.QSS_DIR + 'mainpage.qss', app)

    window = Main()
    window.show()
    app.processEvents()

    window.showMinimized()
    app.processEvents()

    ticks = {'n': 0}
    original = window.mini.refresh

    def counted():
        ticks['n'] += 1
        original()

    window.mini.refresh = counted
    try:
        window.mini._tick.timeout.disconnect()
    except Exception:
        pass
    window.mini._tick.timeout.connect(counted)

    def report():
        mini = window.mini
        print(
            f"[{datetime.now():%H:%M:%S}] "
            f"tick={mini._tick.isActive()} "
            f"panel={mini.panel.isVisible()} "
            f"chip={mini.chip.isVisible()} "
            f"label={mini.panel.time_l.text()} "
            f"刷新次数={ticks['n']}",
            flush=True,
        )

    for _ in range(12):
        QTimer.singleShot(int(_ * 1000), report)
    QTimer.singleShot(12_500, app.quit)
    app.exec()


if __name__ == '__main__':
    main()
