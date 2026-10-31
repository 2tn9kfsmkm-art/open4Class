import os

def setQss(filepath: str, widget):
    if not os.path.exists(filepath):
        print(f'[setQss] QSS not found: {filepath}')   # 至少能定位问题
        return
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            qss = f.read()
    except Exception as e:
        print(f'[setQss] read failed: {e!r}')
        return
    widget.setStyleSheet(qss)