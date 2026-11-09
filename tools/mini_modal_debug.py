"""诊断：设置窗口开着时最小化，点「班级」没反应。

用法：
    python tools/mini_modal_debug.py

步骤：
    1. 程序起来后，点左下角学校图标 → 打开设置（不要关）
    2. 从任务栏右键把主窗口最小化
    3. 点右下角「班级」小窗
    4. 把控制台输出整段发我
"""

import sys

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication, QDialog

sys.path.insert(0, '.')

import config                                     # noqa: E402
from tools.qss2qt import setQss                   # noqa: E402
import ui.window.main_window as mw                # noqa: E402


def main():
    app = QApplication(sys.argv)
    setQss(config.QSS_DIR + 'mainpage.qss', app)

    window = mw.Main()
    window.show()
    app.processEvents()

    # 1) 监听最小化/恢复
    original_change = window.changeEvent

    def change(event):
        if event.type() == QEvent.Type.WindowStateChange:
            print(f'[state] minimized={window.isMinimized()} '
                  f'modal={QApplication.activeModalWidget() is not None}', flush=True)
        original_change(event)

    window.changeEvent = change

    # 2) 监听小窗点击
    original_back = window.mini._back

    def back():
        print('[click] 收到「班级」点击', flush=True)
        original_back()
        print(f'[click] 恢复完成 minimized={window.isMinimized()} '
              f'hidden_modal={getattr(window, "_hidden_modal", None) is not None}', flush=True)

    window.mini._back = back
    window.mini.chip.clicked.disconnect()
    window.mini.chip.clicked.connect(back)

    # 3) 每秒打印一次状态
    def report():
        modal = QApplication.activeModalWidget()
        print(f'[tick] minimized={window.isMinimized()} '
              f'mini_visible={window.mini.is_visible()} '
              f'active_modal={type(modal).__name__ if modal else None} '
              f'hidden={getattr(window, "_hidden_modal", None) is not None}',
              flush=True)

    timer = QTimer()
    timer.timeout.connect(report)
    timer.start(1000)

    print('就绪：打开设置 → 最小化 → 点「班级」', flush=True)
    app.exec()


if __name__ == '__main__':
    main()
