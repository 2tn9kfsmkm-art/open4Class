"""core/ 层的边界保障。

两条约束（HANDOFF §5.2）：
1. core 不依赖 Qt、不依赖 config —— 否则"纯函数"就名不副实，
   测试和将来的 data 层都会被拖进 GUI 依赖。
2. 旧的 import 路径必须继续可用（tools.shape / tools.num2word / ondutySpawn），
   而且指向同一批函数，不能是复制出来的另一份。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_core_does_not_import_config_or_qt():
    """用子进程验证：当前测试进程里 config 早就被别的用例导入了。"""
    code = (
        "import sys, core.shape, core.weekday, core.onduty;"
        "bad = sorted(m for m in sys.modules"
        " if m.split('.')[0] in ('config', 'PySide6', 'tools', 'ondutySpawn'));"
        "print('|'.join(bad))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"core 意外拉入了: {result.stdout.strip()}"


class TestCompatibilityAliases:
    def test_shape_alias(self):
        import core.shape
        import tools.shape

        assert tools.shape.reshapeRow is core.shape.reshapeRow
        assert tools.shape.unpack_index is core.shape.unpack_index

    def test_weekday_alias(self):
        import core.weekday
        import tools.num2word

        assert tools.num2word.weekday2word is core.weekday.weekday2word

    def test_onduty_alias(self):
        import core.onduty
        import ondutySpawn

        assert ondutySpawn.build_onduty_df is core.onduty.build_onduty_df
        assert ondutySpawn.build_onduty_df_from_groups is core.onduty.build_onduty_df_from_groups
        assert ondutySpawn.compute_stats is core.onduty.compute_stats
        assert ondutySpawn.split_groups is core.onduty.split_groups

    def test_io_helpers_stay_in_onduty_spawn(self):
        """文件读写属于 I/O，暂时不进 core（P6 会搬到 data/）。"""
        import core.onduty
        import ondutySpawn

        assert hasattr(ondutySpawn, "read_names")
        assert hasattr(ondutySpawn, "read_groups")
        assert not hasattr(core.onduty, "read_names")
