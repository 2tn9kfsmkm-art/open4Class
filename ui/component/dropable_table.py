from PySide6 import QtCore, QtGui, QtWidgets
from tools.PandasQModel import PandasQItemModel


class dragdropQTableView(QtWidgets.QTableView):
    exchange = QtCore.Signal(object, object)

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.data1 = None
        self.data1Index = None
        self.selections = self.selectedIndexes()
        self.titleFilter = QComboBoxDelegate
        self.contentFilter = QComboBoxDelegate

    def setTitleFilter(self, _filter):
        self.titleFilter = _filter

    def setContentFilter(self, _filter):
        self.contentFilter = _filter

    def setupSelection(self, title_selections=None, content_selections=None):
        if title_selections is None:
            title_selections = []
        if content_selections is None:
            content_selections = []
        self.selection_model = self.selectionModel()
        self.selection_model.selectionChanged.connect(self.selectionUpdate)
        self.model().dataChanged.connect(self.selectionUpdate)
        if self.contentFilter is not QNoDelegate:
            self.setItemDelegate(self.contentFilter(content_selections))
        if self.titleFilter is not QNoDelegate:
            self.setItemDelegateForRow(0, self.titleFilter(title_selections))

    def _apply_fixed_size(self, visible_rows, visible_cols):
        total_width = 0
        total_height = 0
        for col in range(min(visible_cols, self.model().columnCount())):
            total_width += self.columnWidth(col)
        for row in range(min(visible_rows, self.model().rowCount())):
            total_height += self.rowHeight(row)
        total_width += self.verticalHeader().width()
        total_height += self.horizontalHeader().height()
        frame_width = self.frameWidth() * 2
        total_width += frame_width
        total_height += frame_width
        if visible_rows < self.model().rowCount():
            total_width += self.verticalScrollBar().sizeHint().width()
        if visible_cols < self.model().columnCount():
            total_height += self.horizontalScrollBar().sizeHint().height()
        self.setFixedSize(total_width, total_height)

    def resize_to_lines(self, visible_rows, visible_cols):
        self.update()
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self._apply_fixed_size(visible_rows, visible_cols)

    def selectionUpdate(self):
        self.selected_indexs = self.selectedIndexes()
        if self.selected_indexs:
            self.data1Index = self.selected_indexs[0]
            self.data1 = self.model().data(self.data1Index)
        else:
            self.data1Index = None
            self.data1 = None

    def dragEnterEvent(self, e: QtGui.QDropEvent):
        data = e.mimeData()
        if data.hasImage():
            QtWidgets.QMessageBox.warning(self, '提示', '不能填入图片',
                                           QtWidgets.QMessageBox.Ok)
            e.ignore()
        elif data.hasUrls():
            print(data.data('Urls'))
        elif data.hasHtml():
            QtWidgets.QMessageBox.warning(self, '提示', '不能填入html',
                                           QtWidgets.QMessageBox.Ok)
            e.ignore()
        else:
            e.acceptProposedAction()

    def dropEvent(self, e: QtGui.QDropEvent):
        data = e.mimeData()
        pos = e.pos()
        index2 = self.indexAt(pos)
        data2 = index2.data()
        self.model().setData(index2, self.data1)
        print(f'exchange {self.data1}, {data2}')
        self.exchange.emit(self.data1Index, index2)
        self.model().setData(self.data1Index, data2)
        self.setCurrentIndex(index2)

    def isMultipleHighlight(self):
        return bool(self.selectionModel())


class QComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items
        self.completer = ListViewedQCompleter(self)
        self.completer.setModel(PandasQItemModel(items))

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        editor.setEditable(True)
        editor.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        editor.setCompleter(self.completer)
        editor.setModel(PandasQItemModel(self.items))
        return editor

    def setEditorData(self, editor: QtWidgets.QComboBox, index):
        value = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        editor.setCurrentText(value)

    def setModelData(self, editor: QtWidgets.QComboBox, model, index):
        value = editor.lineEdit().text()
        model.setData(index, value, QtCore.Qt.ItemDataRole.EditRole)


class QDateEditDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QDateEdit(parent)
        editor.setDisplayFormat('yyyy-MM-dd')
        return editor

    def setEditorData(self, editor, index):
        if editor is None:
            return
        value = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        editor.setDate(QtCore.QDate.fromString(value, 'yyyy-MM-dd'))

    def setModelData(self, editor, model, index):
        value = editor.date().toString('yyyy-MM-dd')
        model.setData(index, value, QtCore.Qt.ItemDataRole.EditRole)


class ListViewedQCompleter(QtWidgets.QCompleter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        self.empty_show_all = True

    def splitPath(self, path):
        if not path and self.empty_show_all:
            return [""]
        return path.lower().split()

    def pathFromIndex(self, index):
        return self.model().data(index, QtCore.Qt.ItemDataRole.DisplayRole)

    def setEmptyShowAll(self, enabled):
        self.empty_show_all = enabled


class QNoDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        return QtWidgets.QLabel(parent)

    def setEditorData(self, editor, index):
        if editor is None:
            return
        value = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        editor.setText(value)

    def setModelData(self, editor, model, index):
        pass

class OndutyContentDelegate(QtWidgets.QStyledItemDelegate):
    """单元格编辑器：姓名 combobox + 职务 combobox。"""

    def __init__(self, names, jobs, parent=None):
        super().__init__(parent)
        self.names = list(names) if names is not None else []
        self.jobs = list(jobs) if jobs is not None else []

    def _make_combo(self, parent, items, placeholder):
        cb = QtWidgets.QComboBox(parent)
        cb.setEditable(True)
        cb.setInsertPolicy(QtWidgets.QComboBox.NoInsert)   # ← 关键：不尝试插入 model
        cb.setModel(PandasQItemModel(items))
        completer = ListViewedQCompleter(cb)
        completer.setModel(PandasQItemModel(items))
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        completer.setEmptyShowAll(True)
        cb.setCompleter(completer)
        if cb.lineEdit():
            cb.lineEdit().setPlaceholderText(placeholder)
        return cb

    @staticmethod
    def _combo_text(cb):
        # editable combo 的可靠文本源是 lineEdit，currentText 在无匹配时会失效
        if cb.lineEdit() is not None:
            return cb.lineEdit().text()
        return cb.currentText()

    def createEditor(self, parent, option, index):
        """改为弹窗编辑：单元格太窄，塞两个下拉会互相挤。"""
        value = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole) or ''
        name, job = _split_name_job(str(value))

        dlg = OndutyEditDialog(self.names, self.jobs, name, job, parent)
        if dlg.exec():
            n, j = dlg.values()
            text = ' '.join(x for x in (n, j) if x)
            index.model().setData(index, text, QtCore.Qt.ItemDataRole.EditRole)
        # 不返回内联编辑器，编辑到此结束
        return None

    def setEditorData(self, editor, index):
        if editor is None:
            return
        value = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        editor.setDate(QtCore.QDate.fromString(value, 'yyyy-MM-dd'))

    def setModelData(self, editor, model, index):
        value = editor.date().toString('yyyy-MM-dd')
        model.setData(index, value, QtCore.Qt.ItemDataRole.EditRole)


class ListViewedQCompleter(QtWidgets.QCompleter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        self.empty_show_all = True

    def splitPath(self, path):
        if not path and self.empty_show_all:
            return [""]
        return path.lower().split()

    def pathFromIndex(self, index):
        return self.model().data(index, QtCore.Qt.ItemDataRole.DisplayRole)

    def setEmptyShowAll(self, enabled):
        self.empty_show_all = enabled


class QNoDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        return QtWidgets.QLabel(parent)

    def setEditorData(self, editor, index):
        if editor is None:
            return
        value = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)
        editor.setText(value)

    def setModelData(self, editor, model, index):
        pass

def _split_name_job(text: str):
    """按最后一个空白切分「姓名 职务」，姓名里的空格保留。"""
    parts = str(text).strip().rsplit(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ''
    return '', ''


class OndutyEditDialog(QtWidgets.QDialog):
    """值日单元格编辑弹窗：姓名 + 职务，两个下拉并排，放得下。"""

    def __init__(self, names, jobs, name='', job='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('修改值日')
        self.setMinimumWidth(420)

        box = QtWidgets.QVBoxLayout(self)

        row = QtWidgets.QHBoxLayout()
        self.name_cb = QtWidgets.QComboBox()
        self.name_cb.setEditable(True)
        self.name_cb.addItems([str(n) for n in names])
        self.name_cb.setCurrentText(name)
        self.job_cb = QtWidgets.QComboBox()
        self.job_cb.setEditable(True)
        self.job_cb.addItems([str(j) for j in jobs])
        self.job_cb.setCurrentText(job)
        for w in (self.name_cb, self.job_cb):
            w.setMinimumHeight(44)
            w.setStyleSheet('font-size: 15pt;')
        row.addWidget(self.name_cb, 2)
        row.addWidget(self.job_cb, 1)
        box.addLayout(row)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)

    def values(self):
        return (self.name_cb.currentText().strip(),
                self.job_cb.currentText().strip())
