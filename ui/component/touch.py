"""触摸滚动支持。

希沃一体屏上手指直接拖内容（QScroller 手势），不必去抓那条细滚动条；
鼠标操作不受影响——QScroller 用 LeftMouseButtonGesture 时，会先判断是否是拖拽。
"""

from PySide6.QtWidgets import QAbstractScrollArea, QScroller


def enable_touch_scroll(widget) -> None:
    """给滚动区/表格启用"手指拖内容"的手势。"""
    if widget is None:
        return
    target = widget.viewport() if isinstance(widget, QAbstractScrollArea) else widget
    try:
        QScroller.ungrabGesture(target)
        QScroller.grabGesture(target, QScroller.ScrollerGestureType.LeftMouseButtonGesture)
    except Exception as e:                      # noqa: BLE001
        print(f'[touch] 启用触摸滚动失败: {e!r}')
