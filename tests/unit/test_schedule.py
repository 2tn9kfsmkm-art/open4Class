"""作息时间与节次判断：悬浮窗的"当前课/下一节"全靠它。"""

from datetime import datetime

import pytest

from core.schedule import (
    DEFAULT_LESSON_TIMES, describe, lesson_state, parse_times,
)


def at(hhmm: str) -> datetime:
    return datetime.strptime(f'2026-11-02 {hhmm}', '%Y-%m-%d %H:%M')


class TestLessonState:
    def test_during_first_lesson(self):
        state = lesson_state(at('07:45'), DEFAULT_LESSON_TIMES)
        assert state['status'] == 'lesson'
        assert state['current'] == 0
        assert state['next'] == 1

    def test_during_fifth_lesson(self):
        state = lesson_state(at('11:10'), DEFAULT_LESSON_TIMES)
        assert state['current'] == 4

    def test_break_between_lessons(self):
        state = lesson_state(at('08:25'), DEFAULT_LESSON_TIMES)   # 08:20~08:30
        assert state['status'] == 'break'
        assert state['current'] is None
        assert state['next'] == 1

    def test_lunch_break(self):
        state = lesson_state(at('12:00'), DEFAULT_LESSON_TIMES)
        assert state['status'] == 'break'
        assert state['next'] == 5

    def test_before_school(self):
        state = lesson_state(at('07:00'), DEFAULT_LESSON_TIMES)
        assert state['status'] == 'before'
        assert state['next'] == 0

    def test_after_school(self):
        state = lesson_state(at('18:30'), DEFAULT_LESSON_TIMES)
        assert state['status'] == 'after'
        assert state['next'] is None

    def test_last_lesson_boundary(self):
        state = lesson_state(at('17:00'), DEFAULT_LESSON_TIMES)
        assert state['status'] == 'lesson'
        assert state['current'] == 9
        assert state['next'] is None


class TestDescribe:
    def test_lesson_shows_slot_and_subject(self):
        courses = ['语文', '数学', '英语']
        title, subject = describe(lesson_state(at('07:45'), DEFAULT_LESSON_TIMES), courses)
        assert title == '第 1 节'
        assert subject == '语文'

    def test_lesson_without_course_falls_back(self):
        title, subject = describe(lesson_state(at('07:45'), DEFAULT_LESSON_TIMES), [])
        assert title == '第 1 节'
        assert subject == '上课中'

    def test_break_shows_next(self):
        title, subject = describe(lesson_state(at('08:25'), DEFAULT_LESSON_TIMES), ['语文', '数学'])
        assert title == '课间'
        assert subject == '下一节 数学'

    def test_after_school(self):
        title, subject = describe(lesson_state(at('18:30'), DEFAULT_LESSON_TIMES), ['语文'])
        assert title == '放学'
        assert subject == '今天没有课了'


class TestParseTimes:
    def test_accepts_settings_format(self):
        slots = parse_times([['07:40', '08:20']])
        assert slots[0][0].strftime('%H:%M') == '07:40'

    def test_bad_format_falls_back_to_default(self):
        slots = parse_times([['乱写', '08:20']])
        assert len(slots) == len(DEFAULT_LESSON_TIMES)

    def test_empty_uses_default(self):
        assert len(parse_times(None)) == len(DEFAULT_LESSON_TIMES)

    def test_time_objects_accepted(self):
        from datetime import time
        slots = parse_times([[time(7, 40), time(8, 20)]])
        assert slots[0][0].hour == 7
