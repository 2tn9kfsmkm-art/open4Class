import os
from datetime import datetime
from collections import Counter

from PySide6.QtWidgets import (
    QCheckBox, QDialogButtonBox,
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QScrollArea,
    QLabel, QLineEdit, QPushButton, QSpinBox, QCheckBox, QToolButton,
    QDateEdit, QTextBrowser, QTabWidget, QMessageBox, QFileDialog, QApplication,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QFrame,
    QAbstractItemView, QHeaderView, QComboBox, QSizePolicy, QTextEdit,
    QInputDialog,
)
from PySide6.QtCore import Qt, QDate, Signal, QTimer
from pandas import DataFrame, read_csv
import pandas as pd

import bootstrap
from data.store import shared_store
from ui.component.dropable_table import (
    dragdropQTableView, QComboBoxDelegate, QNoDelegate,
)
from tools.PandasQModel import PandasQItemModel

from config import (
    FILE_DIR, ENCODING, wordday, today, str_date,
    load_user_settings, save_user_settings,
)
from ondutySpawn import (
    build_onduty_df, build_onduty_df_from_groups,
    read_names, read_groups, compute_stats,
    write_sample_name_csv, write_sample_group_csv, open_file_external,
)
from services.imports import read_table, write_template
from ui.component.touch import enable_touch_scroll
from tools.SettingsWidgetBase import SettingsWidgetBase


# ============================================================
# Tab 1：值日生生成（现有功能 + 直接编辑按钮）
# ============================================================
class OndutySpawnWidget(SettingsWidgetBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh_preview()

    # ---------- UI ----------
    def _build_ui(self):
        cfg = load_user_settings()
        layout = QVBoxLayout(self)
        self.layout_form = QFormLayout()

        self.start_date_de = QDateEdit(QDate.currentDate())
        self.start_date_de.setCalendarPopup(True)
        self.start_date_de.setDisplayFormat('yyyy-MM-dd')
        self.layout_form.addRow('起始日期：', self.start_date_de)

        self.weeks_sb = QSpinBox()
        self.weeks_sb.setRange(1, 100)
        self.weeks_sb.setValue(22)
        self.weeks_sb.setSuffix(' 周')
        self.layout_form.addRow('周数：', self.weeks_sb)

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(['名单顺序轮值', '分组表格轮值'])
        self.layout_form.addRow('生成模式：', self.mode_cb)

        # 名单模式
        self.name_row_widget = QWidget()
        name_row = QHBoxLayout(self.name_row_widget)
        name_row.setContentsMargins(0, 0, 0, 0)
        self.name_le = QLineEdit('')
        self.name_le.setPlaceholderText('留空 = 使用「名单」Tab 里的名单')
        self.name_btn = QPushButton('...')
        self.name_btn.setMinimumWidth(40)
        self.name_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.sample_btn = QPushButton('样板')
        self.sample_btn.setMinimumWidth(64)
        self.sample_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        name_row.addWidget(self.name_le)
        name_row.addWidget(self.name_btn)
        name_row.addWidget(self.sample_btn)
        self.layout_form.addRow('名单文件：', self.name_row_widget)

        self.daily_sb = QSpinBox()
        self.daily_sb.setRange(1, 20)
        self.daily_sb.setValue(5)
        self.daily_sb.setSuffix(' 人/天')
        self.layout_form.addRow('每日人数：', self.daily_sb)

        # 分组模式
        self.group_row_widget = QWidget()
        group_row = QHBoxLayout(self.group_row_widget)
        group_row.setContentsMargins(0, 0, 0, 0)
        self.group_le = QLineEdit(FILE_DIR + '分组.csv')
        self.group_btn = QPushButton('...')
        self.group_btn.setMinimumWidth(40)
        self.group_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.group_sample_btn = QPushButton('样板')
        self.group_sample_btn.setMinimumWidth(64)
        self.group_sample_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        group_row.addWidget(self.group_le)
        group_row.addWidget(self.group_btn)
        group_row.addWidget(self.group_sample_btn)
        self.layout_form.addRow('分组文件：', self.group_row_widget)

        # 共享配置
        self.jobs_enum_le = QLineEdit(','.join(cfg['onduty_jobs']))
        self.layout_form.addRow('职务枚举：', self.jobs_enum_le)

        self.jobs_le = QLineEdit(','.join(cfg['onduty_daily_template']))
        self.layout_form.addRow('职务模板：', self.jobs_le)

        self.skip_weekend_cb = QCheckBox('跳过周末（周一至周五）')
        self.skip_weekend_cb.setChecked(True)
        self.layout_form.addRow('', self.skip_weekend_cb)

        self.overwrite_cb = QCheckBox('覆盖现有值日表')
        self.layout_form.addRow('', self.overwrite_cb)

        layout.addLayout(self.layout_form)

        # 高级选项
        self._build_adv_panel(layout)

        # 预览
        layout.addWidget(QLabel('预览（前 5 天 + 统计）：'))
        self.preview_tb = QTextBrowser()
        self.preview_tb.setMinimumHeight(160)
        layout.addWidget(self.preview_tb)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton('刷新预览')
        self.spawn_btn = QPushButton('生成')
        self.edit_btn = QPushButton('直接编辑未来值日')
        self.open_csv_btn = QPushButton('打开值日生表')
        for b in (self.refresh_btn, self.spawn_btn,
                  self.edit_btn, self.open_csv_btn):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        bottom_row = QHBoxLayout()
        self.reset_btn = QPushButton('重置配置')
        self.save_btn = QPushButton('保存配置')
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.reset_btn)
        bottom_row.addWidget(self.save_btn)
        layout.addLayout(bottom_row)

        # 连接
        self.mode_cb.currentIndexChanged.connect(self._on_mode_changed)
        self.name_btn.clicked.connect(self._choose_name)
        self.sample_btn.clicked.connect(self._write_sample)
        self.group_btn.clicked.connect(self._choose_group)
        self.group_sample_btn.clicked.connect(self._write_group_sample)
        self.refresh_btn.clicked.connect(self.refresh_preview)
        self.spawn_btn.clicked.connect(self.generate)
        self.edit_btn.clicked.connect(self._open_editor)
        self.open_csv_btn.clicked.connect(self._open_onduty_csv)
        self.reset_btn.clicked.connect(self.reset)
        self.save_btn.clicked.connect(self.save)

        self._on_mode_changed()

    def _build_adv_panel(self, parent_layout):
        self.adv_btn = QToolButton()
        self.adv_btn.setText('▶ 高级选项')
        self.adv_btn.setCheckable(True)
        self.adv_btn.setChecked(False)
        self.adv_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.adv_btn.setStyleSheet(
            'QToolButton { border: none; font-weight: bold; padding: 4px 0; }')
        self.adv_btn.toggled.connect(self._toggle_advanced)
        parent_layout.addWidget(self.adv_btn)

        self.adv_panel = QWidget()
        adv = QFormLayout(self.adv_panel)
        adv.setContentsMargins(20, 4, 0, 4)

        self.offset_sb = QSpinBox()
        self.offset_sb.setRange(0, 9999)
        self.offset_sb.setValue(0)
        self.offset_sb.setToolTip(
            '名单模式：从第 N 位开始（0=首位）\n分组模式：从第 N 组开始')
        adv.addRow('起始偏移：', self.offset_sb)

        self.stride_sb = QSpinBox()
        self.stride_sb.setRange(1, 9999)
        self.stride_sb.setValue(1)
        self.stride_sb.setToolTip(
            '每次前进位数\n1=顺序；>1 可形成不同组合\n'
            '注意：若与人数不互质，可能有部分人永远轮不到（统计会预警）')
        adv.addRow('轮换步长：', self.stride_sb)

        self.shuffle_cb = QCheckBox('生成前随机打乱（名单/组内顺序）')
        adv.addRow('', self.shuffle_cb)

        self.seed_sb = QSpinBox()
        self.seed_sb.setRange(0, 999999)
        self.seed_sb.setValue(0)
        self.seed_sb.setToolTip('0 = 每次不同；填入固定值可复现结果')
        adv.addRow('随机种子：', self.seed_sb)

        adv.addRow(QLabel('跳过名单（每行一个，仅本次生成生效）：'))
        self.skip_te = QTextEdit()
        self.skip_te.setMaximumHeight(90)
        self.skip_te.setPlaceholderText('例如：\n张三\n李四')
        adv.addRow(self.skip_te)

        self.adv_panel.setVisible(False)
        parent_layout.addWidget(self.adv_panel)

    def _toggle_advanced(self, checked):
        self.adv_panel.setVisible(checked)
        self.adv_btn.setText(('▼' if checked else '▶') + ' 高级选项')

    def _set_row_visible(self, widget, visible):
        widget.setVisible(visible)
        lbl = self.layout_form.labelForField(widget)
        if lbl is not None:
            lbl.setVisible(visible)

    def _on_mode_changed(self):
        is_group = self.mode_cb.currentIndex() == 1
        self._set_row_visible(self.name_row_widget, not is_group)
        self._set_row_visible(self.daily_sb, not is_group)
        self._set_row_visible(self.group_row_widget, is_group)
        # 分组模式不需要每日人数、步长
        self.stride_sb.setEnabled(not is_group)

    # ---------- 选文件 / 样板 ----------
    def _choose_name(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择名单文件', FILE_DIR, 'CSV (*.csv)')
        if path:
            self.name_le.setText(path)
            self.refresh_preview()

    def _choose_group(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择分组文件', FILE_DIR,
            '表格 (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)')
        if path:
            self.group_le.setText(path)
            self.refresh_preview()

    def _write_sample(self):
        default_path = FILE_DIR + '名单样板.csv'
        path, _ = QFileDialog.getSaveFileName(
            self, '保存样板名单', default_path, 'CSV (*.csv)')
        if not path:
            return
        try:
            write_sample_name_csv(path)
        except Exception as e:
            QMessageBox.warning(self, '保存失败', f'{e!r}')
            return
        QMessageBox.information(self, '完成', f'样板已保存到：\n{path}')

    def _write_group_sample(self):
        default_path = FILE_DIR + '分组样板.csv'
        path, _ = QFileDialog.getSaveFileName(
            self, '保存样板分组', default_path, 'CSV (*.csv)')
        if not path:
            return
        try:
            write_sample_group_csv(path)
        except Exception as e:
            QMessageBox.warning(self, '保存失败', f'{e!r}')
            return
        QMessageBox.information(self, '完成', f'样板已保存到：\n{path}')

    # ---------- 参数 / 数据 ----------
    def _read_params(self):
        start_date = self.start_date_de.date().toPython()
        start_dt = datetime.combine(start_date, datetime.min.time())
        weeks = self.weeks_sb.value()
        daily = self.daily_sb.value()
        skip_weekend = self.skip_weekend_cb.isChecked()
        name_path = self.name_le.text().strip()
        group_path = self.group_le.text().strip()
        jobs = [j.strip() for j in self.jobs_le.text().split(',') if j.strip()]
        mode = self.mode_cb.currentIndex()
        offset = self.offset_sb.value()
        stride = self.stride_sb.value()
        shuffle = self.shuffle_cb.isChecked()
        seed = self.seed_sb.value() or None
        skip_names = [s.strip() for s in self.skip_te.toPlainText().splitlines()
                      if s.strip()]
        return (start_dt, weeks, daily, skip_weekend,
                name_path, group_path, jobs, mode,
                offset, stride, shuffle, seed, skip_names)

    def _build_dataframe(self):
        (start_dt, weeks, daily, skip_weekend,
         name_path, group_path, jobs, mode,
         offset, stride, shuffle, seed, skip_names) = self._read_params()

        if mode == 0:
            if name_path and os.path.exists(name_path):
                names = read_names(name_path)
            else:
                names = shared_store().load_names()['name'].tolist()
            df = build_onduty_df(
                start=start_dt, weeks=weeks, daily=daily,
                names=names, jobs=jobs, skip_weekend=skip_weekend,
                offset=offset, stride=stride,
                skip_names=skip_names, shuffle=shuffle, seed=seed,
            )
            parts = [f'名单模式（{len(names)} 人']
            if skip_names:
                parts.append(f'跳过 {len(skip_names)} 人')
            if offset:
                parts.append(f'起始偏移 {offset}')
            if stride > 1:
                parts.append(f'步长 {stride}')
            if shuffle:
                parts.append(f'随机打乱(seed={seed or "每次不同"})')
            parts.append('）')
            return df, ''.join(parts)
        else:
            if group_path.lower().endswith(('.xlsx', '.xlsm')):
                from core.onduty import read_groups_from_df
                groups = read_groups_from_df(read_table(group_path))
            else:
                groups = read_groups(group_path)
            df = build_onduty_df_from_groups(
                start=start_dt, weeks=weeks,
                groups=groups, jobs=jobs, skip_weekend=skip_weekend,
                offset=offset, skip_names=skip_names,
                shuffle=shuffle, seed=seed,
            )
            parts = [f'分组模式（{len(groups)} 组']
            if skip_names:
                parts.append(f'跳过 {len(skip_names)} 人')
            if offset:
                parts.append(f'起始组偏移 {offset}')
            if shuffle:
                parts.append(f'组内打乱(seed={seed or "每次不同"})')
            parts.append('）')
            return df, ''.join(parts)

    # ---------- 预览 / 生成 ----------
    def refresh_preview(self):
        try:
            df, summary = self._build_dataframe()
        except Exception as e:
            self.preview_tb.setPlainText(f'预览失败：{e!r}')
            return

        n_show = min(5, df.shape[1])
        preview = df.iloc[:, :n_show].to_string()

        counter, n_days = compute_stats(df)
        stat_section = ''
        if counter:
            counts = list(counter.values())
            min_c, max_c = min(counts), max(counts)
            warnings = []
            if min_c == 0:
                warnings.append('有人 0 次值日（检查跳过/步长）')
            if max_c - min_c > 1:
                warnings.append(f'分布不均：最多 {max_c} 次、最少 {min_c} 次')
            # 预期次数 & 偏差
            expected = (n_days * df.shape[0]) / len(counter) if len(counter) else 0
            warn_str = ('  ⚠ ' + '；'.join(warnings)) if warnings else ''
            lines = '\n'.join(
                f'  {name}: {c} 次'
                for name, c in sorted(counter.items(), key=lambda x: -x[1])
            )
            stat_section = (
                f'\n\n值日统计（{len(counter)} 人，'
                f'平均 {expected:.1f} 次/人）{warn_str}\n{lines}')

        self.preview_tb.setPlainText(
            f'{summary}\n'
            f'共 {n_days} 天 × {df.shape[0]} 人/天\n\n'
            f'{preview}{stat_section}'
        )

    def generate(self):
        try:
            df, summary = self._build_dataframe()
        except Exception as e:
            QMessageBox.warning(self, '生成失败', f'{e!r}')
            return

        store = shared_store()
        has_existing = len(store.load_onduty()) > 0
        if not self.overwrite_cb.isChecked() and has_existing:
            ans = QMessageBox.question(
                self, '提示', '已有值日表，是否覆盖？',
                QMessageBox.Yes | QMessageBox.No)
            if ans != QMessageBox.Yes:
                return

        try:
            store.save_onduty(df)
        except Exception as e:
            QMessageBox.warning(self, '写入失败', f'{e!r}')
            return

        QMessageBox.information(
            self, '完成',
            f'{summary}\n已生成 {df.shape[1]} 天值日表')
        self.changed.emit()
        notify_saved(self)

    # ---------- 文件打开 / 编辑器 ----------
    def _open_onduty_csv(self):
        path = FILE_DIR + '未来值日.csv'
        if not os.path.exists(path):
            QMessageBox.information(self, '提示', '未来值日.csv 尚未生成')
            return
        try:
            open_file_external(path)
        except Exception as e:
            QMessageBox.warning(self, '打开失败', f'{e!r}')

    def _open_editor(self):
        from ui.window.table_editor import TableEditor
        from tools.PandasQModel import PandasQItemModel
        store = shared_store()
        try:
            df = store.load_onduty()
            if len(df) == 0:
                QMessageBox.information(self, '提示', '还没有值日表')
                return
            model = PandasQItemModel(data=df)
            editor = TableEditor(
                model, title='直接编辑未来值日',
                savepath=FILE_DIR + '未来值日.csv', extraHeader=True,
                default_simple=False, show_size='6x5',
                on_save=store.save_onduty,
            )
            editor.exec()
        except Exception as e:
            QMessageBox.warning(self, '打开失败', f'{e!r}')
            return
        self.changed.emit()
        notify_saved(self)

    # ---------- 配置 ----------
    def reset(self):
        cfg = load_user_settings()
        self.jobs_enum_le.setText(','.join(cfg['onduty_jobs']))
        self.jobs_le.setText(','.join(cfg['onduty_daily_template']))
        # 高级选项
        self.offset_sb.setValue(0)
        self.stride_sb.setValue(1)
        self.shuffle_cb.setChecked(False)
        self.seed_sb.setValue(0)
        self.skip_te.clear()
        self.refresh_preview()

    def save(self):
        enum = [s.strip() for s in self.jobs_enum_le.text().split(',') if s.strip()]
        tpl = [s.strip() for s in self.jobs_le.text().split(',') if s.strip()]
        if not enum:
            QMessageBox.warning(self, '保存失败', '值日职务枚举不能为空')
            return
        if not tpl:
            QMessageBox.warning(self, '保存失败', '每日值日模板不能为空')
            return

        cfg = load_user_settings()
        cfg['onduty_jobs'] = enum
        cfg['onduty_daily_template'] = tpl
        save_user_settings(cfg)
        self.changed.emit()
        notify_saved(self)



# ============================================================
# Tab 2：名单
# ============================================================
class StudentListWidget(SettingsWidgetBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('学生名单（顺序即值日轮值顺序）'))
        self.listw = QListWidget()
        self.listw.setEditTriggers(QListWidget.DoubleClicked)
        layout.addWidget(self.listw, 1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton('新增')
        self.del_btn = QPushButton('删除选中')
        self.imp_btn = QPushButton('导入 CSV')
        self.reset_btn = QPushButton('重置')
        self.save_btn = QPushButton('保存')
        for b in (self.add_btn, self.del_btn, self.imp_btn,
                  self.reset_btn, self.save_btn):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.add_btn.clicked.connect(self._on_add)
        self.del_btn.clicked.connect(self._on_del)
        self.imp_btn.clicked.connect(self._on_import)
        self.reset_btn.clicked.connect(self._load)
        self.save_btn.clicked.connect(self.save)

    def _load(self):
        try:
            names = shared_store().load_names()['name'].tolist()
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'{e!r}')
            names = []
        self.listw.clear()
        self.listw.addItems([str(n) for n in names if str(n).strip()])

    def _on_add(self):
        it = QListWidgetItem('新学生')
        it.setFlags(it.flags() | Qt.ItemIsEditable)
        self.listw.addItem(it)
        self.listw.setCurrentItem(it)
        self.listw.editItem(it)

    def _on_del(self):
        for it in self.listw.selectedItems():
            self.listw.takeItem(self.listw.row(it))

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '导入名单', FILE_DIR, 'CSV (*.csv)')
        if not path:
            return
        try:
            names = read_names(path)
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'{e!r}')
            return
        ans = QMessageBox.question(
            self, '确认',
            f'将覆盖当前 {self.listw.count()} 条记录，继续？',
            QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        self.listw.clear()
        self.listw.addItems(names)

    def _collect(self) -> list:
        result = []
        for i in range(self.listw.count()):
            s = self.listw.item(i).text().strip()
            if s:
                result.append(s)
        return result

    def reset(self):
        self._load()

    def save(self):
        names = self._collect()
        if not names:
            QMessageBox.warning(self, '保存失败', '名单不能为空')
            return
        dups = [n for n, c in Counter(names).items() if c > 1]
        if dups:
            QMessageBox.warning(self, '保存失败', f'存在重名：{dups}')
            return

        store = shared_store()
        store.save_names(DataFrame({'name': names}))

        if len(store.load_onduty()) > 0:
            QMessageBox.information(
                self, '提示',
                '名单已保存。\n已有的值日表仍按旧名单轮值，'
                '如需重新生成，请到「值日生生成」Tab。')
        self.changed.emit()
        notify_saved(self)

class CourseComboBoxDelegate(QComboBoxDelegate):
    """课程单元格编辑器：可下拉选，也可直接输入非选项。"""
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        editor.setInsertPolicy(QComboBox.NoInsert)
        if editor.lineEdit():
            editor.lineEdit().setPlaceholderText('选择或输入')
        editor.setMinimumHeight(36)
        editor.view().setMinimumWidth(180)
        return editor


# ============================================================
# Tab 3：课程 & 课表
# ============================================================
class CourseEditorWidget(SettingsWidgetBase):
    WEEKDAYS = ['周一', '周二', '周三', '周四', '周五']
    DEFAULT_ROWS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel('课程单（课程名列表，用于下拉候选）'))
        self.course_list = QListWidget()
        self.course_list.setEditTriggers(QListWidget.DoubleClicked)
        layout.addWidget(self.course_list, 1)

        row = QHBoxLayout()
        self.add_course_btn = QPushButton('新增课程')
        self.del_course_btn = QPushButton('删除选中')
        row.addWidget(self.add_course_btn)
        row.addWidget(self.del_course_btn)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(QLabel('周模板课表（双击进入编辑，可拖拽交换）'))
        self.table_view = dragdropQTableView(self)
        layout.addWidget(self.table_view, 2)

        row2 = QHBoxLayout()
        self.add_row_btn = QPushButton('增加一节')
        self.del_row_btn = QPushButton('删除一节')
        self.row_count_l = QLabel()
        self.import_btn = QPushButton('导入课表...')
        row2.addWidget(self.add_row_btn)
        row2.addWidget(self.del_row_btn)
        row2.addWidget(self.import_btn)
        row2.addStretch(1)
        row2.addWidget(self.row_count_l)
        layout.addLayout(row2)

        bottom = QHBoxLayout()
        self.reset_btn = QPushButton('重置')
        self.save_btn = QPushButton('保存')
        bottom.addStretch(1)
        bottom.addWidget(self.reset_btn)
        bottom.addWidget(self.save_btn)
        layout.addLayout(bottom)

        self.add_course_btn.clicked.connect(self._on_add_course)
        self.del_course_btn.clicked.connect(self._on_del_course)
        self.add_row_btn.clicked.connect(self._add_row)
        self.del_row_btn.clicked.connect(self._del_row)
        self.reset_btn.clicked.connect(self._load)
        self.save_btn.clicked.connect(self.save)
        self.import_btn.clicked.connect(self._on_import_classlist)

    # ---------- 课程单 ----------
    def _on_add_course(self):
        it = QListWidgetItem('新课程')
        it.setFlags(it.flags() | Qt.ItemIsEditable)
        self.course_list.addItem(it)
        self.course_list.setCurrentItem(it)
        self.course_list.editItem(it)

    def _on_del_course(self):
        for it in self.course_list.selectedItems():
            self.course_list.takeItem(self.course_list.row(it))

    def _get_courses(self):
        return [self.course_list.item(i).text().strip()
                for i in range(self.course_list.count())
                if self.course_list.item(i).text().strip()]

    WEEKDAY_ALIASES = {
        '周一': ['周一', '星期一', '一', 'mon', 'monday', '周1', '星期1', '1'],
        '周二': ['周二', '星期二', '二', 'tue', 'tuesday', '周2', '星期2', '2'],
        '周三': ['周三', '星期三', '三', 'wed', 'wednesday', '周3', '星期3', '3'],
        '周四': ['周四', '星期四', '四', 'thu', 'thursday', '周4', '星期4', '4'],
        '周五': ['周五', '星期五', '五', 'fri', 'friday', '周5', '星期5', '5'],
    }

    @classmethod
    def _normalize_weekday_columns(cls, df):
        """把任意表格规整为列名 周一~周五、共 5 列。无法识别时返回 None。

        做成类方法是为了让首次启动向导也能复用同一套列名识别规则。
        """
        col_map = {}
        for col in df.columns:
            key = str(col).strip().lower()
            for wd, aliases in cls.WEEKDAY_ALIASES.items():
                if wd in col_map:
                    continue
                if key in [a.lower() for a in aliases]:
                    col_map[wd] = col
                    break
        if len(col_map) == 5:
            out = DataFrame()
            for wd in cls.WEEKDAYS:
                out[wd] = df[col_map[wd]].tolist()
            return out
        if df.shape[1] >= 5:
            out = df.iloc[:, :5].copy()
            out.columns = cls.WEEKDAYS
            return out
        return None

    def _on_import_classlist(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '导入课表', FILE_DIR,
            '表格文件 (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)')
        if not path:
            return

        try:
            if path.lower().endswith('.xlsx'):
                src = pd.read_excel(path)
            elif path.lower().endswith('.xls'):
                QMessageBox.warning(
                    self, '不支持的格式',
                    '旧版 .xls 需要额外组件。\n'
                    '请用 Excel 打开后「另存为」.xlsx 或 .csv 再导入。')
                return
            else:
                src = pd.read_csv(path)
        except ImportError:
            QMessageBox.warning(
                self, '缺少依赖',
                '读取 Excel 需要 openpyxl 组件。\n\n'
                '请在命令行执行：\n'
                '    python -m pip install openpyxl\n\n'
                '或把表格另存为 CSV 后再导入。')
            return
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'{e!r}')
            return

        normalized = self._normalize_weekday_columns(src)
        if normalized is None or len(normalized) == 0:
            QMessageBox.warning(
                self, '导入失败',
                '无法识别课表结构：需要 5 列（周一~周五）或至少 5 列数据')
            return

        n_rows = len(normalized)
        ans = QMessageBox.question(
            self, '确认导入',
            f'将导入 {n_rows} 行课表，覆盖当前编辑内容，继续？',
            QMessageBox.Yes | QMessageBox.No)
        if ans != QMessageBox.Yes:
            return

        # 规整：NaN → '', index 设为 第N节
        normalized.index = [f'第{i + 1}节' for i in range(n_rows)]
        normalized = normalized.where(pd.notna(normalized), None)

        # 询问是否把未知课程加入课程单
        existing = set(self._get_courses())
        new_courses = sorted({
            str(v).strip()
            for v in normalized.values.flatten()
            if pd.notna(v) and str(v).strip() and str(v).strip() not in existing
        })
        if new_courses:
            preview = '、'.join(new_courses[:10]) + ('…' if len(new_courses) > 10 else '')
            ans = QMessageBox.question(
                self, '发现新课程',
                f'课表中出现课程单没有的课程：\n{preview}\n\n是否加入课程单？',
                QMessageBox.Yes | QMessageBox.No)
            if ans == QMessageBox.Yes:
                for c in new_courses:
                    self.course_list.addItem(c)

        # 应用
        self.model = PandasQItemModel(data=normalized)
        self.table_view.setModel(self.model)
        self._apply_touch_view()
        self._refresh_buttons()
        self._resize_later()

        QMessageBox.information(self, '完成',
                                f'已导入 {n_rows} 行课表，请点「保存」写回文件。')

    # ---------- 模型 ----------
    def _make_df(self, n_rows, src=None):
        index = [f'第{i + 1}节' for i in range(n_rows)]
        df = DataFrame(index=index, columns=self.WEEKDAYS)
        if src is not None:
            for i in range(min(n_rows, len(src))):
                for c in range(len(self.WEEKDAYS)):
                    v = src.iat[i, c] if c < src.shape[1] else None
                    df.iat[i, c] = v if pd.notna(v) else None
        return df

    def _apply_touch_view(self):
        tv = self.table_view
        tv.setAcceptDrops(True)
        tv.setDragEnabled(True)
        tv.setDragDropMode(QAbstractItemView.DragDrop)         # ← 问题1
        tv.setDefaultDropAction(Qt.MoveAction)
        tv.setSelectionMode(QAbstractItemView.SingleSelection) # ← 问题1
        tv.setEditTriggers(QAbstractItemView.DoubleClicked)    # ← 问题2
        tv.setTabKeyNavigation(False)

        tv.setTitleFilter(QNoDelegate)
        tv.setContentFilter(CourseComboBoxDelegate)
        tv.setupSelection(content_selections=self._get_courses())

        tv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tv.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def _resize_later(self):
        # 问题3：首开布局未刷新，等下一帧再算一次
        def _do():
            tv = self.table_view
            if tv.model() is not None:
                tv.resizeColumnsToContents()
                tv.resizeRowsToContents()
                tv.viewport().update()
        QTimer.singleShot(0, _do)

    def _refresh_buttons(self):
        n = self.model.rowCount() if self.model else 0
        self.row_count_l.setText(f'当前 {n} 节')

    # ---------- 加载 / 保存 ----------
    def _load(self):
        self.course_list.clear()
        store = shared_store()
        try:
            cdf = store.load_courses()
            if len(cdf.columns):
                self.course_list.addItems(
                    [str(x) for x in cdf.iloc[:, 0] if pd.notna(x)])
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'课程单：{e!r}')

        n_rows = self.DEFAULT_ROWS
        src = None
        try:
            loaded = store.load_classlist()
            if len(loaded.columns):
                src = loaded.reindex(columns=self.WEEKDAYS)
                n_rows = max(1, len(src))
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'课表：{e!r}')
            src = None

        self.model = PandasQItemModel(data=self._make_df(n_rows, src))
        self.table_view.setModel(self.model)
        self._apply_touch_view()
        self._refresh_buttons()
        self._resize_later()

    def _add_row(self):
        if self.model is None:
            return
        n = self.model._df.shape[0]
        new_row = DataFrame([[''] * len(self.WEEKDAYS)],
                            columns=self.WEEKDAYS,
                            index=[f'第{n + 1}节'])
        self.model.concat([new_row])
        self._refresh_buttons()
        self._resize_later()

    def _del_row(self):
        if self.model is None:
            return
        df = self.model._df
        if df.shape[0] <= 1:
            return
        self.model.beginResetModel()
        try:
            self.model._bind_df(df.iloc[:-1])
        finally:
            self.model.endResetModel()
        self._refresh_buttons()
        self._resize_later()

    def reset(self):
        self._load()

    def save(self):
        courses = self._get_courses()
        store = shared_store()
        store.save_courses(DataFrame({'课程': courses}))

        if self.model is None:
            return
        df = self.model._df.reindex(columns=self.WEEKDAYS)
        store.save_classlist(df)

        if store.has_classlist_override(today.date()) and wordday in df.columns:
            ans = QMessageBox.question(
                self, '确认',
                f'今天（{str_date}）已有临时课表，是否按新模板覆盖？',
                QMessageBox.Yes | QMessageBox.No)
            if ans == QMessageBox.Yes:
                store.save_classlist_override(
                    today.date(), [str(v) for v in df[wordday].tolist()])

        self.changed.emit()
        notify_saved(self)

    def _on_add_course(self):
            it = QListWidgetItem('新课程')
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            self.course_list.addItem(it)
            self.course_list.setCurrentItem(it)
            self.course_list.editItem(it)
    
    def _on_del_course(self):
        for it in self.course_list.selectedItems():
            self.course_list.takeItem(self.course_list.row(it))


# ============================================================
# Tab 4/5：外部对话框入口
# ============================================================
class ExternalToolTab(QWidget):
    clicked = Signal()

    def __init__(self, title, desc, btn_text, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        t = QLabel(title)
        t.setStyleSheet('font-size: 16pt; font-weight: bold;')
        t.setAlignment(Qt.AlignCenter)
        layout.addWidget(t)
        d = QLabel(desc)
        d.setAlignment(Qt.AlignCenter)
        layout.addWidget(d)
        btn = QPushButton(btn_text)
        btn.setMinimumWidth(220)
        btn.clicked.connect(self.clicked)
        layout.addWidget(btn, alignment=Qt.AlignCenter)
        layout.addStretch(1)


# ============================================================
# Tab 6：通用
# ============================================================
class GeneralWidget(SettingsWidgetBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QFormLayout(self)

        self.short_le = QLineEdit()
        self.full_le = QLineEdit()
        self.school_le = QLineEdit()
        layout.addRow('班级短名：', self.short_le)
        layout.addRow('班级全名：', self.full_le)
        layout.addRow('学校名称：', self.school_le)

        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton('重置')
        self.save_btn = QPushButton('保存')
        btn_row.addStretch(1)
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.save_btn)
        layout.addRow('', btn_row)

        self.reset_btn.clicked.connect(self._load)
        self.save_btn.clicked.connect(self.save)

        # ---------- 危险操作 ----------
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet('color: #E0E0E0;')
        layout.addRow(line)

        danger_title = QLabel('危险操作')
        danger_title.setStyleSheet(
            'font-size: 12pt; font-weight: bold; color: #C62828;')
        layout.addRow(danger_title)

        danger_desc = QLabel(
            '删除本机保存的班级数据（名单、课表、值日、消息与照片、倒计时、班级名称），'
            '然后重新进入首次使用向导。\n'
            '应用链接与存储方式会保留。\n'
            '删除前会自动备份到数据目录下的 backup\\ 里。')
        danger_desc.setWordWrap(True)
        danger_desc.setStyleSheet('font-size: 10pt; color: #666666;')
        layout.addRow(danger_desc)

        self.console_btn = QPushButton('打开调试控制台（开发用）…')
        self.console_btn.clicked.connect(self._on_open_console)
        layout.addRow('', self.console_btn)

        self.quit_btn = QPushButton('退出程序')
        self.quit_btn.clicked.connect(self._on_quit)
        layout.addRow('', self.quit_btn)

        self.template_btn = QPushButton('下载导入模板（Excel）…')
        self.template_btn.clicked.connect(self._on_template)
        layout.addRow('导入模板', self.template_btn)

        self.rerun_btn = QPushButton('重新运行设置向导（保留现有数据）…')
        self.rerun_btn.clicked.connect(self._on_rerun_wizard)
        layout.addRow('', self.rerun_btn)

        self.wipe_btn = QPushButton('删除全部数据，重新开始首次使用向导…')
        self.wipe_btn.setStyleSheet(
            'background-color: #ffffff; color: #C62828; border: 1px solid #C62828;'
            'border-radius: 6px; padding: 6px 16px; font-size: 11pt;')
        layout.addRow('', self.wipe_btn)
        self.wipe_btn.clicked.connect(self._on_wipe_all)

    def _on_open_console(self):
        """以带控制台的方式重启一份进程，方便看 print 输出。"""
        import subprocess
        import sys

        import config
        main_py = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))), 'main.py')
        try:
            subprocess.Popen(
                ['cmd', '/c', 'start', '班级管理系统（调试）',
                 sys.executable, main_py],
                cwd=os.path.dirname(main_py),
            )
        except Exception as e:                  # noqa: BLE001
            QMessageBox.warning(self, '打开失败', f'{e!r}')
            return
        QMessageBox.information(
            self, '已打开',
            '已在新窗口启动一份带控制台的程序。\n本窗口可以关掉了。')

    def _on_quit(self):
        main = self.parent()
        if hasattr(main, 'quit_app'):
            main.quit_app()
        else:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()

    # ---------- 导入模板 / 重跑向导 ----------
    def _on_template(self):
        default_path = FILE_DIR + '导入模板.xlsx'
        path, _ = QFileDialog.getSaveFileName(
            self, '保存导入模板', default_path, 'Excel (*.xlsx)')
        if not path:
            return
        try:
            write_template(path)
        except Exception as e:                  # noqa: BLE001
            QMessageBox.warning(self, '保存失败', f'{e!r}')
            return
        try:
            open_file_external(path)
        except Exception:                       # noqa: BLE001
            pass

    def _ask_keep(self):
        """勾选这次要**保留**的内容；没勾的会以空白形式进入向导。"""
        dlg = QDialog(self)
        dlg.setWindowTitle('重新运行设置向导')
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel('勾选要保留的现有内容；没勾的部分会在向导里清空重填。\n'
                             '开始前仍会自动备份。'))
        boxes = {}
        for key, text in (
            ('info', '班级信息（校名、班级名）'),
            ('roster', '学生名单'),
            ('classlist', '课程表'),
            ('schedule', '作息时间'),
        ):
            cb = QCheckBox(text)
            cb.setChecked(True)
            lay.addWidget(cb)
            boxes[key] = cb
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if not dlg.exec():
            return None
        return {k for k, cb in boxes.items() if cb.isChecked()}

    def _on_rerun_wizard(self):
        keep = self._ask_keep()
        if keep is None:
            return
        try:
            backup = bootstrap.backup_all()
        except Exception as e:                  # noqa: BLE001
            QMessageBox.critical(self, '备份失败', f'{e}')
            return
        from ui.window.setup_wizard import SetupWizard
        wizard = SetupWizard(self, prefill=True, keep=keep)
        if not wizard.exec():
            return
        parent = self.parent()
        if hasattr(parent, 'reload_data'):
            parent.reload_data()
        QMessageBox.information(
            self, '已完成', f'设置已更新。\n备份：{backup}')

    # ---------- 危险操作：三重确认 ----------
    def _on_wipe_all(self):
        cfg = load_user_settings()
        short_name = cfg.get('class_short_name', '')

        # 第 1 重：说清楚删什么、留什么
        ans = QMessageBox.question(
            self, '删除全部数据',
            '将删除的内容：\n'
            '    · 学生名单、课程表、值日表\n'
            '    · 消息正文与班级照片\n'
            '    · 倒计时、班级名称等设置\n\n'
            '会保留：应用链接（这台电脑的配置）与存储方式。\n'
            '会先自动备份到数据目录的 backup\\ 下。\n\n'
            '删除完成后程序会退出，需要你手动重新打开，才会进入首次使用向导。\n\n'
            '确定继续吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return

        # 第 2 重：手打班级短名
        text, ok = QInputDialog.getText(
            self, '确认删除',
            f'请输入当前班级短名以确认：\n（{short_name}）')
        if not ok:
            return
        if text.strip() != short_name:
            QMessageBox.warning(self, '已取消', '输入的班级短名不匹配，未做任何改动。')
            return

        # 第 3 重：最终确认
        ans = QMessageBox.question(
            self, '最后确认',
            '这是最后一次确认。\n\n'
            '删除后程序会立即退出，你需要手动重新打开，'
            '然后会进入「首次使用设置」向导。\n\n'
            '确定要删除全部数据吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return

        try:
            backup = bootstrap.backup_all()
            bootstrap.reset_all(keep_messages=False)
        except Exception as e:
            QMessageBox.critical(self, '删除失败', f'{e}')
            return

        QMessageBox.information(
            self, '已完成',
            f'数据已清空，备份保存在：\n{backup}\n\n'
            '请手动重新打开程序，届时会进入首次使用设置向导。')

        main = self.parent()
        if main is not None and hasattr(main, 'quit_app'):
            main.quit_app()                     # 走真正的退出，不被 closeEvent 拦成最小化
            return
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _load(self):
        cfg = load_user_settings()
        self.short_le.setText(cfg['class_short_name'])
        self.full_le.setText(cfg['class_full_name'])
        self.school_le.setText(cfg['school_name'])

    def reset(self):
        self._load()

    def save(self):
        # read-modify-write，避免覆盖其它 Tab 的字段（countdowns / onduty_* 等）
        cfg = load_user_settings()
        cfg['class_short_name'] = self.short_le.text().strip()
        cfg['class_full_name'] = self.full_le.text().strip()
        cfg['school_name'] = self.school_le.text().strip()
        save_user_settings(cfg)
        self.changed.emit()
        notify_saved(self)



# ============================================================
# Tab 7：倒计时编辑
# ============================================================
def notify_saved(widget, text: str = '已保存'):
    """沿父链找到设置窗口，在底部闪一条「已保存」。"""
    node = widget
    for _ in range(8):
        if node is None:
            break
        if hasattr(node, 'show_saved'):
            node.show_saved(text)
            return
        node = node.parent()


class AppLinkWidget(SettingsWidgetBase):
    """应用链接：直接在这里增删改，保存后主界面图标刷新。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('主界面右下角显示的应用图标；名称可用中文，'
                                '路径支持 .exe / .lnk / 文件夹。'))

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['名称', '路径'])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton('添加应用…')
        self.add_btn.clicked.connect(self._on_add)
        self.del_btn = QPushButton('删除选中')
        self.del_btn.clicked.connect(self._on_delete)
        self.up_btn = QPushButton('上移')
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = QPushButton('下移')
        self.down_btn.clicked.connect(lambda: self._move(1))
        for b in (self.add_btn, self.del_btn, self.up_btn, self.down_btn):
            b.setMinimumHeight(36)
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        self.save_btn = QPushButton('保存')
        self.save_btn.setMinimumHeight(36)
        self.save_btn.clicked.connect(self.save)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self._load()

    # ---------- 数据 ----------
    def _load(self):
        try:
            df = shared_store().load_apps()
        except Exception as e:                  # noqa: BLE001
            print(f'[apps] 读取失败: {e!r}')
            return
        self.table.setRowCount(0)
        for _, row in df.iterrows():
            self._append_row(str(row.iloc[0]), str(row.iloc[1]))

    def _append_row(self, name: str, path: str):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(name))
        self.table.setItem(r, 1, QTableWidgetItem(path))

    def _on_add(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, '选择应用', '', '程序 (*.exe *.lnk *.bat);;所有文件 (*)')
        if not paths:
            return
        for path in paths:
            name = os.path.splitext(os.path.basename(path))[0]
            self._append_row(name, path)

    def _on_delete(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()},
                      reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def _move(self, delta: int):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if len(rows) != 1:
            return
        r = rows[0]
        target = r + delta
        if not (0 <= target < self.table.rowCount()):
            return
        values = [self.table.item(r, c).text() if self.table.item(r, c) else ''
                  for c in range(2)]
        self.table.removeRow(r)
        self.table.insertRow(target)
        for c, v in enumerate(values):
            self.table.setItem(target, c, QTableWidgetItem(v))
        self.table.selectRow(target)

    def reset(self):
        self._load()

    def save(self):
        rows = []
        for r in range(self.table.rowCount()):
            name = self.table.item(r, 0).text().strip() if self.table.item(r, 0) else ''
            path = self.table.item(r, 1).text().strip() if self.table.item(r, 1) else ''
            if name and path:
                rows.append((name, path))

        from pandas import DataFrame
        from data.store import APPS_COLUMNS

        shared_store().save_apps(DataFrame(rows, columns=APPS_COLUMNS))
        self.changed.emit()
        notify_saved(self)

        node = self
        for _ in range(8):
            node = node.parent() if node is not None else None
            if node is None:
                break
            if hasattr(node, 'refresh_apps'):
                node.refresh_apps()
                break


class ScheduleWidget(SettingsWidgetBase):
    """作息时间：五个工作日各自可调，与向导共用 ScheduleEditor。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        from ui.component.schedule_editor import ScheduleEditor

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('每节课的起止时间；表头切换星期，五天可不同。'))
        self.editor = ScheduleEditor()
        layout.addWidget(self.editor, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.save_btn = QPushButton('保存')
        self.save_btn.setMinimumHeight(36)
        self.save_btn.clicked.connect(self.save)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)
        self._load()

    def _load(self):
        try:
            store = shared_store()
            self.editor.set_times(store.load_lesson_times())
            # 节数跟课程表对齐
            rows = len(store.load_classlist())
            if rows > 0:
                self.editor.set_row_count(rows)
        except Exception as e:                  # noqa: BLE001
            print(f'[settings] 读取作息失败: {e!r}')

    def reset(self):
        self._load()

    def save(self):
        shared_store().save_lesson_times(self.editor.collect())
        self.changed.emit()
        notify_saved(self)


class CountdownWidget(SettingsWidgetBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('倒计时列表（显示在主界面左侧栏，顺序即显示顺序）'))

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['名称', '日期 (YYYY-MM-DD)'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.add_btn = QPushButton('新增')
        self.del_btn = QPushButton('删除选中')
        self.up_btn = QPushButton('上移')
        self.down_btn = QPushButton('下移')
        for b in (self.add_btn, self.del_btn, self.up_btn, self.down_btn):
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)

        bottom = QHBoxLayout()
        self.reset_btn = QPushButton('重置')
        self.save_btn = QPushButton('保存')
        bottom.addStretch(1)
        bottom.addWidget(self.reset_btn)
        bottom.addWidget(self.save_btn)
        layout.addLayout(bottom)

        self.add_btn.clicked.connect(self._on_add)
        self.del_btn.clicked.connect(self._on_del)
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.reset_btn.clicked.connect(self._load)
        self.save_btn.clicked.connect(self.save)

    MAX_COUNTDOWNS = 3

    def _on_add(self):
        if self.table.rowCount() >= self.MAX_COUNTDOWNS:
            QMessageBox.information(
                self, '提示', f'最多只能有 {self.MAX_COUNTDOWNS} 个倒计时')
            return
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem('新倒计时'))
        self.table.setItem(r, 1, QTableWidgetItem(datetime.now().strftime('%Y-%m-%d')))

    def _on_del(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    def _move(self, delta: int):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if len(rows) != 1:
            return
        r = rows[0]
        target = r + delta
        if not (0 <= target < self.table.rowCount()):
            return
        values = [self.table.item(r, c).text() if self.table.item(r, c) else ''
                  for c in range(2)]
        self.table.removeRow(r)
        self.table.insertRow(target)
        for c, v in enumerate(values):
            self.table.setItem(target, c, QTableWidgetItem(v))
        self.table.selectRow(target)

    def _load(self):
        cfg = load_user_settings()
        data = cfg.get('countdowns') or []
        self.table.setRowCount(0)
        for cd in data:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(cd.get('label', '')))
            self.table.setItem(r, 1, QTableWidgetItem(cd.get('date', '')))

    def reset(self):
        self._load()

    def save(self):
        items = []
        for r in range(self.table.rowCount()):
            li = self.table.item(r, 0)
            di = self.table.item(r, 1)
            label = li.text().strip() if li else ''
            date = di.text().strip() if di else ''
            if not label or not date:
                continue
            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                QMessageBox.warning(
                    self, '保存失败',
                    f'第 {r + 1} 行日期格式错误："{date}"，应为 YYYY-MM-DD')
                return
            items.append({'label': label, 'date': date})

        cfg = load_user_settings()
        cfg['countdowns'] = items
        save_user_settings(cfg)
        self.changed.emit()
        notify_saved(self)



# ============================================================
# 设置对话框
# ============================================================
class SettingsDialog(QDialog):
    changed = Signal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('设置')

        # 按屏幕尺寸自适应（原来固定 760x640 会溢出）
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.resize(min(int(avail.width() * 0.9), 1400),
                        min(int(avail.height() * 0.88), 950))
        else:
            self.resize(880, 720)

        self._dirty = set()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        # Tab 条放底部：内容区更靠上，点起来也离手更近（HANDOFF §7.6）
        self.tabs.setTabPosition(QTabWidget.South)
        layout.addWidget(self.tabs, 1)

        self.onduty_widget = OndutySpawnWidget(self)
        self.onduty_widget.changed.connect(lambda: self._dirty.add('onduty'))
        self.tabs.addTab(self._wrap_scroll(self.onduty_widget), '值日生生成')

        self.stu_widget = StudentListWidget(self)
        self.stu_widget.changed.connect(lambda: self._dirty.add('stu'))
        self.tabs.addTab(self._wrap_scroll(self.stu_widget), '名单')

        self.course_widget = CourseEditorWidget(self)
        self.course_widget.changed.connect(lambda: self._dirty.add('classlist'))
        self.tabs.addTab(self._wrap_scroll(self.course_widget), '课程')

        self.countdown_widget = CountdownWidget(self)
        self.countdown_widget.changed.connect(
            lambda: self._dirty.add('countdown'))
        self.schedule_widget = ScheduleWidget(self)
        self.schedule_widget.changed.connect(lambda: self._dirty.add('schedule'))
        self.tabs.addTab(self._wrap_scroll(self.schedule_widget), '作息')

        self.tabs.addTab(self._wrap_scroll(self.countdown_widget), '倒计时')

        self.app_widget = AppLinkWidget(self)
        self.app_widget.changed.connect(lambda: self._dirty.add('apps'))
        self.tabs.addTab(self._wrap_scroll(self.app_widget), '应用链接')

        self.message_tab = ExternalToolTab(
            '消息管理', '通过独立对话框管理（保存后主页消息会自动刷新）',
            '打开消息编辑...', parent=self)
        self.message_tab.clicked.connect(self._open_message)
        self.tabs.addTab(self._wrap_scroll(self.message_tab), '消息')

        self.general_widget = GeneralWidget(self)
        self.general_widget.changed.connect(lambda: self._dirty.add('general'))
        self.tabs.addTab(self._wrap_scroll(self.general_widget), '通用')

        bottom = QHBoxLayout()
        self.saved_l = QLabel('')
        self.saved_l.setStyleSheet('color: @primary; font-size: 12pt;')
        bottom.addWidget(self.saved_l)
        bottom.addStretch(1)
        self.close_btn = QPushButton('关闭')
        self.close_btn.clicked.connect(self.accept)
        bottom.addWidget(self.close_btn)
        layout.addLayout(bottom)

    def show_saved(self, text: str = '已保存'):
        """底部闪一条提示，2 秒后自动消失。"""
        from PySide6.QtCore import QTimer

        self.saved_l.setText(f'✓ {text}')
        QTimer.singleShot(2000, lambda: self.saved_l.setText(''))

    def _wrap_scroll(self, widget, min_width=0):
        """把任意 QWidget 包成带滚动条的 Tab 内容。"""
        sa = QScrollArea()
        sa.setWidgetResizable(True)          # ← 关键：内容宽度跟随窗口
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sa.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sa.setWidget(widget)
        enable_touch_scroll(sa)
        if min_width:
            sa.setMinimumWidth(min_width)
        return sa

    def _open_addapp(self):
        p = self.parent()
        if p is not None and hasattr(p, 'openWn_AddApp'):
            p.openWn_AddApp()

    def _open_message(self):
        p = self.parent()
        if p is not None and hasattr(p, 'openWn_Message'):
            p.openWn_Message()

    def accept(self):
        if self._dirty:
            self.changed.emit(set(self._dirty))
            self._dirty.clear()
        super().accept()