"""ondutySpawn.py 的值日表生成测试。

覆盖 HANDOFF.md §8.3 中列出的关键用例：空名单/空职务/负数参数、
offset/stride 边界、shuffle + seed 可复现、skip_names 过滤、
分组模式空组过滤、compute_stats 对空单元格与含空格姓名的处理。
"""

from datetime import datetime

import pytest
from pandas import DataFrame

from ondutySpawn import (
    build_onduty_df,
    build_onduty_df_from_groups,
    compute_stats,
)

MONDAY = datetime(2026, 10, 26)          # 周一
NAMES = ["甲", "乙", "丙", "丁", "戊"]
JOBS = ["扫", "擦"]


def all_cells(df):
    return [c for col in df.columns for c in df[col] if c]


class TestValidation:
    def test_empty_names_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df(MONDAY, weeks=1, daily=2, names=[], jobs=JOBS)

    def test_empty_jobs_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df(MONDAY, weeks=1, daily=2, names=NAMES, jobs=[])

    def test_non_positive_daily_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df(MONDAY, weeks=1, daily=0, names=NAMES, jobs=JOBS)

    def test_non_positive_weeks_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df(MONDAY, weeks=0, daily=2, names=NAMES, jobs=JOBS)

    def test_skipping_everyone_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df(
                MONDAY, weeks=1, daily=2, names=NAMES, jobs=JOBS,
                skip_names=NAMES,
            )


class TestShapeAndFormat:
    def test_weekdays_only(self):
        df = build_onduty_df(MONDAY, weeks=2, daily=2, names=NAMES, jobs=JOBS)
        assert df.shape[1] == 10
        assert all(datetime.strptime(c, "%Y-%m-%d").weekday() < 5 for c in df.columns)

    def test_including_weekend(self):
        df = build_onduty_df(
            MONDAY, weeks=1, daily=2, names=NAMES, jobs=JOBS, skip_weekend=False,
        )
        assert df.shape[1] == 7

    def test_first_column_is_start_date(self):
        df = build_onduty_df(MONDAY, weeks=1, daily=2, names=NAMES, jobs=JOBS)
        assert df.columns[0] == "2026-10-26"

    def test_cell_format_is_name_space_job(self):
        df = build_onduty_df(MONDAY, weeks=1, daily=2, names=NAMES, jobs=JOBS)
        name, job = df.iloc[0, 0].rsplit(None, 1)
        assert name in NAMES
        assert job in JOBS

    def test_daily_decides_row_count(self):
        df = build_onduty_df(MONDAY, weeks=1, daily=3, names=NAMES, jobs=JOBS)
        assert df.shape[0] == 3

    def test_jobs_cycle_when_daily_exceeds_jobs(self):
        df = build_onduty_df(MONDAY, weeks=1, daily=3, names=NAMES, jobs=JOBS)
        jobs = [df.iloc[i, 0].rsplit(None, 1)[1] for i in range(3)]
        assert jobs == ["扫", "擦", "扫"]


class TestRotation:
    def test_offset_starts_from_given_index(self):
        df = build_onduty_df(
            MONDAY, weeks=1, daily=1, names=NAMES, jobs=JOBS, offset=2,
        )
        assert df.iloc[0, 0].startswith("丙 ")

    def test_stride_skips_people(self):
        df = build_onduty_df(
            MONDAY, weeks=1, daily=1, names=NAMES, jobs=JOBS, stride=2,
        )
        picked = [df.iloc[0, i].rsplit(None, 1)[0] for i in range(df.shape[1])]
        assert picked[:3] == ["甲", "丙", "戊"]

    def test_skip_names_are_excluded(self):
        df = build_onduty_df(
            MONDAY, weeks=2, daily=2, names=NAMES, jobs=JOBS, skip_names=["乙"],
        )
        assert all(not c.startswith("乙 ") for c in all_cells(df))

    def test_everyone_appears_over_enough_days(self):
        df = build_onduty_df(MONDAY, weeks=2, daily=2, names=NAMES, jobs=JOBS)
        seen = {c.rsplit(None, 1)[0] for c in all_cells(df)}
        assert seen == set(NAMES)

    def test_shuffle_with_same_seed_is_reproducible(self):
        a = build_onduty_df(
            MONDAY, weeks=2, daily=2, names=NAMES, jobs=JOBS,
            shuffle=True, seed=42,
        )
        b = build_onduty_df(
            MONDAY, weeks=2, daily=2, names=NAMES, jobs=JOBS,
            shuffle=True, seed=42,
        )
        assert a.equals(b)


class TestGroups:
    GROUPS = {"一组": ["甲", "乙"], "二组": ["丙", "丁"]}

    def test_empty_groups_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df_from_groups(MONDAY, weeks=1, groups={}, jobs=JOBS)

    def test_empty_jobs_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df_from_groups(MONDAY, weeks=1, groups=self.GROUPS, jobs=[])

    def test_non_positive_weeks_raises(self):
        with pytest.raises(ValueError):
            build_onduty_df_from_groups(MONDAY, weeks=0, groups=self.GROUPS, jobs=JOBS)

    def test_groups_rotate_by_day(self):
        df = build_onduty_df_from_groups(
            MONDAY, weeks=1, groups=self.GROUPS, jobs=JOBS,
        )
        first_of_day = [df.iloc[0, i].rsplit(None, 1)[0] for i in range(df.shape[1])]
        assert first_of_day == ["甲", "丙", "甲", "丙", "甲"]

    def test_offset_rotates_starting_group(self):
        df = build_onduty_df_from_groups(
            MONDAY, weeks=1, groups=self.GROUPS, jobs=JOBS, offset=1,
        )
        assert df.iloc[0, 0].startswith("丙 ")

    def test_uneven_groups_are_padded_with_empty_cells(self):
        groups = {"大组": ["甲", "乙", "丙"], "小组": ["丁"]}
        df = build_onduty_df_from_groups(MONDAY, weeks=1, groups=groups, jobs=JOBS)
        assert df.shape[0] == 3
        assert df.iloc[1, 1] == ""      # 第二天的组只有一个人

    def test_group_emptied_by_skip_is_dropped(self):
        df = build_onduty_df_from_groups(
            MONDAY, weeks=1, groups=self.GROUPS, jobs=JOBS, skip_names=["丙", "丁"],
        )
        assert all(c.startswith("甲 ") or c.startswith("乙 ") for c in all_cells(df))


class TestComputeStats:
    def test_counts_and_day_number(self):
        df = DataFrame({
            "2026-10-26": ["甲 扫", "乙 擦"],
            "2026-10-27": ["甲 擦", "丙 扫"],
        })
        counter, n_days = compute_stats(df)
        assert n_days == 2
        assert counter["甲"] == 2
        assert counter["乙"] == 1

    def test_empty_cells_are_skipped(self):
        df = DataFrame({"d": ["甲 扫", "", None]})
        counter, _ = compute_stats(df)
        assert dict(counter) == {"甲": 1}

    def test_name_with_inner_spaces_is_kept(self):
        df = DataFrame({"d": ["曾   域 扫"]})
        counter, _ = compute_stats(df)
        assert dict(counter) == {"曾   域": 1}

    def test_cell_without_job_counts_whole_string(self):
        df = DataFrame({"d": ["甲"]})
        counter, _ = compute_stats(df)
        assert dict(counter) == {"甲": 1}
