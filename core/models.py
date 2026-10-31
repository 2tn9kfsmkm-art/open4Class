"""领域数据结构（无 Qt 依赖）。"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OndutyEntry:
    """一条值日记录：某天某个位置上的某位学生。"""

    date: date
    slot: int
    student: str
    job: str


@dataclass(frozen=True)
class AppEntry:
    """一个应用链接。"""

    name: str
    path: str
