from pandas import DataFrame, read_csv, isna, concat
from pandas.core.indexing import _AtIndexer, _iAtIndexer, _LocIndexer, _iLocIndexer
from pandas._libs.lib import infer_dtype

from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Signal, QObject, QAbstractItemModel, QSortFilterProxyModel, Qt, QModelIndex

from core.shape import unpack_index, unpack_str_index
import os

#PandasQItemModel:支持pandas操作的QItemModel
#PandasQProxyModel:配套的带有纵向过滤的model
#divideModel:可控更新的QItemModel,autoUpdate为True时自动更新,略等于proxyModel,但是可以增加项

#以下是对dataframe的改造，使其可以用dataframe的方法修改

_e = type(...)

class PandasError(Exception):...


class DataFrameWS(DataFrame, QObject):
    dataChanged = Signal(object, object)

    def __init__(self, *args, parent=None, data=None, **kwargs):
        super().__init__(data, *args, **kwargs)
        QObject.__init__(self, parent=parent)

    def _emit_data_changed(self, key, is_label):
        parent = self.parent()
        if parent is None:
            return

        # 数据已经写进去了，这里只是通知视图刷新。
        # 万一某个写入路径的索引形态解不出来（例如布尔掩码），
        # 宁可不刷新也不能把写操作本身弄崩。
        try:
            if is_label:
                (r0, c0), (r1, c1) = unpack_str_index(
                    key, (self.index, self.columns)
                )
            else:
                (r0, c0), (r1, c1) = unpack_index(
                    key, (len(self), len(self.columns))
                )

            if getattr(parent, 'extraHeader', False):
                r0 += 1
                r1 += 1

            top_left = parent.index(r0, c0)
            bottom_right = parent.index(r1, c1)
            if top_left.isValid() and bottom_right.isValid():
                parent.dataChanged.emit(top_left, bottom_right)
        except Exception as e:
            print(f'[PandasQModel] dataChanged 范围解析失败，已跳过刷新: {e!r}')

    class _LocIndexerWS(_LocIndexer):
        def __setitem__(self, key, value):
            result = super().__setitem__(key, value)
            self.obj._emit_data_changed(key, True)
            return result

    class _iLocIndexerWS(_iLocIndexer):
        def __setitem__(self, key, value):
            result = super().__setitem__(key, value)
            self.obj._emit_data_changed(key, False)
            return result

    class _AtIndexerWS(_AtIndexer):
        def __setitem__(self, key, value):
            result = super().__setitem__(key, value)
            self.obj._emit_data_changed(key, True)
            return result

    class _iAtIndexerWS(_iAtIndexer):
        def __setitem__(self, key, value):
            result = super().__setitem__(key, value)
            self.obj._emit_data_changed(key, False)
            return result

    # 下面四个属性是把上面的 WS indexer 真正"装上"的唯一入口。
    # 之前只定义了子类却没有覆盖属性，pandas 仍然返回原生 indexer，
    # 所以通过 df.loc/iloc/at/iat 写入时从来不会发 dataChanged。
    @property
    def loc(self):
        return self._LocIndexerWS("loc", self)

    @property
    def iloc(self):
        return self._iLocIndexerWS("iloc", self)

    @property
    def at(self):
        return self._AtIndexerWS("at", self)

    @property
    def iat(self):
        return self._iAtIndexerWS("iat", self)

#class PandasQAbstractModel()

class PandasQItemModel(QAbstractItemModel):
    def __init__(self, data=None, parent=None,
                 alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
                 extraHeader: bool = False):
        super().__init__(parent=parent)

        self.alignment = alignment
        self.extraHeader = extraHeader
        self._bind_df(data)

    def _bind_df(self, data=None):
        self._df = DataFrameWS(data=data, parent=self)
        self.loc = self._df.loc
        self.iloc = self._df.iloc
        self.at = self._df.at
        self.iat = self._df.iat


    #设置是否要添加额外的表头
    def setExtraHeader(self, a0:bool):
        self.extraHeader = a0
    
    #设置对齐
    def setAlignment(self, alignment):
        self.alignment = alignment

    #允许直接用DataFrame的方式修改model
    def __setitem__(self, key, value):
        self._df[key] = value   

    #允许像DataFrame一样访问Model数据
    def __getitem__(self, key):
        return self._df[key]

    #获取具体的数据
    def data(self, index, role = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
        # 检查索引是否在有效范围内
        if index.row() < 0 or index.row() >= self.rowCount() or \
            index.column() < 0 or index.column() >= self.columnCount():
            return None
        
        if role in [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]:#如果请求是是编辑/显示,返回相应内容
            if self.extraHeader:    #如果要额外表头
                if index.row() == 0:    #如果访问第一行,那么提供表头
                    value = self._df.columns[index.column()]
                else:   #否则提供具体的数据(现有索引-1)
                    value = self._df.iat[index.row()-1, index.column()]#这里溢出发生,不可合并
            else:
                value = self._df.iat[index.row(), index.column()]#提供正常数据
            return str(value) if not isna(value) else ''#如果该值时空值(pandas的NaN)那么返回''
        
        if role == Qt.ItemDataRole.TextAlignmentRole:#如果是对齐,那么返回设置的对齐方式
            return self.alignment
        
        return None         #其余情况返回空
    
    #获取列数
    def columnCount(self, parent = QModelIndex()):
        return 0 if parent.isValid() else self._df.shape[1]
    
    #获取行数
    def rowCount(self, parent = QModelIndex()):
        row = self._df.shape[0]
        if parent.isValid():
            return 0
        if self.extraHeader:
            return row+1
        else:
            return row
        #如果要额外标题,那么实际显示的会多一行
    
    #获取表头数据(Qt的要求)
    def headerData(self, section, orientation, role = Qt.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:#判断是不是正确的类型
            #判断是横表头还是纵表头
            if orientation == Qt.Orientation.Horizontal:#如果是横表头
                if section in range(len(self._df.columns)):#如果选择区域在范围内
                    return str(self._df.columns[section])
                return None
            
            elif orientation == Qt.Orientation.Vertical:#如果是纵表头(要考虑额外标题)
                if self.extraHeader:#如果有额外标题
                    if section in range(1, len(self._df.index)+1):#要多考虑一个标题,因为返回给qt的数据长度比_df的长度长1
                        return str(self._df.index[section-1])
                    elif section == 0:
                        return 'header'
                else:
                    if section in range(0, len(self._df.index)):
                        return str(self._df.index[section])
                return None
            
        return None
    

    #设置数据(qt的要求)
    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            try:
                if self.extraHeader and index.row() == 0:
                    # pandas 3 里 df.columns.values 是只读的 StringArray，
                    # 不能原地赋值；整体替换 columns 才能改列名
                    new_columns = list(self._df.columns)
                    new_columns[index.column()] = value
                    self._df.columns = new_columns
                    self.headerDataChanged.emit(
                        Qt.Orientation.Horizontal,
                        index.column(),
                        index.column()
                    )
                    self.dataChanged.emit(index, index)
                    return True

                row = index.row() - (1 if self.extraHeader else 0)
                # self._df.iat 会通过 _iAtIndexerWS 自动发 dataChanged
                self._df.iat[row, index.column()] = value
                return True
            except Exception as e:
                raise PandasError(e)

        return False

   #转为数据列表 
    def to_data(self, defaultNone=None, header=False):
        rows = self.rowCount()
        cols = self.columnCount()
        data = []

        # 没有额外表头但要求输出表头时，手动补一行列名
        if header and not self.extraHeader:
            data.append([
                self.headerData(c, Qt.Orientation.Horizontal)
                for c in range(cols)
            ])

        # extraHeader=True 且不要表头时，跳过模型第 0 行
        start = 1 if (self.extraHeader and not header) else 0

        for r in range(start, rows):
            row_data = []
            for c in range(cols):
                item = self.data(self.index(r, c))
                row_data.append(defaultNone if item is None else item)
            data.append(row_data)

        return data
    
    #转为代理模型
    def to_proxyModel(self, filter, alignment=Qt.AlignmentFlag.AlignLeft):
        proxy = PandasQProxyModel(parent=self, alignment=alignment)
        proxy.setSourceModel(self)
        proxy.setColumnFilter(filter)
        return proxy 
    
    #通过proxyModel转化为divideModel(这样具有一定的过滤功能)
    def to_divideModel_with_filter(self, filter,
                                   alignment: Qt.AlignmentFlag = ...,
                                   autoUpdate: bool = False,
                                   extraHeader: bool = ...):
        _extraHeader = self.extraHeader if isinstance(extraHeader, _e) else extraHeader
        _alignment = self.alignment if isinstance(alignment, _e) else alignment

        proxy = self.to_proxyModel(filter, alignment=_alignment)
        return proxy.to_divideModel(
            autoUpdate=autoUpdate,
            alignment=_alignment,
            extraHeader=_extraHeader
        )
    
    #转化为divideModel(具有缓存功能的Model)
    
    def to_divideModel(self, key,
                       alignment: Qt.AlignmentFlag = ...,
                       autoUpdate: bool = False,
                       extraHeader: bool = ...):
        _extraHeader = self.extraHeader if isinstance(extraHeader, _e) else extraHeader
        _alignment = self.alignment if isinstance(alignment, _e) else alignment

        if isinstance(key, str):
            data = self._df[[key]]
        elif isinstance(key, slice):
            data = self._df.loc[:, key]
        else:
            raise TypeError(f'unsupported key type: {type(key)}')

        return divideModel(
            data=data,
            resource=self,
            autoUpdate=autoUpdate,
            alignment=_alignment,
            extraHeader=_extraHeader
        )

    #获取表的标题(使用的方法)
    def getHeader(self):
        return list(self._df.columns)
    
    def index(self, row, column, parent = QModelIndex()):
        # 移除 qt 参数，简化逻辑
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        # 对于 extraHeader 情况，确保索引创建正确
        if self.extraHeader:
            # 确保 row 在有效范围内
            if row < 0 or row >= self.rowCount() or column < 0 or column >= self.columnCount():
                return QModelIndex()
        else:
            if row < 0 or row >= len(self._df) or column < 0 or column >= len(self._df.columns):
                return QModelIndex()
        
        return self.createIndex(row, column)
    
    #返回每父类(暂时不用)(Qt要求)
    def parent(self, index=None):
        return QModelIndex()
    
    #每一个单元格的"标志"(Qt要求)
    def flags(self, index):
        if index.isValid():
            if self.extraHeader and index.row() == 0:
                return Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable
                #若为标题设置为:可用、可以选择、可以编辑、不可拖放
            else:
                return Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable|\
                    Qt.ItemFlag.ItemIsDragEnabled|Qt.ItemFlag.ItemIsDropEnabled#若不是标题,则为可用、可以选择、可以编辑、可拖放
        return Qt.ItemFlag.NoItemFlags
    
    #合并几个DataFrame的数据
    def concat(self, df_list: list, ahead=False, **kwargs):
        self.beginResetModel()
        try:
            if ahead:
                new_df = concat(df_list + [self._df], **kwargs)
            else:
                new_df = concat([self._df] + df_list, **kwargs)
            self._bind_df(new_df)
        finally:
            self.endResetModel()


class PandasQProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None, alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__(parent)
        self._column_filter = []
        self.alignment = alignment

    def lessThan(self, left, right):
        source = self.sourceModel()
        if source is None:
            return super().lessThan(left, right)

        ls = self.mapToSource(left)
        rs = self.mapToSource(right)
        if not ls.isValid() or not rs.isValid():
            return False

        has_extra = bool(getattr(source, 'extraHeader', False))

        if has_extra and (ls.row() == 0 or rs.row() == 0):
            return str(source.data(ls)) < str(source.data(rs))

        lrow = ls.row() - (1 if has_extra else 0)
        rrow = rs.row() - (1 if has_extra else 0)

        try:
            left_data = source._df.iloc[lrow, ls.column()]
            right_data = source._df.iloc[rrow, rs.column()]
        except Exception:
            return False

        if isna(left_data) and isna(right_data):
            return False
        if isna(left_data):
            return True
        if isna(right_data):
            return False

        try:
            return float(left_data) < float(right_data)
        except (ValueError, TypeError):
            return str(left_data) < str(right_data)

    def setColumnFilter(self, _filter):
        self._column_filter = [] if _filter is None else _filter
        self.invalidateFilter()

    def filterAcceptsColumn(self, source_column, source_parent):
        if not self._column_filter:
            return True

        source_model = self.sourceModel()
        if source_model is None:
            return True

        if isinstance(self._column_filter, range):
            return source_column in self._column_filter

        if isinstance(self._column_filter, list):
            if source_column >= len(source_model._df.columns):
                return False
            column_name = source_model._df.columns[source_column]
            return (column_name in self._column_filter) or (source_column in self._column_filter)

        raise TypeError(f'unsupported filter type: {type(self._column_filter)}')

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self.alignment
        return super().data(index, role)

    def setAlignment(self, alignment):
        self.alignment = alignment

    def to_data(self, defaultNone=None, header=True):
        rows = self.rowCount()
        cols = self.columnCount()
        source = self.sourceModel()
        has_extra = bool(getattr(source, 'extraHeader', False))

        data = []

        # 源模型没有额外表头时，输出 header=True 就手动补一行列名
        if header and not has_extra:
            data.append([
                self.headerData(c, Qt.Orientation.Horizontal)
                for c in range(cols)
            ])

        start = 1 if (has_extra and not header) else 0

        for r in range(start, rows):
            row_data = []
            for c in range(cols):
                item = self.data(self.index(r, c))
                row_data.append(defaultNone if item is None else item)
            data.append(row_data)

        return data

    def to_pd(self, header=False, defaultNone=None):
        cols = self.columnCount()
        source = self.sourceModel()
        has_extra = bool(getattr(source, 'extraHeader', False))

        data = self.to_data(defaultNone=defaultNone, header=header)

        if header:
            if not data:
                return DataFrame()
            title = data[0]
            rows = data[1:]
            data_proxy_start = 1 if has_extra else 0
        else:
            title = list(range(cols))
            rows = data
            data_proxy_start = 1 if has_extra else 0

        df = DataFrame(rows, columns=title)

        # 尽量保留源 DataFrame 的索引，方便 divideModel 回写
        try:
            if source is not None and len(rows) > 0 and cols > 0:
                idx = []
                for i in range(len(rows)):
                    proxy_row = data_proxy_start + i
                    src_idx = self.mapToSource(self.index(proxy_row, 0))
                    src_row = src_idx.row() - (1 if has_extra else 0)
                    idx.append(source._df.index[src_row])
                df.index = idx
        except Exception:
            pass

        return df

    def to_divideModel(self,
                       alignment: Qt.AlignmentFlag = ...,
                       autoUpdate: bool = False,
                       extraHeader: bool = ...):
        source = self.sourceModel()

        if isinstance(extraHeader, _e):
            extraHeader = bool(getattr(source, 'extraHeader', False))

        _alignment = self.alignment if isinstance(alignment, _e) else alignment

        return divideModel(
            parent=self,
            data=self.to_pd(header=True),
            resource=source,
            autoUpdate=autoUpdate,
            alignment=_alignment,
            extraHeader=extraHeader
        )
    

class divideModel(PandasQItemModel):
    def __init__(self, parent=None, data=None, resource: PandasQItemModel = None,
                 autoUpdate: bool = False, extraHeader: bool = False,
                 alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__(
            data=data,
            parent=parent,
            extraHeader=extraHeader,
            alignment=alignment
        )
        self.resource = resource
        self.autoUpdate = autoUpdate
        if autoUpdate:
            self.dataChanged.connect(self.update)

    def setAutoUpdate(self, a0: bool):
        if a0 == self.autoUpdate:
            return

        if a0:
            self.dataChanged.connect(self.update)
        else:
            try:
                self.dataChanged.disconnect(self.update)
            except TypeError:
                pass

        self.autoUpdate = a0

    def update(self, *args):
        if self.resource is None:
            return

        src = self.resource._df
        df = self._df

        # 新增列
        for col in df.columns:
            if col not in src.columns:
                src[col] = df[col]

        # 按索引回写/新增行
        if len(df.index) > 0 and len(df.columns) > 0:
            src.loc[df.index, df.columns] = df

        self.resource.layoutChanged.emit()

    def setAllData(self, data: DataFrame):
        self.beginResetModel()
        try:
            self._bind_df(data)
        finally:
            self.endResetModel()




def q_read_csv(path:str, *args, encoding:str='utf-8', **kwargs):
    if not os.path.exists(path):
        raise FileNotFoundError(f'File {path} does not exist')
        
    data = read_csv(path, *args, encoding=encoding, index_col=False, **kwargs)
    return PandasQItemModel(data=data)