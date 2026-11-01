"""tools/PandasQModel.py 的模型层测试。

重点覆盖两个已修复的缺陷：

1. DataFrameWS 的 loc/iloc/at/iat 写回钩子从未被安装 —— 导致真实表格里
   改单元格不会触发 dataChanged，TableEditor 的「*(未保存)」标记不亮。
2. headerData 的 role 默认值被写成了枚举类而不是枚举值 —— 导致
   to_data(header=True) 输出的表头整行是 None。

注意：测试数据统一用字符串列。pandas 3 起向 int64 列写字符串会直接抛
TypeError（2.x 是警告后 upcast），而真实业务里表格列几乎都是文本。
"""

from pandas import DataFrame
from PySide6.QtCore import Qt

from tools.PandasQModel import PandasQItemModel, divideModel


def make_model(data=None, **kwargs):
    return PandasQItemModel(
        DataFrame(data if data is not None else {"a": ["1", "2"], "b": ["3", "4"]}),
        **kwargs,
    )


class TestBasics:
    def test_shape(self):
        model = make_model()
        assert model.rowCount() == 2
        assert model.columnCount() == 2

    def test_data_returns_string(self):
        model = make_model()
        assert model.data(model.index(0, 0)) == "1"

    def test_missing_value_is_empty_string(self):
        model = make_model({"a": [None]})
        assert model.data(model.index(0, 0)) == ""

    def test_header_data_horizontal(self):
        model = make_model()
        assert model.headerData(0, Qt.Orientation.Horizontal) == "a"

    def test_extra_header_shifts_rows(self):
        model = make_model({"a": ["1"]}, extraHeader=True)
        assert model.rowCount() == 2
        assert model.data(model.index(0, 0)) == "a"
        assert model.data(model.index(1, 0)) == "1"


class TestWriteBackSignals:
    """修复 1 的回归测试：indexer 写入路径必须发 dataChanged。"""

    def test_set_data_emits(self):
        model = make_model()
        events = []
        model.dataChanged.connect(lambda *a: events.append(a))
        assert model.setData(model.index(0, 0), "9") is True
        assert events, "setData 没有发出 dataChanged"
        assert model._df.iat[0, 0] == "9"

    def test_iat_assignment_emits(self):
        model = make_model()
        events = []
        model.dataChanged.connect(lambda *a: events.append(a))
        model._df.iat[1, 1] = "7"
        assert events

    def test_loc_assignment_emits(self):
        model = make_model()
        events = []
        model.dataChanged.connect(lambda *a: events.append(a))
        model._df.loc[0, "a"] = "5"
        assert events

    def test_emit_carries_valid_indexes(self):
        model = make_model()
        captured = {}
        model.dataChanged.connect(
            lambda tl, br, *_: captured.update(tl=tl.row(), br=br.row())
        )
        model.setData(model.index(1, 0), "x")
        assert captured == {"tl": 1, "br": 1}

    def test_extra_header_write_targets_model_row_zero(self):
        """extraHeader 模式下，写第 0 行改的是列名而不是数据。"""
        model = make_model({"a": ["1"]}, extraHeader=True)
        model.setData(model.index(0, 0), "新标题")
        assert list(model._df.columns) == ["新标题"]
        assert model._df.iat[0, 0] == "1"


class TestToData:
    def test_without_header(self):
        model = make_model()
        assert model.to_data() == [["1", "3"], ["2", "4"]]

    def test_with_header_prepends_column_names(self):
        """修复 2 的回归测试：表头行不能是 None。"""
        model = make_model()
        assert model.to_data(header=True)[0] == ["a", "b"]

    def test_extra_header_mode_includes_row_zero(self):
        model = make_model({"a": ["1"]}, extraHeader=True)
        rows = model.to_data(header=True)
        assert rows[0] == ["a"]
        assert rows[1] == ["1"]


class TestDivideModel:
    def test_is_a_cache_of_source(self):
        src = make_model()
        dm = divideModel(data=src._df.copy())
        assert dm.rowCount() == src.rowCount()

    def test_auto_update_writes_back_to_resource(self):
        src = make_model()
        dm = divideModel(data=src._df.copy(), resource=src, autoUpdate=True)
        dm.setData(dm.index(0, 0), "42")
        assert src._df.iat[0, 0] == "42"

    def test_without_auto_update_does_not_touch_resource(self):
        src = make_model()
        dm = divideModel(data=src._df.copy(), resource=src)
        dm.setData(dm.index(0, 0), "42")
        assert src._df.iat[0, 0] == "1"
