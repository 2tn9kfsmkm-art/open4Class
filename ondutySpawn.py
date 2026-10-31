"""值日相关的**文件读写**与样板生成。

生成逻辑本身在 ``core/onduty.py``；这里保留 CSV 解析、样板导出和"用系统程序
打开文件"这些 I/O 操作（P6 数据层落地后会迁到 data/ 层）。

为兼容旧代码，本模块继续转出 core 里的生成函数：
    from ondutySpawn import build_onduty_df   # 仍可用
"""

import os
import subprocess
import sys

import pandas as pd

from core.onduty import (  # noqa: F401  （转出给旧调用方）
    DEFAULT_JOBS,
    TIME_FORMAT,
    build_onduty_df,
    build_onduty_df_from_groups,
    compute_stats,
    split_groups,
)

SAMPLE_NAMES = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十']

# 常见表头关键词（小写比较）
_HEADER_KEYWORDS = {
    'name', '姓名', '名字', '学生', '学生姓名', 'student', 'students',
    'id', 'no', '序号', '学号', 'class', '班级', '年级', '性别', 'sex', 'gender',
}

# ------------------------ 名单解析 ------------------------

def _clean_names(values) -> list:
    result = []
    for v in values:
        if pd.isna(v):
            continue
        s = str(v).strip()
        if s:
            result.append(s)
    if not result:
        raise ValueError('名单为空')
    return result


def _looks_like_header(s: str) -> bool:
    s = str(s).strip()
    if not s:
        return True
    if s.lower() in _HEADER_KEYWORDS:
        return True
    if len(s) > 30:
        return True
    if any(c.isdigit() for c in s):
        return True
    if any(c in s for c in '_./\\@#()[]{}'):
        return True
    return False


def read_names_from_df(df) -> list:
    """从已读入的表格中识别姓名列（CSV / Excel 共用）。

    Args:
        df: 已读入的表格（pandas DataFrame）。
    Returns:
        清洗后的姓名列表（去首尾空白、跳过空值）。
    Raises:
        ValueError: 表格没有可用的列。
    """
    if df is None or df.shape[1] == 0:
        raise ValueError('表格中没有可识别的列')

    # 1. 精确列名匹配
    for col in df.columns:
        if str(col).strip().lower() in _HEADER_KEYWORDS:
            return _clean_names(df[col].tolist())

    # 2. 兜底：取第一列
    print(f'Warning: 未识别到 name/姓名 列，使用第一列 "{df.columns[0]}"')
    return _clean_names(df.iloc[:, 0].tolist())


def read_names(path: str) -> list:
    """智能读取名单：支持 name 列、姓名列、无表头单列、兜底第一列。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f'名单文件不存在：{path}')

    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise ValueError(f'无法解析 CSV：{e!r}')

    # 单列且列名不像表头 → 视为无表头，按无表头重读一次
    if len(df.columns) == 1:
        first_col = df.columns[0]
        if not _looks_like_header(first_col):
            df2 = pd.read_csv(path, header=None)
            return _clean_names(df2.iloc[:, 0].tolist())

    return read_names_from_df(df)


def write_sample_name_csv(path: str) -> None:
    """生成一份样板名单（带 name 表头）。"""
    pd.DataFrame({'name': SAMPLE_NAMES}).to_csv(
        path, index=False, encoding='utf-8')


def open_file_external(path: str) -> None:
    """跨平台用系统默认程序打开文件。"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if os.name == 'nt':
        os.startfile(path)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])


# ------------------------ 分组表 ------------------------

def read_groups_from_df(df) -> dict:
    """从已读入的表格识别分组：**每列一组，列名为组名，单元格为成员**。

    Args:
        df: 已读入的表格（CSV / Excel 共用）。
    Returns:
        {组名: [成员...]}；空列与空单元格会被跳过；
        列名为空或是 pandas 的 "Unnamed: N" 时自动命名「第N组」。
    Raises:
        ValueError: 表格没有列，或所有列都是空的。
    """
    if df is None or df.shape[1] == 0:
        raise ValueError('分组表没有可用的列')

    groups = {}
    for index, col in enumerate(df.columns):
        name = str(col).strip()
        if not name or name.lower().startswith('unnamed'):
            name = f'第{index + 1}组'
        members = []
        for v in df[col].tolist():
            if v is None or pd.isna(v):
                continue
            s = str(v).strip()
            if s:
                members.append(s)
        if members:
            groups[name] = members

    if not groups:
        raise ValueError('分组表为空')
    return groups


def read_groups(path: str) -> dict:
    """读取分组表：CSV 每列为一组，列名为组名，单元格为成员名。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f'分组文件不存在：{path}')
    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise ValueError(f'无法解析 CSV：{e!r}')
    return read_groups_from_df(df)


def write_sample_group_csv(path: str) -> None:
    """生成一份样板分组表（4 组 × 6 人）。"""
    sample = {
        '第一组': ['张三', '李四', '王五', '赵六', '钱七', '孙八'],
        '第二组': ['周九', '吴十', '郑一', '王二', '李三', '张四'],
        '第三组': ['赵五', '钱六', '孙七', '李八', '周五', '吴一'],
        '第四组': ['郑二', '王三', '冯四', '陈五', '褚六', '卫七'],
    }
    pd.DataFrame(sample).to_csv(path, index=False, encoding='utf-8')


if __name__ == '__main__':
    from datetime import datetime

    from data.store import shared_store

    store = shared_store()
    names = store.load_names()['name'].tolist()
    df = build_onduty_df(
        start=datetime(2026, 10, 26),
        weeks=22, daily=5,
        names=names, jobs=DEFAULT_JOBS,
        skip_weekend=True,
    )
    store.save_onduty(df)
    print(f'generated {df.shape[1]} days, {len(names)} students')
