from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QDropEvent, QDragEnterEvent
from tools.parent import *

def _empty(*args, **kwargs):pass


class dropableQWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)


    def dragEnterEvent(self, e:QDragEnterEvent):
        data = e.mimeData()
        if data.hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

        
    def dropEvent(self, e:QDropEvent, after_drop_func=_empty):
        data = e.mimeData()
        if data.hasUrls():
            file_paths = []
            for url in data.urls():
                file_paths.append(url.toString())
            after_drop_func(file_paths)
            
