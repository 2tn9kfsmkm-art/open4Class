"""首次运行自举：分发包里没有 datas/ 时也必须能启动。

对应故障链：
    config._init_datas() 发现没有 datas/ → 静默返回
    loading.classlist_chain.load() → q_read_csv('课表.csv')
    tools.PandasQModel.q_read_csv → FileNotFoundError
    → 一路抛到 Main.__init__，双击闪退
"""

import pytest
from pandas import read_csv

from config import CLASS_WEEKDAYS, DEFAULT_CLASS_ROWS, ensure_minimal_data
from tools.PandasQModel import q_read_csv


class TestCreatesSkeletons:
    def test_creates_both_files_in_empty_dir(self, tmp_dir):
        created = ensure_minimal_data(str(tmp_dir))
        assert set(created) == {"课表.csv", "课程单.csv"}
        assert (tmp_dir / "课表.csv").is_file()
        assert (tmp_dir / "课程单.csv").is_file()

    def test_classlist_shape(self, tmp_dir):
        ensure_minimal_data(str(tmp_dir))
        df = read_csv(tmp_dir / "课表.csv")
        assert list(df.columns) == CLASS_WEEKDAYS
        assert len(df) == DEFAULT_CLASS_ROWS

    def test_classlist_is_readable_by_model(self, tmp_dir):
        """真实调用方用的是 q_read_csv，必须能读出模型。"""
        ensure_minimal_data(str(tmp_dir))
        model = q_read_csv(str(tmp_dir / "课表.csv"))
        assert model.rowCount() == DEFAULT_CLASS_ROWS
        assert model.columnCount() == len(CLASS_WEEKDAYS)

    def test_course_list_has_header_only(self, tmp_dir):
        ensure_minimal_data(str(tmp_dir))
        df = read_csv(tmp_dir / "课程单.csv")
        assert list(df.columns) == ["课程"]
        assert len(df) == 0


class TestSafety:
    def test_idempotent(self, tmp_dir):
        ensure_minimal_data(str(tmp_dir))
        first = (tmp_dir / "课表.csv").read_text(encoding="utf-8")
        created = ensure_minimal_data(str(tmp_dir))
        assert created == []
        assert (tmp_dir / "课表.csv").read_text(encoding="utf-8") == first

    def test_existing_files_are_not_overwritten(self, tmp_dir):
        target = tmp_dir / "课表.csv"
        target.write_text("周一,周二\nA,B\n", encoding="utf-8")
        ensure_minimal_data(str(tmp_dir))
        assert target.read_text(encoding="utf-8") == "周一,周二\nA,B\n"

    def test_creates_target_dir_if_missing(self, tmp_dir):
        nested = tmp_dir / "a" / "b"
        ensure_minimal_data(str(nested))
        assert (nested / "课表.csv").is_file()
