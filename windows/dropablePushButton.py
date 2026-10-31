#可能会弃用


from PyQt5 import QtCore, QtWidgets, QtGui

class dropableQPushButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)

    
    def dragEnterEvent(self, e:QtGui.QDragEnterEvent):
        data = e.mimeData()
        if data.hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore

        
    def dropEvent(self):
        return super().dropEvent()