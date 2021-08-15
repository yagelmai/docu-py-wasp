import traceback
from typing import Tuple, Dict, List, Union, Optional, Any

from PyQt5 import Qt

from py_wasp import FileValue, ReferenceValue, ViewConfig, Wasp


class CollectionViewModel(Qt.QObject):
    """
    This object represents data of a single collection necessary to display the records.
    """
    def __init__(self, conduit_api, collection):
        super().__init__()
        self._api = conduit_api
        self._collection = collection
        self._loading = False
        self._records = []
        self._thread = None
        self._columns = []  # list of ViewConfig.Column
        self._sort_by = []
        self._update()
        self._record_versions = {}  # map record ID to previous versions
        self._parent_record = {}  # reverse of the record_versions
        self._outstanding_history = {}  # map of outstanding calls to expand history

    property_changed = Qt.pyqtSignal(str, object)  # emitted when one of the properties changes

    @property
    def loading(self) -> bool:
        """
        :return: true if the model view is updating and false otherwise
        """
        return self._loading

    @property
    def records(self) -> List[Dict[str, Union[str, FileValue, ReferenceValue, Dict]]]:
        """
        :return: List of all records in the view model
        """
        return self._records

    @property
    def columns(self) -> List[ViewConfig.Column]:
        """
        :return: List of all columns in the view model
        """
        return self._columns

    def is_latest(self, record_id: str) -> bool:
        """
        :param record_id: record id to check
        :return: True if specified record ID is the latest version
        """
        return record_id not in self._parent_record

    def is_history(self, record_id: str) -> bool:
        """
        :param record_id:
        :return: True if record id belongs to a currently displayed record history
        """
        return record_id in self._record_versions or record_id in self._parent_record

    def expand_history(self, record_id) -> None:
        """
        Expand history for specified record ID (calls Wasp asynchronously)
        :param record_id: record['_id'] of a currently displayed record
        :return:
        """
        async_call = AsyncCall(target=lambda: self._api.get_record_history(self._collection, record_id))
        async_call.finished.connect(lambda: self._on_history_done(record_id, async_call))
        self._outstanding_history[record_id] = async_call
        async_call.start()

    def collapse_history(self, record_id) -> None:
        """
        Remove all records but latest for the history list of record_id
        :param record_id: record['_id'] of a currently displayed record
        :return:
        """
        if record_id in self._record_versions:
            parent_id = record_id
        else:
            if record_id not in self._parent_record:
                return
            parent_id = self._parent_record[record_id]
            if parent_id not in self._record_versions:
                return

        remove_ids = set([rec['_id'] for rec in self._record_versions[parent_id]])

        for id_ in remove_ids:
            self._parent_record.pop(id_, None)
        self._record_versions.pop(parent_id, None)

        self._records = [rec for rec in self._records if rec['_id'] not in remove_ids]
        self.property_changed.emit('records', self._records)

    def _update(self) -> None:
        # Request to update the records list and view configuration
        if self._thread is not None:
            # TODO: find a way to cancel async request / update cleanly
            self._thread.requestInterruption()

        self._loading = True
        self.property_changed.emit('loading', True)

        thread = AsyncCall(target=lambda: self._async_get_update(self._api, self._collection))
        thread.finished.connect(lambda: self._on_update_done(thread))

        self._thread = thread
        thread.start()

    @staticmethod
    def _async_get_update(api: Wasp, collection: str) -> Tuple[List[Dict], List[ViewConfig.Column]]:
        # Executed asynchronously
        records = api.find_records(collection)
        view = api.get_view_info(collection, 'default')
        return records, view.columns

    def _on_update_done(self, thread) -> None:
        """
        handle results of async update
        :param thread:
        """
        if thread.isInterruptionRequested() or thread != self._thread:
            return

        self._thread = None
        self._loading = False
        self._parent_record = {}
        self._record_versions = {}

        if thread.result is None:
            self._records, self._columns = [], []
        else:
            self._records, self._columns = thread.result

        self.property_changed.emit(None, None)

    def _on_history_done(self, record_id: str, async_call) -> None:
        """
        FIXME: typing
        Called when request to get record history finishes
        :param record_id: Record ID
        :param async_call:
        :return:
        """

        # check for obsolete request:
        if record_id not in self._outstanding_history or self._outstanding_history[record_id] != async_call:
            return
        self._outstanding_history.pop(record_id, None)
        if async_call.isInterruptionRequested() or not async_call.result:
            return

        # merge history with the list of records:
        history_records = async_call.result
        if len(history_records):
            # assumes records are sorted by version:
            self._record_versions[history_records[-1]['_id']] = history_records[:-1]
            for rec in history_records[:-1]:
                self._parent_record[rec['_id']] = history_records[-1]['_id']

        history_ids = set([record['_id'] for record in history_records])

        # find latest record in the list of records
        # note: if another record was meanwhile pushed into server, latest might not be there
        i = 0
        for i in range(len(self._records)):
            rec = self._records[i]
            if rec['_id'] in history_ids:
                break

        self._records = [rec for rec in self._records if rec['_id'] not in history_ids]
        self._records = self._records[:i] + history_records + self._records[i:]
        self.property_changed.emit("records", self._records)


class AsyncCall(Qt.QThread):
    """
    A simple QThread that runs python callback
    """
    def __init__(self, target):
        super().__init__()
        self._target = target
        self._result = None
        self._exception = None

    @property
    def result(self) -> Any:
        """
        :return: Return value of target function
        """
        return self._result

    @property
    def exception(self) -> Optional[Exception]:
        """
        :return: Exception or None
        """
        return self._exception

    def run(self) -> None:
        """
        Try to run the target function
        :return:
        """
        try:
            self._result = self._target()
        except Exception as e:
            traceback.print_exc()
            self._exception = e
