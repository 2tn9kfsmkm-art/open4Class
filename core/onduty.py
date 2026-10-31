"""值日安排的纯领域逻辑（不依赖 Qt、不依赖 config、不做任何文件读写）。

原来的实现分散在 ``ondutySpawn.py``（生成）与 ``UserSettings.py``（参数收集），
这里只保留"给参数 → 出结果"的部分，文件读取与落盘留在 ``ondutySpawn.py``
（后续 P6 会迁到 ``data/`` 层）。
"""

from datetime import timedelta

import pandas as pd

TIME_FORMAT = '%Y-%m-%d'
DEFAULT_JOBS = ['扫', '扫', '擦', '排', '理']


def _weekday_dates(start, weeks, skip_weekend):
    """返回需要排值的日期列表。

    Args:
        start: 起始日期（date / datetime）。
        weeks: 周数。
        skip_weekend: 为真时只取周一至周五。
    """
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
    return dates


def build_onduty_df(start, weeks, daily, names, jobs, skip_weekend=True,
                    offset=0, stride=1, skip_names=None,
                    shuffle=False, seed=None):
    """按名单顺序 / 步长生成值日表。

    Args:
        start: 起始日期（date 或 datetime）。
        weeks: 生成周数，必须大于 0。
        daily: 每日人数，必须大于 0。
        names: 学生名单（顺序即轮值顺序）。
        jobs: 职务列表，按 ``daily`` 循环取用。
        skip_weekend: 为真时只排周一至周五。
        offset: 起始偏移（0 = 首位）。
        stride: 每次前进的人数（1 = 顺序）。
        skip_names: 本次生成要跳过的人（不影响名单文件）。
        shuffle: 生成前随机打乱名单。
        seed: 随机种子（None / 0 表示每次不同）。
    Returns:
        列名为 ``YYYY-MM-DD`` 的 DataFrame，单元格格式为 ``"{姓名} {职务}"``。
    Raises:
        ValueError: 名单为空、职务为空、daily ≤ 0、weeks ≤ 0，或跳过名单后无人可排。
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

    for day in _weekday_dates(start, weeks, skip_weekend):
        df[day.strftime(TIME_FORMAT)] = _make_col()

    return df


def build_onduty_df_from_groups(start, weeks, groups, jobs, skip_weekend=True,
                                offset=0, skip_names=None,
                                shuffle=False, seed=None):
    """按分组表生成值日：每天一个组，组内成员按职务模板依次排。

    Args:
        start: 起始日期。
        weeks: 生成周数，必须大于 0。
        groups: ``{组名: [成员...]}``。
        jobs: 职务列表。
        skip_weekend: 为真时只排周一至周五。
        offset: 起始组偏移（0 = 第一组）。
        skip_names: 本次生成要跳过的人。
        shuffle: 生成前打乱每组内成员顺序。
        seed: 随机种子。
    Returns:
        列名为日期的 DataFrame；人数不足的组用空字符串补齐到最大组人数。
    Raises:
        ValueError: 分组为空、职务为空、weeks ≤ 0，或跳过名单后无人可排。
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

    df = pd.DataFrame()
    for i, day in enumerate(_weekday_dates(start, weeks, skip_weekend)):
        members = groups[group_keys[i % len(group_keys)]]
        col = [f'{m} {jobs[k % len(jobs)]}' for k, m in enumerate(members)]
        if len(col) < max_size:
            col += [''] * (max_size - len(col))
        df[day.strftime(TIME_FORMAT)] = col

    return df


def compute_stats(df):
    """统计每人值日次数。

    Args:
        df: 值日表 DataFrame（列是日期，单元格是"{姓名} {职务}"或空）。
    Returns:
        ``(Counter, 天数)``。单元格为空字符串或 NaN 时跳过；
        姓名内部允许有空格，按最后一个空格切掉职务。
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


def split_groups(names, count: int) -> dict:
    """把名单按顺序平均分成 count 组（轮流发放，余数落在前面的组）。

    Args:
        names: 姓名序列（顺序会被保留）。
        count: 组数，小于 1 时按 1 组处理。
    Returns:
        ``{"第1组": [姓名...], ...}``；名单为空时返回空字典。
    """
    clean = [str(n).strip() for n in names if str(n).strip()]
    count = max(1, int(count))
    if not clean:
        return {}
    buckets = {f'第{i + 1}组': clean[i::count] for i in range(count)}
    return {k: v for k, v in buckets.items() if v}
