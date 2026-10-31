"""tools/num2word.py 的星期转换测试。"""

import pytest

from tools.num2word import weekday2word


class TestWeekday2Word:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, "周一"),
            (1, "周二"),
            (2, "周三"),
            (3, "周四"),
            (4, "周五"),
            (5, "周六"),
            (6, "周日"),
        ],
    )
    def test_zero_based_mapping(self, value, expected):
        assert weekday2word(value) == expected

    def test_string_input_is_accepted(self):
        assert weekday2word("3") == "周四"

    def test_start_shifts_the_mapping(self):
        # start=1 时，1 被当作一周的第一天
        assert weekday2word(1, start=1) == "周一"

    def test_non_numeric_string_raises_type_error(self):
        with pytest.raises(TypeError):
            weekday2word("周一")

    def test_float_raises_type_error(self):
        with pytest.raises(TypeError):
            weekday2word(1.5)

    def test_out_of_range_raises_index_error(self):
        with pytest.raises(IndexError):
            weekday2word(7)
