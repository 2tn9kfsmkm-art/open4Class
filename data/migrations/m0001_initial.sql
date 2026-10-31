-- ClassManager schema v1
-- 约定：日期列统一 TEXT + YYYY-MM-DD；不写 IF NOT EXISTS，靠版本号保证只执行一次。

-- 学生名单（sort_order 即轮值顺序）
CREATE TABLE students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    sort_order   INTEGER NOT NULL DEFAULT 0
);

-- 课程单（下拉候选）
CREATE TABLE courses (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT NOT NULL UNIQUE
);

-- 周模板课表（周一~周五 × 节次）
CREATE TABLE classlist_template (
    weekday       INTEGER NOT NULL CHECK (weekday BETWEEN 1 AND 5),
    lesson_index  INTEGER NOT NULL CHECK (lesson_index >= 1),
    course_name   TEXT,
    PRIMARY KEY (weekday, lesson_index)
);

-- 特定日期的临时课表（优先于模板）
CREATE TABLE classlist_override (
    date          TEXT NOT NULL,
    lesson_index  INTEGER NOT NULL CHECK (lesson_index >= 1),
    course_name   TEXT,
    PRIMARY KEY (date, lesson_index)
);

-- 值日表：一天最多 5 个位置
CREATE TABLE onduty (
    date          TEXT NOT NULL,
    slot_index    INTEGER NOT NULL CHECK (slot_index BETWEEN 0 AND 4),
    student_name  TEXT NOT NULL,
    job           TEXT NOT NULL,
    PRIMARY KEY (date, slot_index)
);

-- 应用链接
CREATE TABLE apps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    path        TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

-- 通用键值（settings.json 整体、last_login 等），value 为 JSON 字符串
CREATE TABLE kv (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
