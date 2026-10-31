#日期和时间的转化

num2word_map = ['一', '二', '三', '四', '五', '六', '日']

def weekday2word(weekday:int|str, format='周%d', start = 0):
    if isinstance(weekday,int):
        _weekday = weekday
    elif isinstance(weekday, str):
        try:
            _weekday = int(weekday)
        except:
            raise TypeError('weekday')
    else:
        raise TypeError()
    _weekday -= start
    return '周'+num2word_map[_weekday]