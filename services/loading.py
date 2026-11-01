import os
from datetime import datetime

from PySide6.QtWidgets import QHeaderView, QMessageBox, QDialog
from PySide6.QtCore import Qt, QEventLoop, QUrl
from pandas import DataFrame

from tools.LoadChain import Chain, ChainPool
from tools.PandasQModel import PandasQItemModel
from core.shape import reshapeRow
from tools.jsonModel import JsonDataModel

from ui.component.dialogs import questionForChoice
from ui.window.table_editor import TableEditor
from config import *

from data.store import shared_store


# ---------- 主线程同步等待 ----------
def wait_all(pool: ChainPool):
    if pool.is_idle():
        return
    loop = QEventLoop()
    handler = loop.quit
    pool.all_done.connect(handler)
    try:
        loop.exec()
    finally:
        try:
            pool.all_done.disconnect(handler)
        except TypeError:
            pass


# ============================================================
class onduty_chain(Chain):
    def __init__(self, parent=None, widget=None, name='onduty'):
        super().__init__(parent, widget, name)

    def load(self):
        # SQLite 是唯一存储，这里不再关心文件在哪
        self.onduty_model = PandasQItemModel(data=shared_store().load_onduty())

    def _save(self):
        shared_store().save_onduty(self.onduty_model._df)

    def process(self):
        df = self.onduty_model._df
        cols_to_drop = []
        for col in df.columns:
            try:
                delta = (datetime.strptime(str(col), '%Y-%m-%d') - datetime.today()).days
            except (ValueError, TypeError):
                print(f'Warning: invalid onduty column "{col}", skipped')
                continue
            if delta < -1:
                cols_to_drop.append(col)

        print('已删除' + str(cols_to_drop) + '值日记录')
        if cols_to_drop:
            df.drop(columns=cols_to_drop, inplace=True)
            self._save()

        if str_date not in df.columns:
            placeholder = ['暂无值日信息'] + [''] * 4
            if len(df) == 0:
                df[str_date] = placeholder
            elif len(df) == 5:
                df.insert(0, str_date, placeholder)
            else:
                # 行数异常：重建并通过 _bind_df 重新绑定索引器
                new_df = DataFrame({str_date: placeholder})
                self.onduty_model._bind_df(new_df)
                df = self.onduty_model._df
            self._save()

        self.emit({'onduty_model': self.onduty_model})

    def play(self, widget):
        if widget is None:
            return
        df = self.onduty_model._df
        today_rows = df[str_date].tolist() if str_date in df.columns else []
        self.model_onduty_today = PandasQItemModel(
            data=DataFrame({str_date: today_rows}))
        self.emit({'model_onduty_today': self.model_onduty_today})

        widget.onduty_tv.setModel(self.model_onduty_today)
        self.model_onduty_today.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.onduty_tv.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.onduty_tv.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.onduty_tv.resizeRowsToContents()


class classlist_chain(Chain):
    def __init__(self, parent=None, widget=None, name='classlist'):
        super().__init__(parent, widget, name)

    def load(self):
        store = shared_store()
        self.classlist_model = PandasQItemModel(data=store.load_classlist())
        self.classes = store.load_courses()

    # ---- 今天的课表：临时课表优先，否则用周模板 ----
    def today_courses(self):
        return shared_store().load_classlist_for_date(today.date())

    def has_today_classlist(self) -> bool:
        return any(str(c).strip() for c in self.today_courses())

    def prepare(self):
        """确定"今天"的课表：周末且久未登录时询问一次。

        选择结果直接写进数据库的临时课表，所以中途退出也不会留下
        "问过了但没课表"的坏状态。
        """
        global class_wordday
        appData = self.parent['appData']
        last_login_dt = datetime.strptime(appData.last_login, '%Y%m%d')
        print(f'delta:{(last_login_dt - today).days}')

        ok = False
        if weekday not in range(5):
            need_ask = (last_login_dt - today).days < -1 or not self.has_today_classlist()
            if need_ask:
                if self.has_today_classlist():
                    answer = QMessageBox.question(
                        self.widget, '提示', '已有临时课表，是否使用？',
                        QMessageBox.Yes | QMessageBox.No)
                    ok = answer == QMessageBox.Yes
                    if not ok:
                        ok = self._set_tmp_classlist()
                else:
                    ok = self._set_tmp_classlist()
            else:
                ok = True
        else:
            class_wordday = wordday
            ok = True

        if ok:
            appData.last_login = today.strftime('%Y%m%d')

    def _set_tmp_classlist(self) -> bool:
        """询问今天按星期几上课，返回是否写入了临时课表。"""
        global class_wordday, classday
        store = shared_store()
        choices = list(range(1, 6)) + ['设置临时课表']
        classday = questionForChoice(
            self.widget, title='提示',
            text='今天没有课表信息，按照星期几上课？', choices=choices)

        if classday == '设置临时课表':
            n_rows = self.classlist_model._df.shape[0]
            if n_rows <= 0:
                n_rows = DEFAULT_CLASS_ROWS
            model = PandasQItemModel({wordday: [None for _ in range(n_rows)]})

            def _save_tmp(df):
                store.save_classlist_override(
                    today.date(), [str(v) for v in df.iloc[:, 0].tolist()])

            editor = TableEditor(
                model, accept_simple=False, savepath='',
                title='设置临时课表', show_size=f'{n_rows}x1',
                row_ops=True, on_save=_save_tmp)
            if editor.exec() == QDialog.Accepted:
                return True
            print('[classlist] 取消了临时课表设置，今日课表留空')
            return False

        if classday is not None:
            classday = int(classday) - 1
            class_wordday = weekday2word(classday)
            template = self.classlist_model._df
            if class_wordday not in template.columns:
                print(f'[classlist] 周模板里没有 "{class_wordday}"，今日课表留空')
                return False
            store.save_classlist_override(
                today.date(),
                [str(v) for v in template[class_wordday].tolist()])
            return True

        print('[classlist] 用户关闭了课表询问，今日课表留空')
        return False

    def input(self, widget):
        pass

    def process(self):
        self.emit({
            'classes': self.classes,
            'classlist_model': self.classlist_model,
        })

    def play(self, widget):
        if widget is None:
            return
        courses = self.today_courses()
        if not courses:
            courses = ['']
        self.model_classlist_today = PandasQItemModel(
            data=DataFrame({wordday: courses}))
        self.emit({'model_classlist_today': self.model_classlist_today})

        widget.classlist_tv.setModel(self.model_classlist_today)
        self.model_classlist_today.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.classlist_tv.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.classlist_tv.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.classlist_tv.resizeRowsToContents()


# ============================================================
class app_chain(Chain):
    def __init__(self, parent=None, widget=None, name='app'):
        super().__init__(parent, widget, name)

    def load(self):
        self.applications = PandasQItemModel(data=shared_store().load_apps())

    def process(self):
        tmp_data = self.applications._df['软件链接'].to_list()
        reshape = reshapeRow(tmp_data, 1, defaultNone=None)
        if reshape and reshape[0]:
            reshape[0].append('...')
        elif not reshape:
            reshape = [['...']]
        self.app_reshape_model = PandasQItemModel(reshape, parent=self.widget)
        self.emit({'applications': self.applications})

    def play(self, widget):
        if widget is None:
            return
        widget.applink_tv.setModel(self.app_reshape_model)
        self.app_reshape_model.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.applink_tv.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.applink_tv.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.applink_tv.resizeRowsToContents()

    def delete(self, appname: str) -> bool:
        df = self.applications._df
        new_df = df[df['软件链接'] != appname]
        if len(new_df) == len(df):
            print(f'[app] 未找到 "{appname}"，删除跳过')
            return False
        try:
            shared_store().save_apps(new_df)
        except Exception as e:
            print(f'[app] 保存失败: {e!r}')
            return False
        self.load()
        self.process()
        return True


# ============================================================
class message_chain(Chain):
    def __init__(self, parent=None, widget=None, name='message'):
        super().__init__(parent, widget, name)

    def load(self):
        path = FILE_DIR  # 占位，实际用 MESSAGE_DIR
        path = MESSAGE_DIR + 'message.html'
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding=ENCODING) as f:
                    self.html = f.read()
            except Exception as e:
                print(f'[message] read failed: {e!r}')
                self.html = ''
        else:
            self.html = ''

    def process(self):
        self.emit({'message_html': self.html})

    def play(self, widget):
        if widget is None:
            return
        widget.message_tb.document().setBaseUrl(
            QUrl.fromLocalFile(os.path.abspath(MESSAGE_DIR)+os.sep)
        )
        widget.message_tb.setHtml(self.html)


# ============================================================
class stu_chain(Chain):
    def __init__(self, parent=None, widget=None, name='stu'):
        super().__init__(parent, widget, name)

    def load(self):
        self.stu_model = PandasQItemModel(data=shared_store().load_names())

    def process(self):
        self.emit({'stu_model': self.stu_model})


# ============================================================
class appData_chain(Chain):
    def __init__(self, parent=None, widget=None, name='app_data'):
        super().__init__(parent, widget, name)

    def load(self):
        self.appData = JsonDataModel(FILE_DIR + 'data.json')

    def process(self):
        self.emit({'appData': self.appData})



# ============================================================
class loadPool(ChainPool):
    def __init__(self, parent=None, widget=None):
        super().__init__(parent)
        self.widget = widget

        self.appData_chain = appData_chain(self, widget)
        self.load(self.appData_chain, autoDelete=False)
        wait_all(self)

        self.classlist_chain = classlist_chain(self, widget)
        self.classlist_chain.load()
        self.classlist_chain.prepare()

        self.onduty_chain = onduty_chain(self, widget)
        self.load(self.onduty_chain, autoDelete=False)

        self.load(self.classlist_chain, autoDelete=False)

        self.app_chain = app_chain(self, widget)
        self.load(self.app_chain, autoDelete=False)

        self.stu_chain = stu_chain(self, widget)
        self.load(self.stu_chain, autoDelete=False)

        # 消息：单条
        self.message_chain = message_chain(self, widget)
        self.load(self.message_chain, autoDelete=False)

        wait_all(self)