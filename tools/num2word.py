"""兼容层：真正的实现在 core/weekday.py。

保留这个文件是为了让 ``from tools.num2word import weekday2word`` 继续可用，
等 P9 目录重构时再统一删除。
"""

from core.weekday import *  # noqa: F401,F403
