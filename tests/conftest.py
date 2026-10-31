"""pytest 全局配置。

两条关键约束：

1. 把所有可写数据重定向到工作区内的 .pytest-appdata/：
   - 不碰用户真实的 %APPDATA%\\ClassManager（测试不该污染班级数据）
   - 也避开沙箱对工作区外写入的限制
   必须在 import 任何项目模块之前完成，因为 config.py 在被 import 时
   就会创建目录、复制种子数据，并实例化一个 PandasQItemModel。

2. 在 import 项目模块之前创建 QApplication：
   config.py 在模块级执行 `ERROR_MODEL = PandasQItemModel(['加载出错'])`，
   没有 QApplication 时构造 QAbstractItemModel 是不安全的行为。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- 1. 隔离可写数据目录 ---
_TEST_DATA = ROOT / ".pytest-appdata"
_TEST_DATA.mkdir(exist_ok=True)
os.environ["APPDATA"] = str(_TEST_DATA)

# --- 2. 无显示器环境 ---
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# --- 3. QApplication（必须早于项目模块导入）---
from PyQt5.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication([])
