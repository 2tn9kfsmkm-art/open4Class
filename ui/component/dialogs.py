from PySide6.QtWidgets import *
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel

from dialogs.LineEditDialog import Ui_LineEditDialog
from dialogs.inputDialog import Ui_inputDialog
from dialogs.showDialog import Ui_Dialog
from tools.PandasQModel import PandasQItemModel


class InputDialog(QDialog, Ui_inputDialog):
    def __init__(self, parent=None, title=None, text=None, content=None,
                 inputwidget=QLineEdit):
        super().__init__(parent)
        self.setupUi(self)
        self._result = None
        self.setWindowTitle(title)
        self.label_text.setText(text)
        self.input_widget_class = inputwidget
        self.setWidget(content)
        self.pushButton_ok.clicked.connect(self.ok)

    def setWidget(self, text):
        self.input_widget = self.input_widget_class(self)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.input_widget.sizePolicy().hasHeightForWidth())
        self.input_widget.setSizePolicy(sizePolicy)
        self.input_widget.setObjectName("input_widget")
        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.input_widget)

    def getInputText(self):
        return None

    def cancel(self):
        self.close()

    def ok(self):
        self._result = self.getInputText()
        self.close()

    def get(self):
        return self._result


class LineEditDialog(InputDialog):
    def __init__(self, parent=None, title=None, text=None, remind=None):
        super().__init__(parent, title=title, text=text, content=remind,
                         inputwidget=QLineEdit)

    def setWidget(self, text):
        super().setWidget(text)
        self.input_widget.setText(text)

    def getInputText(self):
        return self.input_widget.text()


def questionForText(parent=None, title=None, text=None, remind=None):
    led = LineEditDialog(parent=parent, title=title, text=text, remind=remind)
    led.exec()
    return led.get()


class ComboboxDialog(InputDialog):
    def __init__(self, parent=None, title=None, text=None, model=None, current=None):
        if model is None:
            model = QStandardItemModel()
        self.current = current
        super().__init__(parent, title, text, content=model, inputwidget=QComboBox)

    def setWidget(self, model):
        super().setWidget(model)
        self.input_widget.setModel(model)
        if self.current:
            self.input_widget.setCurrentText(self.current)

    def getInputText(self):
        return self.input_widget.currentText()


def questionForChoice(parent=None, title=None, text=None, choices=None):
    if choices is None:
        choices = []
    if isinstance(choices, QStandardItemModel):
        model = choices
    else:
        model = PandasQItemModel(data=choices)
    cbd = ComboboxDialog(parent=parent, title=title, text=text, model=model)
    cbd.exec()
    return cbd.get()


class showDialog(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.ok_pb.clicked.connect(self.close)
        self.retry_pb.clicked.connect(self.retry)

    def retry(self):
        pass


class wn_random(showDialog):
    from random import choice

    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.data = data if data is not None else []
        # 随机点人是要投到教室大屏上给全班看的：
        # 名字是主角（更大更粗），按钮退居次要，避免视觉重心跑到按钮上。
        self.setStyleSheet(
            'QLabel { font-size: 40pt; font-weight: bold; }'
            'QPushButton { font-size: 20pt; font-weight: normal; }')
        self.setupRandom()

    def setupRandom(self):
        if self.data:
            self.show_l.setText(self.choice(self.data))
        else:
            self.show_l.setText('无学生')

    def retry(self):
        return self.setupRandom()