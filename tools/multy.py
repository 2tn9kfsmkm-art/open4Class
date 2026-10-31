
#用于批量选中data字典中元素/任意元素以进行操作
#target可以是list[str]或者是str
#operate是函数,要求有一个输入为需要被操作的单个对象的函数
def apply(data, target:list[str]|str, operate):
    if isinstance(target, str):
        operate(data[target])
    elif isinstance(target, list):
        for i in target:
            operate(data[i])
    elif isinstance(target, type(None)):
        for i in data:
            operate(data[i])