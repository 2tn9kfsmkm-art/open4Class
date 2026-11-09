"""轻量诊断日志：写到数据目录下的 debug.log，排查真机问题时用。

只记关键事件（窗口状态、悬浮层显隐、点击），不记任何学生数据。
文件超过 200KB 自动清空重来，不会无限增长。
"""

import os
from datetime import datetime

from config import DATA_BASE

LOG_PATH = os.path.join(DATA_BASE, 'debug.log')
_MAX_BYTES = 200 * 1024
_ENABLED = True


def log(tag: str, message: str = '') -> None:
    if not _ENABLED:
        return
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > _MAX_BYTES:
            os.remove(LOG_PATH)
        stamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f'{stamp} [{tag}] {message}\n')
    except Exception:                           # noqa: BLE001
        pass                                    # 日志失败绝不影响主流程
