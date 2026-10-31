import os
import subprocess

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog
from PyQt5.QtCore import QThread
import pandas as pd
from pylnk3 import Lnk

from windows.wn_AddApp import Ui_Dialog_AddApp as wn_AppApp
from config import *
from data.store import shared_store


class AddApp(QDialog, wn_AppApp):
    COL_NAME = '软件链接'
    COL_PATH = 'path'

    def __init__(self, parent=None, urls=None):
        super().__init__(parent)
        self.setupUi(self)

        self.urls = list(urls) if urls else []
        self.apps = []
        self.option = self.type_cbb.currentIndex()

        self.df_apps = shared_store().load_apps()

        # 拖放支持
        self.path_le.setAcceptDrops(True)
        self.path_le.dragEnterEvent = self._line_edit_drag_enter
        self.path_le.dropEvent = self._line_edit_drop

        if self.urls:
            self.setup_path(self.urls[0])
            self.urls.pop(0)

        self.path_tb.clicked.connect(self._choose_path)
        self.tag_tb.clicked.connect(self._choose_tag)
        self.cancel_pb.clicked.connect(self.cancel)
        self.ok_pb.clicked.connect(self.finish)
        self.type_cbb.currentIndexChanged.connect(self.on_option_changed)

    def _choose_path(self):
        url, _ = QFileDialog.getOpenFileName(self, '选择应用路径', '', 'All Files (*)')
        if url:
            self.setup_path(url)

    def _choose_tag(self):
        url, _ = QFileDialog.getOpenFileName(self, '选择图标/标签', '', 'All Files (*)')
        if url:
            self.tag_le.setText(url)

    def setup_path(self, url: str):
        tag = ''
        if url.lower().endswith('.lnk'):
            try:
                import pylnk3
                lnk = pylnk3.parse(url)
                if lnk.path:
                    url = str(lnk.path)
                tag = str(lnk.description or '')
            except Exception as e:
                print(f'解析 lnk 失败: {e!r}')   # 至少暴露问题
        self.path_le.setText(url)
        if tag:
            self.tag_le.setText(tag)
        elif not self.tag_le.text():
            self.tag_le.setText(os.path.splitext(os.path.basename(url))[0])

    def _line_edit_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _line_edit_drop(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0].toLocalFile()
            self.setup_path(url)
            event.acceptProposedAction()
        else:
            event.ignore()

    def on_option_changed(self):
        self.option = self.type_cbb.currentIndex()

    def finish(self):
        if self.urls:
            self._append_current()
            self.path_le.clear()
            self.tag_le.clear()
            self.setup_path(self.urls[0])
            self.urls.pop(0)
        else:
            self._append_current()
            self.save()
            self.accept()

    def _append_current(self):
        path = self.path_le.text().strip()
        tag = self.tag_le.text().strip()
        if not path:
            return
        if not tag:
            tag = os.path.splitext(os.path.basename(path))[0]
        self.apps.append([tag, path])

    def cancel(self):
        self.close()

    def save(self):
        if not self.apps:
            return
        new_df = pd.DataFrame(self.apps, columns=[self.COL_NAME, self.COL_PATH])
        self.df_apps = pd.concat([self.df_apps, new_df], ignore_index=True)
        self.df_apps = self.df_apps.drop_duplicates(subset=[self.COL_PATH], keep='last')
        shared_store().save_apps(self.df_apps)


class LoadApp(QThread):
    def __init__(self, parent=None, app_path=''):
        super().__init__(parent)
        self.app_path = app_path

    def run(self):
        try:
            if os.name == 'nt':
                os.startfile(self.app_path)
            else:
                subprocess.Popen([self.app_path])
        except Exception as e:
            print(f'LoadApp failed: {e!r}')
        self.deleteLater()


if __name__ == '__main__':
    app = QApplication([])
    win = AddApp()
    if win.exec_() == QDialog.Accepted:
        pass
    app.exec_()