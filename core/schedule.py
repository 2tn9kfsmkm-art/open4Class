"""作息时间：判断"现在是第几节 / 课间 / 放学后"。

悬浮窗只需要回答两个问题：
    1. 现在在上第几节课？
    2. 下一节是什么？

时间表放在 settings.json 的 ``lesson_times`` 里（形如 ``[["07:40","08:20"], ...]``），
没配置时用下面这份默认值。
"""

from datetime import datetime, time

# 高中常见作息：10 节，含上午 4 节、下午 4 节、晚自习 2 节占位
DEFAULT_LESSON_TIMES = [
    ("07:40", "08:20"),
    ("08:30", "09:10"),
    ("09:20", "10:00"),
    ("10:10", "10:50"),
    ("11:00", "11:40"),
    ("13:00", "13:40"),
    ("13:50", "14:30"),
    ("14:40", "15:20"),
    ("15:30", "16:10"),
    ("16:20", "17:00"),
]


def _to_time(value) -> time:
    if isinstance(value, time):
        return value
    text = str(value).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"无法识别的时间：{value!r}")


def parse_times(raw) -> list[tuple[time, time]]:
    """把 [['07:40','08:20'], ...] 解析成 [(time, time), ...]。

    解析失败时回退到默认表，不让悬浮窗因为配置写坏而崩掉。
    """
    if not raw:
        raw = DEFAULT_LESSON_TIMES
    result = []
    try:
        for item in raw:
            start, end = item
            result.append((_to_time(start), _to_time(end)))
    except (TypeError, ValueError):
        result = [(_to_time(a), _to_time(b)) for a, b in DEFAULT_LESSON_TIMES]
    return result


def lesson_state(now: datetime, times) -> dict:
    """返回当前节次状态。

    status:
        'before'  还没到第一节课
        'lesson'  正在上课
        'break'   课间（两节之间 / 午休 / 放学后都算，但放学后 next 为 None）
        'after'   今天所有课都结束了
    current / next 都是 0 起的下标，没有则为 None。
    """
    slots = parse_times(times)
    hhmm = now.time()

    for i, (start, end) in enumerate(slots):
        if start <= hhmm <= end:
            return {"status": "lesson", "current": i,
                    "next": i + 1 if i + 1 < len(slots) else None,
                    "starts_at": start, "ends_at": end}

    if hhmm < slots[0][0]:
        return {"status": "before", "current": None, "next": 0,
                "starts_at": hhmm, "ends_at": slots[0][0]}

    for i, (start, end) in enumerate(slots):
        if hhmm < start:
            prev_end = slots[i - 1][1] if i > 0 else hhmm
            return {"status": "break", "current": None, "next": i,
                    "starts_at": prev_end, "ends_at": start}

    return {"status": "after", "current": None, "next": None,
            "starts_at": slots[-1][1], "ends_at": slots[-1][1]}


def describe(state: dict, courses: list[str]) -> tuple[str, str]:
    """把状态翻译成悬浮窗要显示的两行字。

    Returns:
        (主标题, 副标题)，例如 ("第 3 节", "数学") 或 ("课间", "下一节 英语")。
    """
    def course_at(index):
        if index is None or index >= len(courses):
            return ""
        return str(courses[index] or "").strip()

    status = state["status"]
    if status == "lesson":
        label = f"第 {state['current'] + 1} 节"
        subject = course_at(state["current"]) or "上课中"
        return label, subject
    if status == "before":
        return "早读前", "下一节 " + (course_at(0) or "—")
    if status == "break":
        nxt = course_at(state["next"])
        return "课间", "下一节 " + (nxt or "—")
    return "放学", "今天没有课了"


def times_for_weekday(raw, weekday: int):
    """从"按星期的作息表"里取出某一天的时间段。

    raw 支持两种形态：
        {1: [("07:40","08:20"), ...], ...}   按星期（新）
        [("07:40","08:20"), ...]             所有人一样（旧）
    weekday: 1=周一 … 7=周日；周末回退到周一那份。
    """
    if isinstance(raw, dict):
        slots = raw.get(weekday) or raw.get(str(weekday)) or raw.get(1)
        return slots or DEFAULT_LESSON_TIMES
    return raw or DEFAULT_LESSON_TIMES
