import os


def setQss(filepath: str, widget, extra: str = ''):
    """给控件套用 qss 文件；extra 用于在末尾追加局部覆盖（同文件内后写的胜出）。"""
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
    widget.setStyleSheet(qss)
