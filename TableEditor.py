from PyQt5.QtWidgets import (QApplication, QDialog, QFileDialog, QMessageBox, QHeaderView,
                             QTableView)
from PyQt5.QtCore import Qt, QDate, QModelIndex
from PyQt5.QtGui import QDropEvent
from pandas import DataFrame, read_csv, concat
import sys

from tools.PandasQModel import PandasQProxyModel, PandasQItemModel, divideModel, q_read_csv
from tools.shape import *
from windows.wn_Onduty import Ui_dialog as wn_Onduty
from windows.dropableTableView import *


WN_ONDUTY_TITLE = '调整值日生'


class TableEditor(QDialog, wn_Onduty):
    def __init__(
        self, data, extraHeader=True, title='',
        selected_index=None, multi_highlight=False,
        savepath='',
        filter=None, title_filter=QComboBoxDelegate,
        content_filter=QComboBoxDelegate,
        content_completer=False, title_completer=False,
        simple_show=2, accept_simple=True, default_simple=True,
        show_size='5x5',
        col_min_width=None,
        row_ops=False):  

        super().__init__()
        self.setupUi(self)

        self.is_saved = True
        self.title = title
        self.setWindowTitle(title)

        self.artifitial = True
        self.simple_mode = default_simple
        self.acceptSimple = accept_simple
        self.simple_show = simple_show
        self.savepath = savepath
        self.col_min_width = col_min_width

        if isinstance(data, DataFrame):
            self.data = PandasQItemModel(data=data)
        elif isinstance(data, PandasQItemModel):
            self.data = PandasQItemModel(data=data._df)
        else:
            raise TypeError(f'unsupported data type: {type(data)}')

        self.extraHeader = extraHeader
        self.content_filter = content_filter
        self.title_filter = title_filter

        self.Onduty_tableView.setContentFilter(content_filter)
        self.Onduty_tableView.setTitleFilter(title_filter if extraHeader else QNoDelegate)

        self.operate = []

        if default_simple:
            data_to_show = self.data._df.iloc[:, 0:self.simple_show]
            self.model_Table = divideModel(parent=self, data=data_to_show)
        else:
            self.model_Table = divideModel(data=self.data._df)

        self.model_Table.setExtraHeader(self.extraHeader)
        self.Onduty_tableView.setModel(self.model_Table)

        self.Onduty_tableView.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.Onduty_tableView.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)

        _show_size = show_size.split('x')
        if len(_show_size) != 2:
            raise ValueError('show_size should be a str like "~x~"')
        
        self.row_show, self.col_show = (int(i) for i in _show_size)
        self.Onduty_tableView.resize_to_lines(self.row_show, self.col_show)

        if self.col_min_width:
            for c in range(self.Onduty_tableView.model().columnCount()):
                if self.Onduty_tableView.columnWidth(c) < self.col_min_width:
                    self.Onduty_tableView.setColumnWidth(c, self.col_min_width)
            self.Onduty_tableView._apply_fixed_size(self.row_show, self.col_show)

        self.Onduty_tableView.setupSelection(
            title_selections=self.model_Table.getHeader(),
            content_selections=filter)

        self.multi_highlight = multi_highlight
        if multi_highlight:
            self.Onduty_tableView.setSelectionMode(QTableView.SelectionMode.MultiSelection)
        else:
            self.Onduty_tableView.setSelectionMode(QTableView.SelectionMode.SingleSelection)

        if selected_index:
            if self.multi_highlight:
                for i in selected_index:
                    idx = self.model_Table.index(*i)
                    if idx.isValid():
                        self.Onduty_tableView.setCurrentIndex(idx)
            else:
                idx = self.model_Table.index(*selected_index[0])
                if idx.isValid():
                    self.Onduty_tableView.setCurrentIndex(idx)

        self.save_pb.setText('完成')
        self.cancel_pb.setText('取消')
        self.save_pb.clicked.connect(self.on_finish)
        self.cancel_pb.clicked.connect(self.on_cancel)
        self.model_Table.dataChanged.connect(self.dataChangeResponse)

        self.fill_pb.setVisible(False)
        self.history_pb.setVisible(False)

        if row_ops:
            self.more_pb.setText('添加行')
            self.more_pb.setVisible(True)
            self.more_pb.clicked.connect(self._add_row)

            self.delete_pb.setText('删除末行')
            self.delete_pb.setVisible(True)
            self.delete_pb.clicked.connect(self._delete_last_row)
        else:
            self.more_pb.setVisible(False)
            self.delete_pb.setVisible(False)

    def setAcceptSimple(self, _accept: bool):
        self.acceptSimple = _accept

    def setWindowTitle(self, a0):
        self.title = a0
        title = a0 if self.is_saved else a0 + ' *(未保存)'
        return super().setWindowTitle(title)

    def _add_row(self):
        """在表格末尾添加一行空白。"""
        from pandas import DataFrame as _DataFrame
        df = self.model_Table._df
        n_cols = df.shape[1]
        if n_cols == 0:
            return
        new_row = _DataFrame([[''] * n_cols], columns=df.columns)
        self.model_Table.concat([new_row], ignore_index=True)
        self.is_saved = False
        self.setWindowTitle(self.title)
        self._refresh_fixed_size()

    def _delete_last_row(self):
        """删除最后一行（至少保留一行）。"""
        df = self.model_Table._df
        if df.shape[0] <= 1:
            return
        self.model_Table.beginResetModel()
        try:
            self.model_Table._bind_df(df.iloc[:-1].reset_index(drop=True))
        finally:
            self.model_Table.endResetModel()
        self.is_saved = False
        self.setWindowTitle(self.title)
        self._refresh_fixed_size()

    def _refresh_fixed_size(self):
        """行数变化后重新计算窗口大小，避免新行被裁掉。"""
        tv = self.Onduty_tableView
        tv.resizeColumnsToContents()
        tv.resizeRowsToContents()
        rows = tv.model().rowCount()
        cols = tv.model().columnCount()
        if rows > 0 and cols > 0:
            tv._apply_fixed_size(rows, cols)
    def on_finish(self):
        """完成：保存并关闭。"""
        try:
            self.save()
        except Exception as e:
            QMessageBox.warning(self, '保存失败', f'{e!r}')
            return
        QDialog.accept(self)

    def on_cancel(self):
        """取消：直接关闭，不保存。"""
        QDialog.reject(self)

    def closeEvent(self, e):
        """右上角 X 视为取消。"""
        e.accept()

    '''
    def addColumn(self):
        index = self.model_Table.index(0, self.model_Table.columnCount() - 1)
        if not index.isValid():
            return
        last_date = self.model_Table.data(index)
        try:
            newdate = QDate.fromString(last_date, 'yyyy-MM-dd').addDays(1).toString('yyyy-MM-dd')
        except Exception:
            newdate = ''

        # 显式用新日期作为列名，避免保存后丢失标题
        column_data = [newdate] + [''] * (self.model_Table.rowCount() - 1)
        column = DataFrame({newdate: column_data})
        self.model_Table.concat([column], axis=1)
        self.model_Table.dataChanged.emit(index, index, [0, 2])
    '''

    def dataChangeResponse(self, index1, index2, roles):
        self.is_saved = False
        self.setWindowTitle(self.title)

    def save(self):
        self.is_saved = True
        from pandas import concat as pd_concat, DataFrame as pd_DataFrame

        model_df = self.model_Table._df
        data_df  = self.data._df

        n_rows_model = model_df.shape[0]
        n_rows_data  = data_df.shape[0]
        n_cols_model = model_df.shape[1]
        n_cols_data  = data_df.shape[1]

        # ---- 行数同步（原来只同步列，行数变化会丢） ----
        if n_rows_model > n_rows_data:
            extra = pd_DataFrame(
                [[None] * n_cols_data for _ in range(n_rows_model - n_rows_data)],
                columns=data_df.columns)
            self.data._bind_df(pd_concat([data_df, extra], ignore_index=True))
            data_df = self.data._df
        elif n_rows_model < n_rows_data:
            self.data._bind_df(data_df.iloc[:n_rows_model].reset_index(drop=True))
            data_df = self.data._df

        # ---- 列同步（只写 model 覆盖到的前 n_sync 列） ----
        n_sync = min(n_cols_model, n_cols_data)
        for i in range(n_sync):
            data_df.iloc[:, i] = model_df.iloc[:n_rows_model, i].values

        if self.savepath:
            data_df.to_csv(self.savepath, header=True, index=False)
        self.operate = []
        self.setWindowTitle(self.title)

    def setModel(self, model):
        self.data = model

    def fill(self):
        pass

    def delete_column(self):
        pass

    def history(self):
        pass

    def openfile(self):
        pass

    def new(self):
        pass

    def move(self):
        pass

    def exchange(self, idx1, idx2):
        pass

    def dragEnterEvent(self, e: QDropEvent):
        data = e.mimeData()
        if data.hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()
            QMessageBox.information(parent=self, title='提示', text='只能拖入文件')

    def dropEvent(self, e: QDropEvent):
        data = e.mimeData()
        if data.hasUrls():
            print(data.data())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    path = QFileDialog.getOpenFileName()[0]
    data = q_read_csv(path)
    te = TableEditor(
        data=data, extraHeader=True, default_simple=True,
        savepath=path, multi_highlight=False,
        content_filter=QNoDelegate
    )
    te.show()
    app.exec_()