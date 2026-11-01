"""课表导入：列名规整 + Excel 读取。

`_normalize_weekday_columns` 是导入功能的唯一入口，负责把任意表格
（周一/星期一/Mon/随便五列）规整成「周一~周五」五列。
其中一个用例需要真实读 xlsx，也顺带充当 openpyxl 依赖的守卫。
"""

import pandas as pd
import pytest

from ui.window.settings_window import CourseEditorWidget

WEEKDAYS = CourseEditorWidget.WEEKDAYS


@pytest.fixture(scope="module")
def editor():
    return CourseEditorWidget()


class TestNormalize:
    def test_standard_headers(self, editor):
        src = pd.DataFrame({d: ["A", "B"] for d in WEEKDAYS})
        out = editor._normalize_weekday_columns(src)
        assert list(out.columns) == WEEKDAYS
        assert len(out) == 2

    def test_chinese_aliases(self, editor):
        src = pd.DataFrame({f"星期{c}": ["A", "B"] for c in "一二三四五"})
        out = editor._normalize_weekday_columns(src)
        assert list(out.columns) == WEEKDAYS

    def test_english_aliases(self, editor):
        src = pd.DataFrame({c: ["A", "B"] for c in ["Mon", "Tue", "Wed", "Thu", "Fri"]})
        out = editor._normalize_weekday_columns(src)
        assert list(out.columns) == WEEKDAYS

    def test_extra_unknown_columns_fall_back_to_first_five(self, editor):
        src = pd.DataFrame({f"列{i}": ["A", "B"] for i in range(1, 7)})
        out = editor._normalize_weekday_columns(src)
        assert list(out.columns) == WEEKDAYS
        assert list(out.iloc[0]) == ["A"] * 5

    def test_too_few_columns_is_rejected(self, editor):
        src = pd.DataFrame({f"列{i}": ["A"] for i in range(1, 4)})
        assert editor._normalize_weekday_columns(src) is None

    def test_values_are_preserved(self, editor):
        src = pd.DataFrame({d: [d, "X"] for d in WEEKDAYS})
        out = editor._normalize_weekday_columns(src)
        assert list(out.iloc[0]) == WEEKDAYS


class TestExcelReading:
    def test_xlsx_roundtrip(self, editor, tmp_dir):
        """需要 openpyxl；缺依赖时这条会失败，提醒补依赖。"""
        path = tmp_dir / "课表样例.xlsx"
        df = pd.DataFrame({f"星期{c}": ["语文", "数学"] for c in "一二三四五"})
        df.to_excel(path, index=False)

        src = pd.read_excel(path)
        out = editor._normalize_weekday_columns(src)

        assert list(out.columns) == WEEKDAYS
        assert list(out.iloc[0]) == ["语文"] * 5
