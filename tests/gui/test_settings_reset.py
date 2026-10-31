"""设置里的「删除全部数据 → 重跑向导」入口。

只测确认编排与守卫；真正删盘的动作由 bootstrap 的测试覆盖，
这里把 backup_all / reset_all 换成记录器，绝不碰真实数据。
"""

import pytest

import bootstrap
import UserSettings


class FakeMsgBox:
    """按队列返回答案，并记录被调用过哪些方法。"""

    Yes = 1
    No = 0

    def __init__(self, answers):
        self._answers = list(answers)
        self.calls = []

    def question(self, *args, **kwargs):
        self.calls.append('question')
        return self._answers.pop(0) if self._answers else self.No

    def warning(self, *args, **kwargs):
        self.calls.append('warning')

    def information(self, *args, **kwargs):
        self.calls.append('information')

    def critical(self, *args, **kwargs):
        self.calls.append('critical')


class FakeInputDialog:
    def __init__(self, text, ok=True):
        self.text = text
        self.ok = ok
        self.calls = 0

    def getText(self, *args, **kwargs):
        self.calls += 1
        return self.text, self.ok


class FakeApp:
    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


@pytest.fixture
def widget():
    return UserSettings.GeneralWidget()


def patch_env(monkeypatch, answers, name_text, name_ok=True):
    box = FakeMsgBox(answers)
    dialog = FakeInputDialog(name_text, name_ok)
    app = FakeApp()

    calls = {'backup': 0, 'reset': 0, 'reset_kwargs': None}

    def fake_backup():
        calls['backup'] += 1
        return 'C:/fake/backup/20260101_000000'

    def fake_reset(**kwargs):
        calls['reset'] += 1
        calls['reset_kwargs'] = kwargs

    monkeypatch.setattr(UserSettings, 'QMessageBox', box)
    monkeypatch.setattr(UserSettings, 'QInputDialog', dialog)
    monkeypatch.setattr(UserSettings, 'QApplication', type('A', (), {'instance': staticmethod(lambda: app)}))
    monkeypatch.setattr(bootstrap, 'backup_all', fake_backup)
    monkeypatch.setattr(bootstrap, 'reset_all', fake_reset)

    return box, dialog, app, calls


def test_button_exists(widget):
    assert '删除全部数据' in widget.wipe_btn.text()
    assert '首次使用向导' in widget.wipe_btn.text()


def test_declines_at_first_confirmation(widget, monkeypatch):
    box, _, app, calls = patch_env(monkeypatch, answers=[0], name_text='高三八班')
    widget._on_wipe_all()
    assert calls['backup'] == 0 and calls['reset'] == 0
    assert app.quit_called is False


def test_wrong_class_name_aborts(widget, monkeypatch):
    box, dialog, app, calls = patch_env(monkeypatch, answers=[1], name_text='错的班名')
    widget._on_wipe_all()
    assert dialog.calls == 1
    assert calls['reset'] == 0
    assert 'warning' in box.calls


def test_cancel_input_dialog_aborts(widget, monkeypatch):
    box, dialog, app, calls = patch_env(
        monkeypatch, answers=[1], name_text='', name_ok=False)
    widget._on_wipe_all()
    assert calls['reset'] == 0


def test_declines_at_final_confirmation(widget, monkeypatch):
    """第一重同意、名字正确，但最后一重选 No —— 必须什么都不删。"""
    box, dialog, app, calls = patch_env(
        monkeypatch, answers=[1, 0], name_text=_short_name())
    widget._on_wipe_all()
    assert calls['reset'] == 0
    assert app.quit_called is False


def test_full_confirmation_wipes_and_quits(widget, monkeypatch):
    box, dialog, app, calls = patch_env(
        monkeypatch, answers=[1, 1], name_text=_short_name())
    widget._on_wipe_all()
    assert calls['backup'] == 1
    assert calls['reset'] == 1
    assert calls['reset_kwargs'] == {'keep_messages': False}
    assert 'information' in box.calls
    assert app.quit_called is True


def _short_name():
    from config import load_user_settings
    return load_user_settings().get('class_short_name', '')
