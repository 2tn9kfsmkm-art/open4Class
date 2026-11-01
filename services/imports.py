"""导入/导出：CSV 与 Excel 统一入口。

约定（详见 docs/IMPORT_FORMATS.md）：
    - 名单：一列，表头 ``name``
    - 课表：5 列，表头 周一~周五，每行一节
    - 分组：每列一组，第一行是组名
"""

import os

from pandas import DataFrame, read_csv


def read_table(path: str) -> DataFrame:
    """按扩展名读 csv / xlsx，返回 DataFrame。"""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if path.lower().endswith(('.xlsx', '.xlsm')):
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not rows:
            return DataFrame()
        header = ['' if c is None else str(c).strip() for c in rows[0]]
        return DataFrame(rows[1:], columns=header)
    return read_csv(path, encoding='utf-8')


def write_template(path: str) -> str:
    """生成导入模板 xlsx：名单 / 分组 / 课表 三个 sheet + 说明。"""
    from openpyxl import Workbook

    wb = Workbook()

    ws = wb.active
    ws.title = '名单'
    ws.append(['name'])
    for name in ('张三', '李四', '王五'):
        ws.append([name])

    ws2 = wb.create_sheet('分组')
    ws2.append(['第一组', '第二组', '第三组', '第四组'])
    for row in (('张三', '王五', '陈七', '周九'),
                ('李四', '赵六', '吴十', '郑十一')):
        ws2.append(list(row))

    ws3 = wb.create_sheet('课表')
    ws3.append(['周一', '周二', '周三', '周四', '周五'])
    for row in (('语文', '数学', '英语', '物理', '化学'),
                ('数学', '语文', '物理', '化学', '英语')):
        ws3.append(list(row))

    ws4 = wb.create_sheet('说明')
    for line in (
        '名单：一列，表头必须是 name（或「姓名」），每行一个学生。',
        '分组：每列一组，第一行写组名，下面是该组成员。',
        '课表：五列表头为 周一~周五，每行一节，空格表示没课。',
        '考勤/值日不需要模板，程序自动生成。',
    ):
        ws4.append([line])

    wb.save(path)
    return path
