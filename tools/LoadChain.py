from PySide6.QtCore import Signal, QObject, QThreadPool, QRunnable
from PySide6.QtWidgets import QWidget


class ChainSignals(QObject):
    step_finished = Signal(str, int, bool)
    result = Signal(object, dict)
    done = Signal(object, bool)  # 传 chain 自身，便于主线程执行 play


class Chain(QRunnable):
    def __init__(self, parent=None, widget=None, name='Chain'):
        super().__init__()
        self.parent = parent
        self.name = name
        self._cancelled = False
        self._result = {}
        self._connected = False

        if isinstance(widget, QWidget):
            self.widget = widget
        elif isinstance(parent, QWidget):
            self.widget = parent
        else:
            self.widget = None

        self.signals = ChainSignals()
        self.step_finished = self.signals.step_finished
        self.result = self.signals.result
        self.done = self.signals.done

    def run(self):
        # play 已移出，交由 ChainPool._on_done 在主线程执行
        steps = (self.load, lambda: self.input(self.widget), self.process)
        ok = True
        for idx, fn in enumerate(steps):
            if self._cancelled:
                ok = False
                break
            try:
                fn()
                self.step_finished.emit(self.name, idx, True)
            except Exception as e:
                ok = False
                self.step_finished.emit(self.name, idx, False)
                print(f'[{self.name}] step {idx} failed: {e!r}')
                break
        self.done.emit(self, ok)

    def cancel(self):
        self._cancelled = True

    def load(self): pass
    def input(self, widget): pass
    def process(self): pass
    def play(self, widget): pass

    def emit(self, data: dict):
        self._result.update(data)
        self.result.emit(self, data)


class ChainPool(QThreadPool):
    all_done = Signal()
    chain_result = Signal(str, dict)
    chain_step = Signal(str, int, bool)

    def __init__(self, parent=None, max_threads=4):
        super().__init__(parent)
        self.setMaxThreadCount(max_threads)
        self.results = {}
        self._pending = 0

    def load(self, chain: Chain, autoDelete=False, priority=0):
        chain.setAutoDelete(autoDelete)
        chain.parent = self
        # 同一个 chain 可能被重复提交，避免信号重复连接
        if not chain._connected:
            chain.result.connect(self._on_result)
            chain.step_finished.connect(self.chain_step)
            chain.done.connect(self._on_done)
            chain._connected = True
        self._pending += 1
        self.start(chain, priority)

    def _on_result(self, chain, data):
        self.results.update(data)
        self.chain_result.emit(chain.name, data)

    def _on_done(self, chain, ok):
        if ok:
            try:
                chain.play(chain.widget)
            except Exception as e:
                print(f'[{chain.name}] play failed: {e!r}')
        self._pending = max(0, self._pending - 1)
        if self._pending == 0:
            self.all_done.emit()

    def __getitem__(self, key):
        return self.results[key]

    def __setitem__(self, key, value):
        self.results[key] = value

    def is_idle(self) -> bool:
        return self._pending == 0