import os
import sys
import traceback
from enum import Enum
from typing import List, Dict, Union, Optional

from PyQt5 import Qt

from py_wasp import Wasp
from .collection_viewmodel import AsyncCall

DEFAULT_SERVER_URL = 'http://iapp405.iil.intel.com:2232'
DEFAULT_COLLECTION = 'task_graphs'


def get_icon(name: str) -> Qt.QIcon:
    """
    Load specified icon
    :param name: short file name under $GUI/icons
    :return: QIcon object
    """
    path = os.path.join(os.path.dirname(__file__), 'icons')
    if not os.path.isdir(path):
        path = os.path.join(os.path.dirname(sys.executable), 'icons')  # distribution mode

    if isinstance(name, Qt.QIcon):
        return name
    return Qt.QIcon(os.path.join(path, name))


def error_box(message: str, title: str = 'Error', parent=None) -> None:
    """
    Display error message box
    :param message: message to display
    :param title: Error box title
    :param parent: parent widget
    :return:
    """
    if isinstance(message, Exception):
        traceback.print_exception(type(message), message, message.__traceback__)
        message = str(message)

    parent = parent or Qt.QApplication.instance().main_window
    Qt.QMessageBox.critical(parent, title, message)


def add_new_record(conduit_url: str = '', collection: str = DEFAULT_COLLECTION, parent=None):
    """
    Opens a dialog to add a new record
    :param conduit_url: conduit URL
    :param collection: collection name
    :param parent: parent Widget
    :return: The server's URL entered by the user, and a dictionary of the new record attributes and their values.
    """

    dlg = Qt.QDialog(parent=parent, windowTitle="Add a new record to " + collection)
    dlg.setAttribute(Qt.Qt.WA_DeleteOnClose)
    dlg.setModal(True)
    dlg.resize(400, 450)
    layout = Qt.QGridLayout(dlg)

    buttons = Qt.QDialogButtonBox(Qt.QDialogButtonBox.Ok | Qt.QDialogButtonBox.Cancel, parent=dlg)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    ok_btn = buttons.button(Qt.QDialogButtonBox.Ok)
    ok_btn.setEnabled(False)

    new_record_url_model = NewRecordURLViewModel(server_url=conduit_url, collection=collection, parent=dlg)
    new_record_url_view = NewRecordURLView(url_view_model=new_record_url_model, parent=dlg)

    layout.addWidget(new_record_url_view, 1, 0)
    layout.addWidget(buttons, 2, 0)

    record_dict = [None]
    server_url = ['']

    def _on_record_done(returned_dict):
        record_dict[0] = returned_dict
        server_url[0] = new_record_url_model.server_url
        ok_btn.setEnabled(returned_dict is not None)

    new_record_url_model.record_changed.connect(_on_record_done)

    select = dlg.exec()

    if select != Qt.QDialog.Accepted or record_dict[0] is None:
        return None

    return server_url[0], record_dict[0]


class AttributesType(Enum):
    LINE_EDIT = 'line_edit'
    COMBOBOX = 'combo_box'
    TEXT_BOX = 'text_box'
    USER_ATTRIBUTE = 'user_attr'


class Attribute(Qt.QObject):
    """
    This object holds the data for a record key
    """
    def __init__(self, name='', val='', is_mandatory=False, attr_type=AttributesType.LINE_EDIT):
        super().__init__()
        self._name = name
        self._val = val
        self._type = attr_type
        self._is_mandatory = is_mandatory
        self._completion_list = Qt.QStringListModel()
        self._name_to_present = self._get_name_to_present(name)
        self._combobox_list = []

    property_changed = Qt.pyqtSignal(str, object)

    @property
    def name(self) -> str:
        """
        :return: Attribute name
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        """
        Set name to attribute and emit property changed
        :param name: name to set
        :return:
        """
        if self._name != name:
            self._name = name
            self._name_to_present = self._get_name_to_present(name)
            self.property_changed.emit('name', self._name)

    @property
    def val(self) -> str:
        """
        :return: Attribute value
        """
        return self._val

    @val.setter
    def val(self, value: str) -> None:
        """
        Set value to attribute and emit property changed
        :param value: value to set.
        :return:
        """
        if self._val != value:
            self._val = value.strip()
            self.property_changed.emit('val', value)

    @property
    def type(self) -> AttributesType:
        """
        :return: Attribute type (AttributesType)
        """
        return self._type

    @type.setter
    def type(self, value: AttributesType) -> None:
        """
        Set type to attribute and emit property changed
        :param value: type to set
        :return:
        """
        self._type = value
        self.property_changed.emit('type', self._type)

    @property
    def is_mandatory(self) -> bool:
        """
        :return: True if attribute is mandatory
        """
        return self._is_mandatory

    @property
    def completion_list(self) -> Qt.QStringListModel:
        """
        :return: Attribute's completion list
        """
        return self._completion_list

    @completion_list.setter
    def completion_list(self, value: Qt.QStringListModel) -> None:
        """
        Set attribute's completion_list and emit property changed
        :param value: Qt.QStringListModel object
        :return:
        """
        self._completion_list.setStringList(value)
        self.property_changed.emit('completion_list', self._completion_list)

    @property
    def combobox_list(self) -> List:
        """
        :return: Attribute's combobox list
        """
        return self._combobox_list

    @combobox_list.setter
    def combobox_list(self, value: List) -> None:
        """
        Set attribute's combobox list
        :param value: combobox list to set
        :return:
        """
        self._combobox_list = value
        self.property_changed.emit('combobox_list', self._combobox_list)

    @property
    def name_to_present(self) -> str:
        """
        :return: the attribute's name as it should be presented in the viewer
        """
        return self._name_to_present

    @staticmethod
    def _get_name_to_present(name: str) -> str:
        """
        replace underscore characters with spaces
        :param name: Name
        :return:
        """
        new_name = name.replace("_", " ")
        return new_name.title()


class AttributeEditor(Qt.QObject):
    """
    A viewer for a new record attribute.
    """
    def __init__(self, layout, parent=None):
        super().__init__(parent=parent)
        self._label = Qt.QLabel(parent=parent)
        self._parent_layout = layout
        self._attribute = None
        self._editor = None
        self._text_box = None

        self._line_editor = Qt.QLineEdit(parent=parent)
        self._line_editor.textChanged.connect(lambda: self._on_line_edit_changed(self._line_editor))
        self._line_editor.setFixedHeight(22)
        completer = Qt.QCompleter()
        completer.setCaseSensitivity(Qt.Qt.CaseInsensitive)
        completer.setFilterMode(Qt.Qt.MatchContains)
        completer.setModelSorting(Qt.QCompleter.CaseInsensitivelySortedModel)
        self._line_editor.setCompleter(completer)

        self._combobox = Qt.QComboBox(parent=parent)
        self._combobox.currentIndexChanged.connect(lambda: self._on_combobox_changed(self._combobox))

        self._discard_button = Qt.QPushButton(icon=get_icon("list-remove.svg"))
        self._discard_button.setFixedSize(22, 22)
        self._discard_button.clicked.connect(lambda: self.discard_button_clicked.emit(self))
        self._discard_button.setToolTip("Remove attribute")

        row = self._parent_layout.rowCount()
        self._parent_layout.addWidget(self._label, row, 0)
        self._parent_layout.addWidget(self._line_editor, row, 1)
        self._parent_layout.addWidget(self._combobox, row, 1)
        self._parent_layout.addWidget(self._discard_button, row, 2)
        self._line_editor.hide()
        self._combobox.hide()

    discard_button_clicked = Qt.pyqtSignal(object)

    @property
    def attribute(self) -> Attribute:
        """
        :return: record's attribute
        """
        return self._attribute

    @attribute.setter
    def attribute(self, val: Attribute) -> None:
        """

        :param val: Attribute object to set
        :return:
        """
        if self._attribute != val:
            if self._attribute is not None:
                # deregister from old one
                self._attribute.property_changed.disconnect(self._on_attribute_changed)
            self._attribute = val
            if self._attribute is not None:
                # register with new one
                self._attribute.property_changed.connect(self._on_attribute_changed)
            self._update()

    @property
    def editor(self) -> Qt.QLineEdit:
        """
        :return: editor QLineEdit object
        """
        return self._editor

    @property
    def label(self) -> Qt.QLabel:
        """
        :return: editor QLabel object
        """
        return self._label

    @property
    def discard_button(self) -> Qt.QPushButton:
        """
        :return: Discard button object (Qt.QPushButton)
        """
        return self._discard_button

    def _update(self) -> None:
        self._on_attribute_changed(None, None)

    def _on_attribute_changed(self, prop, value):
        # create the object to be added to grid according to type
        if prop is None or prop == 'type':
            if self._attribute is not None:
                if self._attribute.type == AttributesType.LINE_EDIT:
                    completer = self._line_editor.completer()
                    completer.setModel(self._attribute.completion_list)
                    self._line_editor.setText(self.attribute.val)
                    self._editor = self._line_editor
                    self._line_editor.show()
                    self._combobox.hide()
                    if self._text_box is not None:
                        self._text_box.hide()

                if self._attribute.type == AttributesType.COMBOBOX:
                    self._combobox.addItems(self.attribute.combobox_list)
                    self._combobox.currentIndexChanged.connect(lambda: self._on_combobox_changed(self._combobox))
                    self._combobox.setCurrentText(self.attribute.val)
                    self._combobox.currentIndexChanged.emit(self._combobox.currentIndex())
                    self._editor = self._combobox
                    self._combobox.show()
                    self._line_editor.hide()
                    if self._text_box is not None:
                        self._text_box.hide()

                if self._attribute.type == AttributesType.TEXT_BOX:
                    self._text_box = Qt.QTextEdit(parent=self.parent())
                    self._text_box.textChanged.connect(lambda: self._on_text_edit_changed(self._text_box))
                    self._text_box.setTabChangesFocus(True)
                    self._text_box.setPlainText(self.attribute.val)
                    # add to layout:
                    editor_index = self._parent_layout.indexOf(self._line_editor)
                    editor_row = self._parent_layout.getItemPosition(editor_index)[0]
                    self._parent_layout.addWidget(self._text_box, editor_row, 1)
                    self._editor = self._text_box
                    self._combobox.hide()
                    self._line_editor.hide()
                    self._text_box.show()

                if self._attribute.type == AttributesType.USER_ATTRIBUTE:
                    self._label.setParent(None)
                    self._label = Qt.QLineEdit(parent=self.parent())
                    self._label.setPlaceholderText("Attribute Name")
                    self._label.textChanged.connect(lambda: self._on_user_attr_name_changed(self._label))
                    self._label.setText(self.attribute.name_to_present + ": ")
                    self._editor = self._line_editor
                    self._line_editor.setText(self.attribute.val)
                    self._line_editor.show()
                    self._combobox.hide()
                    if self._text_box is not None:
                        self._text_box.hide()
                    # add label to layout:
                    editor_index = self._parent_layout.indexOf(self._editor)
                    editor_row = self._parent_layout.getItemPosition(editor_index)[0]
                    self._parent_layout.addWidget(self._label, editor_row, 0)
                else:
                    if type(self._label) != Qt.QLabel:
                        self._label.setParent(None)
                        self._label = Qt.QLabel(parent=self.parent())
                    self._label.setText(self._attribute.name_to_present + ": ")

                if self._attribute.is_mandatory:
                    self._discard_button.hide()
                else:
                    self._discard_button.show()

        if prop == 'val' or prop is None:
            if self.attribute.is_mandatory:
                if self.attribute.val == '':
                    self._line_editor.setStyleSheet("border: 1px solid red")
                else:
                    self._line_editor.setStyleSheet("border: 1px solid black")
            if self.attribute.val != self._line_editor.text().strip():
                self._line_editor.setText(self.attribute.val)
            if self._text_box is not None and self.attribute.val != self._text_box.toPlainText().strip():
                self._text_box.setPlainText(self.attribute.val)
            self._combobox.setCurrentText(self.attribute.val)

        if prop == 'name' or prop is None:
            if self.attribute.name != self._label.text():
                self._label.setText(self.attribute.name_to_present + ": ")

    def remove_from_layout(self) -> None:
        # remove the editor from the layout (with the label & discard button)
        self._parent_layout.removeWidget(self._editor)
        self._parent_layout.removeWidget(self._label)
        self._parent_layout.removeWidget(self._discard_button)
        self._editor.setParent(None)
        self._label.setParent(None)
        self._discard_button.setParent(None)

    def add_to_layout(self) -> None:
        # add editor to layout (with label and discard button)
        row = self._parent_layout.rowCount()
        if self.attribute.name == 'comments':
            self._parent_layout.addWidget(self._label, row, 0)
            self._parent_layout.addWidget(self._editor, row, 1)
            self._parent_layout.addWidget(self._discard_button, row, 2)

    def _on_text_edit_changed(self, text_editor):
        self.attribute.val = text_editor.toPlainText().strip()

    def _on_line_edit_changed(self, text_editor):
        self.attribute.val = text_editor.text().strip()

    def _on_combobox_changed(self, combobox):
        self.attribute.val = combobox.currentText()

    def _on_user_attr_name_changed(self, name_label):
        if not self._check_user_name_validity(name_label.text()):
            error_box("Name tag should not start with a digit, and contain only alpha-numeric characters",
                      title="Invalid Name Tag", parent=self.parent())
            self.label.setStyleSheet("border: 1px solid red")
            self.label.setFocus()
        else:
            self._attribute.name = name_label.text().strip()
            self.label.setStyleSheet("border: 1px solid black")

    @staticmethod
    def _check_user_name_validity(name):
        validator = Qt.QRegExpValidator(Qt.QRegExp(r"\w*"))
        if len(name) == 0 or (validator.validate(name, 0)[0] == Qt.QValidator.Acceptable and not name[0].isdigit()):
            return True
        return False


class NewRecordViewModel(Qt.QObject):
    """
    This object holds the data for all of the new record keys.
    """
    def __init__(self, server_url=DEFAULT_SERVER_URL, collection=DEFAULT_COLLECTION, parent=None):
        super().__init__(parent=parent)
        self._conduit_api = Wasp(server_urls=[server_url])
        self._collection = collection
        self._keys = []
        self._loading = False
        self._thread = None
        self._lists_threads = {}
        self._comment_attribute = Attribute(name='comments', is_mandatory=False, attr_type=AttributesType.TEXT_BOX)
        self._comment_attribute.property_changed.connect(self._on_attribute_changed)
        self._update()

    property_changed = Qt.pyqtSignal(str, object)
    record_changed = Qt.pyqtSignal(object)

    @property
    def loading(self) -> bool:
        """
        :return: True if the viewmodel is updating
        """
        return self._loading

    @property
    def keys(self) -> List[Attribute]:
        """
        :return: List of record's keys
        """
        return self._keys

    @property
    def comment_attribute(self) -> Attribute:
        """
        :return: Comment attribute object
        """
        return self._comment_attribute

    @property
    def conduit_api(self) -> Wasp:
        """
        :return: Wasp API object
        """
        return self._conduit_api

    @conduit_api.setter
    def conduit_api(self, new_conduit_api: Wasp) -> None:
        """
        Set new Wasp API
        :param new_conduit_api: Wasp API (Wasp object) to set
        :return:
        """
        self._conduit_api = new_conduit_api
        self._update()

    def get_record_data(self) -> Optional[Dict]:
        """
        Checks if the user had entered values for all of the mandatory keys
        :return: a dict of the record key names and their values if all of the mandatory keys are filled,
        else return None.
        """
        record_data = dict()
        record_data['comments'] = self._comment_attribute.val
        for key in self.keys:
            if key.is_mandatory and key.val == '':
                return None
            else:
                record_data[key.name] = key.val
        return record_data

    def add_key(self) -> Attribute:
        """
        Add a key to model keys
        :return: New attribute which added to model
        """
        attribute = Attribute()
        attribute.type = AttributesType.USER_ATTRIBUTE
        attribute.property_changed.connect(self._on_attribute_changed)
        self._keys.append(attribute)
        return attribute

    def remove_key(self, key) -> None:
        """
        remove a key from the model keys
        :param key: the key to be removed
        """
        if key in self._keys:
            self._keys.remove(key)
            self.record_changed.emit(self.get_record_data())

    def _update(self):
        if self._thread is not None:
            self._thread.requestInterruption()

        self._loading = True
        self.property_changed.emit('loading', True)

        thread = AsyncCall(target=lambda: self._async_get_collection_keys(self._conduit_api, self._collection))
        thread.finished.connect(lambda: self._on_get_collection_keys_done(thread))
        self._thread = thread

        thread.start()

    @staticmethod
    def _async_get_collection_keys(conduit_api, collection):
        keys = conduit_api.get_system_info(collection).key_tags
        mandatory_keys = conduit_api.get_system_info(collection).mandatory_tags
        return keys, mandatory_keys

    def _on_get_collection_keys_done(self, thread):
        if thread.isInterruptionRequested() or thread != self._thread:
            return

        if thread.exception is not None:
            error_box(thread.exception)

        self._thread = None
        self._loading = False

        new_keys = []
        if thread.result is not None:
            keys, mandatory_keys = thread.result
            for key in keys:
                attribute = Attribute(key, is_mandatory=(key in mandatory_keys))
                attribute.property_changed.connect(self._on_attribute_changed)
                self._get_attribute_lists_aux(attribute)
                new_keys.append(attribute)
            self._keys = new_keys

        self.property_changed.emit('keys', self._keys)
        self.property_changed.emit('Loading', self._loading)

    def _get_attribute_lists_aux(self, attribute):
        if attribute.name in self._lists_threads.keys() and self._lists_threads[attribute.name] is not None:
            self._lists_threads[attribute.name].requestInterruption()
            self._lists_threads.pop(attribute.name)
        thread = AsyncCall(target=lambda: self._async_get_attribute_lists(attribute))
        thread.finished.connect(lambda: self._get_attribute_lists_done(thread, attribute))
        self._lists_threads[attribute.name] = thread
        thread.start()

    def _async_get_attribute_lists(self, key):
        """
        Get the completion list for the attribute line edit, and the combobox list for the attribute combobox.
        The combobox list is empty in case that the attribute is not of select type.
        :param key: an attribute object
        :return: the attributes's completion list and combobox list, in this order.
        """
        completion_list = self._conduit_api.get_tag_values(self._collection, key.name)
        combobox_list = self._conduit_api.get_system_info(self._collection).get_possible_values(key.name)
        return completion_list, combobox_list

    def _get_attribute_lists_done(self, thread, key):
        if key.name not in self._lists_threads.keys() or self._lists_threads[key.name] != thread:
            return
        self._lists_threads.pop(key.name)
        if thread.isInterruptionRequested() or thread.result is None:
            return
        key.completion_list, key.combobox_list = thread.result
        if len(key.combobox_list) > 0:  # if key is not of select type, the combobox list will be empty
            key.type = AttributesType.COMBOBOX

    def _on_url_vm_changed(self, prop, value):
        self._conduit_api = Wasp(value)
        self._update()

    def _on_attribute_changed(self, prop, value):
        self.record_changed.emit(self.get_record_data())


class NewRecordView(Qt.QWidget):
    """
    This object contains the view data of the new record attributes.
    """
    def __init__(self, view_model, parent=None):
        super().__init__(parent=parent)
        self._view_model = view_model
        self._view_model.property_changed.connect(self._on_model_changed)
        self._attribute_views = []
        main_layout = Qt.QGridLayout(self)

        self._new_record_widget = Qt.QWidget()
        self.layout = Qt.QGridLayout(self._new_record_widget)

        scroll = Qt.QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)
        scroll.setWidget(self._new_record_widget)

        self._add_button = Qt.QPushButton(icon=get_icon("list-add.svg"))
        self._add_button.setFixedSize(22, 22)
        self._add_button.clicked.connect(self._on_add_button_clicked)
        self._add_button.setToolTip("Add attribute")

        self._comment_attribute = AttributeEditor(self.layout, parent=self)
        self._comment_attribute.attribute = self._view_model.comment_attribute
        self._comment_attribute.discard_button.hide()

        self._progress = Qt.QWidget()
        progress_bar = Qt.QProgressBar(minimum=0, maximum=0, value=0)
        progress_bar.setFixedWidth(200)
        frame_layout = Qt.QGridLayout(self._progress)
        frame_layout.addWidget(Qt.QLabel("Loading..."), 0, 0)
        frame_layout.addWidget(progress_bar, 1, 0)
        main_layout.addWidget(self._progress, 0, 0, Qt.Qt.AlignCenter)

        self._on_model_changed(None, None)

    finished_updating = Qt.pyqtSignal()

    def _on_model_changed(self, prop, val) -> None:
        if self._view_model.loading:
            self._progress.show()
            self._new_record_widget.hide()
            self._comment_attribute.editor.hide()
        else:
            self._progress.hide()
            self._new_record_widget.show()
            self._comment_attribute.editor.show()
            self._update()

    def _update(self) -> None:
        """
        updates the attributes viewers according to the current viewers needed.
        """
        attributes = self._view_model.keys

        while len(self._attribute_views) > len(attributes):
            view_to_delete = self._attribute_views.pop()
            view_to_delete.setParent(None)

        while len(self._attribute_views) < len(attributes):
            attribute_object = AttributeEditor(self.layout, parent=self)
            self._attribute_views.append(attribute_object)

        # update existing
        for view, model in zip(self._attribute_views, attributes):
            view.attribute = model
            view.discard_button_clicked.connect(self._on_discard_button_clicked)

        self.layout.addWidget(self._add_button)
        self._comment_attribute.add_to_layout()
        self._new_record_widget.setTabOrder(self._add_button, self._comment_attribute.editor)
        self.finished_updating.emit()

    def _on_discard_button_clicked(self, attribute_editor):
        if attribute_editor in self._attribute_views:
            self._attribute_views.remove(attribute_editor)
            attribute_editor.remove_from_layout()
            self._view_model.remove_key(attribute_editor.attribute)
            attribute_editor.setParent(None)

    def _on_add_button_clicked(self) -> None:
        attribute = self._view_model.add_key()

        attribute_editor = AttributeEditor(self.layout, parent=self)
        attribute_editor.attribute = attribute
        attribute_editor.discard_button_clicked.connect(self._on_discard_button_clicked)
        self._attribute_views.append(attribute_editor)

        self.layout.addWidget(self._add_button)
        self._comment_attribute.add_to_layout()

        self.finished_updating.emit()

    def set_tab_order(self) -> None:
        # setting the focus order to be in the right order.

        if len(self._attribute_views) > 0:
            last_view = self._attribute_views[0]
            for view in self._attribute_views[1:]:
                if view.attribute.type == AttributesType.USER_ATTRIBUTE:
                    if not last_view.attribute.is_mandatory:  # has a discard button
                        self._new_record_widget.setTabOrder(last_view.discard_button, view.label)
                    else:
                        self._new_record_widget.setTabOrder(last_view.editor, view.label)
                    self._new_record_widget.setTabOrder(view.label, view.editor)
                    self._new_record_widget.setTabOrder(view.editor, view.discard_button)
                else:
                    if not last_view.attribute.is_mandatory:
                        self._new_record_widget.setTabOrder(last_view.discard_button, view.editor)
                    else:
                        self._new_record_widget.setTabOrder(last_view.editor, view.editor)
                last_view = view
            if not last_view.attribute.is_mandatory:
                self._new_record_widget.setTabOrder(last_view.discard_button, self._add_button)
            else:
                self._new_record_widget.setTabOrder(last_view.editor, self._add_button)
            self._new_record_widget.setTabOrder(self._add_button, self._comment_attribute.editor)

    def get_first_in_tab_order(self) -> Union[AttributeEditor, Qt.QPushButton]:
        if len(self._attribute_views) != 0:
            return self._attribute_views[0].editor
        return self._add_button


class NewRecordURLViewModel(Qt.QObject):
    """
    This object represent the data for the new record - its attributes and their values inserted by the user,
    and the server URL.
    """
    def __init__(self, server_url='', collection=DEFAULT_COLLECTION, parent=None):
        super().__init__(parent=parent)
        self._server_url = server_url
        vm_server_url = server_url if server_url != '' else DEFAULT_SERVER_URL
        self._new_record_vm = NewRecordViewModel(vm_server_url, collection, parent=self)
        self._new_record_vm.record_changed.connect(self.record_changed.emit)

    property_changed = Qt.pyqtSignal(str, object)
    record_changed = Qt.pyqtSignal(object)

    @property
    def server_url(self) -> str:
        """
        :return: Server URL
        """
        return self._server_url

    @server_url.setter
    def server_url(self, new_url: str) -> None:
        """
        Update Wasp API with new server URL
        :param new_url: new server URL
        :return:
        """
        self._server_url = new_url.strip()
        self.new_record_vm.conduit_api = Wasp(server_urls=[new_url])
        self.property_changed.emit('server_url', new_url)

    @property
    def new_record_vm(self) -> NewRecordViewModel:
        """
        :return: NewRecord ViewModel object
        """
        return self._new_record_vm


class NewRecordURLView(Qt.QWidget):
    """
    The main view of adding a new record to a certain collection.
    Signaling when one of the records keys is changed.
    """
    def __init__(self, url_view_model, parent=None):
        super().__init__(parent=parent)
        self._view_model = url_view_model

        server_group = Qt.QGroupBox(parent=self)
        server_layout = Qt.QGridLayout(server_group)

        self._url_label = Qt.QLabel(parent=server_group, text="Server URL")

        self._url_editor = Qt.QLineEdit(parent=server_group)
        self._url_editor.setPlaceholderText("Default server: " + DEFAULT_SERVER_URL)
        self._url_editor.setText(url_view_model.server_url)

        self._apply_button = Qt.QPushButton(icon=get_icon("dialog-ok-apply.png"), parent=self)
        self._apply_button.setFixedSize(22, 22)
        self._apply_button.clicked.connect(self._on_apply)

        server_layout.addWidget(self._url_label, 0, 0)
        server_layout.addWidget(self._url_editor, 0, 1)
        server_layout.addWidget(self._apply_button, 0, 2)

        new_record_group = Qt.QGroupBox(title="Attributes", parent=self)
        new_record_layout = Qt.QGridLayout(new_record_group)
        self._new_record_view = NewRecordView(view_model=self._view_model.new_record_vm, parent=self)
        self._new_record_view.finished_updating.connect(self._on_record_view_ready)
        new_record_layout.addWidget(self._new_record_view)

        main_layout = Qt.QGridLayout(self)
        main_layout.addWidget(server_group)
        main_layout.addWidget(new_record_group)
        url_view_model.property_changed.connect(self._on_model_property_changed)

    @property
    def new_record_view(self) -> NewRecordView:
        """
        :return: NewRecord View object
        """
        return self._new_record_view

    def _on_apply(self) -> None:
        editor_text = self._url_editor.text()
        if editor_text != '' and editor_text != self._view_model.server_url:
            self._view_model.server_url = editor_text

    def _on_record_view_ready(self) -> None:
        # setting the tab order:
        self.setTabOrder(self._apply_button, self._new_record_view.get_first_in_tab_order())
        self._new_record_view.set_tab_order()

    def _on_model_property_changed(self, prop, value) -> None:
        if prop == 'server_url':
            self._url_editor.setText(value)
