"""作息编辑控件：表头选星期，一张表里编五天的节次时间。

向导和设置页共用这一个控件，保证两边行为一致。
"""

from PySide6.QtCore import QTime
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QVBoxLayout, QWidget,
)

from config import CLASS_WEEKDAYS, DEFAULT_CLASS_ROWS


class ScheduleEditor(QWidget):
    def __init__(self, parent=None, rows: int = DEFAULT_CLASS_ROWS):
        super().__init__(parent)
        self._loading = False
        self._current = 1
        self._days = {d: [] for d in range(1, 6)}
        self._default_rows = max(1, int(rows))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(QLabel('星期'))
        self.day_cb = QComboBox()
        self.day_cb.addItems(CLASS_WEEKDAYS)
        self.day_cb.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.day_cb.currentIndexChanged.connect(self._on_day_changed)
        top.addWidget(self.day_cb)

        self.copy_btn = QPushButton('把本日复制到其余四天')
        self.copy_btn.clicked.connect(self._copy_all)
        top.addWidget(self.copy_btn)
        top.addStretch(1)
        lay.addLayout(top)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ['开始 时', '开始 分', '结束 时', '结束 分'])
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.add_btn = QPushButton('加一节')
        self.add_btn.clicked.connect(self._add_row)
        self.del_btn = QPushButton('删末节')
        self.del_btn.clicked.connect(self._del_last)
        for b in (self.add_btn, self.del_btn):
            b.setMinimumHeight(36)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        self._render()

    # ---------- 单元格 ----------
    @staticmethod
    def _combo(values, current):
        cb = QComboBox()
        cb.addItems([f'{v:02d}' for v in values])
        cb.setCurrentText(f'{current:02d}')
        cb.setMinimumHeight(32)
        return cb

    def _render(self):
        rows = self._days[self._current] or [
            (7, 40, 8, 20) for _ in range(self._default_rows)]
        self._days[self._current] = list(rows)
        self._loading = True
        self.table.setRowCount(len(rows))
        for r, (sh, sm, eh, em) in enumerate(rows):
            self.table.setCellWidget(r, 0, self._combo(range(24), sh))
            self.table.setCellWidget(r, 1, self._combo(range(60), sm))
            self.table.setCellWidget(r, 2, self._combo(range(24), eh))
            self.table.setCellWidget(r, 3, self._combo(range(60), em))
        self.table.setMinimumHeight(38 * len(rows) + 44)
        self._loading = False

    def _save_current(self):
        if self._loading:
            return
        rows = []
        for r in range(self.table.rowCount()):
            cbs = [self.table.cellWidget(r, c) for c in range(4)]
            if any(cb is None for cb in cbs):
                continue
            rows.append(tuple(int(cb.currentText()) for cb in cbs))
        if rows:
            self._days[self._current] = rows

    def _on_day_changed(self, index):
        self._save_current()
        self._current = index + 1
        self._render()

    def _copy_all(self):
        self._save_current()
        rows = list(self._days[self._current])
        for d in range(1, 6):
            if d != self._current:
                self._days[d] = list(rows)

    def _add_row(self):
        self._save_current()
        last = self._days[self._current][-1] if self._days[self._current] else (7, 40, 8, 20)
        self._days[self._current].append(last)
        self._render()

    def _del_last(self):
        self._save_current()
        if len(self._days[self._current]) > 1:
            self._days[self._current].pop()
            self._render()

    # ---------- 对外 ----------
    def set_row_count(self, count: int) -> None:
        """把每一天的节数调整到 count（多退少补）。"""
        count = max(1, int(count))
        self._save_current()
        for d in range(1, 6):
            rows = list(self._days[d])
            if len(rows) > count:
                rows = rows[:count]
            while len(rows) < count:
                rows.append(rows[-1] if rows else (7, 40, 8, 20))
            self._days[d] = rows
        self._render()

    def set_times(self, mapping: dict) -> None:
        if not mapping:
            return
        for weekday in range(1, 6):
            slots = mapping.get(weekday) or mapping.get(str(weekday))
            if not slots:
                continue
            rows = []
            for start, end in slots:
                sh, sm = (int(x) for x in str(start).split(':'))
                eh, em = (int(x) for x in str(end).split(':'))
                rows.append((sh, sm, eh, em))
            self._days[weekday] = rows
        self._render()

    def collect(self) -> dict:
        self._save_current()
        return {
            d: [(f'{sh:02d}:{sm:02d}', f'{eh:02d}:{em:02d}')
                for sh, sm, eh, em in rows]
            for d, rows in self._days.items() if rows
        }
