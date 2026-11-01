"""导入服务：CSV/Excel 统一读取与模板生成。"""

import pytest

from services.imports import read_table, write_template


class TestReadTable:
    def test_reads_csv(self, tmp_dir):
        path = tmp_dir / "names.csv"
        path.write_text("name\n张三\n李四\n", encoding="utf-8")
        df = read_table(str(path))
        assert df["name"].tolist() == ["张三", "李四"]

    def test_reads_xlsx(self, tmp_dir):
        from openpyxl import Workbook

        path = tmp_dir / "names.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["name"])
        ws.append(["王五"])
        wb.save(path)

        df = read_table(str(path))
        assert df["name"].tolist() == ["王五"]

    def test_missing_file_raises(self, tmp_dir):
        with pytest.raises(FileNotFoundError):
            read_table(str(tmp_dir / "nope.csv"))


class TestTemplate:
    def test_writes_four_sheets(self, tmp_dir):
        from openpyxl import load_workbook

        path = tmp_dir / "tpl.xlsx"
        write_template(str(path))

        wb = load_workbook(path)
        assert wb.sheetnames == ["名单", "分组", "课表", "说明"]
        assert wb["名单"]["A1"].value == "name"
        assert wb["课表"]["A1"].value == "周一"

    def test_groups_are_columns(self, tmp_dir):
        from openpyxl import load_workbook

        path = tmp_dir / "tpl.xlsx"
        write_template(str(path))
        ws = load_workbook(path)["分组"]
        assert ws["A1"].value == "第一组"
        assert ws["B1"].value == "第二组"
