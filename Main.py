import os
import sys
import json
from datetime import datetime
from functools import partial

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMessageBox, QDialog, QMenu, QLabel,
)
from PyQt5.QtCore import QTimer, QModelIndex, Qt
from PyQt5.QtGui import QPixmap, QIcon
from numpy import where

from windows.wn_Main import Ui_MainWindow as wn_Main
from windows.dropableTableView import QDateEditDelegate, OndutyContentDelegate

from Addapp import AddApp, LoadApp
import bootstrap
from Dialogs import wn_random
from Message import wn_Message
from SetupWizard import SetupWizard
from TableEditor import TableEditor
from UserSettings import SettingsDialog
from loading import loadPool, wait_all

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
        setQss(QSS_DIR + 'tableview.qss', self.classlist_tv)
        setQss(QSS_DIR + 'applink.qss', self.applink_tv)
        setQss(QSS_DIR + 'sidebar.qss', self.sidebar_wg)

        # Logo
        logo = QPixmap(RESOURCE_DIR + 'logo.png')
        self.icon_l.setPixmap(logo)

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

        # 数据加载
        self.data = loadPool(parent=self, widget=self)

    def updateClock(self):
        time_str = datetime.now().strftime('%Y年\n%m月%d日\n%H:%M:%S\n' + wordday)
        self.time_l.setText(time_str)
        self._update_countdowns()

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
            fixed = w is self.setting_pb or w is self.icon_l
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
        menu.exec_(self.applink_tv.viewport().mapToGlobal(pos))

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
        dlg.exec_()

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
                    savepath=classlist_path,
                    show_size=show_size, default_simple=True,
                    row_ops=True)                       # ← 允许加/删行
            else:
                self.wn_classlist = TableEditor(
                    self.data['model_classlist_today'],
                    filter=self.data['classes'], title='调整课表',
                    savepath=classlist_path,
                    default_simple=True, show_size=show_size,
                    row_ops=True)                       # ← 允许加/删行
            self.wn_classlist.exec_()
            self.data.classlist_chain.play(self)

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
                savepath=FILE_DIR + '未来值日.csv',
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
                savepath=FILE_DIR + '未来值日.csv',
                title_filter=QDateEditDelegate,
                content_filter=content_delegate,
                simple_show=5, default_simple=True, show_size='6x5',
                col_min_width=220,
                on_save=_save_onduty_from_editor)

        self.wn_Onduty.exec_()
        self.data.onduty_chain.load()
        self.data.onduty_chain.process()
        self.data.onduty_chain.play(self)
    def openWn_AddApp(self, urls=None):
        self.wn_AddApp = AddApp(self, urls=urls)
        if self.wn_AddApp.exec_() == QDialog.Accepted:
            self.data.load(self.data.app_chain)
            wait_all(self.data)

    def openWn_Message(self):
        self.wn_Message = wn_Message(self)
        self.wn_Message.exec_()
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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(RESOURCE_DIR + 'icon.png'))
    setQss(QSS_DIR + 'mainpage.qss', app)

    # 首次使用：先确认数据是否就绪，再创建主窗口。
    # 顺序很重要 —— 不能让向导卡在 Main.__init__ 里面（那样主窗口还没出来
    # 就先弹窗，用户会以为程序挂了）。
    if not bootstrap.is_initialized():
        if bootstrap.infer_legacy_state():
            # 老用户：已有名单和真实课表，静默补标记，不打扰
            bootstrap.mark_initialized(note='老用户推断')
        else:
            if not SetupWizard.run():
                sys.exit(0)

    mainwindow = Main()
    mainwindow.showMaximized()
    app.exec_()