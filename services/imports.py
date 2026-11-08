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


def parse_lesson_times(df):
    """把导入表解析成 {星期: [(开始, 结束), ...]}。

    支持两种格式：
        1) 五列（周一/周二/…/周五），每个单元格写 "07:40-08:20"
        2) 两列（开始 / 结束），所有工作日共用
    解析不出的行跳过；完全解析不出时返回空 dict。
    """
    from config import CLASS_WEEKDAYS

    def _norm(cell) -> str:
        text = '' if cell is None else str(cell).strip()
        return text.replace('：', ':').replace('~', '-').replace('—', '-')

    def _split(text):
        text = _norm(text)
        if not text:
            return None
        parts = [p.strip() for p in text.split('-') if p.strip()]
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    columns = [str(c).strip() for c in df.columns]
    result = {}

    # 格式 1：按星期分列
    week_cols = [c for c in CLASS_WEEKDAYS if c in columns]
    if len(week_cols) >= 2:
        for weekday, name in enumerate(CLASS_WEEKDAYS, start=1):
            if name not in columns:
                continue
            slots = []
            for value in df[name].tolist():
                parsed = _split(value)
                if parsed:
                    slots.append(parsed)
            if slots:
                result[weekday] = slots
        return result

    # 格式 2：开始/结束 两列，五天共用
    start_col = next((c for c in columns if c in ('开始', '开始时间', '起')), None)
    end_col = next((c for c in columns if c in ('结束', '结束时间', '止')), None)
    if start_col and end_col:
        slots = []
        for start, end in zip(df[start_col].tolist(), df[end_col].tolist()):
            s, e = _norm(start), _norm(end)
            if s and e:
                slots.append((s, e))
        if slots:
            for weekday in range(1, 6):
                result[weekday] = list(slots)
    return result
