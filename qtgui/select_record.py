from typing import Optional, Dict

from PyQt5 import Qt

from py_wasp import Wasp
from .collection_view import CollectionView
from .collection_viewmodel import CollectionViewModel


def select_record(conduit_api: Wasp, collection: str, parent: Qt.QWidget = None) -> Optional[Dict]:
    """
    Open a dialog to select a record from Wasp collection
    :param conduit_api: Wasp object
    :param collection: collection name
    :param parent: parent QWidget
    :return: selected record or None
    """
    dlg = Qt.QDialog(parent=parent, windowTitle="Select record from " + collection)
    dlg.setAttribute(Qt.Qt.WA_DeleteOnClose)
    dlg.setWindowModality(Qt.Qt.ApplicationModal)
    dlg.resize(1200, 800)  # fixme: need to support small displays ?
    layout = Qt.QGridLayout(dlg)
    layout.setRowStretch(0, 1)
    layout.setColumnStretch(0, 1)

    buttons = Qt.QDialogButtonBox(Qt.QDialogButtonBox.Ok | Qt.QDialogButtonBox.Cancel, parent=dlg)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    ok_btn = buttons.button(Qt.QDialogButtonBox.Ok)
    ok_btn.setEnabled(False)

    selection = [None]  # record selection is kept here

    def _on_select(rec) -> None:
        selection[0] = rec
        ok_btn.setEnabled(rec is not None)

    # collection view:
    view_model = CollectionViewModel(conduit_api=conduit_api, collection=collection)
    collection_view = CollectionView(model=view_model, parent=dlg)
    collection_view.record_selected.connect(_on_select)

    layout.addWidget(collection_view, 0, 0)
    layout.addWidget(buttons, 1, 0)

    code = dlg.exec()

    if code != Qt.QDialog.Accepted or selection[0] is None:
        return None

    return selection[0]
