import os
import re
import shutil
from datetime import datetime

from PySide6.QtWidgets import QDialog, QMessageBox, QFileDialog
from PySide6.QtGui import QTextCharFormat, QTextImageFormat, QFont, QImage, QTextCursor
from PySide6.QtCore import QUrl

from windows.wn_Message import Ui_Dialog as wn_Mes
from config import *


IMAGE_DIR = MESSAGE_DIR + 'images/'
os.makedirs(IMAGE_DIR, exist_ok=True)

DEFAULT_MAIN_PATH = MESSAGE_DIR + 'message.html'
DEFAULT_FONT_SIZE = 24


class wn_Message(wn_Mes, QDialog):
    def __init__(self, parent=None, filename=None):
        super().__init__(parent)
        self.setupUi(self)

        self.filename = filename or DEFAULT_MAIN_PATH
        self.is_saved = True

        # 默认字体 24pt
        font = QFont()
        font.setPointSize(DEFAULT_FONT_SIZE)
        self.edit_te.document().setDefaultFont(font)
        self.edit_te.setFontPointSize(DEFAULT_FONT_SIZE)

        # baseUrl（注意末尾 os.sep）
        self.edit_te.document().setBaseUrl(
            QUrl.fromLocalFile(os.path.abspath(MESSAGE_DIR) + os.sep)
        )

        # 加载文件
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding=ENCODING) as f:
                    self.edit_te.setHtml(f.read())
            except Exception as e:
                QMessageBox.warning(self, '错误', f'读取失败：{e!r}')

        # 同步滑块到文档当前字号（此时 valueChanged 还没连，blockSignals 只是保险）
        size = self._get_uniform_font_size()
        self.fontSize_slider.blockSignals(True)
        self.fontSize_slider.setValue(size)
        self.fontSize_slider.blockSignals(False)
        self.fontSize_value_l.setText(str(size))

        # 连接信号
        self.fontSize_slider.valueChanged.connect(self.update_font_size)
        self.bold_tb.toggled.connect(self.on_bold_toggled)
        self.image_tb.clicked.connect(self.insert_image)
        self.upload_tb.clicked.connect(self.upload_file)
        self.save_tb.clicked.connect(self.save)
        self.home_tb.clicked.connect(lambda: self.close())

        self.edit_te.textChanged.connect(self._on_text_changed)

    # ----- 编辑操作 -----

    def _on_text_changed(self):
        self.is_saved = False

    def _get_uniform_font_size(self) -> int:
        """优先取第一个非空片段的字号，回退到 defaultFont。"""
        doc = self.edit_te.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.text().strip():
                    size = frag.charFormat().fontPointSize()
                    if size > 0:
                        return int(size)
                it += 1
            block = block.next()
        size = doc.defaultFont().pointSize()
        return size if size > 0 else DEFAULT_FONT_SIZE
    

    def update_font_size(self, size: int):
        self.fontSize_value_l.setText(str(size))

        # 备份光标
        cursor = self.edit_te.textCursor()

        # 全选并应用字号
        # mergeCurrentCharFormat 只覆盖设置了值的属性（pointSize），
        # 不会抹掉加粗（weight）、图片等
        self.edit_te.selectAll()
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self.edit_te.mergeCurrentCharFormat(fmt)

        # 恢复光标
        self.edit_te.setTextCursor(cursor)

        # 同步默认字体（让后续输入也是这个字号）
        font = self.edit_te.document().defaultFont()
        font.setPointSize(size)
        self.edit_te.document().setDefaultFont(font)

    def on_bold_toggled(self, checked: bool):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if checked else QFont.Normal)
        self.edit_te.mergeCurrentCharFormat(fmt)

    def insert_image(self):
        url, _ = QFileDialog.getOpenFileName(
            self, '选择图片', '',
            '图片 (*.png *.jpg *.jpeg *.bmp *.gif)'
        )
        if not url:
            return

        img = QImage(url)
        if img.isNull():
            QMessageBox.warning(self, '提示', '无法读取图片')
            return

        base = os.path.basename(url)
        # 避免文件名里的空格/中文百分号被 Qt 转义后路径对不上
        base = base.replace(' ', '_')
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        name = f'{ts}_{base}'
        dst = os.path.join(IMAGE_DIR, name)
        try:
            shutil.copyfile(url, dst)
        except Exception as e:
            QMessageBox.warning(self, '拷贝失败', f'{e!r}')
            return

        fmt = QTextImageFormat()
        fmt.setName('images/' + name)

        # 限制最大宽度 1500，等比缩放
        max_w = 1500
        w, h = img.width(), img.height()
        if w > max_w:
            scale = max_w / w
            w = max_w
            h = int(h * scale)
        fmt.setWidth(w)
        fmt.setHeight(h)

        cursor = self.edit_te.textCursor()
        cursor.insertImage(fmt)

    def upload_file(self):
        url, _ = QFileDialog.getOpenFileName(
            self, '导入 HTML', '',
            'HTML (*.html *.htm);;所有文件 (*)'
        )
        if not url or not os.path.exists(url):
            return
        try:
            with open(url, 'r', encoding=ENCODING) as f:
                html = f.read()
        except Exception as e:
            QMessageBox.warning(self, '导入失败', f'{e!r}')
            return
        self.edit_te.setHtml(html)
        self.is_saved = False

    # ----- 保存 / 关闭 -----

    def save(self) -> bool:
        html = self.edit_te.toHtml()

        # 1) 若 Qt 把 baseUrl 前缀写进了 src，剥掉
        prefix = QUrl.fromLocalFile(
            os.path.abspath(MESSAGE_DIR) + os.sep
        ).toString()
        html = html.replace(prefix, '')

        # 2) 兜底：任何 file:///.../messages/ 前缀都还原为相对路径
        html = re.sub(
            r'src="file:///[^"]*?/messages/([^"]+)"',
            r'src="\1"',
            html
        )

        try:
            with open(self.filename, 'w', encoding=ENCODING) as f:
                f.write(html)
        except Exception as e:
            QMessageBox.warning(self, '保存失败', f'{e!r}')
            return False
        self.is_saved = True
        return True

    def closeEvent(self, e):
        if not self.is_saved:
            ans = QMessageBox.question(
                self, '提示', '是否保存？',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if ans == QMessageBox.Yes:
                if not self.save():
                    e.ignore()
                    return
            elif ans == QMessageBox.Cancel:
                e.ignore()
                return
        e.accept()