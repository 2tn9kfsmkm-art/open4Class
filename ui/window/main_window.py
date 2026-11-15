import os
import sys
import json
from datetime import datetime
from functools import partial

from PySide6.QtWidgets import (
    QSizePolicy,
    QApplication, QMainWindow, QWidget, QMessageBox, QDialog, QMenu, QLabel,
    QHeaderView, QPushButton,
)
from PySide6.QtCore import QEvent, QModelIndex, QPoint, QTimer, Qt
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
from ui.tokens import COLORS
from services.diag import log
from ui.component.touch import enable_touch_scroll
from ui.component.winutil import (
    force_foreground, foreground_covers_screen, is_shell_foreground,
)
from ui.window.mini_window import MiniController
from ui.window.settings_window import SettingsDialog
from services.loading import loadPool, wait_all

from tools.PandasQModel import PandasQItemModel, q_read_csv
from tools.qss2qt import setQss
from config import *
from config import load_user_settings, get_onduty_jobs, school_logo_path
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
        # 课表列宽按内容：字体放大时不再被省略号截断
        self.classlist_tv.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        setQss(QSS_DIR + 'applink.qss', self.applink_tv)
        setQss(QSS_DIR + 'sidebar.qss', self.sidebar_wg)

        # Logo：记住原图，显示时按侧栏宽度等比拉伸
        self._logo_source = QPixmap(school_logo_path())
        self._fit_logo()

        # 侧栏最小宽度跟着字体走：300% 缩放下 24pt 的日期需要更宽的栏
        _fm = self.time_l.fontMetrics()
        self.sidebar_wg.setMinimumWidth(max(
            260,
            max(_fm.horizontalAdvance('2026年'),
                _fm.horizontalAdvance('周三')) + 60))

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
        self.icon_l.clicked.connect(self.open_start_menu)

        # 点表格空白处清除选中（Qt 默认不清，选中框会一直留着）
        self._clear_filter = ClickToClearFilter(self)
        for _tv in (self.onduty_tv, self.classlist_tv):
            _tv.viewport().installEventFilter(self._clear_filter)

        log('app', 'main window ready')

        # 数据加载
        for _tv in (self.classlist_tv, self.onduty_tv, self.applink_tv):
            enable_touch_scroll(_tv)

        self.data = loadPool(parent=self, widget=self)

        # 系统托盘（希沃上可能不可用，可用才建）
        self.tray = None
        if TrayIcon.available():
            self.tray = TrayIcon(
                RESOURCE_DIR + 'icon.png',
                on_show_main=self._restore_from_mini,
                on_show_mini=lambda: self.mini.show_all(),
                on_quit=self.quit_app,
                parent=self,
            )
            self.tray.show()

        # 悬浮层随前台状态自动出现/消失（每 0.4 秒判断一次）
        self._mini_poll = QTimer(self)
        self._mini_poll.setInterval(400)
        self._mini_poll.timeout.connect(self._poll_mini)
        self._mini_poll.start()

        # 三层窗口：主窗口 --最小化--> 悬浮窗 --20 秒--> 右下角小方块
        self.mini = MiniController(
            courses_provider=self._today_courses,
            countdowns_provider=lambda: load_user_settings().get('countdowns'),
            lesson_times_provider=self._today_lesson_times,
            on_back=self._restore_from_mini,
        )

    def reload_data(self):
        """重新跑一遍数据加载（重跑向导后调用）。"""
        try:
            from data.store import reset_shared_store
            reset_shared_store()
            self._countdown_labels = []
            self._render_countdowns()
            self.data = loadPool(parent=self, widget=self)
        except Exception as e:                  # noqa: BLE001
            print(f'[reload] 重新加载失败: {e!r}')

    # ---------- 悬浮层显示策略 ----------
    def _poll_mini(self):
        """决定悬浮层是否显示。

        规则（按优先级）：
            1. 拖小窗 / 刚拖完 → 不动
            2. 主窗口最小化 → 显示
            3. 前台是本程序的主窗口 → 收起
            4. 前台是本程序的悬浮层自己 → 保持显示（否则会自己闪）
            5. 没显示时，别的程序铺满屏幕（最大化/全屏）→ 显示
            6. 其它情况 → 保持现状（已经显示就不收）
        """
        import time

        mini = getattr(self, 'mini', None)
        if mini is None:
            return
        if getattr(mini.chip, '_dragging', False) or mini.is_holding():
            return

        if self.isMinimized():
            if not mini.is_visible():
                self._remember_window_state()
                log('poll', 'minimized -> show_all')
                mini.show_all()
            return

        active = QApplication.activeWindow()
        if active is self:
            if mini.is_visible():
                mini.hide_all()
            return
        if active is mini.bar or active is mini.chip:
            # 用户正在操作悬浮层本身，别收
            if not mini.is_visible():
                mini.show_all()
            return

        # 已经显示的情况下，只要不是回到主窗口就一直留着：
        # 前面开个小窗口、点开始菜单都不该把它弄没。
        if not mini.is_visible() and not is_shell_foreground() \
                and foreground_covers_screen():
            self._remember_window_state()
            mini.show_all()

    # ---------- 悬浮窗数据 ----------
    def _today_lesson_times(self):
        """优先用数据库里的作息（按星期），没有再退回 settings 里的旧配置。"""
        from core.schedule import times_for_weekday
        from config import get_today_weekday

        weekday = get_today_weekday() or datetime.now().isoweekday()
        try:
            raw = shared_store().load_lesson_times()
            if raw:
                return times_for_weekday(raw, weekday)
        except Exception:                       # noqa: BLE001
            pass
        return times_for_weekday(
            load_user_settings().get('lesson_times'), weekday)

    def _today_courses(self) -> list:
        try:
            df = self.data['model_classlist_today']._df
            return [str(v) for v in df.iloc[:, 0].tolist()]
        except Exception:                       # noqa: BLE001
            return []

    def _restore_from_mini(self):
        log('restore', f'enter minimized={self.isMinimized()} '
                       f'modal={type(self._visible_modal()).__name__ if self._visible_modal() else None}')
        """从悬浮层回到主界面。

        如果此时开着模态窗口（设置、向导等），主窗口是被禁用的，
        直接 activateWindow 只会"叮"一声。这种情况把模态窗口带到前面，
        主窗口在它后面恢复。
        """
        from PySide6.QtWidgets import QApplication, QDialog

        modal = None
        for widget in QApplication.topLevelWidgets():
            if (isinstance(widget, QDialog) and widget.isVisible()
                    and widget.parent() is self):
                modal = widget
                break

        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        if getattr(self, '_was_maximized', False):
            self.showMaximized()
        else:
            self.showNormal()

        if modal is not None:
            log('restore', 'raise modal')
            modal.raise_()
            modal.activateWindow()
            return

        force_foreground(self, maximize=getattr(self, '_was_maximized', True))

    def _remember_window_state(self):
        """显示悬浮层前记住主窗口是不是最大化，回来时才能还原。"""
        self._was_maximized = self.isMaximized()

    def _visible_modal(self):
        """当前属于主窗口的可见模态对话框（设置、向导等）。"""
        from PySide6.QtWidgets import QDialog

        for widget in QApplication.topLevelWidgets():
            if (isinstance(widget, QDialog) and widget.isVisible()
                    and widget.isModal() and widget.parent() is self):
                return widget
        return None

    # ---------- 最小化 / 恢复 ----------
    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            modal = self._visible_modal()
            log('state', f'minimized={self.isMinimized()} '
                         f'active={self.isActiveWindow()} '
                         f'modal={type(modal).__name__ if modal else None}')
        mini = getattr(self, 'mini', None)
        if mini is None:
            return

        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() and self._visible_modal() is not None:
                # 模态窗口开着时没法操作悬浮层（输入被拦），直接回到主界面
                QTimer.singleShot(0, self._restore_from_mini)
                return
            if self.isMinimized():
                self._remember_window_state()
                # 用 singleShot 让窗口状态先落定，再摆悬浮窗
                QTimer.singleShot(0, mini.show_all)
            elif mini.is_visible() and self.isActiveWindow():
                mini.hide_all()
            return

        # 悬浮层的显示/隐藏交给 _poll_mini 轮询处理：
        # 只靠激活事件会漏掉"从桌面点回来""关掉上层窗口"这些路径。

    def closeEvent(self, event):
        if getattr(self, '_really_quit', False):
            mini = getattr(self, 'mini', None)
            if mini is not None:
                mini.hide_all()
            tray = getattr(self, 'tray', None)
            if tray is not None:
                tray.hide()
            super().closeEvent(event)
            return
        # × = 收进悬浮窗，程序继续待命（真要退出走托盘或设置里的「退出程序」）
        event.ignore()
        self.showMinimized()

    def quit_app(self):
        self._really_quit = True
        self.close()

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
            fixed = w in (self.setting_pb, self.icon_l)
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

    def open_start_menu(self):
        """点 logo 弹出开始菜单；开着时再点一次收起。

        面板是 Qt.Popup：点 logo 时那一击会先关掉面板、再传给 logo，
        "关闭"与"重新打开"会撞在一起。用 _menu_closed_at 做 0.4 秒防抖，
        让关闭它的那一下不会又把它打开。
        """
        import time
        from ui.component.start_menu import StartMenu

        closed_at = getattr(self, '_menu_closed_at', 0.0)
        if closed_at and (time.monotonic() - closed_at) < 0.4:
            self._menu_closed_at = 0.0
            return                       # 这一下是关闭动作，忽略

        current = getattr(self, '_start_menu', None)
        if current is not None and current.isVisible():
            current.close()
            self._start_menu = None
            return

        sidebar = self.sidebar_wg
        menu = StartMenu(
            on_settings=lambda: self.open_settings(),
            on_minimize=lambda: self.showMinimized(),
            on_quit=lambda: self.quit_app(),
            parent=self,
        )
        menu.on_closed = lambda: setattr(
            self, '_menu_closed_at', time.monotonic())

        # 盖住侧栏，但把底部 logo 让出来：这样还能再点图标收起
        logo_h = self.icon_l.height() + 24
        top_left = sidebar.mapToGlobal(QPoint(0, 0))
        menu.show_over(top_left, sidebar.width(),
                       max(120, sidebar.height() - logo_h))
        self._start_menu = menu          # 持有引用，避免被回收

    def open_settings(self):
        """打开设置。

        用非模态 show() 而不是 exec()：模态会拦掉同程序其它窗口的输入，
        最小化后连「班级」小窗都点不动（系统只会响一声）。
        """
        existing = getattr(self, '_settings_dlg', None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        dlg = SettingsDialog(self)
        dlg.setModal(False)                 # 明确非模态
        dlg.changed.connect(self._on_settings_changed)
        self._settings_dlg = dlg            # 持有引用，避免被回收
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

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
        self.wn_random.setModal(False)      # 非模态：开着也能操作主界面
        self.wn_random.show()
        self.wn_random.raise_()

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
            self.wn_classlist.setModal(False)
            self.wn_classlist.finished.connect(self._after_classlist_edit)
            self.wn_classlist.show()
            self.wn_classlist.raise_()

    def _after_classlist_edit(self, _result=0):
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

        self.wn_Onduty.setModal(False)
        self.wn_Onduty.finished.connect(self._after_onduty_edit)
        self.wn_Onduty.show()
        self.wn_Onduty.raise_()

    def _after_onduty_edit(self, _result=0):
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

    def apply_theme(self):
        """主题色改变后重新渲染样式（全局 QSS + 各控件的局部 QSS）。"""
        from ui.tokens import set_primary
        cfg = load_user_settings()
        set_primary(cfg.get('theme_color', '#9B0D14'))

        setQss(QSS_DIR + 'mainpage.qss', QApplication.instance())
        setQss(QSS_DIR + 'title.qss', self.title_l)
        setQss(QSS_DIR + 'tableview.qss', self.onduty_tv)
        setQss(QSS_DIR + 'tableview.qss', self.classlist_tv,
               extra='QTableView::item { padding: 6px 5px; }')
        setQss(QSS_DIR + 'applink.qss', self.applink_tv)
        setQss(QSS_DIR + 'sidebar.qss', self.sidebar_wg)
        self.update()

    def refresh_logo(self):
        """设置里换过学校图标后，刷新侧栏底部那张图。"""
        self._logo_source = QPixmap(school_logo_path())
        self._fit_logo()

    def _fit_logo(self):
        """让学校图标铺满侧栏宽度（只调高度，绝不动宽度约束）。

        icon_l 是 RatioPixmapQLabel，会把 pixmap 缩放成标签自身尺寸；
        而标签宽度由布局决定 = 侧栏宽度。这里只把高度按原图比例设好，
        宽度交给布局，避免反过来把侧栏挤窄。
        """
        if self._logo_source.isNull():
            return
        layout = self.sidebar_wg.layout()
        margins = layout.contentsMargins() if layout is not None else None
        pad = (margins.left() + margins.right()) if margins is not None else 16
        width = max(self.sidebar_wg.minimumWidth(), self.sidebar_wg.width()) - pad
        width = max(80, width)
        height = int(width * self._logo_source.height() / max(1, self._logo_source.width()))
        height = max(40, min(height, 200))

        self.icon_l.setMinimumWidth(0)
        self.icon_l.setMaximumWidth(16777215)          # QWIDGETSIZE_MAX，等于不限制
        self.icon_l.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.icon_l.setFixedHeight(height)
        self.icon_l.setPixmap(self._logo_source)
        self.icon_l.updatePixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_logo()

    def refresh_apps(self):
        """设置里改完应用链接后，刷新主界面的图标网格。"""
        try:
            self.data.load(self.data.app_chain)
            wait_all(self.data)
        except Exception as e:                  # noqa: BLE001
            print(f'[apps] 刷新失败: {e!r}')

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
