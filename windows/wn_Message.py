# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(1200, 800)

        self.gridLayout = QtWidgets.QGridLayout(Dialog)
        self.gridLayout.setContentsMargins(6, 6, 6, 6)

        # ----- 编辑区（上方，占满空间）-----
        self.edit_te = QtWidgets.QTextEdit(Dialog)
        self.gridLayout.addWidget(self.edit_te, 0, 0)

        # ----- 工具栏（下方）-----
        self.toolbar = QtWidgets.QHBoxLayout()
        self.toolbar.setSpacing(6)

        self.fontSize_l = QtWidgets.QLabel("字号")
        self.toolbar.addWidget(self.fontSize_l)

        self.fontSize_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.fontSize_slider.setRange(8, 72)
        self.fontSize_slider.setValue(24)
        self.fontSize_slider.setSingleStep(1)
        self.fontSize_slider.setPageStep(4)
        self.fontSize_slider.setMinimumWidth(180)
        self.toolbar.addWidget(self.fontSize_slider)

        self.fontSize_value_l = QtWidgets.QLabel("24")
        self.fontSize_value_l.setMinimumWidth(36)
        self.fontSize_value_l.setAlignment(QtCore.Qt.AlignCenter)
        self.toolbar.addWidget(self.fontSize_value_l)

        self.toolbar.addSpacing(12)

        self.bold_tb = self._make_text_button("粗体", checkable=True)
        self.toolbar.addWidget(self.bold_tb)

        self.image_tb = self._make_text_button("插入图片")
        self.toolbar.addWidget(self.image_tb)

        self.toolbar.addStretch()

        self.upload_tb = self._make_text_button("导入")
        self.toolbar.addWidget(self.upload_tb)

        self.save_tb = self._make_text_button("保存")
        self.toolbar.addWidget(self.save_tb)

        self.home_tb = self._make_text_button("关闭")
        self.toolbar.addWidget(self.home_tb)

        self.gridLayout.addLayout(self.toolbar, 1, 0)

        self.retranslateUi(Dialog)

    def _make_text_button(self, text, checkable=False):
        btn = QtWidgets.QPushButton(text)
        btn.setCheckable(checkable)
        btn.setMinimumHeight(32)
        # 中文字符平均约 15–16px，按字数估宽 + padding
        btn.setMinimumWidth(max(72, len(text) * 18 + 16))
        return btn

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "消息编辑"))