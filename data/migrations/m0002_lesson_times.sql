-- 作息时间表：每个工作日可以不同
CREATE TABLE lesson_times (
    weekday      INTEGER NOT NULL,     -- 1=周一 … 5=周五
    period_index INTEGER NOT NULL,     -- 1=第一节
    start_time   TEXT    NOT NULL,     -- HH:MM
    end_time     TEXT    NOT NULL,     -- HH:MM
    PRIMARY KEY (weekday, period_index)
);
