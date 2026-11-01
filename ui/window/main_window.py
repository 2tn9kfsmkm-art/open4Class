import os
import sys
import json
from datetime import datetime
from functools import partial

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMessageBox, QDialog, QMenu, QLabel,
    QPushButton,
)
from PySide6.QtCore import QEvent, QModelIndex, QTimer, Qt
from PySide6.QtGui import QPixmap, QIcon
from numpy import where

from windows.wn_Main import Ui_MainWindow as wn_Main
from ui.component.dropable_table import (
    ClickToClearFilter, QDateEditDelegate, OndutyContentDelegate,
)

from ui.window.add_app_dialog import AddApp, LoadApp
import bootstrap
from ui.component.dialogs import wn_random
from ui.window.message_editor import wn_Message
from ui.window.setup_wizard import SetupWizard
from ui.window.table_editor import TableEditor
from ui.component.tray import TrayIcon
from ui.window.mini_window import MiniController
from ui.window.settings_window import SettingsDialog
from services.loading import loadPool, wait_all

from tools.PandasQModel import PandasQItemModel, q_read_csv
from tools.qss2qt import setQss
from config import *
from config import load_user_settings, get_onduty_jobs
from data.store import shared_store


def ensure_data_json():
    path = FILE_DIR + 'data.json'
    if not os.path.exists(path):
        with open(path, 'w', encoding=ENCODING) as f:
            json.dump({'last_login': datetime.today().strftime('%Y%m%d')}, f)


def _save_today_classlist(df):
    """把"今日课表"的编辑结果写成当天的临时课表（覆盖周模板）。"""
    try:
        if df.shape[1] == 0:
            return
        courses = [str(v) for v in df.iloc[:, 0].tolist()]
        shared_store().save_classlist_override(today.date(), courses)
    except Exception as e:                      # noqa: BLE001
        print(f'[classlist] 保存临时课表失败: {e!r}')


def _save_onduty_from_editor(df):
    """值日编辑器保存后把结果写回当前存储（SQLite 模式必需，CSV 模式重复写一次无妨）。"""
    try:
        shared_store().save_onduty(df)
    except Exception as e:                      # noqa: BLE001
        print(f'[onduty] 同步到存储失败: {e!r}')


class Main(wn_Main, QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_data_json()

        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)
        self.setupUi(centralWidget)

        
        cfg = load_user_settings()
        self.setWindowTitle(f'{cfg["class_short_name"]}  班级管理系统')
        self.title_l.setText(f'{cfg["school_name"]} {cfg["class_full_name"]}')

        # 样式
        setQss(QSS_DIR + 'title.qss', self.title_l)
        setQss(QSS_DIR + 'tableview.qss', self.onduty_tv)
        # 课表行数多（10~12 行），单元格上下内边距比其他表格再收一点，
        # 免得出现纵向滚动条
        setQss(QSS_DIR + 'tableview.qss', self.classlist_tv,
               extra='QTableView::item { padding: 6px 5px; }')
        setQss(QSS_DIR + 'applink.qss', self.applink_tv)
        setQss(QSS_DIR + 'sidebar.qss', self.sidebar_wg)

        # Logo
        logo = QPixmap(RESOURCE_DIR + 'logo.png')
        self.icon_l.setPixmap(logo)

        # 侧栏最小化按钮：倒计时下方、设置入口上方
        self.mini_pb = QPushButton('最小化')
        self.mini_pb.setMinimumHeight(44)          # 触摸目标
        self.mini_pb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_pb.clicked.connect(self.showMinimized)
        _idx = self.verticalLayout.indexOf(self.setting_pb)
        self.verticalLayout.insertWidget(_idx, self.mini_pb)

        # 倒计时
        self._countdown_labels = []
        self._render_countdowns()

        # 时钟
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateClock)
        self.timer.start(1000)
        self.updateClock()

        # 信号连接（只连接一次，避免 play 重复连接）
        self.onduty_tv.activated.connect(self.openWn_Onduty)
        self.classlist_tv.activated.connect(self.openWn_classlist)
        self.applink_tv.clicked.connect(self.open_app)
        self.applink_tv.setContextMenuPolicy(Qt.CustomContextMenu)
        self.applink_tv.customContextMenuRequested.connect(self._on_app_context_menu)
        self.random_pb.clicked.connect(self.openWn_random)
        self.message_tb.mouseDoubleClickEvent = self._on_message_double_click
        self.icon_l.clicked.connect(self.open_settings)

        # 点表格空白处清除选中（Qt 默认不清，选中框会一直留着）
        self._clear_filter = ClickToClearFilter(self)
        for _tv in (self.onduty_tv, self.classlist_tv):
            _tv.viewport().installEventFilter(self._clear_filter)

        # 数据加载
        self.data = loadPool(parent=self, widget=self)

        # 系统托盘（希沃上可能不可用，可用才建）
        self.tray = None
        if TrayIcon.available():
            self.tray = TrayIcon(
                RESOURCE_DIR + 'icon.png',
                on_show_main=self._restore_from_mini,
                on_show_mini=lambda: self.mini.show_panel(),
                on_quit=self.close,
                parent=self,
            )
            self.tray.show()

        # 三层窗口：主窗口 --最小化--> 悬浮窗 --20 秒--> 右下角小方块
        self.mini = MiniController(
            courses_provider=self._today_courses,
            countdowns_provider=lambda: load_user_settings().get('countdowns'),
            lesson_times_provider=lambda: load_user_settings().get('lesson_times'),
            on_back=self._restore_from_mini,
        )

    # ---------- 悬浮窗数据 ----------
    def _today_courses(self) -> list:
        try:
            df = self.data['model_classlist_today']._df
            return [str(v) for v in df.iloc[:, 0].tolist()]
        except Exception:                       # noqa: BLE001
            return []

    def _restore_from_mini(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---------- 最小化 / 恢复 ----------
    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        mini = getattr(self, 'mini', None)
        if mini is None:
            return
        if self.isMinimized():
            # 用 singleShot 让窗口状态先落定，再摆悬浮窗
            QTimer.singleShot(0, mini.show_panel)
        elif mini.is_visible():
            mini.hide_all()

    def closeEvent(self, event):
        mini = getattr(self, 'mini', None)
        if mini is not None:
            mini.hide_all()
        tray = getattr(self, 'tray', None)
        if tray is not None:
            tray.hide()
        super().closeEvent(event)

    def updateClock(self):
        time_str = datetime.now().strftime('%Y年\n%m月%d日\n%H:%M:%S\n' + wordday)
        self.time_l.setText(time_str)
        self._update_countdowns()
        mini = getattr(self, 'mini', None)
        if mini is not None and mini.is_visible():
            mini.refresh()

    def _render_countdowns(self):
        """按 settings.json 的 countdowns 重建左侧栏倒计时标签。"""
        layout = self.verticalLayout

        # 清理旧标签（首次运行时的硬编码两个 + 之前渲染过的）
        for attr in ('countdown_l', 'nextclass_l'):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                layout.removeWidget(lbl)
                lbl.deleteLater()
                setattr(self, attr, None)
        for lbl in self._countdown_labels:
            layout.removeWidget(lbl)
            lbl.deleteLater()
        self._countdown_labels = []

        cfg = load_user_settings()
        countdowns = cfg.get('countdowns') or DEFAULT_COUNTDOWNS

        idx_time = layout.indexOf(self.time_l)
        insert_at = idx_time + 1
        for _ in countdowns:
            lbl = QLabel(self.sidebar_wg)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMinimumSize(100, 180)
            layout.insertWidget(insert_at, lbl)
            self._countdown_labels.append(lbl)
            insert_at += 1

        # 重置拉伸：时间 / 倒计时等比，底部设置区（按钮 + logo）固定高度
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            fixed = w in (self.setting_pb, self.icon_l, self.mini_pb)
            layout.setStretch(i, 0 if fixed else 1)

        self._update_countdowns()

    def _update_countdowns(self):
        if not self._countdown_labels:
            return
        now = datetime.now()
        cfg = load_user_settings()
        countdowns = cfg.get('countdowns') or DEFAULT_COUNTDOWNS
        for lbl, cd in zip(self._countdown_labels, countdowns):
            label = cd.get('label', '目标')
            date_str = cd.get('date', '')
            try:
                target = datetime.strptime(date_str, '%Y-%m-%d')
                days = (target - now).days + 1
                lbl.setText(
                    f'<p><span style="font-size:20pt;font-weight:bold;">'
                    f'距离{label}还有 </span></p>'
                    f'<p><span style="font-size:40pt;font-weight:bold;">{days}</span>'
                    f'<span style="font-size:20pt;font-weight:bold;"> 天</span></p>'
                )
            except Exception:
                lbl.setText(f'<p>{label}</p><p>{date_str}</p>')

    def _on_message_double_click(self, event):
        self.openWn_Message()

    def _on_app_context_menu(self, pos):
        index = self.applink_tv.indexAt(pos)
        if not index.isValid():
            return
        appname = index.data()
        # 空单元格 / 右下角的“添加”按钮不弹菜单
        if not appname or appname == '...':
            return

        menu = QMenu(self)
        act_del = menu.addAction(f'删除 "{appname}"')
        act_del.triggered.connect(partial(self._delete_app, appname))
        menu.exec(self.applink_tv.viewport().mapToGlobal(pos))

    def _delete_app(self, appname):
        ans = QMessageBox.question(
            self, '确认删除',
            f'确定要删除应用 "{appname}" 吗？',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return

        chain = self.data.app_chain
        if not chain.delete(appname):
            QMessageBox.warning(self, '提示', f'删除 "{appname}" 失败，请检查 CSV 是否被占用')
            return

        # 同步刷新界面
        chain.play(self)
        # open_app 读的是 self.data['applications']，需要同步
        self.data.results['applications'] = chain.applications

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.changed.connect(self._on_settings_changed)
        dlg.exec()

    def _on_settings_changed(self, keys: set):
        for k in keys:
            fn = {
                'general':   self._reload_general,
                'stu':       self._reload_stu,
                'classlist': self._reload_classlist,
                'onduty':    self._reload_onduty,
                'countdown': self._render_countdowns,   # 新增
            }.get(k)
            if fn:
                fn()

    def _reload_general(self):
        cfg = load_user_settings()
        self.setWindowTitle(f'{cfg["class_short_name"]}  班级管理系统')
        self.title_l.setText(f'{cfg["school_name"]} {cfg["class_full_name"]}')

    def _reload_stu(self):
        self.data.stu_chain.load()
        self.data.stu_chain.process()

    def _reload_classlist(self):
        self.data.classlist_chain.load()
        self.data.classlist_chain.process()
        self.data.classlist_chain.play(self)

    def _reload_onduty(self):
        self.data.onduty_chain.load()
        self.data.onduty_chain.process()
        self.data.onduty_chain.play(self)


    def openWn_random(self):
        names = self.data['stu_model']._df['name'].tolist()
        self.wn_random = wn_random(data=names)
        self.wn_random.show()

    def openWn_classlist(self, lesson: QModelIndex|None = None):
        if lesson is not None:
            data = lesson.data()
            self.onduty_tv.clearSelection()
            selected_index = list(zip(*where(
                self.data['model_classlist_today']._df == data)))

            # 按实际行数决定窗口大小（+1 为表头行）
            n_rows = self.data['model_classlist_today']._df.shape[0]
            show_size = f'{max(n_rows + 1, 2)}x5'

            if len(selected_index):
                self.wn_classlist = TableEditor(
                    self.data['model_classlist_today'],
                    selected_index=selected_index,
                    filter=self.data['classes'], title='调整课表',
                    savepath='',
                    on_save=_save_today_classlist,
                    show_size=show_size, default_simple=True,
                    row_ops=True)                       # ← 允许加/删行
            else:
                self.wn_classlist = TableEditor(
                    self.data['model_classlist_today'],
                    filter=self.data['classes'], title='调整课表',
                    savepath='',
                    on_save=_save_today_classlist,
                    default_simple=True, show_size=show_size,
                    row_ops=True)                       # ← 允许加/删行
            self.wn_classlist.exec()
            self.data.classlist_chain.play(self)
            self.classlist_tv.clearSelection()
            self.classlist_tv.setCurrentIndex(QModelIndex())

    def openWn_Onduty(self, stu: QModelIndex|None = None):
        if stu is None:
            return
        data = stu.data()
        self.onduty_tv.clearSelection()

        content_delegate = lambda names: OndutyContentDelegate(names, get_onduty_jobs())

        if data == '暂无值日信息':
            self.wn_Onduty = TableEditor(
                self.data['onduty_model'],
                filter=self.data['stu_model']['name'], title='调整值日',
                savepath='',
                title_filter=QDateEditDelegate,
                content_filter=content_delegate,
                simple_show=5, default_simple=True, show_size='6x5',
                col_min_width=220,
                on_save=_save_onduty_from_editor)
        else:
            today_df = self.data['model_onduty_today']._df
            rows = today_df.index[today_df.iloc[:, 0] == data]

            onduty_df = self.data['onduty_model']._df
            if str_date in onduty_df.columns:
                col = int(onduty_df.columns.get_loc(str_date))
            else:
                col = 0

            if len(rows) and col < 5:
                selected_index = [(int(r), col) for r in rows]
            else:
                selected_index = None

            self.wn_Onduty = TableEditor(
                self.data['onduty_model'],
                selected_index=selected_index,
                filter=self.data['stu_model']['name'], title='调整值日',
                savepath='',
                title_filter=QDateEditDelegate,
                content_filter=content_delegate,
                simple_show=5, default_simple=True, show_size='6x5',
                col_min_width=220,
                on_save=_save_onduty_from_editor)

        self.wn_Onduty.exec()
        self.data.onduty_chain.load()
        self.data.onduty_chain.process()
        self.data.onduty_chain.play(self)
        # 编辑完清掉选中框，避免看起来"卡在某一格"
        self.onduty_tv.clearSelection()
        self.onduty_tv.setCurrentIndex(QModelIndex())
    def openWn_AddApp(self, urls=None):
        self.wn_AddApp = AddApp(self, urls=urls)
        if self.wn_AddApp.exec() == QDialog.Accepted:
            self.data.load(self.data.app_chain)
            wait_all(self.data)

    def openWn_Message(self):
        self.wn_Message = wn_Message(self)
        self.wn_Message.exec()
        self.data.load(self.data.message_chain)
        wait_all(self.data)

    def open_app(self, appIndex: QModelIndex):
        appname = appIndex.data()
        if not appname:
            return
        if appname == '...':
            self.applink_tv.clearSelection()
            self.openWn_AddApp()
            return

        self.applink_tv.clearSelection()
        apps = self.data['applications']._df
        matches = apps[apps['软件链接'] == appname]
        if matches.empty:
            QMessageBox.warning(self, '提示', f'未找到应用 "{appname}"')
            return

        app_path = matches['path'].to_list()[0]
        appthread = LoadApp(self, app_path)
        appthread.start()
        self.showMinimized()
