"""从云端导入传输账号的对话框。

老师先在 class-setup 网页端填好数据、生成一组 24 小时有效的传输账号，
这里输入 6 位账号 + 12 位密码，把数据取回来填进向导。

约定：
- 只负责「拉取 + 解密 + 校验」，拿到 ``ImportPreview`` 就 accept，填表由向导完成；
- 密码只在本进程内存里用一次，不写配置、不进日志；
- 服务器地址记进 settings（``cloud_server``），账号密码不记。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from config import load_user_settings, save_user_settings
from services.class_api import DEFAULT_SERVER, normalize_account, normalize_password
from services.cloud_import import CloudImportError, ImportPreview, fetch_preview


class _FetchWorker(QThread):
    """后台拉取，避免 PBKDF2 + 网络把对话框卡住。"""

    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, server: str, account: str, password: str, parent=None):
        super().__init__(parent)
        self._server = server
        self._account = account
        self._password = password

    def run(self) -> None:  # noqa: D401
        try:
            self.succeeded.emit(
                fetch_preview(self._server, self._account, self._password))
        except CloudImportError as exc:
            self.failed.emit(exc)
        except Exception as exc:                      # noqa: BLE001
            self.failed.emit(CloudImportError(f'导入失败：{exc}'))


class CloudImportDialog(QDialog):
    """输入账号密码 → 返回 ``ImportPreview``。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preview: ImportPreview | None = None
        self._thread: _FetchWorker | None = None
        self._cursor_overridden = False

        self.setWindowTitle('从云端导入')
        self.setModal(True)
        self.setMinimumWidth(520)
        self._build_ui()

    # ------------------------------------------------------------ 界面
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(12)

        title = QLabel('从云端导入班级数据')
        title.setStyleSheet('font-size: 15pt; font-weight: bold; color: #1A1A1A;')
        root.addWidget(title)

        desc = QLabel(
            '老师可以在网页端填好名单、课表、作息和值日规则，'
            '生成一组 24 小时有效的「传输账号 + 密码」。在这里输入即可导入，'
            '之后每一页仍然可以修改。'
        )
        desc.setWordWrap(True)
        desc.setStyleSheet('font-size: 10.5pt; color: #666666;')
        root.addWidget(desc)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        cfg = load_user_settings()
        self.server_edit = QLineEdit(str(cfg.get('cloud_server') or DEFAULT_SERVER))
        self.server_edit.setMinimumWidth(360)
        form.addRow('服务器地址：', self.server_edit)

        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText('ABC-DEF')
        self.account_edit.setMaxLength(16)
        form.addRow('传输账号：', self.account_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText('XXXX-XXXX-XXXX')
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setMaxLength(20)
        form.addRow('传输密码：', self.password_edit)

        self.show_pw_cb = QCheckBox('显示密码')
        self.show_pw_cb.toggled.connect(self._toggle_password)
        form.addRow('', self.show_pw_cb)
        root.addLayout(form)

        self.hint = QLabel('账号 24 小时内有效；密码只在本机内存中使用，不会保存。')
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet('font-size: 9.5pt; color: #888888;')
        root.addWidget(self.hint)

        self.error_l = QLabel()
        self.error_l.setWordWrap(True)
        self.error_l.setStyleSheet(
            'font-size: 10pt; color: #C62828; background: #FDF0F0;'
            'border: 1px solid #F0C0C0; border-radius: 6px; padding: 8px;')
        self.error_l.hide()
        root.addWidget(self.error_l)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet('color: #E3E5E8;')
        root.addWidget(line)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.setStyleSheet('font-size: 11pt; padding: 6px 18px; color: #666666;')
        self.import_btn = QPushButton('导入')
        self.import_btn.setStyleSheet(
            'font-size: 11pt; padding: 6px 24px; background: #9b0d14; color: white;'
            'border: none; border-radius: 4px;')
        self.import_btn.setDefault(True)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.import_btn)
        root.addLayout(buttons)

        self.cancel_btn.clicked.connect(self.reject)
        self.import_btn.clicked.connect(self._on_import)
        self.password_edit.returnPressed.connect(self._on_import)
        self.account_edit.returnPressed.connect(self._on_import)

    def _toggle_password(self, checked: bool) -> None:
        self.password_edit.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password)

    # ------------------------------------------------------------ 交互
    def _inputs(self) -> tuple[str, str, str]:
        return (
            self.server_edit.text().strip() or DEFAULT_SERVER,
            normalize_account(self.account_edit.text()),
            normalize_password(self.password_edit.text()),
        )

    def validation_error(self) -> str | None:
        """本地校验；返回错误文案，None 表示可以发请求。"""
        server, account, password = self._inputs()
        if not server.lower().startswith(('http://', 'https://')):
            return '服务器地址要以 http:// 或 https:// 开头'
        if len(account) != 6:
            return '传输账号应为 6 位，例如 ABC-DEF'
        if len(password) != 12:
            return '传输密码应为 12 位，例如 XXXX-XXXX-XXXX'
        return None

    def _on_import(self) -> None:
        error = self.validation_error()
        if error:
            self._show_error(error)
            return

        self.error_l.hide()
        self._set_busy(True)
        server, account, password = self._inputs()
        self._thread = _FetchWorker(server, account, password, self)
        self._thread.succeeded.connect(self._on_success)
        self._thread.failed.connect(self._on_failed)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _set_busy(self, busy: bool) -> None:
        self.import_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(not busy)
        for widget in (self.server_edit, self.account_edit, self.password_edit,
                       self.show_pw_cb):
            widget.setEnabled(not busy)
        self.import_btn.setText('导入中…' if busy else '导入')
        self._apply_busy_cursor(busy)

    def _apply_busy_cursor(self, busy: bool) -> None:
        """维护全局等待光标。

        必须自己记着有没有 push 过：``restoreOverrideCursor()`` 是弹栈，
        多调一次会把别的窗口（或 Qt 自己）压进去的光标弹掉。
        """
        if busy:
            if not self._cursor_overridden:
                QGuiApplication.setOverrideCursor(Qt.WaitCursor)
                self._cursor_overridden = True
        elif self._cursor_overridden:
            QGuiApplication.restoreOverrideCursor()
            self._cursor_overridden = False

    def _show_error(self, message: str) -> None:
        self.error_l.setText(message)
        self.error_l.show()

    def _on_success(self, preview: object) -> None:
        if not isinstance(preview, ImportPreview):
            self._show_error('云端返回的数据无法识别')
            return
        self._remember_server()
        self.preview = preview
        self.accept()

    def _on_failed(self, exc: object) -> None:
        message = str(exc) if exc is not None else ''
        self._show_error(message or '导入失败')

    def _on_thread_finished(self) -> None:
        self._thread = None
        # 成功时 _on_success 已经 accept() 把对话框藏起来了，这里不能再看
        # isVisible()，否则等待光标会一直留在整个应用上。
        self._set_busy(False)

    def done(self, result: int) -> None:          # noqa: D401
        """accept / reject / 关闭 都走这里：先收掉等待光标和禁用状态。"""
        self._set_busy(False)
        super().done(result)

    def _remember_server(self) -> None:
        server = self.server_edit.text().strip()
        if not server:
            return
        try:
            settings = load_user_settings()
            if settings.get('cloud_server') != server:
                settings['cloud_server'] = server
                save_user_settings(settings)
        except OSError:
            pass                      # 记不住地址不影响导入

    # ------------------------------------------------------------ 收尾
    def _busy(self) -> bool:
        return self._thread is not None

    def reject(self) -> None:          # noqa: D401
        if self._busy():
            return                     # 拉取中不允许关闭，避免线程悬空
        super().reject()

    def closeEvent(self, event) -> None:   # noqa: N802
        if self._busy():
            event.ignore()
            return
        self.password_edit.clear()
        super().closeEvent(event)
