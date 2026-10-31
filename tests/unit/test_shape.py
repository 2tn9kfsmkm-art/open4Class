"""tools/shape.py 的纯函数测试（无 Qt 依赖）。"""

import pytest

from tools.shape import (
    compare,
    find,
    findone,
    reshapeCol,
    reshapeRow,
    unpack_index,
)


class TestReshapeRow:
    def test_single_row_keeps_order(self):
        assert reshapeRow([1, 2, 3], 1) == [[1, 2, 3]]

    def test_two_rows_fill_column_major(self):
        assert reshapeRow([1, 2, 3, 4, 5], 2) == [[1, 3, 5], [2, 4, None]]

    def test_padding_uses_default(self):
        assert reshapeRow([1, 2, 3], 2, defaultNone="") == [[1, 3], [2, ""]]

    def test_empty_input(self):
        assert reshapeRow([], 1) == [[]]

    def test_row_must_be_positive(self):
        with pytest.raises(ValueError):
            reshapeRow([1], 0)

    def test_every_row_same_length(self):
        rows = reshapeRow(list(range(7)), 3)
        assert len({len(r) for r in rows}) == 1


class TestReshapeCol:
    def test_exact_multiple(self):
        assert reshapeCol([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]

    def test_tail_is_padded(self):
        assert reshapeCol([1, 2, 3], 2, defaultNone="") == [[1, 2], [3, ""]]


class TestUnpackIndex:
    def test_scalar_pair(self):
        assert unpack_index((1, 2), (5, 5)) == ((1, 2), (1, 2))

    def test_slice_range(self):
        assert unpack_index((slice(1, 3), slice(None)), (5, 5)) == ((1, 0), (2, 4))

    def test_none_means_full_range(self):
        assert unpack_index(None, (5, 5)) == ((0, 0), (4, 4))

    def test_list_is_reduced_to_bounds(self):
        assert unpack_index(([3, 1], [2, 0]), (5, 5)) == ((1, 0), (3, 2))

    def test_negative_index_counts_from_end(self):
        assert unpack_index((-1, -2), (5, 5)) == ((4, 3), (4, 3))

    def test_out_of_range_raises(self):
        with pytest.raises(IndexError):
            unpack_index((5, 0), (5, 5))

    def test_non_tuple_key_is_row_only(self):
        assert unpack_index(2, (5, 5)) == ((2, 0), (2, 4))

    def test_three_dimensional_key_is_rejected(self):
        with pytest.raises(RuntimeError):
            unpack_index((1, 2, 3), (5, 5))


class TestHelpers:
    def test_find_all_occurrences(self):
        assert find(2, [1, 2, 2, 3]) == [1, 2]

    def test_find_none_returns_index_or_empty(self):
        assert find(9, [1, 2]) == []

    def test_findone(self):
        assert findone(2, [1, 2, 2]) == 1
        assert findone(9, [1, 2]) is None

    def test_compare(self):
        assert compare([1, 2], [1, 3]) == 1
        assert compare([1, 2], [1, 2]) == -2
        assert compare([1], [1, 2]) == -1
