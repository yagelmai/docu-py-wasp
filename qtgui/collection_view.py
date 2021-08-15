import datetime
from typing import Dict, Optional, List, Union, Any

from PyQt5 import Qt
from PyQt5.QtCore import QModelIndex
from PyQt5.QtGui import QContextMenuEvent

from py_wasp import FileValue, ReferenceValue, ViewConfig
from .json_view import JsonView


def _parse_datetime(json_str: str) -> Optional[datetime.datetime]:
    """
    Attempt to parse JSON datetime format
    :param json_str: Example: '2018-06-28T18:20:32.058Z', UTC timezone
    :return: datetime object or None
    """
    if json_str[-1] != 'Z':
        return None
    json_str = json_str[:-1] + '000Z'  # milli- to micro-

    try:
        dt = datetime.datetime.strptime(json_str, '%Y-%m-%dT%H:%M:%S.%fZ')
    except ValueError:
        return None

    dt = dt.replace(tzinfo=datetime.timezone.utc)

    return dt


def _format_time(time_str: str) -> str:
    """
    Re-format time string from Wasp
    :param time_str: string representation of time (Example: '2018-06-28T18:20:32.058Z')
    :return: string representation of time with the format %d-%m-%Y %H:%M:%S or time_str if parsing failed.
    """
    dt = _parse_datetime(time_str)
    if dt is None:
        return time_str

    # convert UTC to local through timestamp (which is UTC)
    dt = datetime.datetime.fromtimestamp(dt.timestamp())  # convert UTC to local

    return dt.strftime('%d-%m-%Y %H:%M:%S')


# should return True if the specified item is a history item for some other record
RECORD_ROLE = Qt.Qt.UserRole + 1
IS_LATEST_ROLE = Qt.Qt.UserRole + 2
IS_HISTORY_ROLE = Qt.Qt.UserRole + 3


class RecordsTableModel(Qt.QAbstractTableModel):
    """
    AbstractTableModel facade for CollectionViewModel object.
    Required for use with QTableView
    """
    def __init__(self, collection_viewmodel):
        super().__init__()
        self._records = []
        self._columns = []
        self._collection_vm = collection_viewmodel
        self._collection_vm.property_changed.connect(self._on_view_model_changed)

    @property
    def records(self) -> List[Dict[str, Union[str, FileValue, ReferenceValue, Dict]]]:
        """
        :return: List of all records in the model.
        """
        return self._records

    @property
    def columns(self) -> List[ViewConfig.Column]:
        """
        :return: List of all columns in the model.
        """
        return self._columns

    def _update(self, records: List[Dict[str, Union[str, FileValue, ReferenceValue, Dict]]],
                columns: List[ViewConfig.Column]):
        """
        update records and columns in the model.
        :param records: List of records to update.
        :param columns: List of columns to update
        """
        self.beginResetModel()
        self._records = records
        self._columns = columns
        self.endResetModel()

    def rowCount(self, parent=None, *args, **kwargs) -> int:
        """
        Returns the number of rows (records) in the model.
        :param parent:
        :param args:
        :param kwargs:
        :return: number of rows in the model.
        """
        return len(self.records)

    def columnCount(self, parent=None, *args, **kwargs) -> int:
        """
        Returns the number of columns in the model.
        :param parent:
        :param args:
        :param kwargs:
        :return: number of columns in the model.
        """
        return len(self.columns)

    def headerData(self, section: int, orientation: int, role: int) -> str or None:
        """
        Return column header data of a given section
        :param section: Section index (int)
        :param orientation: Qt Orientation (for example: Qt.Qt.Horizontal, Qt.Qt.Vertical ...)
        :param role: Qt Role (for example: Qt.Qt.DisplayRole, Qt.Qt.SizeHintRole ...)
        :return: Section header data (String)
        """
        if orientation != Qt.Qt.Horizontal:
            return None
        if role != Qt.Qt.DisplayRole:
            return None
        name = self._columns[section].name
        return ' '.join([n[0].upper() + n[1:] for n in name.split('_')])

    def data(self, index: QModelIndex, role: int) ->\
            Union[int, bool, str, Qt.QVariant, Dict[str, Union[str, FileValue, ReferenceValue, Dict]]] or None:
        """
        Returns model data based on index and display role.
        :param index: QModelIndex object.
        :param role: Qt display role.
        :return: Model data based on index and display role.
        """
        if not index.isValid():
            return Qt.QVariant()

        if role == Qt.Qt.TextAlignmentRole:
            return Qt.Qt.AlignCenter

        if role == RECORD_ROLE:
            return self._records[index.row()]

        record = self._records[index.row()]

        if role == IS_LATEST_ROLE:
            return self._collection_vm.is_latest(record['_id'])

        if role == IS_HISTORY_ROLE:
            return self._collection_vm.is_history(record['_id'])

        if role != Qt.Qt.DisplayRole:
            return None

        col = self._columns[index.column()]
        val = RecordsTableModel._try_get_prop(record, col.calculate_path if col.calculate_path else (col.name,))

        if col.name == 'date' and (col.calculate_path == ['date'] or not col.calculate_path):
            val = _format_time(val)

        return val

    def _on_view_model_changed(self, prop, value) -> None:
        """
        Update records and columns in the model when the view model has changed.
        :param prop:
        :param value:
        :return:
        """
        self._update(self._collection_vm.records,
                     self._collection_vm.columns)

    @staticmethod
    def _try_get_prop(obj: Dict, path: str) -> Any:
        """
        FIXME: typing
        Get hierarchical property value from JSON record
        :param obj: JSON record
        :param path: prop1.prop2.prop3 ...
        :return: value of the property
        """
        for prop in path:
            if prop not in obj:
                return None
            obj = obj[prop]
            if not isinstance(obj, dict):
                return obj

        return None


class RecordsTableView(Qt.QTableView):
    """
    Implements a records table based on Qt.QTableView.
    Most of the functionality provided by RecordsTableModel provided in "model" argument.
    """
    def __init__(self, model, parent=None):
        super().__init__(parent=parent)
        self.setModel(model)
        self.setSelectionMode(Qt.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(Qt.QAbstractItemView.SelectRows)
        self.setVerticalScrollMode(Qt.QAbstractItemView.ScrollPerPixel)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)

        self._expand_action = Qt.QAction("Expand history", triggered=self._on_expand_history)
        self._collapse_action = Qt.QAction("Collapse history", triggered=self._on_collapse_history)
        self.addActions([
            self._expand_action,
            self._collapse_action
        ])

        self._menu = Qt.QMenu(self)
        self._menu_record = None

    # signals
    expand_record_history = Qt.pyqtSignal(object)
    collapse_record_history = Qt.pyqtSignal(object)
    context_menu_prepare = Qt.pyqtSignal(object)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """
        Override to generate signals
        :param event: QContextMenuEvent object
        :return:
        """
        row = self.rowAt(event.y())
        record = None
        index = Qt.QModelIndex()
        if 0 <= row < self.model().rowCount(Qt.QModelIndex()):
            index = self.model().index(row, 0)
            record = index.data(RECORD_ROLE)

        version = int(record["version"]) if "version" in record else 1

        # emit an event for others to update actions prior to posting a context menu
        self.context_menu_prepare.emit(record)

        self._menu.clear()
        self._menu.addActions(self.actions())

        self._expand_action.setVisible(record is not None and version > 1 and not index.data(IS_HISTORY_ROLE))
        self._collapse_action.setVisible(record is not None and index.data(IS_HISTORY_ROLE))

        self._menu_record = record
        self._menu.exec(event.globalPos())
        self._menu_record = None

    def _on_expand_history(self) -> None:
        record = self._menu_record
        if record is None:
            return
        self.expand_record_history.emit(record)

    def _on_collapse_history(self) -> None:
        record = self._menu_record
        if record is None:
            return
        self.collapse_record_history.emit(record)


class CollectionView(Qt.QWidget):
    """
    View for displaying a list of records and signaling selection of a record.
    """
    def __init__(self, model, parent=None):
        super().__init__(parent=parent)
        self._model = model
        self._model.property_changed.connect(self._update_view)

        # main layout
        layout = Qt.QGridLayout(self)
        split = Qt.QSplitter()
        layout.addWidget(split, 0, 0)
        layout.setRowStretch(0, 1)
        layout.setColumnStretch(0, 1)

        # records table
        self._table = RecordsTableView(model=RecordsTableModel(model), parent=self)
        self._table.expand_record_history.connect(lambda rec: self._model.expand_history(rec['_id']))
        self._table.collapse_record_history.connect(lambda rec: self._model.collapse_history(rec['_id']))
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        # self._table.setContextMenuPolicy(Qt.Qt.CustomContextMenu)

        group = Qt.QGroupBox(title="Records")
        group_layout = Qt.QGridLayout(group)
        group_layout.setRowStretch(0, 1)
        group_layout.setColumnStretch(0, 1)
        group_layout.addWidget(self._table, 0, 0)
        split.addWidget(group)

        # record details
        self._details = JsonView()
        scroll = Qt.QScrollArea()
        scroll.setWidget(self._details)
        scroll.setWidgetResizable(True)

        group = Qt.QGroupBox(title="Attributes")
        group_layout = Qt.QGridLayout(group)
        group_layout.addWidget(scroll, 0, 0)
        group_layout.setColumnStretch(0, 1)
        group_layout.setRowStretch(0, 1)

        split.addWidget(group)

        self._progress = Qt.QWidget()
        progress = Qt.QProgressBar(minimum=0, maximum=0, value=0)
        progress.setFixedWidth(200)
        frame_layout = Qt.QGridLayout(self._progress)
        frame_layout.addWidget(Qt.QLabel("Loading..."), 0, 0)
        frame_layout.addWidget(progress, 1, 0)

        layout.addWidget(self._progress, 0, 0, Qt.Qt.AlignCenter)

        self._update_view(None, None)

    record_selected = Qt.pyqtSignal(object)  # triggered when a record is selected

    def _update_view(self, prop, val) -> None:
        """
        Triggered when view model changes
        """
        if self._model.loading:
            self._progress.show()
            self._table.setEnabled(False)
        else:
            self._progress.hide()
            self._table.setEnabled(True)

    def _on_selection_changed(self, selected, deselected) -> None:
        index = selected.indexes()
        if not len(index):
            self._details.set_json(None)
            self.record_selected.emit(None)
            return

        record = self._model.records[index[0].row()]
        self._details.set_json(record)
        self.record_selected.emit(record)
