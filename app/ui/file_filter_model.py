"""Proxy filtering/sorting with explicit filesystem-index mapping."""

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt

from app.services.search_service import matches


class FileFilterModel(QSortFilterProxyModel):
    def __init__(self, source, location: str, parent=None) -> None:
        super().__init__(parent)
        self.location = location
        self.query = self.extension_filter = self.category = ""
        self.setSourceModel(source)
        self.setDynamicSortFilter(True)

    def set_filters(self, query: str, extension_filter: str, category: str) -> None:
        self.beginFilterChange()
        self.query, self.extension_filter, self.category = query, extension_filter, category
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        source = self.sourceModel()
        if source.filePath(parent) != self.location:
            return True  # Never filter the root's ancestors or scan descendants.
        index = source.index(row, 0, parent)
        return matches(source.fileName(index), source.isDir(index), self.query, self.extension_filter, self.category)

    def lessThan(self, left, right) -> bool:
        source = self.sourceModel()
        first, second = source.fileInfo(left), source.fileInfo(right)
        column = left.column()
        def key(info, index):
            value = (info.fileName().casefold(), info.size(), source.type(index), info.lastModified().toMSecsSinceEpoch())[column]
            return value, info.fileName().casefold()
        return key(first, left) < key(second, right)

    def index(self, *args):
        if args and isinstance(args[0], str):
            return self.mapFromSource(self.sourceModel().index(*args))
        return super().index(*args)

    def filePath(self, index):
        return self.sourceModel().filePath(self.mapToSource(index))

    def fileName(self, index):
        return self.sourceModel().fileName(self.mapToSource(index))

    def isDir(self, index):
        return self.sourceModel().isDir(self.mapToSource(index))

    def isReadOnly(self):
        return self.sourceModel().isReadOnly()
