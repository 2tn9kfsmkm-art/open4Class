"""云端导入：payload 解析与规整（不联网、不起界面）。"""

from __future__ import annotations

import pytest

from pandas import DataFrame

from services.cloud_import import (
    CloudImportError,
    format_expiry,
    parse_payload,
    summary_text,
)


def full_payload() -> dict:
    return {
        'v': 1,
        'info': {
            'school_name': '市西中学',
            'class_full_name': '高三（8）班',
            'class_short_name': '高三八班',
        },
        'names': ['张三', '李四', '王五', '赵六'],
        'classlist': {
            'columns': ['周一', '周二', '周三', '周四', '周五'],
            'rows': [
                ['语文', '数学', '英语', '物理', '化学'],
                ['体育', '', '', '', ''],
            ],
        },
        'lesson_times': {
            '1': [['07:40', '08:20'], ['08:30', '09:10']],
            '2': [['07:40', '08:20']],
        },
        'onduty': {
            'mode': 'sequence',
            'start': '2026-11-09',
            'weeks': 20,
            'jobs': ['扫', '扫', '擦', '排', '理'],
            'skip_weekend': True,
            'daily': 3,
        },
    }


def test_parse_full_payload():
    preview = parse_payload(full_payload())

    assert preview.names == ['张三', '李四', '王五', '赵六']
    assert preview.info['school_name'] == '市西中学'
    assert isinstance(preview.classlist, DataFrame)
    assert preview.rows == 2
    assert list(preview.classlist.columns) == ['周一', '周二', '周三', '周四', '周五']
    assert preview.classlist.iloc[0, 0] == '语文'
    assert preview.classlist.iloc[1, 1] == ''

    assert preview.lesson_times[1] == [('07:40', '08:20'), ('08:30', '09:10')]
    assert preview.lesson_times[2] == [('07:40', '08:20')]
    assert preview.lesson_days == 2

    assert preview.onduty['mode'] == 'sequence'
    assert preview.onduty['start'] == '2026-11-09'
    assert preview.onduty['weeks'] == 20
    assert preview.onduty['daily'] == 3
    assert preview.onduty['jobs'][0] == '扫'
    assert preview.onduty['skip_weekend'] is True


def test_classlist_accepts_plain_rows_and_pads_columns():
    payload = full_payload()
    payload['classlist'] = [['语文'], ['数学', '英语', '  ', None, '化学', '多余列']]

    preview = parse_payload(payload)

    assert preview.classlist.shape == (2, 5)
    assert preview.classlist.iloc[0, 1] == ''
    assert preview.classlist.iloc[1, 4] == '化学'
    # 第 6 列被截断
    assert preview.classlist.iloc[1, 3] == ''


def test_classlist_drops_trailing_empty_rows():
    payload = full_payload()
    payload['classlist'] = {'rows': [['语文', '', '', '', ''], ['', '', '', '', '']]}

    preview = parse_payload(payload)

    assert preview.rows == 1


def test_lesson_times_drops_invalid_slots_and_keys():
    payload = full_payload()
    payload['lesson_times'] = {
        '1': [['07:40', '08:20'], ['08:30', '08:10'], ['bad'], ['25:00', '26:00']],
        '9': [['07:40', '08:20']],
        'x': [['07:40', '08:20']],
    }

    preview = parse_payload(payload)

    assert preview.lesson_times == {1: [('07:40', '08:20')]}


def test_onduty_skip_only_needs_mode():
    payload = full_payload()
    payload['onduty'] = {'mode': 'skip'}

    preview = parse_payload(payload)

    assert preview.onduty == {'mode': 'skip'}


def test_onduty_groups_are_kept():
    payload = full_payload()
    payload['onduty'] = {
        'mode': 'groups',
        'start': '2026-11-09',
        'weeks': 8,
        'jobs': ['扫', '擦'],
        'skip_weekend': False,
        'group_count': 2,
        'groups': {'第1组': ['张三', '王五'], '第2组': ['李四'], '空组': []},
    }

    preview = parse_payload(payload)

    assert preview.onduty['mode'] == 'groups'
    assert preview.onduty['group_count'] == 2
    assert preview.onduty['groups'] == {'第1组': ['张三', '王五'], '第2组': ['李四']}
    assert preview.onduty['skip_weekend'] is False


def test_onduty_daily_is_capped_to_roster():
    payload = full_payload()
    payload['onduty']['daily'] = 99

    preview = parse_payload(payload)

    assert preview.onduty['daily'] == 4          # = 名单人数


def test_missing_info_and_onduty_are_tolerated():
    payload = {'v': 1, 'names': ['张三'], 'classlist': [['语文']]}

    preview = parse_payload(payload)

    assert preview.info == {}
    assert preview.onduty == {}
    assert preview.rows == 1


def test_missing_names_is_rejected():
    payload = full_payload()
    payload.pop('names')

    with pytest.raises(CloudImportError) as info:
        parse_payload(payload)
    assert '名单' in str(info.value)


def test_empty_names_is_rejected():
    payload = full_payload()
    payload['names'] = ['  ', '']

    with pytest.raises(CloudImportError):
        parse_payload(payload)


def test_duplicate_names_are_rejected():
    payload = full_payload()
    payload['names'] = ['张三', '李四', '张三']

    with pytest.raises(CloudImportError) as info:
        parse_payload(payload)
    assert '重名' in str(info.value)


def test_empty_classlist_is_rejected():
    payload = full_payload()
    payload['classlist'] = {'rows': []}

    with pytest.raises(CloudImportError) as info:
        parse_payload(payload)
    assert '课程表' in str(info.value)


def test_payload_must_be_object():
    with pytest.raises(CloudImportError):
        parse_payload(['not', 'a', 'dict'])


def test_bad_version_is_rejected():
    payload = full_payload()
    payload['v'] = 0

    with pytest.raises(CloudImportError) as info:
        parse_payload(payload)
    assert '版本' in str(info.value)


def test_summary_and_expiry_text():
    preview = parse_payload(full_payload())
    text = summary_text(preview)

    assert '4 人' in text
    assert '2 节课表' in text
    assert format_expiry('2026-11-11T15:37:39.829Z')
    assert format_expiry('') == ''
    assert format_expiry('not-a-date') == 'not-a-date'
