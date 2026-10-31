import os
import sys
import subprocess
from datetime import datetime, timedelta

import pandas as pd

from config import FILE_DIR

TIME_FORMAT = '%Y-%m-%d'
DEFAULT_JOBS = ['扫', '扫', '擦', '排', '理']
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


def read_names(path: str) -> list:
    """智能读取名单：支持 name 列、姓名列、无表头单列、兜底第一列。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f'名单文件不存在：{path}')

    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise ValueError(f'无法解析 CSV：{e!r}')

    # 1. 精确列名匹配
    for col in df.columns:
        if str(col).strip().lower() in _HEADER_KEYWORDS:
            return _clean_names(df[col].tolist())

    # 2. 单列且列名不像表头 → 视为无表头
    if len(df.columns) == 1:
        first_col = df.columns[0]
        if not _looks_like_header(first_col):
            df2 = pd.read_csv(path, header=None)
            return _clean_names(df2.iloc[:, 0].tolist())

    # 3. 兜底：取第一列
    if len(df.columns) == 0:
        raise ValueError('CSV 中没有可识别的列')
    print(f'Warning: 未识别到 name/姓名 列，使用第一列 "{df.columns[0]}"')
    return _clean_names(df.iloc[:, 0].tolist())


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


# ------------------------ 生成 ------------------------

def build_onduty_df(start, weeks, daily, names, jobs, skip_weekend=True,
                    offset=0, stride=1, skip_names=None,
                    shuffle=False, seed=None):
    """按名单顺序/步长轮值。

    offset:     起始偏移（0 = 首位）
    stride:     每次前进位数（1 = 顺序）
    skip_names: 本次生成要跳过的人（不影响名单文件）
    shuffle:    生成前随机打乱名单
    seed:       随机种子（None/0 = 每次不同）
    """
    if not names:
        raise ValueError('名单为空')
    if not jobs:
        raise ValueError('职务列表为空')
    if daily <= 0:
        raise ValueError('每日人数必须大于 0')
    if weeks <= 0:
        raise ValueError('周数必须大于 0')

    # 1) 过滤跳过的人
    if skip_names:
        skip_set = set(skip_names)
        names = [n for n in names if n not in skip_set]
        if not names:
            raise ValueError('跳过名单后无可安排人员')

    # 2) 随机打乱
    if shuffle:
        import random
        rng = random.Random(seed if seed else None)
        names = list(names)
        rng.shuffle(names)

    # 3) 起始偏移
    if offset:
        offset %= len(names)
        names = names[offset:] + names[:offset]

    stride = max(1, int(stride))

    effective_jobs = [jobs[i % len(jobs)] for i in range(daily)]

    df = pd.DataFrame()
    stu_ord = 0

    def _make_col():
        nonlocal stu_ord
        col = []
        for k in range(daily):
            col.append(f'{names[stu_ord % len(names)]} {effective_jobs[k]}')
            stu_ord = (stu_ord + stride) % len(names)
        return col

    t0 = start
    if skip_weekend:
        while t0.weekday() >= 5:
            t0 += timedelta(days=1)
        total = weeks * 5
        generated = 0
        while generated < total:
            if t0.weekday() < 5:
                df[t0.strftime(TIME_FORMAT)] = _make_col()
                generated += 1
            t0 += timedelta(days=1)
    else:
        total = weeks * 7
        for _ in range(total):
            df[t0.strftime(TIME_FORMAT)] = _make_col()
            t0 += timedelta(days=1)

    return df

# ------------------------ 分组表 ------------------------

def read_groups(path: str) -> dict:
    """读取分组表：CSV 每列为一组，列名为组名，单元格为成员名。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f'分组文件不存在：{path}')
    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise ValueError(f'无法解析 CSV：{e!r}')

    groups = {}
    for col in df.columns:
        members = []
        for v in df[col].tolist():
            if pd.isna(v):
                continue
            s = str(v).strip()
            if s:
                members.append(s)
        if members:
            groups[str(col).strip()] = members

    if not groups:
        raise ValueError('分组表为空')
    return groups


def write_sample_group_csv(path: str) -> None:
    """生成一份样板分组表（4 组 × 6 人）。"""
    sample = {
        '第一组': ['张三', '李四', '王五', '赵六', '钱七', '孙八'],
        '第二组': ['周九', '吴十', '郑一', '王二', '李三', '张四'],
        '第三组': ['赵五', '钱六', '孙七', '李八', '周五', '吴一'],
        '第四组': ['郑二', '王三', '冯四', '陈五', '褚六', '卫七'],
    }
    pd.DataFrame(sample).to_csv(path, index=False, encoding='utf-8')


def build_onduty_df_from_groups(start, weeks, groups, jobs, skip_weekend=True,
                                offset=0, skip_names=None,
                                shuffle=False, seed=None):
    """按分组表生成值日：每天一个组。

    offset:     起始组偏移（0 = 第一组）
    skip_names: 本次生成要跳过的人
    shuffle:    生成前打乱每组内成员顺序
    seed:       随机种子
    """
    if not groups:
        raise ValueError('分组为空')
    if not jobs:
        raise ValueError('职务列表为空')
    if weeks <= 0:
        raise ValueError('周数必须大于 0')

    if skip_names:
        skip_set = set(skip_names)
        groups = {
            k: [m for m in v if m not in skip_set]
            for k, v in groups.items()
        }
        groups = {k: v for k, v in groups.items() if v}
        if not groups:
            raise ValueError('跳过名单后无可安排人员')

    if shuffle:
        import random
        rng = random.Random(seed if seed else None)
        groups = {k: rng.sample(v, len(v)) for k, v in groups.items()}

    group_keys = list(groups.keys())
    max_size = max(len(m) for m in groups.values())

    if offset:
        offset %= len(group_keys)
        group_keys = group_keys[offset:] + group_keys[:offset]

    dates = []
    t0 = start
    if skip_weekend:
        while t0.weekday() >= 5:
            t0 += timedelta(days=1)
        total = weeks * 5
        generated = 0
        while generated < total:
            if t0.weekday() < 5:
                dates.append(t0)
                generated += 1
            t0 += timedelta(days=1)
    else:
        total = weeks * 7
        for _ in range(total):
            dates.append(t0)
            t0 += timedelta(days=1)

    df = pd.DataFrame()
    for i, day in enumerate(dates):
        members = groups[group_keys[i % len(group_keys)]]
        col = [f'{m} {jobs[k % len(jobs)]}' for k, m in enumerate(members)]
        if len(col) < max_size:
            col += [''] * (max_size - len(col))
        df[day.strftime(TIME_FORMAT)] = col

    return df

def compute_stats(df):
    """统计每人出现次数。返回 (Counter, n_days)。

    兼容 "张 三 扫" / "李四 擦" 这类带职务的单元格，
    以及分组模式下的空单元格。
    """
    from collections import Counter
    counter = Counter()
    for col in df.columns:
        for cell in df[col]:
            # 空单元格可能是 ''（生成时补的），也可能是 NaN（从 CSV 读回时），
            # 后者用 `not cell` 判断不出来，会被当成名字 "nan" 统计进去
            if cell is None or pd.isna(cell):
                continue
            s = str(cell).strip()
            if not s:
                continue
            name = s.rsplit(None, 1)[0] if ' ' in s else s
            counter[name] += 1
    return counter, len(df.columns)


if __name__ == '__main__':
    names = read_names(FILE_DIR + '名单.csv')
    df = build_onduty_df(
        start=datetime(2026, 10, 26),
        weeks=22, daily=5,
        names=names, jobs=DEFAULT_JOBS,
        skip_weekend=True,
    )
    df.to_csv(FILE_DIR + '未来值日.csv', index=False)
    print(f'generated {df.shape[1]} days, {len(names)} students')