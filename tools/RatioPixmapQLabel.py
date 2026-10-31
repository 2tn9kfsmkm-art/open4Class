from PyQt5 import QtCore, QtWidgets


class RatioPixmapQLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def setPixmap(self, pixmap):
        self.original_pixmap = pixmap
        self.updatePixmap()

    def updatePixmap(self):
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled_pixmap = self.original_pixmap.scaled(
                self.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            super().setPixmap(scaled_pixmap)
        else:
            super().clear()

    def resizeEvent(self, a0):
        self.updatePixmap()
        return super().resizeEvent(a0)