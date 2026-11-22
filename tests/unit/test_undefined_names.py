"""静态守卫：函数里引用了模块级不存在的名字。

这类错误 `py_compile` 和 `import` 都查不出来——只有执行到那一行才会
`NameError`。v1.0.0 的启动崩溃就是这么来的：

    main.py 里 `from PySide6.QtCore import QTimer as _QTimer` 被删掉了，
    但 `_QTimer.singleShot(0, _force_maximize)` 还在，
    于是每次启动都崩在 `main()` 里，窗口一个都不出来。

用 `symtable` 静态检查：函数体里引用、既不是模块级名字也不是内置名的标识符，
就是运行时必炸的悬空引用。

已知边界：含 `from x import *` 的文件无法静态解析（跳过），
`globals()` / `exec()` 动态注入名字的模块也不适用。
"""

import builtins
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKIP_DIRS = {
    '.git', '__pycache__', '.pytest-appdata', '.test-tmp', '.pytest_cache',
    'build', 'installer', 'dist',
}
_BUILTIN = set(dir(builtins))


def _project_files():
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield path, rel


def _undefined_names(path):
    """返回 [(所在函数名, 未定义的名字)]。"""
    src = path.read_text(encoding='utf-8-sig', errors='replace')
    if 'import *' in src:                       # 静态解析不了
        return None
    top = symtable.symtable(src, str(path), 'exec')
    module_names = set(top.get_identifiers())
    found = []

    def walk(table):
        for sym in table.get_symbols():
            if sym.is_global() and not sym.is_assigned():
                name = sym.get_name()
                if (name not in module_names and name not in _BUILTIN
                        and not name.startswith('__')):
                    found.append((table.get_name(), name))
        for child in table.get_children():
            walk(child)

    for child in top.get_children():
        walk(child)
    return found


def test_no_undefined_global_names():
    problems = []
    checked = 0
    skipped = []
    for path, rel in _project_files():
        result = _undefined_names(path)
        if result is None:
            skipped.append(str(rel))
            continue
        checked += 1
        problems.extend(f'{rel} :: {func}() -> {name}'
                        for func, name in result)

    assert checked > 20, '扫描到的模块太少，路径可能不对'
    assert not problems, (
        '以下地方引用了不存在的名字，执行到就会 NameError：\n  '
        + '\n  '.join(problems)
        + (f'\n（已跳过含 import * 的文件：{len(skipped)} 个）' if skipped else '')
    )


def test_entry_module_uses_defined_timer():
    """回归：main.py 的启动路径不得再出现 `_QTimer` 这类别名残留。"""
    src = (ROOT / 'main.py').read_text(encoding='utf-8-sig')
    assert 'QTimer.singleShot' in src
    assert '_QTimer' not in src
