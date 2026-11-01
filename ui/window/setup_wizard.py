from PySide6.QtCore import QTime
"""首次使用向导。

约定：**向导只收集表单，落盘全部交给 bootstrap.save_all**。
这样以后 P6 换 SQLite，只改 bootstrap，向导不用动。

对外入口：
    SetupWizard.run()       首次启动时调用，返回是否完成
"""

from pandas import DataFrame, read_csv
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QTimeEdit,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import bootstrap
from config import CLASS_WEEKDAYS, DEFAULT_CLASS_ROWS, load_user_settings
from ondutySpawn import (
    build_onduty_df,
    build_onduty_df_from_groups,
    compute_stats,
    read_groups_from_df,
    read_names_from_df,
    split_groups,
)

PAGE_WIDTH = 900
PAGE_HEIGHT = 620


# ============================================================
# 页面基类
# ============================================================
class _Page(QWidget):
    title = ''
    subtitle = ''

    def __init__(self, wizard):
        super().__init__(wizard)
        self.wizard = wizard

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        head = QLabel(self.title)
        head.setStyleSheet('font-size: 18pt; font-weight: bold; color: #1A1A1A;')
        root.addWidget(head)

        sub = QLabel(self.subtitle)
        sub.setWordWrap(True)
        sub.setStyleSheet('font-size: 11pt; color: #666666;')
        root.addWidget(sub)
        root.addSpacing(14)

        # 内容放进滚动区：窗口由用户自由拖动缩放，内容多了就滚动，不挤压控件
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.content = QWidget()
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)

        self._build()

    def _build(self):
        """子类在这里搭界面。"""

    def validate(self):
        """返回错误文案；None 表示可以继续。"""
        return None

    def on_enter(self):
        """每次切换到本页时调用。"""

    def collect(self):
        """返回要合并进 wizard.data 的字典。"""
        return {}


# ============================================================
# ① 欢迎
# ============================================================
class WelcomePage(_Page):
    title = '欢迎使用班级管理系统'
    subtitle = '这个向导会用 5 步帮你把班级的基础数据准备好，之后就可以直接使用了。'

    def _build(self):
        tip = QLabel(
            '接下来会依次设置：\n\n'
            '    1. 班级信息（学校、班级名称）\n'
            '    2. 学生名单（粘贴或导入 CSV / Excel）\n'
            '    3. 课程表（导入表格或手动填写）\n'
            '    4. 值日安排（按名单顺序生成）\n'
            '    5. 完成\n\n'
            '随时可以点「取消」退出；数据只会在这最后一步才写入。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('font-size: 11pt; line-height: 170%;')
        self.body.addWidget(tip)
        self.body.addStretch(1)

        warn = QLabel(
            '注意：如果这台电脑上已经有班级数据，请直接取消 —— '
            '本向导写入时会覆盖现有的名单与课表。'
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(
            'font-size: 11pt; color: #C62828; background: #FDF0F0;'
            'border: 1px solid #F0C0C0; border-radius: 6px; padding: 10px;')
        self.body.addWidget(warn)


# ============================================================
# ② 班级信息
# ============================================================
class ClassInfoPage(_Page):
    title = '班级信息'
    subtitle = '这些内容会显示在主窗口标题和侧栏上。'

    def _build(self):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.school_le = QLineEdit()
        self.full_le = QLineEdit()
        self.short_le = QLineEdit()
        for le in (self.school_le, self.full_le, self.short_le):
            le.setFixedWidth(400)

        form.addRow('学校名称：', self.school_le)
        form.addRow('班级全名：', self.full_le)
        form.addRow('班级短名：', self.short_le)
        self.body.addLayout(form)

        hint = QLabel('例：市西中学 / 高三（8）班 / 高三八班。短名用在窗口标题，建议不超过 10 个字。')
        hint.setWordWrap(True)
        hint.setStyleSheet('font-size: 10pt; color: #888888;')
        self.body.addWidget(hint)
        self.body.addStretch(1)

        cfg = load_user_settings()
        self.school_le.setText(cfg.get('school_name', ''))
        self.full_le.setText(cfg.get('class_full_name', ''))
        self.short_le.setText(cfg.get('class_short_name', ''))

    def validate(self):
        if not self.school_le.text().strip():
            return '请填写学校名称'
        if not self.full_le.text().strip():
            return '请填写班级全名'
        short = self.short_le.text().strip()
        if not short:
            return '请填写班级短名'
        if len(short) > 10:
            return '班级短名请控制在 10 个字以内'
        return None

    def collect(self):
        return {'info': {
            'school_name': self.school_le.text().strip(),
            'class_full_name': self.full_le.text().strip(),
            'class_short_name': self.short_le.text().strip(),
        }}


# ============================================================
# ③ 学生名单
# ============================================================
class RosterPage(_Page):
    title = '学生名单'
    subtitle = '顺序就是值日表的轮值顺序。每行一个姓名，也可以直接导入表格。'

    def _build(self):
        row = QHBoxLayout()

        left = QVBoxLayout()
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText('张三\n李四\n王五')
        self.text_edit.textChanged.connect(self._sync_preview)
        left.addWidget(self.text_edit, 1)

        btns = QHBoxLayout()
        self.csv_btn = QPushButton('导入 CSV')
        self.xlsx_btn = QPushButton('导入 Excel')
        for b in (self.csv_btn, self.xlsx_btn):
            b.setStyleSheet('font-size: 11pt; padding: 4px 12px;')
            btns.addWidget(b)
        btns.addStretch(1)
        left.addLayout(btns)
        row.addLayout(left, 3)

        right = QVBoxLayout()
        right.addWidget(QLabel('解析结果：'))
        self.listw = QListWidget()
        self.listw.setSelectionMode(QAbstractItemView.NoSelection)
        right.addWidget(self.listw, 1)
        self.count_l = QLabel('共 0 人')
        self.count_l.setStyleSheet('font-size: 11pt; color: #666666;')
        right.addWidget(self.count_l)
        row.addLayout(right, 2)

        self.body.addLayout(row, 1)

        self.csv_btn.clicked.connect(lambda: self._import('csv'))
        self.xlsx_btn.clicked.connect(lambda: self._import('xlsx'))

    def names(self):
        return [ln.strip() for ln in self.text_edit.toPlainText().splitlines() if ln.strip()]

    def _sync_preview(self):
        names = self.names()
        self.listw.clear()
        self.listw.addItems(names)
        self.count_l.setText(f'共 {len(names)} 人')

    def _import(self, kind):
        filters = 'CSV (*.csv)' if kind == 'csv' else 'Excel (*.xlsx)'
        path, _ = QFileDialog.getOpenFileName(self, '选择名单文件', '', filters)
        if not path:
            return
        try:
            if kind == 'xlsx':
                src = read_excel_safe(path)
            else:
                src = read_csv(path)
            names = read_names_from_df(src)
        except Exception as e:
            QMessageBox.warning(self, '导入失败', f'{e}')
            return
        self.text_edit.setPlainText('\n'.join(names))
        self._sync_preview()

    def validate(self):
        names = self.names()
        if not names:
            return '请至少填写一名学生'
        dups = sorted({n for n in names if names.count(n) > 1})
        if dups:
            return '存在重名：' + '、'.join(dups) + '\n请修改后再继续'
        return None

    def collect(self):
        return {'names': self.names()}


# ============================================================
# ④ 课程表
# ============================================================
class ClasslistPage(_Page):
    title = '课程表'
    subtitle = '每周模板课表。可以导入表格，也可以直接在下面的格子里填。'

    def _build(self):
        btns = QHBoxLayout()
        self.import_btn = QPushButton('导入 Excel / CSV')
        self.add_row_btn = QPushButton('插入一节')
        self.del_row_btn = QPushButton('删除末节')
        for b in (self.import_btn, self.add_row_btn, self.del_row_btn):
            b.setStyleSheet('font-size: 11pt; padding: 4px 12px;')
            btns.addWidget(b)
        btns.addStretch(1)
        self.body.addLayout(btns)

        self.table = QTableWidget(DEFAULT_CLASS_ROWS, len(CLASS_WEEKDAYS))
        self.table.setHorizontalHeaderLabels(CLASS_WEEKDAYS)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.body.addWidget(self.table, 1)

        hint = QLabel('提示：空白格子表示那节课没课。列固定为周一~周五；导入时会自动识别「星期一 / Mon」等写法。')
        hint.setWordWrap(True)
        hint.setStyleSheet('font-size: 10pt; color: #888888;')
        self.body.addWidget(hint)

        self.import_btn.clicked.connect(self._import)
        self.add_row_btn.clicked.connect(self._add_row)
        self.del_row_btn.clicked.connect(self._del_row)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '导入课表', '', '表格文件 (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)')
        if not path:
            return
        try:
            src = read_excel_safe(path) if path.lower().endswith('.xlsx') else read_csv(path)
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'{e}')
            return

        from ui.window.settings_window import CourseEditorWidget
        normalized = CourseEditorWidget._normalize_weekday_columns(src)
        if normalized is None or len(normalized) == 0:
            QMessageBox.warning(
                self, '导入失败',
                '无法识别课表结构：需要 5 列（周一~周五）或至少 5 列数据。')
            return
        self._fill_table(normalized)

    def _fill_table(self, df):
        self.table.setRowCount(len(df))
        for r in range(len(df)):
            for c in range(len(CLASS_WEEKDAYS)):
                v = df.iat[r, c] if c < df.shape[1] else ''
                text = '' if v is None or v != v else str(v)
                self.table.setItem(r, c, QTableWidgetItem(text))

    def _add_row(self):
        self.table.insertRow(self.table.rowCount())

    def _del_row(self):
        if self.table.rowCount() > 1:
            self.table.removeRow(self.table.rowCount() - 1)

    def dataframe(self):
        rows = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(len(CLASS_WEEKDAYS)):
                item = self.table.item(r, c)
                row.append(item.text().strip() if item else '')
            rows.append(row)
        return DataFrame(rows, columns=CLASS_WEEKDAYS)

    def validate(self):
        df = self.dataframe()
        if not any(str(v).strip() for v in df.values.flatten()):
            return '课程表还是空的，请至少填一节课'
        return None

    def collect(self):
        return {'classlist': self.dataframe()}


# ============================================================
# ⑤ 值日安排
# ============================================================
class SchedulePage(_Page):
    """作息时间：一个小表，用表头的星期下拉切换周一~周五。"""

    title = "作息时间"
    subtitle = ("表头选星期，同一张表里分别选时、分（精确到 1 分钟）。"
                "五天可以不一样。")

    def __init__(self, wizard):
        super().__init__(wizard)
        self._loading = False

        from core.schedule import DEFAULT_LESSON_TIMES
        base = []
        for start, end in DEFAULT_LESSON_TIMES:
            sh, sm = (int(x) for x in start.split(':'))
            eh, em = (int(x) for x in end.split(':'))
            base.append((sh, sm, eh, em))
        self._days = {d: list(base) for d in range(1, 6)}
        self._current = 1

        lay = self.body
        top = QHBoxLayout()
        top.addWidget(QLabel('星期'))
        self.day_cb = QComboBox()
        self.day_cb.addItems(CLASS_WEEKDAYS)
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

    # ---------- 表格 ----------
    @staticmethod
    def _combo(values, current):
        cb = QComboBox()
        cb.addItems([f'{v:02d}' for v in values])
        cb.setCurrentText(f'{current:02d}')
        cb.setMinimumHeight(32)
        return cb

    def _render(self):
        rows = self._days[self._current]
        self._loading = True
        self.table.setRowCount(len(rows))
        for r, (sh, sm, eh, em) in enumerate(rows):
            self.table.setCellWidget(r, 0, self._combo(range(0, 24), sh))
            self.table.setCellWidget(r, 1, self._combo(range(0, 60), sm))
            self.table.setCellWidget(r, 2, self._combo(range(0, 24), eh))
            self.table.setCellWidget(r, 3, self._combo(range(0, 60), em))
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
        self._days[self._current].append((7, 40, 8, 20))
        self._render()

    def _del_last(self):
        self._save_current()
        if len(self._days[self._current]) > 1:
            self._days[self._current].pop()
            self._render()

    # ---------- 对外 ----------
    def set_times(self, mapping: dict):
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
        result = {}
        for weekday, rows in self._days.items():
            if rows:
                result[weekday] = [(f'{sh:02d}:{sm:02d}', f'{eh:02d}:{em:02d}')
                                   for sh, sm, eh, em in rows]
        return result


class OndutyPage(_Page):
    title = '值日安排'
    subtitle = '可以按名单顺序轮值，也可以按分组轮值。之后随时能在「设置 → 值日生生成」里重做。'

    def _build(self):
        self._imported_groups = None

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.form = form

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(['按名单顺序轮值', '按分组轮值', '暂时不生成，稍后自己设置'])
        form.addRow('生成方式：', self.mode_cb)

        self.start_de = QDateEdit(QDate.currentDate())
        self.start_de.setCalendarPopup(True)
        self.start_de.setDisplayFormat('yyyy-MM-dd')
        form.addRow('起始日期：', self.start_de)

        self.weeks_sb = QSpinBox()
        self.weeks_sb.setRange(1, 100)
        self.weeks_sb.setValue(20)
        self.weeks_sb.setSuffix(' 周')
        form.addRow('生成周数：', self.weeks_sb)

        self.daily_sb = QSpinBox()
        self.daily_sb.setRange(1, 20)
        self.daily_sb.setValue(5)
        self.daily_sb.setSuffix(' 人/天')
        form.addRow('每日人数：', self.daily_sb)

        cfg = load_user_settings()
        self.jobs_le = QLineEdit(','.join(cfg.get('onduty_daily_template') or ['扫', '扫', '擦', '排', '理']))
        form.addRow('职务模板：', self.jobs_le)

        self.skip_weekend_cb = QCheckBox('跳过周末（只排周一至周五）')
        self.skip_weekend_cb.setChecked(True)
        form.addRow('', self.skip_weekend_cb)

        self.body.addLayout(form)

        # ---- 分组设置（独立分组框，整块显示/隐藏，避免表单行隐藏后仍占位） ----
        self.group_box = QGroupBox('分组设置')
        self.group_box.setStyleSheet(
            'QGroupBox { margin-top: 0.9em; padding-top: 6px; }')
        group_form = QFormLayout(self.group_box)
        group_form.setLabelAlignment(Qt.AlignRight)

        self.group_count_sb = QSpinBox()
        self.group_count_sb.setRange(2, 12)
        self.group_count_sb.setValue(4)
        self.group_count_sb.setSuffix(' 组')
        group_form.addRow('分成几组：', self.group_count_sb)

        self.group_src_l = QLabel('当前：按名单顺序平均分组')
        self.group_src_l.setWordWrap(True)
        self.group_src_l.setStyleSheet('font-size: 10pt; color: #666666;')
        group_form.addRow('分组来源：', self.group_src_l)

        group_btns = QHBoxLayout()
        self.group_import_btn = QPushButton('导入分组表（Excel / CSV）')
        self.group_clear_btn = QPushButton('改回自动均分')
        for b in (self.group_import_btn, self.group_clear_btn):
            b.setMinimumHeight(30)
            b.setStyleSheet('font-size: 11pt; padding: 4px 12px;')
            group_btns.addWidget(b)
        group_btns.addStretch(1)
        self.group_btns_w = QWidget()
        self.group_btns_w.setLayout(group_btns)
        group_form.addRow('', self.group_btns_w)

        self.body.addWidget(self.group_box)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton('刷新预览')
        self.refresh_btn.setStyleSheet('font-size: 11pt; padding: 4px 12px;')
        row.addWidget(self.refresh_btn)
        row.addStretch(1)
        self.body.addLayout(row)

        self.preview = QTextBrowser()
        self.preview.setMinimumHeight(70)
        self.body.addWidget(self.preview, 1)

        self.refresh_btn.clicked.connect(self.refresh_preview)
        self.mode_cb.currentIndexChanged.connect(self._on_mode_changed)
        self.group_count_sb.valueChanged.connect(self._on_group_source_changed)
        self.group_import_btn.clicked.connect(self._on_import_groups)
        self.group_clear_btn.clicked.connect(self._on_clear_groups)
        self._on_mode_changed()

    # ---------- 模式 / 分组 ----------
    def _on_mode_changed(self):
        mode = self.mode_cb.currentIndex()
        is_group = mode == 1
        enabled = mode in (0, 1)

        for w in (self.start_de, self.weeks_sb, self.jobs_le,
                  self.skip_weekend_cb, self.refresh_btn):
            w.setEnabled(enabled)
        self.daily_sb.setEnabled(mode == 0)          # 分组模式下人数由组大小决定

        self.group_box.setVisible(is_group)
        self._on_group_source_changed()
        self.refresh_preview()

    def _on_group_source_changed(self):
        if self._imported_groups:
            sizes = '、'.join(f'{k}({len(v)})' for k, v in self._imported_groups.items())
            self.group_src_l.setText(f'已导入 {len(self._imported_groups)} 组：{sizes}')
        else:
            self.group_src_l.setText(f'当前：按名单顺序平均分成 {self.group_count_sb.value()} 组')
        self.group_clear_btn.setEnabled(bool(self._imported_groups))

    def _on_import_groups(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '导入分组表', '', '表格文件 (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)')
        if not path:
            return
        try:
            src = read_excel_safe(path) if path.lower().endswith('.xlsx') else read_csv(path)
            groups = read_groups_from_df(src)
        except Exception as e:
            QMessageBox.warning(self, '导入失败', f'{e}')
            return
        self._imported_groups = groups
        self.group_count_sb.setEnabled(False)
        self._on_group_source_changed()
        self.refresh_preview()

    def _on_clear_groups(self):
        self._imported_groups = None
        self.group_count_sb.setEnabled(True)
        self._on_group_source_changed()
        self.refresh_preview()

    def groups(self):
        """返回 {组名: [成员...]}；优先用导入的分组表。"""
        if self._imported_groups:
            return dict(self._imported_groups)
        names = self.wizard.data.get('names') or []
        n = self.group_count_sb.value()
        return split_groups(names, n)

    # ---------- 生成 ----------
    def _jobs(self):
        return [j.strip() for j in self.jobs_le.text().split(',') if j.strip()]

    def build(self):
        """返回 (df 或 None, 错误文案 或 None)。"""
        mode = self.mode_cb.currentIndex()
        if mode == 2:
            return None, None

        jobs = self._jobs()
        if not jobs:
            return None, '职务模板不能为空'
        start = self.start_de.date().toPython()
        weeks = self.weeks_sb.value()

        try:
            if mode == 0:
                names = self.wizard.data.get('names') or []
                if not names:
                    return None, '还没有学生名单'
                daily = self.daily_sb.value()
                if daily > len(names):
                    return None, f'每日人数（{daily}）不能超过学生人数（{len(names)}）'
                df = build_onduty_df(
                    start=start, weeks=weeks, daily=daily,
                    names=names, jobs=jobs,
                    skip_weekend=self.skip_weekend_cb.isChecked(),
                )
            else:
                groups = self.groups()
                if not groups:
                    return None, '分组表是空的'
                df = build_onduty_df_from_groups(
                    start=start, weeks=weeks, groups=groups, jobs=jobs,
                    skip_weekend=self.skip_weekend_cb.isChecked(),
                )
        except Exception as e:
            return None, str(e)
        return df, None

    def refresh_preview(self):
        df, err = self.build()
        if err:
            self.preview.setPlainText(f'无法生成：{err}')
            return
        if df is None or df.empty:
            self.preview.setPlainText('（已选择"暂时不生成"）')
            return
        counter, n_days = compute_stats(df)
        lines = [f'共 {n_days} 天 × {df.shape[0]} 人/天', '']
        lines.append(df.iloc[:, :min(5, df.shape[1])].to_string())
        lines.append('')
        lines.append('值日次数统计：')
        for name, c in sorted(counter.items(), key=lambda x: -x[1]):
            lines.append(f'  {name}：{c} 次')
        self.preview.setPlainText('\n'.join(lines))

    def on_enter(self):
        self.refresh_preview()

    def validate(self):
        df, err = self.build()
        if err:
            return err
        return None

    def collect(self):
        df, _ = self.build()
        return {'onduty': df}


# ============================================================
# ⑥ 完成
# ============================================================
class DonePage(_Page):
    title = '准备就绪'
    subtitle = '点「完成」后数据才会写入。之后可以在设置里随时修改。'

    def _build(self):
        self.summary_l = QLabel()
        self.summary_l.setWordWrap(True)
        self.summary_l.setStyleSheet(
            'font-size: 12pt; background: #FAFAFA; border: 1px solid #E0E0E0;'
            'border-radius: 8px; padding: 18px;')
        self.body.addWidget(self.summary_l)

        tip = QLabel(
            '写入位置：%APPDATA%\\ClassManager\\data\\\n'
            '这些数据只保存在本机，不会上传到任何地方。'
        )
        tip.setWordWrap(True)
        tip.setStyleSheet('font-size: 10pt; color: #888888;')
        self.body.addWidget(tip)
        self.body.addStretch(1)

    def on_enter(self):
        d = self.wizard.data
        names = d.get('names') or []
        classlist = d.get('classlist')
        onduty = d.get('onduty')
        rows = 0 if classlist is None else len(classlist)
        days = 0 if onduty is None else int(onduty.shape[1])
        info = d.get('info') or {}
        self.summary_l.setText(
            f"班级：{info.get('school_name', '')} {info.get('class_full_name', '')}\n"
            f"学生：{len(names)} 人\n"
            f"课表：{rows} 节 × 5 天\n"
            f"值日：{'未生成' if days == 0 else f'{days} 天'}"
        )


# ============================================================
# 向导窗口
# ============================================================
class SetupWizard(QDialog):
    STEPS = ['欢迎', '班级信息', '学生名单', '课程表', '作息时间', '值日安排', '完成']

    def __init__(self, parent=None, root=None, prefill=False, keep=None):
        super().__init__(parent)
        self._root = root
        self._prefill = prefill
        self._keep = set(keep) if keep is not None else {'info', 'roster', 'classlist', 'schedule'}
        self.data = {}
        self.current = 0
        self.summary = None

        self.setWindowTitle('首次使用设置')
        # 窗口尺寸只定一次，之后交给用户拖动：不在切模式/切页时改大小
        # （那样会在重绘时留下残影）。内容溢出由页面内的滚动区兜底。
        self.setMinimumSize(760, 520)
        self._extra_height = 0
        self.resize(PAGE_WIDTH, self._default_height())

        self._build_layout()

        self.pages = [
            WelcomePage(self),
            ClassInfoPage(self),
            RosterPage(self),
            ClasslistPage(self),
            SchedulePage(self),
            OndutyPage(self),
            DonePage(self),
        ]
        for page in self.pages:
            self.stack.addWidget(page)

        if self._prefill:
            self.setWindowTitle('重新设置（保留现有数据）')
            self._apply_prefill()

        self._goto(0)

    @staticmethod
    def _available_height() -> int:
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        return screen.availableGeometry().height() if screen else 1080

    @classmethod
    def _default_height(cls) -> int:
        """默认高度：尽量放得下值日页分组模式，同时不超出屏幕。"""
        return max(520, min(820, cls._available_height() - 100))

    # ---------- 布局 ----------
    def _build_layout(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 左侧步骤条
        self.step_panel = QWidget()
        self.step_panel.setFixedWidth(200)
        self.step_panel.setStyleSheet('background-color: #9b0d14;')
        step_layout = QVBoxLayout(self.step_panel)
        step_layout.setContentsMargins(0, 28, 0, 0)
        step_layout.setSpacing(2)

        title = QLabel('首次设置')
        title.setStyleSheet(
            'color: white; font-size: 15pt; font-weight: bold; padding: 0 18px 16px 18px;')
        step_layout.addWidget(title)

        self.step_labels = []
        for name in self.STEPS:
            lbl = QLabel(name)
            lbl.setStyleSheet('color: rgba(255,255,255,140); font-size: 12pt; padding: 8px 18px;')
            step_layout.addWidget(lbl)
            self.step_labels.append(lbl)
        step_layout.addStretch(1)
        outer.addWidget(self.step_panel)

        # 右侧内容
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(32, 28, 32, 20)
        right_layout.setSpacing(16)

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack, 1)

        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.setStyleSheet('font-size: 11pt; padding: 6px 18px; color: #666666;')
        buttons.addWidget(self.cancel_btn)
        buttons.addStretch(1)

        self.back_btn = QPushButton('上一步')
        self.back_btn.setStyleSheet('font-size: 11pt; padding: 6px 18px;')
        self.next_btn = QPushButton('下一步')
        self.next_btn.setStyleSheet('font-size: 11pt; padding: 6px 24px;')
        buttons.addWidget(self.back_btn)
        buttons.addWidget(self.next_btn)
        right_layout.addLayout(buttons)

        outer.addWidget(right, 1)

        self.cancel_btn.clicked.connect(self._on_cancel)
        self.back_btn.clicked.connect(self._on_back)
        self.next_btn.clicked.connect(self._on_next)

    # ---------- 导航 ----------
    def _goto(self, index):
        self.current = index
        self.stack.setCurrentIndex(index)
        self.pages[index].on_enter()
        self._refresh_steps()
        self.back_btn.setEnabled(index > 0)
        self.next_btn.setText('完成' if index == len(self.pages) - 1 else '下一步')

    def _refresh_steps(self):
        for i, lbl in enumerate(self.step_labels):
            if i == self.current:
                lbl.setStyleSheet('color: white; font-size: 12pt; font-weight: bold;'
                                  'padding: 8px 18px; background: rgba(255,255,255,30);')
            elif i < self.current:
                lbl.setStyleSheet('color: rgba(255,255,255,230); font-size: 12pt; padding: 8px 18px;')
            else:
                lbl.setStyleSheet('color: rgba(255,255,255,120); font-size: 12pt; padding: 8px 18px;')

    def _on_back(self):
        if self.current > 0:
            self._goto(self.current - 1)

    def _apply_prefill(self):
        """把数据库里现有的内容填进各页，用户只需确认或局部修改。"""
        from data.store import shared_store

        cfg = load_user_settings()
        keep = self._keep
        info = self.pages[1]
        if 'info' in keep:
            info.school_le.setText(str(cfg.get('school_name', '')))
            info.full_le.setText(str(cfg.get('class_full_name', '')))
            info.short_le.setText(str(cfg.get('class_short_name', '')))

        store = shared_store()
        if 'roster' in keep:
            names = store.load_names()['name'].tolist()
            self.pages[2].text_edit.setPlainText('\n'.join(str(n) for n in names))

        if 'schedule' in keep:
            self.pages[4].set_times(store.load_lesson_times())

        df = store.load_classlist() if 'classlist' in keep else store.load_classlist().iloc[0:0]
        page = self.pages[3]
        rows = max(df.shape[0], page.table.rowCount())
        page.table.setRowCount(rows)
        for r in range(df.shape[0]):
            for c in range(min(len(CLASS_WEEKDAYS), df.shape[1])):
                value = df.iat[r, c]
                text = '' if value is None else str(value).strip()
                if text in ('', 'nan'):
                    continue
                item = page.table.item(r, c)
                if item is None:
                    from PySide6.QtWidgets import QTableWidgetItem
                    item = QTableWidgetItem()
                    page.table.setItem(r, c, item)
                item.setText(text)

    def _on_next(self):
        page = self.pages[self.current]
        error = page.validate()
        if error:
            QMessageBox.warning(self, '还不能继续', error)
            return

        payload = page.collect()
        if payload:
            self.data.update(payload)

        if self.current == len(self.pages) - 1:
            self._finish()
        else:
            self._goto(self.current + 1)

    def _finish(self):
        try:
            self.summary = bootstrap.save_all(
                self.data['info'],
                self.data['names'],
                self.data['classlist'],
                self.data.get('onduty'),
                lesson_times=self.pages[4].collect(),
                root=self._root,
            )
        except Exception as e:
            QMessageBox.warning(self, '保存失败', f'{e}')
            return
        self.accept()

    def _on_cancel(self):
        if self._confirm_quit():
            self.reject()

    def _confirm_quit(self) -> bool:
        ans = QMessageBox.question(
            self, '确认退出',
            '还没有完成设置，退出后下次启动会重新进入向导。\n确定退出吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return ans == QMessageBox.Yes

    def closeEvent(self, event):
        if self._confirm_quit():
            event.accept()
        else:
            event.ignore()

    # ---------- 入口 ----------
    @classmethod
    def run(cls, parent=None, root=None) -> bool:
        wizard = cls(parent=parent, root=root)
        return wizard.exec() == QDialog.Accepted


def read_excel_safe(path: str):
    """读 Excel 并给出缺依赖时的可读提示。"""
    from pandas import read_excel
    try:
        return read_excel(path)
    except ImportError as e:
        raise RuntimeError(
            '读取 Excel 需要 openpyxl，请先执行：python -m pip install openpyxl'
        ) from e
