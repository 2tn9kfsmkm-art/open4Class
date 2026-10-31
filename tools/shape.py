"""兼容层：真正的实现在 core/shape.py。

保留这个文件是为了让 ``from tools.shape import ...`` 这类旧写法继续可用，
等 P9 目录重构时再统一删除。
"""

from core.shape import *  # noqa: F401,F403
