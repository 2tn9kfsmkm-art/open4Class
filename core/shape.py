def find(target, data, defaultNone=None):
    if target is None:
        if isinstance(defaultNone, type(None)):
            result = []
        else:
            result = [defaultNone]
    else:
        result = [idx for idx, i in enumerate(data) if i == target]
    return result


def findItem(target, data, defaultNone=None):
    result = []
    for irow, row in enumerate(data):
        result += [(irow, icol) for icol in find(target, row, defaultNone=None)]
    if not result and defaultNone is not None:
        result = [defaultNone]
    return result


def checkIndex(key, data):
    if len(data) == 0:
        raise KeyError(key)
    if len(data) > 1:
        raise KeyError(f'index "{key}" is not unique, qualified index:{data}')


def checkIndexRange(key, stop):
    if key not in range(stop):
        raise KeyError(key)


def findone(target, data, defaultNone=None):
    if target is None:
        return defaultNone
    for idx, i in enumerate(data):
        if i == target:
            return idx
    return None


def compare(data1, data2):
    if len(data1) != len(data2):
        return -1
    for idx, (i, j) in enumerate(zip(data1, data2)):
        if i != j:
            return idx
    return -2


def is_listlike(self, value):
    return isinstance(value, (range, list, tuple))


def indexAnalyze(key, data):
    pass


def reshapeCol(data, col, defaultNone=None):
    result = []
    icol = 0
    while len(data) >= col * (icol + 1):
        result.append(data[col * icol:col * (icol + 1)])
        icol += 1
    if col * icol != len(data):
        last_col = data[col * icol:]
        last_col += [defaultNone for _ in range(col - len(last_col) % col)]
        result.append(last_col)
    return result


def reshapeRow(data, row, defaultNone=None):
    """按列优先填充为 row 行；每行长度一致，不足处补 defaultNone。"""
    if row <= 0:
        raise ValueError('row must be positive')
    n = len(data)
    col_count = (n + row - 1) // row
    result = []
    for i in range(row):
        segment = list(data[i::row])
        if len(segment) < col_count:
            segment += [defaultNone] * (col_count - len(segment))
        result.append(segment)
    return result


def _norm_pos(i, n):
    i = int(i)
    if i < 0:
        i += n
    if i < 0 or i >= n:
        raise IndexError(i)
    return i


def _label_pos(label, labels, end=False):
    loc = labels.get_loc(label)
    if isinstance(loc, slice):
        if end:
            return (loc.stop - 1) if loc.stop is not None else len(labels) - 1
        return loc.start if loc.start is not None else 0
    if isinstance(loc, int):
        return loc
    try:
        import numpy as np
        if isinstance(loc, np.ndarray) and loc.dtype == bool:
            pos = np.flatnonzero(loc)
            return int(pos[-1] if end else pos[0])
        arr = list(loc)
        return int(arr[-1] if end else arr[0])
    except Exception:
        raise KeyError(label)


def _is_sequence_indexer(idx):
    """是否是需要逐项解包的"多项索引"。

    除了 list/tuple/range，还要认 pandas Index、numpy 数组这类可迭代对象 ——
    df.loc[df.index, df.columns] = ... 这种写法传进来的就是 Index。
    字符串、bytes、slice 是标量式索引，不能按迭代拆。
    """
    if isinstance(idx, (str, bytes, slice, type(None))):
        return False
    if isinstance(idx, (list, tuple, range)):
        return True
    return hasattr(idx, '__iter__')


def _unpack_pos_indexer(idx, n):
    if idx is None:
        return 0, n - 1
    if isinstance(idx, slice):
        start = 0 if idx.start is None else _norm_pos(idx.start, n)
        stop = n if idx.stop is None else _norm_pos(idx.stop, n)
        end = stop - 1 if stop > start else start
        return min(start, end), max(start, end)
    if _is_sequence_indexer(idx):
        pos = [_norm_pos(i, n) for i in idx]
        if not pos:
            return 0, 0
        return min(pos), max(pos)
    p = _norm_pos(idx, n)
    return p, p


def _unpack_label_indexer(idx, labels):
    n = len(labels)
    if idx is None:
        return 0, n - 1
    if isinstance(idx, slice):
        start = 0 if idx.start is None else _label_pos(idx.start, labels, end=False)
        stop = n - 1 if idx.stop is None else _label_pos(idx.stop, labels, end=True)
        return min(start, stop), max(start, stop)
    if _is_sequence_indexer(idx):
        pos = []
        for i in idx:
            pos.append(_label_pos(i, labels, end=False))
            pos.append(_label_pos(i, labels, end=True))
        if not pos:
            return 0, 0
        return min(pos), max(pos)
    p = _label_pos(idx, labels, end=False)
    return p, p


def unpack_index(key, size):
    if not isinstance(key, tuple):
        key = (key, slice(None))
    if len(key) != 2:
        raise RuntimeError('unfinished')
    r0, r1 = _unpack_pos_indexer(key[0], size[0])
    c0, c1 = _unpack_pos_indexer(key[1], size[1])
    return (r0, c0), (r1, c1)


def unpack_str_index(key, labels):
    if not isinstance(key, tuple):
        key = (key, slice(None))
    if len(key) != 2:
        raise RuntimeError('unfinished')
    row_labels, col_labels = labels
    r0, r1 = _unpack_label_indexer(key[0], row_labels)
    c0, c1 = _unpack_label_indexer(key[1], col_labels)
    return (r0, c0), (r1, c1)