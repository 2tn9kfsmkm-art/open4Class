def topParent(obj):
    if obj.parent():
        return topParent(obj.parent())
    return obj


def _searchParentAttr(obj, attr, parent_with_attr=None):
    if parent_with_attr is None:
        parent_with_attr = []
    if hasattr(obj, attr):
        parent_with_attr.append(obj)
    if obj.parent():
        return _searchParentAttr(obj.parent(), attr, parent_with_attr)
    return parent_with_attr


def searchAttr(obj, attr):
    return _searchParentAttr(obj, attr)