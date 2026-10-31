import os
from datetime import datetime

from PyQt5.QtWidgets import QHeaderView, QMessageBox, QDialog
from PyQt5.QtCore import Qt, QEventLoop, QUrl
from pandas import DataFrame, read_csv

from tools.LoadChain import Chain, ChainPool
from tools.PandasQModel import q_read_csv, read_csv, PandasQItemModel
from core.shape import reshapeRow
from tools.jsonModel import JsonDataModel

from Dialogs import questionForChoice
from TableEditor import TableEditor
from config import *


# ---------- 主线程同步等待 ----------
def wait_all(pool: ChainPool):
    if pool.is_idle():
        return
    loop = QEventLoop()
    handler = loop.quit
    pool.all_done.connect(handler)
    try:
        loop.exec_()
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
        path = FILE_DIR + '未来值日.csv'
        if not os.path.exists(path):
            DataFrame().to_csv(path, index=False)
        self.onduty_model = q_read_csv(path)

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
            df.to_csv(FILE_DIR + '未来值日.csv', index=False)

        if str_date in df.columns:
            df[str_date].to_csv(onduty_today_path, index=False)
        else:
            placeholder = ['暂无值日信息'] + [''] * 4
            DataFrame(placeholder).to_csv(onduty_today_path, index=False,
                                        header=[str_date])
            if len(df) == 0:
                df[str_date] = placeholder
            elif len(df) == 5:
                df.insert(0, str_date, placeholder)
            else:
                # 行数异常：重建并通过 _bind_df 重新绑定索引器
                new_df = DataFrame({str_date: placeholder})
                self.onduty_model._bind_df(new_df)
                df = self.onduty_model._df
            df.to_csv(FILE_DIR + '未来值日.csv', index=False)

        self.emit({'onduty_model': self.onduty_model})

    def play(self, widget):
        if widget is None:
            return
        if not os.path.exists(onduty_today_path):
            print(f'Warning: File {onduty_today_path} does not exist')
            return
        data = read_csv(onduty_today_path, encoding='utf-8', index_col=False)
        self.model_onduty_today = PandasQItemModel(data=data)
        self.emit({'model_onduty_today': self.model_onduty_today})

        widget.onduty_tv.setModel(self.model_onduty_today)
        self.model_onduty_today.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.onduty_tv.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.onduty_tv.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.onduty_tv.resizeRowsToContents()
        # 不再在这里 connect openWn_random（Main 里统一连接）


# ============================================================
class classlist_chain(Chain):
    def __init__(self, parent=None, widget=None, name='classlist'):
        super().__init__(parent, widget, name)

    def load(self):
        self.classlist_model = q_read_csv(FILE_DIR + '课表.csv')
        self.classes = read_csv(FILE_DIR + '课程单.csv')

    def prepare(self):
        """确定"今天"的课表：周末且久未登录时询问一次，必要时生成临时课表。

        只有确实拿到可用课表后才写 last_login —— 否则中途退出（关掉询问框、
        结束进程）会把"今天已经问过"记下来，当天就再也拿不到课表了。
        """
        global class_wordday
        appData = self.parent['appData']
        last_login_dt = datetime.strptime(appData.last_login, '%Y%m%d')
        print(f'delta:{(last_login_dt - today).days}')

        ok = False
        if weekday not in range(5):
            # 今天的课表文件不存在时，即使"今天问过"也要重新问，
            # 这样上次中途退出留下的空状态能自动恢复
            need_ask = (last_login_dt - today).days < -1 or not os.path.exists(classlist_path)
            if need_ask:
                if os.path.exists(classlist_path):
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
            self.classlist_model[class_wordday].to_csv(classlist_path, index=False)
            ok = True

        if ok:
            appData.last_login = today.strftime('%Y%m%d')

    def _set_tmp_classlist(self) -> bool:
        """询问今天按星期几上课，返回是否成功得到一份可用课表。

        用户直接关掉询问框、或在临时课表编辑器里取消时返回 False，
        并且不写任何文件，留待下次启动重新询问，而不是塞一张空表。
        """
        global class_wordday, classday
        choices = list(range(1, 6)) + ['设置临时课表']
        classday = questionForChoice(
            self.widget, title='提示',
            text='今天没有课表信息，按照星期几上课？', choices=choices)

        if classday == '设置临时课表':
            # 行数从周模板读取
            n_rows = self.classlist_model._df.shape[0]
            if n_rows <= 0:
                n_rows = 8
            model = PandasQItemModel({wordday: [None for _ in range(n_rows)]})

            editor = TableEditor(
                model, accept_simple=False, savepath=classlist_path,
                title='设置临时课表', show_size=f'{n_rows}x1',
                row_ops=True)
            # 只有"完成"才写盘；"取消"不再覆盖成空表，也不再回退写周模板
            if editor.exec_() == QDialog.Accepted:
                return True
            print('[classlist] 取消了临时课表设置，今日课表留空')
            return False

        if classday is not None:
            classday = int(classday) - 1
            class_wordday = weekday2word(classday)
            if class_wordday not in self.classlist_model._df.columns:
                print(f'[classlist] 周模板里没有 "{class_wordday}"，今日课表留空')
                return False
            self.classlist_model[class_wordday].to_csv(classlist_path, index=False)
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
        self.model_classlist_today = q_read_csv(classlist_path)
        self.emit({'model_classlist_today': self.model_classlist_today})

        widget.classlist_tv.setModel(self.model_classlist_today)
        self.model_classlist_today.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.classlist_tv.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.classlist_tv.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        widget.classlist_tv.resizeRowsToContents()
        # 不再在这里 connect openWn_classlist（Main 里统一连接）


# ============================================================
class app_chain(Chain):
    def __init__(self, parent=None, widget=None, name='app'):
        super().__init__(parent, widget, name)

    def load(self):
        path = FILE_DIR + '应用路径.csv'
        if not os.path.exists(path):
            DataFrame(columns=['软件链接', 'path']).to_csv(path, index=False)
        self.applications = q_read_csv(path)

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
        path = FILE_DIR + '应用路径.csv'
        df = self.applications._df
        new_df = df[df['软件链接'] != appname]
        if len(new_df) == len(df):
            print(f'[app] 未找到 "{appname}"，删除跳过')
            return False
        try:
            new_df.to_csv(path, index=False)
        except Exception as e:
            print(f'[app] 写 CSV 失败: {e!r}')
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
        path = FILE_DIR + '名单.csv'
        if not os.path.exists(path):
            DataFrame(columns=['name']).to_csv(path, index=False)
        self.stu_model = q_read_csv(path)

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