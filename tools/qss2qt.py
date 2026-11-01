import os

from ui.tokens import render


def setQss(filepath: str, widget, extra: str = ''):
    """读取 qss 文件 → 替换 @token → 套到控件上；extra 用于局部覆盖。"""
    if not os.path.exists(filepath):
        print(f'[setQss] QSS not found: {filepath}')   # 至少能定位问题
        return
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            qss = f.read()
    except Exception as e:
        print(f'[setQss] read failed: {e!r}')
        return
    if extra:
        qss = qss + '\n' + extra
    widget.setStyleSheet(render(qss))
